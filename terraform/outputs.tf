output "vpc_id" {
  description = "ID của VPC."
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block của VPC."
  value       = module.vpc.vpc_cidr_block
}

output "public_subnets" {
  description = "Danh sách public subnet IDs."
  value       = module.vpc.public_subnets
}

output "private_subnets" {
  description = "Danh sách private subnet IDs."
  value       = module.vpc.private_subnets
}

# output "nat_gateway_ids" {
#   description = "Danh sách NAT Gateway IDs."
#   value       = module.vpc.nat_gateway_ids
# }

output "eks_cluster_name" {
  description = "EKS Cluster Name"
  value       = module.eks.eks_cluster_name
}

# output "eks_cluster_endpoint" {
#   description = "EKS Cluster endpoint"
#   value       = module.eks.eks_cluster_endpoint
# }

output "eks_cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = module.eks.eks_cluster_arn
}

output "aws_load_balancer_controller_helm_release_version" {
  description = "Version of the AWS Load Balancer Controller"
  value       = module.eks_addons.aws_load_balancer_controller_helm_release_version
}

output "cert_manager_helm_release_version" {
  description = "Version of the Cert Manager"
  value       = module.eks_addons.cert_manager_helm_release_version
}

output "cluster_autoscaler_helm_release_version" {
  description = "Version of the Cluster Autoscaler"
  value       = module.eks_addons.cluster_autoscaler_helm_release_version
}

output "velero_backup_bucket_arn" {
  description = "ARN of the velero backup bucket"
  value       = module.eks_addons.velero_backup_bucket_arn
}

output "velero_helm_release_version" {
  description = "Version of the Velero"
  value       = module.eks_addons.velero_helm_release_version
}

output "metrics_server_helm_release_version" {
  description = "Version of the Metrics Server"
  value       = module.eks_addons.metrics_server_helm_release_version
}

output "cnpg_helm_release_version" {
  description = "Version of the CloudNative PostgreSQL"
  value       = module.eks_addons.cnpg_helm_release_version
}

output "cnpg_backup_bucket_arn" {
  description = "ARN of the cnpg backup bucket"
  value       = module.eks_addons.cnpg_backup_bucket_arn
}

output "cnpg_role_arn" {
  description = "ARN of the cnpg role"
  value       = module.eks_addons.cnpg_role_arn
}

output "external_secrets_operator_helm_release_version" {
  description = "Version of the External Secrets Operator"
  value       = module.eks_addons.external_secrets_operator_helm_release_version
}