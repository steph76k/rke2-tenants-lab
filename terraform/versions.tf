terraform {
  required_version = ">= 1.3.0, < 2.0.0"
  required_providers {
    rancher2 = {
      source  = "rancher/rancher2"
      version = "15.1.2"
    }
    keycloak = {
      source  = "keycloak/keycloak"
      version = "5.10.0"
    }
    harbor = {
      source  = "goharbor/harbor"
      version = "3.12.5"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "3.3.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "5.12.0"
    }
  }
}
