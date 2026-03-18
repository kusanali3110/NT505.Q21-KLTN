# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = var.eks_cluster_name
  kubernetes_version = var.eks_cluster_version

  vpc_id                   = var.vpc_id
  subnet_ids               = var.subnet_ids
  control_plane_subnet_ids = var.control_plane_subnet_ids

  # Optional
  endpoint_private_access = var.endpoint_private_access
  endpoint_public_access  = var.endpoint_public_access

  # Optional: Adds the current caller identity as an administrator via cluster access entry
  enable_cluster_creator_admin_permissions = var.enable_cluster_creator_admin_permissions

  # Addons
  addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent    = true
      before_compute = true
    }
    aws-ebs-csi-driver = {
      most_recent                 = true
      resolve_conflicts_on_update = "OVERWRITE"
      service_account_role_arn    = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Enable IRSA for AWS Load Balancer Controller, EBS CSI Driver and other addons
  enable_irsa = true

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    # Spot Nodes for general workload
    spot_nodes = {
      name           = "spot-nodes"
      instance_types = var.spot_nodes_instance_types
      ami_type       = "AL2023_x86_64_STANDARD"
      min_size       = var.spot_nodes_min_size
      max_size       = var.spot_nodes_max_size
      desired_size   = var.spot_nodes_desired_size
      disk_size      = var.spot_nodes_disk_size
      capacity_type  = "SPOT"

      labels = {
        "node-type"     = "spot"
        "workload-type" = "general"
      }

      # Enable cluster autoscaler
      tags = {
        "k8s.io/cluster-autoscaler/enabled"    = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}" = "owned"
      }
    }

    # On Demand Nodes for critical workload
    on_demand_nodes = {
      name = "on-demand-nodes"

      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.on_demand_nodes_instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = var.on_demand_nodes_min_size
      max_size     = var.on_demand_nodes_max_size
      desired_size = var.on_demand_nodes_desired_size

      disk_size = var.on_demand_nodes_disk_size

      labels = {
        "node-type"     = "on-demand"
        "workload-type" = "critical"
      }

      # Enable cluster autoscaler 
      tags = {
        "k8s.io/cluster-autoscaler/enabled"         = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}" = "owned"
      }
    }
  }

  # Needed by the aws-ebs-csi-driver
  iam_role_additional_policies = {
    AmazonEBSCSIDriverPolicy = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  }

  tags = var.tags
}

# IRSA Role for ebs-csi-controller-sa
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "AmazonEKS_EBS_CSI_DriverRole"

  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}