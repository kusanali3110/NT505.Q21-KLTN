aws_region  = "ap-southeast-1"

# VPC Configuration
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
private_subnet_cidrs = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

# EKS Configuration
eks_cluster_name        = "Lab_EKS"
eks_cluster_version     = "1.32"
endpoint_public_access  = true
endpoint_private_access = true

# Node Groups Configuration
spot_nodes_instance_types = ["c7i-flex.large"]
spot_nodes_min_size       = 3
spot_nodes_max_size       = 10
spot_nodes_desired_size   = 3
spot_nodes_disk_size      = 20

# On Demand Nodes Configuration
on_demand_nodes_instance_types           = ["t3.small","c7i-flex.large"]
on_demand_nodes_min_size                 = 3
on_demand_nodes_max_size                 = 10
on_demand_nodes_desired_size             = 3
on_demand_nodes_disk_size                = 20

# Addons Configuration
enable_cluster_creator_admin_permissions = true
enable_aws_load_balancer_controller = true
enable_cert_manager = true
enable_cluster_autoscaler = true
enable_metrics_server = true
enable_velero = true
enable_cloudnative_postgresql = true
enable_external_secrets_operator = true

# Velero Configuration
velero_backup_bucket_arn = "arn:aws:s3:::YOUR_VELERO_BACKUP_BUCKET_NAME"
velero_backup_storage_location_name = "veleros3"
velero_volume_snapshot_location_name = "veleroebs"

# CloudNative PostgreSQL Configuration
cnpg_backup_bucket_arn = "arn:aws:s3:::YOUR_CNPG_BACKUP_BUCKET_NAME"

# Tags
tags = {
  Project     = "Lab_Project"
  Environment = "dev"
}