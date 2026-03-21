#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_FILE="$SCRIPT_DIR/backend.tf"
TFVARS_FILE="$SCRIPT_DIR/terraform.tfvars"
TFVARS_BACKUP_FILE="$SCRIPT_DIR/.terraform.tfvars.pre-bootstrap.bak"

required_commands=("aws")

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

delete_all_object_versions() {
  local bucket="$1"
  local had_entries=0

  while IFS=$'\t' read -r key version_id; do
    [[ -z "$key" || -z "$version_id" || "$key" == "None" || "$version_id" == "None" ]] && continue
    had_entries=1
    aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" >/dev/null
  done < <(aws s3api list-object-versions \
    --bucket "$bucket" \
    --query 'Versions[].[Key,VersionId]' \
    --output text 2>/dev/null || true)

  while IFS=$'\t' read -r key version_id; do
    [[ -z "$key" || -z "$version_id" || "$key" == "None" || "$version_id" == "None" ]] && continue
    had_entries=1
    aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" >/dev/null
  done < <(aws s3api list-object-versions \
    --bucket "$bucket" \
    --query 'DeleteMarkers[].[Key,VersionId]' \
    --output text 2>/dev/null || true)

  if [[ "$had_entries" -eq 1 ]]; then
    return 0
  fi
  return 1
}

force_delete_bucket() {
  local bucket="$1"

  if [[ -z "$bucket" || "$bucket" == YOUR_* || "$bucket" == *YOUR_* ]]; then
    echo "Skipping unresolved placeholder bucket: $bucket"
    return 0
  fi

  if ! aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    echo "Bucket does not exist or not accessible, skipping: $bucket"
    return 0
  fi

  echo "Cleaning bucket: $bucket"

  # Remove current objects (for non-versioned or visible current versions).
  aws s3 rm "s3://$bucket" --recursive >/dev/null 2>&1 || true

  # Remove all historical versions and delete markers if bucket is versioned.
  local keep_cleaning=1
  while [[ "$keep_cleaning" -eq 1 ]]; do
    keep_cleaning=0
    if delete_all_object_versions "$bucket"; then
      keep_cleaning=1
    fi
  done

  # Finally delete bucket.
  aws s3api delete-bucket --bucket "$bucket" >/dev/null
  echo "Deleted bucket: $bucket"
}

echo "==> Checking AWS credentials..."
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured or expired."
  echo "Run: aws configure"
  exit 1
fi

BACKEND_BUCKET_RAW="${BACKEND_BUCKET:-$(read_tf_string_value "backend_bucket_name" "$TFVARS_FILE")}"
if [[ -z "$BACKEND_BUCKET_RAW" ]]; then
  BACKEND_BUCKET_RAW="$(read_tf_string_value "bucket" "$BACKEND_FILE")"
fi
VELERO_ARN_RAW="${VELERO_BUCKET_ARN:-$(read_tf_string_value "velero_backup_bucket_arn" "$TFVARS_FILE")}"
CNPG_ARN_RAW="${CNPG_BUCKET_ARN:-$(read_tf_string_value "cnpg_backup_bucket_arn" "$TFVARS_FILE")}"

BACKEND_BUCKET_NAME="$(extract_bucket_name_from_arn_or_name "$BACKEND_BUCKET_RAW")"
VELERO_BUCKET_NAME="$(extract_bucket_name_from_arn_or_name "$VELERO_ARN_RAW")"
CNPG_BUCKET_NAME="$(extract_bucket_name_from_arn_or_name "$CNPG_ARN_RAW")"

echo "==> Buckets to delete:"
echo " - Backend state : $BACKEND_BUCKET_NAME"
echo " - Velero backup : $VELERO_BUCKET_NAME"
echo " - CNPG backup   : $CNPG_BUCKET_NAME"
echo
echo "IMPORTANT: Make sure you already ran 'terraform destroy'."
read -r -p "Type 'yes' to continue deleting these buckets: " confirm

if [[ "$confirm" != "yes" ]]; then
  echo "Cancelled."
  exit 0
fi

force_delete_bucket "$VELERO_BUCKET_NAME"
force_delete_bucket "$CNPG_BUCKET_NAME"
force_delete_bucket "$BACKEND_BUCKET_NAME"

if [[ -f "$TFVARS_BACKUP_FILE" ]]; then
  mv "$TFVARS_BACKUP_FILE" "$TFVARS_FILE"
  echo "Restored terraform.tfvars to its pre-bootstrap state."
else
  echo "No backup file found at: $TFVARS_BACKUP_FILE"
  echo "Skipped terraform.tfvars restore."
fi

echo "Cleanup completed."
