variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "vpc_name" {
  description = "Name of the VPC."
  type        = string
  default     = "Lab_VPC"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["ap-southeast-1a", "ap-southeast-1b"]
}

variable "public_subnet_cidrs" {
  description = "List of public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "List of private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Create a single NAT Gateway across all AZs."
  type        = bool
  default     = true
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames for the VPC."
  type        = bool
  default     = true
}

variable "eks_cluster_name" {
  description = "Tên EKS cluster"
  type        = string
  default     = "Lab_EKS"
}

variable "eks_cluster_version" {
  description = "Phiên bản Kubernetes cho EKS"
  type        = string
  default     = "1.31.0"
}

variable "endpoint_public_access" {
  description = "Endpoint public access cho EKS cluster"
  type        = bool
  default     = true
}

variable "endpoint_private_access" {
  description = "Endpoint private access cho EKS cluster"
  type        = bool
  default     = false
}

variable "spot_nodes_instance_types" {
  description = "Danh sách instance types cho spot nodes"
  type        = list(string)
  default     = ["t3.small"]
}

variable "spot_nodes_min_size" {
  description = "Số lượng node tối thiểu cho spot nodes"
  type        = number
  default     = 1
}

variable "spot_nodes_max_size" {
  description = "Số lượng node tối đa cho spot nodes"
  type        = number
  default     = 6
}

variable "spot_nodes_desired_size" {
  description = "Số lượng node mong muốn cho spot nodes"
  type        = number
  default     = 1
}

variable "spot_nodes_disk_size" {
  description = "Kích thước đĩa cho spot nodes (GB)"
  type        = number
  default     = 20
}

variable "on_demand_nodes_instance_types" {
  description = "Danh sách instance types cho on demand nodes"
  type        = list(string)
  default     = ["t3.small"]
}

variable "on_demand_nodes_min_size" {
  description = "Số lượng node tối thiểu cho on demand nodes"
  type        = number
  default     = 1
}

variable "on_demand_nodes_max_size" {
  description = "Số lượng node tối đa cho on demand nodes"
  type        = number
  default     = 3
}

variable "on_demand_nodes_desired_size" {
  description = "Số lượng node mong muốn cho on demand nodes"
  type        = number
  default     = 1
}

variable "on_demand_nodes_disk_size" {
  description = "Kích thước đĩa cho on demand nodes (GB)"
  type        = number
  default     = 20
}

variable "enable_cluster_creator_admin_permissions" {
  description = "Enable cluster creator admin permissions"
  type        = bool
  default     = true
}

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

variable "enable_cloudnative_postgresql" {
  description = "Enable CloudNative PostgreSQL"
  type        = bool
  default     = true
}

variable "enable_external_secrets_operator" {
  description = "Enable External Secrets Operator"
  type        = bool
  default     = true
}

variable "velero_backup_bucket_arn" {
  description = "ARN of the velero backup bucket"
  type        = string
}

variable "velero_backup_storage_location_name" {
  description = "Name of the backup storage location for Velero"
  type        = string
  default     = "default"
}

variable "velero_volume_snapshot_location_name" {
  description = "Name of the volume snapshot location for Velero"
  type        = string
  default     = "default"
}

variable "cnpg_backup_bucket_arn" {
  description = "ARN of the cnpg backup bucket"
  type        = string
}

variable "tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
  default = {
    Project     = "Lab_Project"
    Environment = "dev"
  }
}