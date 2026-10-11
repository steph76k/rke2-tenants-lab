locals {
  egress_gateways = jsondecode(file("${path.module}/../config/egress-gateways.json"))
  egress_bindings = merge([for slug, tenant in local.tenants : {
    for worker, ip in tenant.egress_ips : "${slug}-${worker}" => merge(local.egress_gateways[worker], {
      ip = ip, owner = slug, worker = worker
    })
  }]...)
  egress_ips = [for binding in local.egress_bindings : binding.ip]
}

resource "terraform_data" "egress_allocations" {
  input = local.egress_bindings
  lifecycle {
    precondition {
      condition = alltrue([for tenant in values(local.tenants) :
        toset(keys(tenant.egress_ips)) == toset(["worker1", "worker2"])
      ])
      error_message = "Each tenant must reserve one Egress IP on worker1 and one on worker2."
    }
    precondition {
      condition = length(distinct(local.egress_ips)) == length(local.egress_ips) && alltrue([
        for ip in local.egress_ips : can(regex("^192\\.168\\.1\\.(20[0-9]|21[0-9]|220)$", ip))
      ])
      error_message = "Egress IPs must be unique across all tenants and within 192.168.1.200–220."
    }
  }
}

# SSH uses the administrator's existing key/agent and strict known_hosts checks.
# No private key or password is placed in configuration or state.
resource "terraform_data" "egress_address" {
  for_each         = local.egress_bindings
  input            = each.value
  triggers_replace = [each.value, filesha256("${path.module}/../scripts/gateway-address.py")]
  provisioner "local-exec" {
    command     = "python3 ../scripts/gateway-address.py --apply"
    working_dir = path.module
    environment = { AFI_EGRESS_BINDING = jsonencode(self.input) }
  }
  provisioner "local-exec" {
    when        = destroy
    command     = "python3 ../scripts/gateway-address.py --remove"
    working_dir = path.module
    environment = { AFI_EGRESS_BINDING = jsonencode(self.input) }
  }
  depends_on = [terraform_data.egress_allocations]
}

resource "kubernetes_manifest" "tenant_egress" {
  for_each = local.egress_bindings
  manifest = {
    apiVersion = "cilium.io/v2"
    kind       = "CiliumEgressGatewayPolicy"
    metadata   = { name = each.key }
    spec = {
      selectors = [{
        podSelector = { matchExpressions = [{
          key    = "io.kubernetes.pod.namespace", operator = "In"
          values = module.tenant[each.value.owner].summary.namespaces
        }] }
        nodeSelector = { matchExpressions = [{
          key      = "kubernetes.io/hostname"
          operator = each.value.worker == "worker1" ? "In" : "NotIn"
          values   = [local.egress_gateways.worker1.node]
        }] }
      }]
      destinationCIDRs = ["0.0.0.0/0"]
      egressGateway = {
        nodeSelector = { matchLabels = { "kubernetes.io/hostname" = each.value.node } }
        egressIP     = each.value.ip
      }
    }
  }
  depends_on = [terraform_data.egress_address]
}

output "egress_addresses" {
  value = { for slug, tenant in local.tenants : slug => tenant.egress_ips }
}
