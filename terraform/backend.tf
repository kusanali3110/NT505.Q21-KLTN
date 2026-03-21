terraform {
  backend "s3" {
    bucket         = var.backend_bucket_name
    key            = "${var.environment}/terraform.tfstate"
    region         = var.aws_region
    encrypt        = true
  }
}