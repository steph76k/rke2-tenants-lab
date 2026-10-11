# Adopt the existing client; preserve its secret, login URI and dedicated mappers.
resource "keycloak_openid_client" "opensearch" {
  realm_id                            = var.realm
  client_id                           = "afi-opensearch"
  name                                = "afi-opensearch"
  description                         = "Managed by rke2-platform-lab AFI bootstrap"
  access_type                         = "CONFIDENTIAL"
  enabled                             = true
  standard_flow_enabled               = true
  implicit_flow_enabled               = false
  direct_access_grants_enabled        = false
  service_accounts_enabled            = false
  full_scope_allowed                  = true
  valid_redirect_uris                 = ["https://opensearch.berger.ph/auth/openid/login"]
  web_origins                         = ["https://opensearch.berger.ph"]
  valid_post_logout_redirect_uris     = ["https://opensearch.berger.ph"]
  backchannel_logout_session_required = true
  lifecycle {
    prevent_destroy = true
  }
}

# Global saved objects are accessible to platform administrators. Tenant log
# reader roles still grant only their own named tenant and their own log indices.
# Storage format verified against the running Dashboards 3.9.0 saved-object API.
resource "opensearch_dashboard_object" "platform_index_pattern" {
  for_each = {
    logs = { title = "logs-*", time_field = "@timestamp" }
    all  = { title = "*", time_field = null }
  }
  body = jsonencode([{
    _id = "index-pattern:afi-platform-${each.key}"
    _source = {
      type = "index-pattern"
      "index-pattern" = merge({ title = each.value.title },
      each.value.time_field == null ? {} : { timeFieldName = each.value.time_field })
      references       = []
      migrationVersion = { "index-pattern" = "7.6.0" }
    }
  }])
}

resource "opensearch_dashboard_object" "platform_defaults" {
  body = jsonencode([{
    _id = "config:3.9.0"
    _source = {
      type = "config"
      config = {
        buildNum                  = 9054
        defaultIndex              = "afi-platform-logs"
        "timepicker:timeDefaults" = jsonencode({ from = "now-24h", to = "now" })
      }
      references       = []
      migrationVersion = { config = "7.9.0" }
    }
  }])
  depends_on = [opensearch_dashboard_object.platform_index_pattern]
}

# The OpenSearch provider intentionally ignores index-pattern.fields. Initialize
# that computed cache through the Dashboards API after creating/changing a view.
resource "terraform_data" "platform_index_fields" {
  triggers_replace = [for name in sort(keys(opensearch_dashboard_object.platform_index_pattern)) :
    sha256(opensearch_dashboard_object.platform_index_pattern[name].body)
  ]
  provisioner "local-exec" {
    command = "python3 ${path.module}/../scripts/refresh-platform-index-fields.py"
  }
  depends_on = [opensearch_dashboard_object.platform_defaults]
}
