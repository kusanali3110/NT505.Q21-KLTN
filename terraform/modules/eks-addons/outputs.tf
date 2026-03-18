output "velero_backup_bucket_arn" {
  description = "ARN of the velero backup bucket"
  value       = var.enable_velero ? var.velero_backup_bucket_arn : null
}

output "velero_helm_release_version" {
  description = "Version of the Velero"
  value       = var.enable_velero ? resource.helm_release.velero[0].version : null
}

output "aws_load_balancer_controller_helm_release_version" {
  description = "Version of the AWS Load Balancer Controller"
  value       = var.enable_aws_load_balancer_controller ? resource.helm_release.aws_load_balancer_controller[0].version : null
}

output "cert_manager_helm_release_version" {
  description = "Version of the Cert Manager"
  value       = var.enable_cert_manager ? resource.helm_release.cert_manager[0].version : null
}

output "cluster_autoscaler_helm_release_version" {
  description = "Version of the Cluster Autoscaler"
  value       = var.enable_cluster_autoscaler ? resource.helm_release.cluster_autoscaler[0].version : null
}

output "metrics_server_helm_release_version" {
  description = "Version of the Metrics Server"
  value       = var.enable_metrics_server ? resource.helm_release.metrics_server[0].version : null
}

output "cnpg_helm_release_version" {
  description = "Version of the CloudNative PostgreSQL"
  value       = var.enable_cloudnative_postgresql ? resource.helm_release.cnpg[0].version : null
}

output "cnpg_backup_bucket_arn" {
  description = "ARN of the cnpg backup bucket"
  value       = var.enable_cloudnative_postgresql ? var.cnpg_backup_bucket_arn : null
}

output "cnpg_role_arn" {
  description = "ARN of the cnpg role"
  value       = var.enable_cloudnative_postgresql ? module.cnpg_irsa[0].iam_role_arn : null
}

output "external_secrets_operator_helm_release_version" {
  description = "Version of the External Secrets Operator"
  value       = var.enable_external_secrets_operator ? resource.helm_release.external_secrets_operator[0].version : null
}