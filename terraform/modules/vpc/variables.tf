variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}
variable "vpc_name" {
  description = "Name of the VPC."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "azs" {
  description = "List of availability zones."
  type        = list(string)
}

variable "public_subnets" {
  description = "List of public subnet CIDRs."
  type        = list(string)
}

variable "private_subnets" {
  description = "List of private subnet CIDRs."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets."
  type        = bool
}

variable "single_nat_gateway" {
  description = "Create a single NAT Gateway across all AZs."
  type        = bool
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames for the VPC."
  type        = bool
}

variable "tags" {
  description = "A map of tags to add to all resources."
  type        = map(string)
}