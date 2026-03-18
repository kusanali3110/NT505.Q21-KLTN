module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0.0"

  name               = var.vpc_name
  cidr               = var.vpc_cidr

  azs                = var.azs
  public_subnets     = var.public_subnets
  private_subnets    = var.private_subnets

  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway
  enable_dns_hostnames = var.enable_dns_hostnames
  
  tags               = var.tags

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
} 