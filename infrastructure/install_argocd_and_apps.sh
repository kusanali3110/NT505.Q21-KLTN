#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TF_DIR="$REPO_ROOT/terraform"
APPS_DIR="$REPO_ROOT/infrastructure/apps"
VALUES_DIR="$REPO_ROOT/infrastructure/values"

required_commands=("kubectl" "helm" "terraform" "python")

check_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing dependency: $cmd"
    exit 1
  fi
}

for cmd in "${required_commands[@]}"; do
  check_command "$cmd"
done

read_terraform_output() {
  local output_name="$1"
  local out_file err_file
  out_file="$(mktemp)"
  err_file="$(mktemp)"

  if terraform -chdir="$TF_DIR" output -raw "$output_name" >"$out_file" 2>"$err_file"; then
    local value
    value="$(tr -d '\r' < "$out_file")"
    rm -f "$out_file" "$err_file"
    if [[ -z "$value" || "$value" == "null" ]]; then
      echo "ERROR: terraform output '$output_name' is empty/null." >&2
      echo "Hint: ensure 'terraform apply' completed successfully in $TF_DIR." >&2
      exit 1
    fi
    printf '%s' "$value"
    return 0
  fi

  echo "ERROR: failed to read terraform output '$output_name'." >&2
  echo "Terraform error details:" >&2
  cat "$err_file" >&2
  rm -f "$out_file" "$err_file"
  echo >&2
  echo "Try running these commands first:" >&2
  echo "  cd \"$TF_DIR\"" >&2
  echo "  terraform init -reconfigure -backend-config=\"bucket=<your_state_bucket>\" -backend-config=\"key=<your_state_key>\" -backend-config=\"region=<your_region>\" -backend-config=\"encrypt=true\"" >&2
  echo "  terraform output" >&2
  exit 1
}

if [[ ! -d "$APPS_DIR" ]]; then
  echo "ERROR: apps directory not found: $APPS_DIR"
  exit 1
fi

if [[ ! -d "$VALUES_DIR" ]]; then
  echo "ERROR: values directory not found: $VALUES_DIR"
  exit 1
fi

echo "==> Installing/Upgrading ArgoCD via Helm..."

helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update >/dev/null 2>&1 || true

helm upgrade --install argocd argo/argo-cd \
  -n argocd --create-namespace \
  --set server.service.type=LoadBalancer

echo "==> Waiting for ArgoCD components..."
kubectl rollout status deployment/argocd-server -n argocd --timeout=300s

echo "==> Reading IRSA role ARNs from Terraform outputs..."
CNPG_ROLE_ARN="$(read_terraform_output "cnpg_role_arn")"
EXTERNAL_SECRETS_OPERATOR_ROLE_ARN="$(read_terraform_output "external_secrets_operator_role_arn")"

echo "==> Patching placeholders in app/value YAMLs..."
python - "$APPS_DIR" "$VALUES_DIR" "$CNPG_ROLE_ARN" "$EXTERNAL_SECRETS_OPERATOR_ROLE_ARN" <<'PY'
import sys
from pathlib import Path

apps_dir = Path(sys.argv[1])
values_dir = Path(sys.argv[2])
cnpg = sys.argv[3]
ext = sys.argv[4]

placeholders = {
  "__CNPG_ROLE_ARN__": cnpg,
  "__EXTERNAL_SECRETS_OPERATOR_ROLE_ARN__": ext,
}

for root in (apps_dir, values_dir):
  for p in sorted(root.glob("*.yaml")):
    txt = p.read_text(encoding="utf-8")
    for k, v in placeholders.items():
      txt = txt.replace(k, v)
    p.write_text(txt, encoding="utf-8")

print("Done.")
PY

echo "==> Applying ArgoCD Applications..."
kubectl apply -f "$APPS_DIR"

echo "Done."
echo "You can watch sync status with:"
echo "  kubectl get applications -n argocd"

