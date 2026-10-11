locals {
  argocd_repositories = merge([for slug, tenant in local.tenants : {
    for url in try(tenant.argocd_repositories, []) : "${slug}-${substr(sha256(url), 0, 10)}" => {
      tenant = slug
      url    = url
    }
  }]...)
  argocd_demo_tenants = { for slug, tenant in local.tenants : slug => tenant if try(tenant.argocd_demo, false) }
  argocd_namespaced_resources = flatten([
    [for kind in ["ConfigMap", "Secret", "Service", "ServiceAccount", "PersistentVolumeClaim", "Pod", "Endpoints"] : { group = "", kind = kind }],
    [for kind in ["Deployment", "StatefulSet", "ReplicaSet"] : { group = "apps", kind = kind }],
    [for kind in ["Job", "CronJob"] : { group = "batch", kind = kind }],
    [{ group = "networking.k8s.io", kind = "Ingress" },
      { group = "autoscaling", kind = "HorizontalPodAutoscaler" },
      { group = "policy", kind = "PodDisruptionBudget" },
    { group = "external-secrets.io", kind = "ExternalSecret" }]
  ])
}

# Fleet owns the Argo CD installation; Terraform owns tenant authorization.
# Protected, non-overlapping namespace prefixes cover self-service namespaces.
resource "kubernetes_manifest" "argocd_project" {
  for_each = local.tenants
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata   = { name = each.key, namespace = "argocd" }
    spec = {
      description                = "${each.value.display_name} application GitOps"
      sourceRepos                = try(each.value.argocd_repositories, [])
      sourceNamespaces           = []
      destinations               = [{ server = "https://kubernetes.default.svc", namespace = "${each.key}-*" }]
      clusterResourceWhitelist   = []
      namespaceResourceWhitelist = local.argocd_namespaced_resources
      roles = [for role, actions in {
        admins     = ["get", "create", "update", "sync", "delete"]
        developers = ["get", "create", "update", "sync"]
        } : {
        name        = role
        description = "${each.key} ${role}"
        groups      = ["${each.key}-${role}"]
        policies = concat(
          [for action in actions : "p, proj:${each.key}:${role}, applications, ${action}, ${each.key}/*, allow"],
          ["p, proj:${each.key}:${role}, logs, get, ${each.key}/*, allow",
          "p, proj:${each.key}:${role}, repositories, get, ${each.key}/*, allow"]
        )
      }]
    }
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition = alltrue(flatten([for left in keys(local.tenants) : [for right in keys(local.tenants) :
        left == right || (!startswith(left, "${right}-") && !startswith(right, "${left}-"))
      ]]))
      error_message = "Tenant prefixes must not overlap: e.g. tenant-a and tenant-a-team would overlap Argo CD namespace destinations."
    }
    precondition {
      condition     = alltrue([for url in try(each.value.argocd_repositories, []) : can(regex("^https://[^*?]+[.]git$", url))])
      error_message = "Use explicit HTTPS Git repository URLs ending in .git, without wildcard permissions."
    }
  }
  depends_on = [kubernetes_manifest.tenant_admission_binding, kubernetes_config_map_v1.argocd_rbac]
}

# These public repository registrations contain no credentials. Future private
# repository credentials must use project-scoped ESO secrets, never shared keys.
resource "kubernetes_secret_v1" "argocd_repository" {
  for_each = local.argocd_repositories
  metadata {
    name      = "tenant-repository-${each.key}"
    namespace = "argocd"
    labels    = { "argocd.argoproj.io/secret-type" = "repository" }
  }
  data       = { type = "git", url = each.value.url, project = each.value.tenant }
  depends_on = [kubernetes_manifest.argocd_project]
}

resource "kubernetes_manifest" "argocd_demo" {
  for_each = local.argocd_demo_tenants
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "${each.key}-demo", namespace = "argocd" }
    spec = {
      project     = each.key
      source      = { repoURL = each.value.argocd_repositories[0], targetRevision = "main", path = "apps/demo" }
      destination = { server = "https://kubernetes.default.svc", namespace = "${each.key}-dev" }
      syncPolicy = {
        automated   = { prune = true, selfHeal = true }
        syncOptions = ["ApplyOutOfSyncOnly=true"]
      }
    }
  }
  depends_on = [kubernetes_secret_v1.argocd_repository, kubernetes_manifest.argocd_demo_ingress]
}

# Rancher project isolation does not include Cilium's reserved ingress identity.
# Permit that proxy only to the explicit demo labels and HTTP port, selected by
# the protected project label so the rule also follows future tenant namespaces.
resource "kubernetes_manifest" "argocd_demo_ingress" {
  for_each = local.argocd_demo_tenants
  manifest = {
    apiVersion = "cilium.io/v2"
    kind       = "CiliumClusterwideNetworkPolicy"
    metadata   = { name = "${each.key}-argocd-demo-ingress" }
    spec = {
      endpointSelector = {
        matchLabels = {
          "k8s:io.cilium.k8s.namespace.labels.field.cattle.io/projectId" = split(":", module.tenant[each.key].summary.project_id)[1]
          "k8s:app.kubernetes.io/name"                                   = "tenant-demo"
          "k8s:app.kubernetes.io/part-of"                                = "${each.key}-demo"
        }
      }
      ingress = [{ fromEntities = ["ingress"], toPorts = [{ ports = [{ port = "8080", protocol = "TCP" }] }] }]
    }
  }
  depends_on = [kubernetes_manifest.tenant_admission_binding]
}

# Project listing is a global Argo RBAC resource, not valid inside AppProject roles.
# Terraform exclusively owns this ConfigMap; the Fleet Helm chart sets rbac.create=false.
resource "kubernetes_config_map_v1" "argocd_rbac" {
  metadata {
    name      = "argocd-rbac-cm"
    namespace = "argocd"
    labels    = { "app.kubernetes.io/part-of" = "argocd" }
  }
  data = {
    "policy.default" = "role:none"
    "scopes"         = "[groups]"
    "policy.csv" = join("\n", flatten([for slug in keys(local.tenants) : [for role in ["admins", "developers"] :
      "p, ${slug}-${role}, projects, get, ${slug}, allow"
    ]]))
  }
}
