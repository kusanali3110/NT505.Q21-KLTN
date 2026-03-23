terraform {
  backend "s3" {
    bucket  = "YOUR_TERRAFORM_STATE_BUCKET_NAME"
    key     = "environments/dev/terraform.tfstate"
    region  = "ap-southeast-1"
    encrypt = true
  }
}
