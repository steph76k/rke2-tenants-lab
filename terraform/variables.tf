variable "rancher_url" { default = "https://rancher.berger.ph" }
variable "keycloak_url" { default = "https://idp.berger.ph" }
variable "harbor_url" { default = "https://harbor-ha.berger.ph" }
variable "openbao_url" { default = "https://openbao.berger.ph" }
variable "realm" { default = "berger" }
variable "cluster_id" { default = "c-44q9v" }
variable "kubeconfig_path" { default = "~/.kube/config" }
variable "kube_context" { default = "rancher" }
variable "kubernetes_host" { default = "https://192.168.1.164:6443" }
variable "kubernetes_ca_file" { default = "../config/cluster2-ca.crt" }

variable "opensearch_url" { default = "https://127.0.0.1:19200" }
variable "opensearch_tls_host" { default = "opensearch-cluster-master.opensearch.svc.cluster.local" }
variable "opensearch_ca_file" { default = "../config/opensearch-ca.crt" }
variable "opensearch_password" {
  type      = string
  sensitive = true
}

variable "cluster_name" { default = "rke2-cluster2" }
variable "kubernetes_provider_host" { default = "https://rancher.berger.ph/k8s/clusters/c-44q9v" }
variable "tokenreview_role_name" { default = "lab-infra-openbao-tokenreview" }
