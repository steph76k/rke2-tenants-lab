terraform {
  required_providers {
    opensearch = { source = "opensearch-project/opensearch" }
    rancher2   = { source = "rancher/rancher2" }
    keycloak   = { source = "keycloak/keycloak" }
    harbor     = { source = "goharbor/harbor" }
    kubernetes = { source = "hashicorp/kubernetes" }
    vault      = { source = "hashicorp/vault" }
  }
}
