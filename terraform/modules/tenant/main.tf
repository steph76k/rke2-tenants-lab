locals {
  namespaces      = [for env in var.environments : "${var.slug}-${env}"]
  service_account = "openbao-${var.slug}"
}
resource "keycloak_group" "tenant" {
  realm_id = var.realm
  name     = var.slug
  lifecycle { prevent_destroy = true }
}
resource "rancher2_project" "tenant" {
  cluster_id = var.cluster_id
  name       = var.display_name
  container_resource_limit {}
  resource_quota {
    project_limit {}
    namespace_default_limit {}
  }
  timeouts {}
  wait_for_cluster = false
  lifecycle { prevent_destroy = true }
}
resource "rancher2_project_role_template_binding" "members" {
  name               = "${var.slug}-members"
  project_id         = rancher2_project.tenant.id
  role_template_id   = var.project_role
  group_principal_id = "keycloakoidc_group://${keycloak_group.tenant.name}"
}
resource "kubernetes_namespace_v1" "environment" {
  for_each = toset(var.environments)
  metadata {
    name        = "${var.slug}-${each.key}"
    annotations = { "field.cattle.io/projectId" = rancher2_project.tenant.id }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      metadata[0].labels["field.cattle.io/projectId"],
      metadata[0].annotations["cattle.io/status"],
      metadata[0].annotations["field.cattle.io/containerDefaultResourceLimit"],
      metadata[0].annotations["field.cattle.io/resourceQuotaProjectId"],
      metadata[0].annotations["lifecycle.cattle.io/create.namespace-auth"]
    ]
  }
}
resource "harbor_project" "tenant" {
  count                  = var.harbor_enabled ? 1 : 0
  name                   = var.slug
  public                 = false
  storage_quota          = var.harbor_storage_gib
  vulnerability_scanning = true
  force_destroy          = false
  lifecycle { prevent_destroy = true }
}
resource "vault_namespace" "tenant" {
  path = var.slug
  lifecycle { prevent_destroy = true }
}
resource "vault_mount" "secrets" {
  namespace = vault_namespace.tenant.path
  path      = "secret"
  type      = "kv"
  options   = { version = "2" }
  lifecycle { prevent_destroy = true }
}
resource "vault_auth_backend" "kubernetes" {
  namespace = vault_namespace.tenant.path
  path      = var.cluster_name
  type      = "kubernetes"
  lifecycle { prevent_destroy = true }
}
resource "vault_kubernetes_auth_backend_config" "cluster" {
  namespace              = vault_namespace.tenant.path
  backend                = vault_auth_backend.kubernetes.path
  kubernetes_host        = var.kubernetes_host
  kubernetes_ca_cert     = var.kubernetes_ca_cert
  disable_local_ca_jwt   = true
  disable_iss_validation = true
}
resource "vault_policy" "eso" {
  namespace = vault_namespace.tenant.path
  name      = "eso-read"
  policy    = <<-EOT
    path "secret/data/*" {
      capabilities = ["read"]
    }
  EOT
}
resource "vault_kubernetes_auth_backend_role" "eso" {
  namespace                        = vault_namespace.tenant.path
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "eso-${var.slug}"
  bound_service_account_names      = [local.service_account]
  bound_service_account_namespaces = ["external-secrets"]
  audience                         = "https://kubernetes.default.svc.cluster.local"
  token_policies                   = [vault_policy.eso.name]
  token_ttl                        = 3600
  token_type                       = "default"
}
resource "kubernetes_service_account_v1" "eso" {
  automount_service_account_token = false
  metadata {
    name      = local.service_account
    namespace = "external-secrets"
  }
}
resource "kubernetes_cluster_role_binding_v1" "tokenreview" {
  metadata { name = "${local.service_account}-tokenreviewer" }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = var.tokenreview_role_name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.eso.metadata[0].name
    namespace = "external-secrets"
  }
}
resource "kubernetes_manifest" "secret_store" {
  manifest = {
    apiVersion = "external-secrets.io/v1"
    kind       = "ClusterSecretStore"
    metadata   = { name = local.service_account }
    spec = {
      conditions = [{ namespaceSelector = { matchLabels = {
        "field.cattle.io/projectId" = split(":", rancher2_project.tenant.id)[1]
      } } }]
      provider = {
        vault = {
          server    = var.openbao_url
          namespace = vault_namespace.tenant.path
          path      = vault_mount.secrets.path
          version   = "v2"
          auth = {
            kubernetes = {
              mountPath = vault_auth_backend.kubernetes.path
              role      = vault_kubernetes_auth_backend_role.eso.role_name
              serviceAccountRef = {
                name      = kubernetes_service_account_v1.eso.metadata[0].name
                namespace = "external-secrets"
                audiences = ["https://kubernetes.default.svc.cluster.local"]
              }
            }
          }
        }
      }
    }
  }
  depends_on = [kubernetes_cluster_role_binding_v1.tokenreview, vault_kubernetes_auth_backend_config.cluster, kubernetes_namespace_v1.environment]
}
