variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "eks_cluster_version" {
  description = "Version of the EKS cluster"
  type        = string
}

variable "endpoint_public_access" {
  description = "Endpoint public access of the EKS cluster"
  type        = bool
}

variable "endpoint_private_access" {
  description = "Endpoint private access of the EKS cluster"
  type        = bool
}

variable "vpc_id" {
  description = "VPC ID of the EKS cluster"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs of the EKS node group"
  type        = list(string)
}

variable "control_plane_subnet_ids" {
  description = "List of subnet IDs of the control plane"
  type        = list(string)
}

variable "spot_nodes_instance_types" {
  description = "List of instance types of the spot nodes"
  type        = list(string)
}

variable "spot_nodes_min_size" {
  description = "Minimum number of nodes of the spot nodes"
  type        = number
}

variable "spot_nodes_max_size" {
  description = "Maximum number of nodes of the spot nodes"
  type        = number
}

variable "spot_nodes_desired_size" {
  description = "Desired number of nodes of the spot nodes"
  type        = number
}

variable "spot_nodes_disk_size" {
  description = "Disk size of the spot nodes (GB)"
  type        = number
}

variable "on_demand_nodes_instance_types" {
  description = "List of instance types of the on demand nodes"
  type        = list(string)
}

variable "on_demand_nodes_min_size" {
  description = "Minimum number of nodes of the on demand nodes"
  type        = number
}

variable "on_demand_nodes_max_size" {
  description = "Maximum number of nodes of the on demand nodes"
  type        = number
}

variable "on_demand_nodes_desired_size" {
  description = "Desired number of nodes of the on demand nodes"
  type        = number
}

variable "on_demand_nodes_disk_size" {
  description = "Disk size of the on demand nodes (GB)"
  type        = number
}

variable "enable_cluster_creator_admin_permissions" {
  description = "Enable cluster creator admin permissions"
  type        = bool
}

variable "tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
}