#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_FILE="$SCRIPT_DIR/backend.tf"
TFVARS_FILE="$SCRIPT_DIR/terraform.tfvars"
TFVARS_BACKUP_FILE="$SCRIPT_DIR/.terraform.tfvars.pre-bootstrap.bak"
PLAN_OUT="${PLAN_OUT:-tfplan}"

required_commands=("terraform" "aws")
optional_commands=("kubectl" "helm")

check_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing dependency: $cmd"
    return 1
  fi
}

echo "==> Checking required dependencies..."
for cmd in "${required_commands[@]}"; do
  check_command "$cmd"
done
echo "Required dependencies are installed."

echo "==> Checking optional tools..."
for cmd in "${optional_commands[@]}"; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo " - $cmd: found"
  else
    echo " - $cmd: not found (optional)"
  fi
done

if [[ ! -f "$BACKEND_FILE" ]]; then
  echo "ERROR: backend.tf not found at: $BACKEND_FILE"
  exit 1
fi

if [[ ! -f "$TFVARS_FILE" ]]; then
  echo "ERROR: terraform.tfvars not found at: $TFVARS_FILE"
  exit 1
fi

read_tf_string_value() {
  local key="$1"
  local file="$2"
  local value
  value="$(sed -nE "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*\"([^\"]*)\".*/\1/p" "$file" | tail -n 1)"
  echo "$value"
}

extract_bucket_name_from_arn_or_name() {
  local input="$1"
  if [[ "$input" == arn:aws:s3:::* ]]; then
    echo "${input#arn:aws:s3:::}"
  else
    echo "$input"
  fi
}

upsert_tfvars_string() {
  local key="$1"
  local value="$2"
  local file="$3"
  local tmp_file
  tmp_file="$(mktemp)"

  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      print key " = \"" value "\""
      updated = 1
      next
    }
    { print }
    END {
      if (updated == 0) {
        print key " = \"" value "\""
      }
    }
  ' "$file" > "$tmp_file"

  mv "$tmp_file" "$file"
}

prompt_if_placeholder() {
  local value="$1"
  local prompt_msg="$2"
  local out_var="$3"

  if [[ -z "$value" || "$value" == YOUR_* || "$value" == *YOUR_* ]]; then
    read -r -p "$prompt_msg: " value
    if [[ -z "$value" ]]; then
      echo "ERROR: Value is required."
      exit 1
    fi
  fi

  printf -v "$out_var" '%s' "$value"
}

create_bucket_if_not_exists() {
  local bucket="$1"
  local region="$2"

  if aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    echo "Bucket already exists: $bucket"
    return 0
  fi

  echo "Creating bucket: $bucket (region: $region)"
  if [[ "$region" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$bucket" >/dev/null
  else
    aws s3api create-bucket \
      --bucket "$bucket" \
      --create-bucket-configuration "LocationConstraint=$region" >/dev/null
  fi

  aws s3api put-bucket-versioning \
    --bucket "$bucket" \
    --versioning-configuration Status=Enabled >/dev/null

  aws s3api put-bucket-encryption \
    --bucket "$bucket" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' >/dev/null

  echo "Created and configured bucket: $bucket"
}

echo "==> Checking AWS credentials..."
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not configured or expired."
  echo "Starting 'aws configure'..."
  aws configure
fi

AWS_REGION="$(read_tf_string_value "aws_region" "$TFVARS_FILE")"
if [[ -z "$AWS_REGION" ]]; then
  AWS_REGION="$(read_tf_string_value "region" "$BACKEND_FILE")"
fi
AWS_REGION="${AWS_REGION:-ap-southeast-1}"

BACKEND_BUCKET_RAW="${BACKEND_BUCKET:-$(read_tf_string_value "backend_bucket_name" "$TFVARS_FILE")}"
if [[ -z "$BACKEND_BUCKET_RAW" ]]; then
  BACKEND_BUCKET_RAW="$(read_tf_string_value "bucket" "$BACKEND_FILE")"
fi
CNPG_BUCKET_RAW="${CNPG_BUCKET_NAME:-$(read_tf_string_value "cnpg_backup_bucket_arn" "$TFVARS_FILE")}"
BACKEND_KEY="$(read_tf_string_value "key" "$BACKEND_FILE")"
BACKEND_KEY="${BACKEND_KEY:-environments/dev/terraform.tfstate}"

prompt_if_placeholder "$BACKEND_BUCKET_RAW" "Enter backend state bucket name" BACKEND_BUCKET_NAME
CNPG_BUCKET_DEFAULT="$(extract_bucket_name_from_arn_or_name "$CNPG_BUCKET_RAW")"
prompt_if_placeholder "$CNPG_BUCKET_DEFAULT" "Enter CNPG S3 bucket name" CNPG_BUCKET_NAME

CNPG_ARN="arn:aws:s3:::$CNPG_BUCKET_NAME"

echo "==> Buckets to ensure:"
echo " - Backend state : $BACKEND_BUCKET_NAME"
echo " - CNPG backup   : $CNPG_BUCKET_NAME"

create_bucket_if_not_exists "$BACKEND_BUCKET_NAME" "$AWS_REGION"
create_bucket_if_not_exists "$CNPG_BUCKET_NAME" "$AWS_REGION"

echo "==> Backing up terraform.tfvars..."
cp "$TFVARS_FILE" "$TFVARS_BACKUP_FILE"
echo "Backup created: $TFVARS_BACKUP_FILE"

echo "==> Updating terraform.tfvars with created bucket names..."
upsert_tfvars_string "backend_bucket_name" "$BACKEND_BUCKET_NAME" "$TFVARS_FILE"
upsert_tfvars_string "cnpg_backup_bucket_arn" "$CNPG_ARN" "$TFVARS_FILE"
echo "terraform.tfvars has been updated."

echo "==> Running Terraform init..."
terraform init -upgrade -reconfigure \
  -backend-config="bucket=$BACKEND_BUCKET_NAME" \
  -backend-config="key=$BACKEND_KEY" \
  -backend-config="region=$AWS_REGION" \
  -backend-config="encrypt=true"

echo "==> Running Terraform validate..."
terraform validate

echo "==> Running Terraform plan..."
terraform plan

echo "Done."
