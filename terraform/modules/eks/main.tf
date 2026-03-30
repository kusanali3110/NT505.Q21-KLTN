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
  }

  # Enable IRSA for AWS Load Balancer Controller, EBS CSI Driver and other addons
  enable_irsa = true

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    # Spot Nodes for general workload
    spot_nodes = {
      name           = "spot-nodes"
      instance_types = var.spot_nodes_instance_types
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
        "k8s.io/cluster-autoscaler/enabled"                 = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}" = "owned"
      }

      # Add custom userdata
      # Installs iscsi-initiator-utils, sets initiator name, and starts iscsid
      cloudinit_pre_nodeadm = [
        {
          content_type = "text/x-shellscript; charset=\"us-ascii\""
          content      = <<-EOT
            #!/bin/bash
            set -ex
            yum install -y iscsi-initiator-utils
            echo "InitiatorName=$(/sbin/iscsi-iname)" > /etc/iscsi/initiatorname.iscsi
            systemctl enable iscsid
            systemctl start iscsid
          EOT
        }
      ]
    }

    # On Demand Nodes for critical workload
    on_demand_nodes = {
      name           = "on-demand-nodes"
      instance_types = var.on_demand_nodes_instance_types
      min_size       = var.on_demand_nodes_min_size
      max_size       = var.on_demand_nodes_max_size
      desired_size   = var.on_demand_nodes_desired_size
      disk_size      = var.on_demand_nodes_disk_size
      capacity_type  = "ON_DEMAND"

      labels = {
        "node-type"     = "on-demand"
        "workload-type" = "critical"
      }

      # Enable cluster autoscaler 
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                 = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}" = "owned"
      }

      # Add custom userdata
      # Installs iscsi-initiator-utils, sets initiator name, and starts iscsid
      cloudinit_pre_nodeadm = [
        {
          content_type = "text/x-shellscript; charset=\"us-ascii\""
          content      = <<-EOT
            #!/bin/bash
            set -ex
            yum install -y iscsi-initiator-utils
            echo "InitiatorName=$(/sbin/iscsi-iname)" > /etc/iscsi/initiatorname.iscsi
            systemctl enable iscsid
            systemctl start iscsid
          EOT
        }
      ]
    }
  }

  node_security_group_additional_rules = {
    ingress_longhorn_webhook = {
      description                   = "Allow EKS control plane to access Longhorn webhook"
      protocol                      = "tcp"
      from_port                     = 9502
      to_port                       = 9502
      type                          = "ingress"
      source_cluster_security_group = true
    }
  }
  tags = var.tags
}
