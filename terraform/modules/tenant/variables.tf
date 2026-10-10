variable "slug" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,39}$", var.slug))
    error_message = "Tenant slug must be 2-40 lowercase letters, digits or hyphens, starting with a letter."
  }
}
variable "display_name" { type = string }
variable "environments" {
  type = list(string)
  validation {
    condition     = length(var.environments) > 0 && length(distinct(var.environments)) == length(var.environments) && alltrue([for e in var.environments : can(regex("^[a-z][a-z0-9-]{0,14}$", e))])
    error_message = "At least one valid environment name is required."
  }
}
variable "project_role" {
  type = string
  validation {
    condition     = contains(["project-member", "read-only", "project-owner"], var.project_role)
    error_message = "Use a built-in Rancher project role."
  }
}
variable "harbor_enabled" { type = bool }
variable "harbor_storage_gib" {
  type = number
  validation {
    condition     = var.harbor_storage_gib >= 1 && floor(var.harbor_storage_gib) == var.harbor_storage_gib
    error_message = "Harbor quota must be a positive integer in GiB."
  }
}
variable "realm" { type = string }
variable "cluster_id" { type = string }
variable "openbao_url" { type = string }
variable "kubernetes_host" { type = string }
variable "kubernetes_ca_cert" { type = string }
