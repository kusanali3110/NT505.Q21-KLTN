#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TF_DIR="$REPO_ROOT/terraform"
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

if [[ ! -d "$VALUES_DIR" ]]; then
  echo "ERROR: values directory not found: $VALUES_DIR"
  exit 1
fi

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
  exit 1
}

echo "==> Reading IRSA role ARNs from Terraform outputs..."
CNPG_ROLE_ARN="$(read_terraform_output "cnpg_role_arn")"
EXTERNAL_SECRETS_OPERATOR_ROLE_ARN="$(read_terraform_output "external_secrets_operator_role_arn")"

echo "==> Patching placeholders in values files..."
python - "$VALUES_DIR" "$CNPG_ROLE_ARN" "$EXTERNAL_SECRETS_OPERATOR_ROLE_ARN" <<'PY'
import sys
from pathlib import Path

values_dir = Path(sys.argv[1])
cnpg = sys.argv[2]
ext = sys.argv[3]

placeholders = {
  "__CNPG_ROLE_ARN__": cnpg,
  "__EXTERNAL_SECRETS_OPERATOR_ROLE_ARN__": ext,
}

for p in sorted(values_dir.glob("*.yaml")):
  txt = p.read_text(encoding="utf-8")
  for k, v in placeholders.items():
    txt = txt.replace(k, v)
  p.write_text(txt, encoding="utf-8")
print("Done.")
PY

echo "==> Adding/updating Helm repositories..."
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo add traefik https://helm.traefik.io/traefik >/dev/null 2>&1 || true
helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
helm repo add longhorn https://charts.longhorn.io >/dev/null 2>&1 || true
helm repo add external-secrets https://charts.external-secrets.io >/dev/null 2>&1 || true
helm repo add cnpg https://cloudnative-pg.github.io/charts >/dev/null 2>&1 || true
helm repo update >/dev/null 2>&1 || true

echo "==> Installing core platform components via Helm..."

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  -f "$VALUES_DIR/cert-manager-values.yaml"

helm upgrade --install traefik traefik/traefik \
  --namespace traefik --create-namespace \
  -f "$VALUES_DIR/traefik-values.yaml"

helm upgrade --install longhorn longhorn/longhorn \
  --namespace longhorn-system --create-namespace \
  -f "$VALUES_DIR/longhorn-values.yaml"

helm upgrade --install external-secrets-operator external-secrets/external-secrets \
  --namespace kube-system --create-namespace \
  -f "$VALUES_DIR/external-secrets-operator-values.yaml"

helm upgrade --install cnpg cnpg/cloudnative-pg \
  --namespace postgres --create-namespace \
  -f "$VALUES_DIR/cnpg-values.yaml"

helm upgrade --install plugin-barman-cloud cnpg/plugin-barman-cloud \
  --namespace postgres --create-namespace \
  -f "$VALUES_DIR/plugin-barman-cloud-values.yaml"

echo "==> Installing ArgoCD via Helm..."
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \

echo "==> Checking releases..."
helm list -A

echo "Done."
