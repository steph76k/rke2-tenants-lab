resource "keycloak_group" "access" {
  for_each = toset(["developers", "admins", "logs-readers"])
  realm_id = var.realm
  name     = "${var.slug}-${each.key}"
  lifecycle { prevent_destroy = true }
}
resource "harbor_group" "access" {
  for_each   = var.harbor_enabled ? toset(["developers", "admins"]) : toset([])
  group_name = keycloak_group.access[each.key].name
  group_type = 3
}
resource "harbor_project_member_group" "access" {
  for_each   = var.harbor_enabled ? { developers = "developer", admins = "projectadmin" } : {}
  project_id = harbor_project.tenant[0].id
  group_name = harbor_group.access[each.key].group_name
  type       = "oidc"
  role       = each.value
}
resource "rancher2_project_role_template_binding" "access" {
  for_each           = { developers = "project-member", admins = "project-owner" }
  name               = "${var.slug}-${each.key}"
  project_id         = rancher2_project.tenant.id
  role_template_id   = each.value
  group_principal_id = "keycloakoidc_group://${keycloak_group.access[each.key].name}"
}
resource "opensearch_dashboard_tenant" "tenant" {
  tenant_name = var.slug
  description = "Saved objects for ${var.display_name}; data access requires the matching index role."
  lifecycle { prevent_destroy = true }
}
resource "opensearch_role" "logs" {
  role_name           = "${var.slug}-logs-read"
  description         = "Only ${var.slug} application logs and its own saved objects"
  cluster_permissions = ["cluster_composite_ops_ro", "cluster:monitor/main"]
  index_permissions {
    index_patterns  = ["logs-rke2-cluster1-${var.slug}-*", "logs-rke2-cluster2-${var.slug}-*"]
    allowed_actions = ["read"]
  }
  tenant_permissions {
    tenant_patterns = [opensearch_dashboard_tenant.tenant.tenant_name]
    allowed_actions = ["kibana_all_read"]
  }
}
resource "opensearch_roles_mapping" "logs" {
  role_name     = opensearch_role.logs.role_name
  backend_roles = [keycloak_group.access["logs-readers"].name]
  description   = "Explicit log reader group for ${var.slug}"
}
