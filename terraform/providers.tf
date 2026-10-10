provider "rancher2" {
  api_url  = var.rancher_url
  insecure = false
}
provider "keycloak" {
  url       = var.keycloak_url
  client_id = "admin-cli"
  realm     = "master"
}
provider "harbor" {
  url      = var.harbor_url
  insecure = false
}
provider "kubernetes" {
  config_path    = pathexpand(var.kubeconfig_path)
  config_context = var.kube_context
}
provider "vault" {
  address                = var.openbao_url
  skip_child_token       = true
  skip_get_vault_version = true
}
