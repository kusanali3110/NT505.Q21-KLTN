variable "aws_region" {
  description = "AWS Region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "eks_cluster_name" {
  description = "EKS Cluster Name"
  type        = string
}

variable "eks_cluster_endpoint" {
  description = "EKS Cluster Endpoint"
  type        = string
}

variable "eks_cluster_certificate_authority_data" {
  description = "EKS Cluster CA Data"
  type        = string
}

variable "eks_cluster_oidc_provider_arn" {
  description = "OIDC provider ARN of the EKS cluster"
  type        = string
}

# --- Feature Flags ---

variable "enable_aws_load_balancer_controller" {
  description = "Enable AWS Load Balancer Controller"
  type        = bool
  default     = true
}

variable "enable_cert_manager" {
  description = "Enable Cert Manager"
  type        = bool
  default     = true
}

variable "enable_cluster_autoscaler" {
  description = "Enable Cluster Autoscaler"
  type        = bool
  default     = true
}

variable "enable_metrics_server" {
  description = "Enable Metrics Server"
  type        = bool
  default     = true
}

variable "enable_velero" {
  description = "Enable Velero"
  type        = bool
  default     = true
}

# --- AWS Load Balancer Controller Config ---
# No extra variables needed beyond region/vpc/cluster info

# --- Cluster Autoscaler Config ---
# No extra variables needed

# --- Metrics Server Config ---
# No extra variables needed

# --- Velero Config ---

variable "velero_backup_bucket_arn" {
  description = "ARN of the Velero backup bucket"
  type        = string
}

variable "velero_volume_snapshot_location_name" {
  description = "Name of the volume snapshot location for Velero"
  type        = string
  default     = "default"
}

variable "velero_backup_storage_location_name" {
  description = "Name of the backup storage location for Velero"
  type        = string
  default     = "default"
}

# --- CloudNative PostgreSQL Config ---

variable "enable_cloudnative_postgresql" {
  description = "Enable CloudNative PostgreSQL"
  type        = bool
  default     = true
}

variable "cnpg_backup_bucket_arn" {
  description = "ARN of the cnpg backup bucket"
  type        = string
}

# --- External Secrets Operator Config ---

variable "enable_external_secrets_operator" {
  description = "Enable External Secrets Operator"
  type        = bool
  default     = true
}

