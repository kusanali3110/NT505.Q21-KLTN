module "vpc" {
  source = "./modules/vpc"

  environment          = var.environment
  vpc_name             = var.vpc_name
  vpc_cidr             = var.vpc_cidr
  azs                  = var.availability_zones
  public_subnets       = var.public_subnet_cidrs
  private_subnets      = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  enable_dns_hostnames = var.enable_dns_hostnames

  tags = merge(var.tags, {
    Environment = var.environment
  })
}

module "eks" {
  source = "./modules/eks"

  aws_region                               = var.aws_region
  eks_cluster_name                         = var.eks_cluster_name
  eks_cluster_version                      = var.eks_cluster_version
  endpoint_public_access                   = var.endpoint_public_access
  endpoint_private_access                  = var.endpoint_private_access
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  control_plane_subnet_ids                 = module.vpc.public_subnets
  spot_nodes_instance_types                = var.spot_nodes_instance_types
  spot_nodes_min_size                      = var.spot_nodes_min_size
  spot_nodes_max_size                      = var.spot_nodes_max_size
  spot_nodes_desired_size                  = var.spot_nodes_desired_size
  spot_nodes_disk_size                     = var.spot_nodes_disk_size
  on_demand_nodes_instance_types           = var.on_demand_nodes_instance_types
  on_demand_nodes_min_size                 = var.on_demand_nodes_min_size
  on_demand_nodes_max_size                 = var.on_demand_nodes_max_size
  on_demand_nodes_desired_size             = var.on_demand_nodes_desired_size
  on_demand_nodes_disk_size                = var.on_demand_nodes_disk_size
  enable_cluster_creator_admin_permissions = var.enable_cluster_creator_admin_permissions

  tags = merge(var.tags, {
    Environment = var.environment
  })
}

module "eks_addons" {
  source = "./modules/eks-addons"

  aws_region = var.aws_region
  vpc_id     = module.vpc.vpc_id

  eks_cluster_name                       = module.eks.eks_cluster_name
  eks_cluster_endpoint                   = module.eks.eks_cluster_endpoint
  eks_cluster_certificate_authority_data = module.eks.eks_cluster_certificate_authority_data
  eks_cluster_oidc_provider_arn          = module.eks.eks_cluster_oidc_provider_arn

  # Addons Flags
  enable_aws_load_balancer_controller = var.enable_aws_load_balancer_controller
  enable_cert_manager                 = var.enable_cert_manager
  enable_cluster_autoscaler           = var.enable_cluster_autoscaler
  enable_metrics_server               = var.enable_metrics_server
  enable_cloudnative_postgresql       = var.enable_cloudnative_postgresql
  enable_external_secrets_operator    = var.enable_external_secrets_operator
  
  # CloudNative PostgreSQL
  cnpg_backup_bucket_arn             = var.cnpg_backup_bucket_arn

  depends_on = [module.eks]
}