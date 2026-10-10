locals {
  tenants = { for f in fileset("${path.module}/../tenants", "*.json") : trimsuffix(f, ".json") => jsondecode(file("${path.module}/../tenants/${f}")) if trimsuffix(f, ".json") == var.tenant_slug }
}
module "tenant" {
  for_each           = local.tenants
  source             = "./modules/tenant"
  slug               = each.key
  display_name       = each.value.display_name
  environments       = each.value.environments
  project_role       = each.value.project_role
  harbor_enabled     = each.value.harbor_enabled
  harbor_storage_gib = each.value.harbor_storage_gib
  realm              = var.realm
  cluster_id         = var.cluster_id
  openbao_url        = var.openbao_url
  kubernetes_host    = var.kubernetes_host
  kubernetes_ca_cert = file(var.kubernetes_ca_file)
}
