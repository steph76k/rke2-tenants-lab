output "summary" {
  value = {
    project_id        = rancher2_project.tenant.id
    group             = keycloak_group.tenant.name
    namespaces        = local.namespaces
    openbao_namespace = vault_namespace.tenant.path
    secret_store      = local.service_account
    harbor_project    = var.harbor_enabled ? harbor_project.tenant[0].name : null
  }
}
