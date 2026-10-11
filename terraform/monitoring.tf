# Explicit lab decision: every tenant group may read the central cluster-wide
# monitoring data. This does not implement tenant isolation or Project Monitoring.
resource "kubernetes_role_v1" "monitoring_viewer" {
  metadata {
    name      = "tenant-monitoring-viewer"
    namespace = "cattle-monitoring-system"
  }
  # Rancher detects Monitoring from the PodMonitor schema and enables UI links
  # by listing Endpoints. These are namespace-scoped discovery permissions only.
  rule {
    api_groups = [""]
    resources  = ["services", "endpoints"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["monitoring.coreos.com"]
    resources  = ["prometheuses", "alertmanagers", "servicemonitors", "podmonitors", "prometheusrules", "alertmanagerconfigs", "probes"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = [""]
    resources  = ["services/proxy"]
    resource_names = [
      "http:rancher-monitoring-prometheus:9090", "https:rancher-monitoring-prometheus:9090",
      "http:rancher-monitoring-alertmanager:9093", "https:rancher-monitoring-alertmanager:9093",
      "http:rancher-monitoring-grafana:80", "https:rancher-monitoring-grafana:80"
    ]
    verbs = ["get"]
  }
  # Grafana uses POST for read-only datasource queries. Its Viewer role remains
  # authoritative; POST to Prometheus/Alertmanager is deliberately not granted.
  rule {
    api_groups     = [""]
    resources      = ["services/proxy"]
    resource_names = ["http:rancher-monitoring-grafana:80", "https:rancher-monitoring-grafana:80"]
    verbs          = ["create"]
  }
}

resource "kubernetes_role_binding_v1" "monitoring_viewer" {
  for_each = local.tenants
  metadata {
    name      = "${each.key}-monitoring-viewer"
    namespace = "cattle-monitoring-system"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.monitoring_viewer.metadata[0].name
  }
  dynamic "subject" {
    for_each = toset(["", "-admins", "-developers", "-logs-readers"])
    content {
      api_group = "rbac.authorization.k8s.io"
      kind      = "Group"
      name      = "keycloakoidc_group://${each.key}${subject.value}"
    }
  }
  depends_on = [module.tenant]
}
