locals {
  logging_routes = merge({ for slug, tenant in module.tenant : slug => {
    project_label = split(":", tenant.summary.project_id)[1]
  } }, { platform = { project_label = "" } })
  logging_output_template = jsondecode(file("${path.module}/../config/logging-output.json"))
}

# All Cluster 2 routes (including the platform fallback) have one Terraform owner.
# Fleet retains ownership of collectors, ingest credentials and monitoring.
resource "kubernetes_manifest" "logging_output" {
  for_each = local.logging_routes
  field_manager {
    force_conflicts = var.logging_takeover
  }
  manifest = {
    apiVersion = "logging.banzaicloud.io/v1beta1"
    kind       = "ClusterOutput"
    metadata   = { name = "afi-${each.key}", namespace = "cattle-logging-system" }
    spec = { opensearch = merge(local.logging_output_template, {
      user            = "afi-ingest-${var.cluster_name}"
      logstash_prefix = "logs-${var.cluster_name}-${each.key}"
      buffer = merge(local.logging_output_template.buffer, {
        total_limit_size = "${var.logging_buffer_mib}m"
      })
    }) }
  }
  lifecycle {
    precondition {
      condition     = length(local.logging_routes) * var.logging_buffer_mib <= var.logging_buffer_budget_mib
      error_message = "Tenant logging queues exceed the reviewed PVC budget. Expand storage or review per-output limits before adding more tenants."
    }
  }
}

resource "kubernetes_manifest" "logging_flow" {
  for_each = local.logging_routes
  field_manager {
    force_conflicts = var.logging_takeover
  }
  manifest = {
    apiVersion = "logging.banzaicloud.io/v1beta1"
    kind       = "ClusterFlow"
    metadata   = { name = "afi-${each.key}", namespace = "cattle-logging-system" }
    spec = {
      # JSON decoding preserves the different select/exclude object shapes.
      match = jsondecode(each.key == "platform" ? jsonencode(concat([
        for slug, tenant in module.tenant : {
          exclude = { namespaces = [], namespace_labels = { "field.cattle.io/projectId" = split(":", tenant.summary.project_id)[1] } }
        }
        ], [{ select = {} }])) : jsonencode([{
        select = { namespaces = [], namespace_labels = { "field.cattle.io/projectId" = each.value.project_label } }
      }]))
      filters = [
        { dedot = { de_dot_nested = true, de_dot_separator = "_" } },
        { record_modifier = { records = [{
          cluster_name = var.cluster_name, cluster_role = "infrastructure", tenant_id = each.key, environment = "lab"
        }] } }
      ]
      globalOutputRefs = ["afi-${each.key}"]
    }
  }
  depends_on = [kubernetes_manifest.logging_output, kubernetes_manifest.tenant_admission_binding]
}

variable "logging_buffer_mib" {
  type    = number
  default = 4096
}

variable "logging_takeover" {
  description = "One-time SSA ownership transfer only after the former Fleet bundle has been removed with keepResources. Leave false for normal runs."
  type        = bool
  default     = false
}

variable "logging_buffer_budget_mib" {
  type    = number
  default = 16384
}
