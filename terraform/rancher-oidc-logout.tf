# Adopt the existing client without rotating its secret or changing its mappers.
resource "keycloak_openid_client" "rancher" {
  realm_id                            = var.realm
  client_id                           = "rancher"
  name                                = "Rancher Manager"
  access_type                         = "CONFIDENTIAL"
  enabled                             = true
  standard_flow_enabled               = true
  implicit_flow_enabled               = false
  direct_access_grants_enabled        = false
  service_accounts_enabled            = false
  full_scope_allowed                  = true
  valid_redirect_uris                 = ["${var.rancher_url}/verify-auth"]
  web_origins                         = [var.rancher_url]
  valid_post_logout_redirect_uris     = [var.rancher_url, "${var.rancher_url}/dashboard/auth/verify?is-slo&logged-out"]
  pkce_code_challenge_method          = "S256"
  backchannel_logout_session_required = true
  lifecycle {
    prevent_destroy = true
  }
}

# The provider adopts the existing singleton through an in-place API update
# on its first apply (it has no importer). Never disable/recreate the provider.
resource "rancher2_auth_config_keycloak_oidc" "platform" {
  enabled     = true
  access_mode = "unrestricted"
  allowed_principal_ids = [
    "keycloakoidc_user://8e8b393b-93cd-405f-a031-d51f2897b82a",
    "keycloakoidc_group://G_Admin",
    "keycloakoidc_user://825b5c03-972c-45bc-9ad7-40dd3e8581b5",
  ]
  client_id            = keycloak_openid_client.rancher.client_id
  client_secret        = keycloak_openid_client.rancher.client_secret
  issuer               = "${var.keycloak_url}/realms/${var.realm}"
  auth_endpoint        = "${var.keycloak_url}/realms/${var.realm}/protocol/openid-connect/auth"
  token_endpoint       = "${var.keycloak_url}/realms/${var.realm}/protocol/openid-connect/token"
  userinfo_endpoint    = "${var.keycloak_url}/realms/${var.realm}/protocol/openid-connect/userinfo"
  jwks_url             = "${var.keycloak_url}/realms/${var.realm}/protocol/openid-connect/certs"
  rancher_url          = "${var.rancher_url}/verify-auth"
  groups_field         = "groups"
  name_claim           = "name"
  email_claim          = "email"
  scopes               = "openid profile email"
  group_search_enabled = true
  pkce_method          = "S256"
  end_session_endpoint = "${var.keycloak_url}/realms/${var.realm}/protocol/openid-connect/logout"
  logout_all_enabled   = true
  logout_all_forced    = true
  lifecycle {
    prevent_destroy = true
  }
}
