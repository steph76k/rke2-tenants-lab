output "tenants" {
  value = { for name, tenant in module.tenant : name => tenant.summary }
}
