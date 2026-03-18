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

output "nat_gateway_ids" {
  description = "Danh sách NAT Gateway IDs."
  value       = module.vpc.natgw_ids
} 