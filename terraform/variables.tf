variable "rancher_url" { default = "https://rancher.berger.ph" }
variable "keycloak_url" { default = "https://idp.berger.ph" }
variable "harbor_url" { default = "https://harbor-ha.berger.ph" }
variable "openbao_url" { default = "https://openbao.berger.ph" }
variable "realm" { default = "berger" }
variable "cluster_id" { default = "c-m-prkskj2p" }
variable "kubeconfig_path" { default = "~/.kube/config" }
variable "kube_context" { default = "rke2-cluster1" }
variable "kubernetes_host" { default = "https://192.168.1.23:6443" }
variable "kubernetes_ca_file" { default = "../config/cluster1-ca.crt" }

variable "tenant_slug" {
  type        = string
  description = "Exactly one tenant per isolated remote state."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,39}$", var.tenant_slug)) && fileexists("${path.module}/../tenants/${var.tenant_slug}.json")
    error_message = "Select an existing tenant declaration."
  }
}

variable "opensearch_url" { default = "https://127.0.0.1:19200" }
variable "opensearch_tls_host" { default = "opensearch-cluster-master.opensearch.svc.cluster.local" }
variable "opensearch_ca_file" { default = "../config/opensearch-ca.crt" }
variable "opensearch_password" {
  type      = string
  sensitive = true
}
