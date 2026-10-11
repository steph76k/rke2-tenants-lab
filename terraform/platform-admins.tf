# Platform privileges are independent of tenant roles. The designated admin's
# memberships are managed below; other membership changes belong in Keycloak.
locals {
  platform_admin_services = toset(["rancher", "harbor", "opensearch", "argocd", "openbao"])
}

resource "keycloak_group" "platform_admins" {
  for_each = local.platform_admin_services
  realm_id = var.realm
  name     = "${each.key}-platform-admins"
  lifecycle {
    prevent_destroy = true
  }
}

data "keycloak_user" "platform_admin" {
  realm_id = var.realm
  username = "admin"
}

# Add only these memberships; preserve any other deliberate memberships.
resource "keycloak_user_groups" "platform_admin" {
  realm_id   = var.realm
  user_id    = data.keycloak_user.platform_admin.id
  group_ids  = [for group in keycloak_group.platform_admins : group.id]
  exhaustive = false
}

resource "rancher2_global_role_binding" "platform_admins" {
  name               = "rancher-platform-admins"
  global_role_id     = "admin"
  group_principal_id = "keycloakoidc_group://${keycloak_group.platform_admins["rancher"].name}"
}

# Preserve the local emergency administrator's existing backend role.
resource "opensearch_roles_mapping" "platform_admins" {
  role_name     = "all_access"
  backend_roles = ["admin", keycloak_group.platform_admins["opensearch"].name]
  lifecycle {
    prevent_destroy = true
  }
}

resource "opensearch_roles_mapping" "platform_security_admins" {
  role_name     = "security_rest_api_access"
  backend_roles = [keycloak_group.platform_admins["opensearch"].name]
}

# Adopt the existing OIDC configuration; the secret is supplied from OpenBao by
# lab-terraform.py and is never persisted in a Terraform plan or state.
variable "harbor_oidc_client_secret" {
  type      = string
  sensitive = true
  ephemeral = true
}

resource "harbor_config_auth" "platform_oidc" {
  auth_mode                     = "oidc_auth"
  oidc_name                     = "Keycloak berger"
  oidc_endpoint                 = "${var.keycloak_url}/realms/${var.realm}"
  oidc_client_id                = "afi-harbor"
  oidc_client_secret_wo         = var.harbor_oidc_client_secret
  oidc_client_secret_wo_version = 1
  oidc_groups_claim             = "groups"
  oidc_admin_group              = keycloak_group.platform_admins["harbor"].name
  oidc_scope                    = "openid,profile,email"
  oidc_verify_cert              = true
  oidc_auto_onboard             = true
  oidc_user_claim               = "preferred_username"
  lifecycle {
    prevent_destroy = true
  }
}

# Existing OpenBao objects are imported in place. OpenBao's OIDC client emits
# full group paths, unlike the other platform clients.
resource "vault_policy" "platform_admins" {
  name   = "platform-admin"
  policy = <<-EOT
    path "*" {
      capabilities = ["create", "read", "update", "patch", "delete", "list", "scan", "sudo"]
    }
  EOT
  lifecycle {
    prevent_destroy = true
  }
}

resource "vault_jwt_auth_backend_role" "platform_admins" {
  backend                = "oidc"
  role_name              = "platform-admin"
  role_type              = "oidc"
  user_claim             = "sub"
  groups_claim           = "groups"
  bound_claims           = { groups = keycloak_group.platform_admins["openbao"].path }
  bound_claims_type      = "string"
  claim_mappings         = { preferred_username = "username" }
  allowed_redirect_uris  = ["${var.openbao_url}/ui/vault/auth/oidc/oidc/callback"]
  oidc_scopes            = ["profile", "email"]
  token_policies         = [vault_policy.platform_admins.name]
  token_ttl              = 900
  token_max_ttl          = 3600
  token_explicit_max_ttl = 3600
  lifecycle {
    prevent_destroy = true
  }
}

output "platform_admin_groups" {
  description = "Assign trusted platform operators to these Keycloak groups; tenant groups do not imply platform access."
  value       = { for service, group in keycloak_group.platform_admins : service => group.name }
}
