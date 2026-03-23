output "cluster_autoscaler_helm_release_version" {
  description = "Version of the Cluster Autoscaler"
  value       = var.enable_cluster_autoscaler ? resource.helm_release.cluster_autoscaler[0].version : null
}

output "metrics_server_helm_release_version" {
  description = "Version of the Metrics Server"
  value       = var.enable_metrics_server ? resource.helm_release.metrics_server[0].version : null
}

output "cnpg_backup_bucket_arn" {
  description = "ARN of the cnpg backup bucket"
  value       = var.enable_cloudnative_postgresql ? var.cnpg_backup_bucket_arn : null
}

output "cnpg_role_arn" {
  description = "ARN of the cnpg role"
  value       = var.enable_cloudnative_postgresql ? module.cnpg_irsa[0].iam_role_arn : null
}

output "external_secrets_operator_role_arn" {
  description = "ARN of the External Secrets Operator IRSA role"
  value       = var.enable_external_secrets_operator ? module.external_secrets_operator_irsa[0].iam_role_arn : null
}