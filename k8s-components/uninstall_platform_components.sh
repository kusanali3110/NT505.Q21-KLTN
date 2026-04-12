#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TF_DIR="$REPO_ROOT/terraform"
VALUES_DIR="$REPO_ROOT/k8s-components/values"

required_commands=("helm" "kubectl" "python")

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

try_terraform_raw_output() {
  local output_name="$1"
  local out_file err_file value
  out_file="$(mktemp)"
  err_file="$(mktemp)"
  if terraform -chdir="$TF_DIR" output -raw "$output_name" >"$out_file" 2>"$err_file"; then
    value="$(tr -d '\r' < "$out_file")"
    rm -f "$out_file" "$err_file"
    if [[ -z "$value" || "$value" == "null" ]]; then
      printf ''
      return 0
    fi
    printf '%s' "$value"
    return 0
  fi
  rm -f "$out_file" "$err_file"
  printf ''
}

reset_values_placeholders() {
  if [[ ! -d "$VALUES_DIR" ]]; then
    echo "WARN: values directory not found, skip ARN placeholder reset: $VALUES_DIR" >&2
    return 0
  fi

  local cnpg_arn ext_arn
  cnpg_arn="$(try_terraform_raw_output "cnpg_role_arn")"
  ext_arn="$(try_terraform_raw_output "external_secrets_operator_role_arn")"

  if [[ -n "$cnpg_arn" ]]; then
    echo "==> Resetting IRSA ARNs in values (from terraform output)..."
  elif [[ -n "$ext_arn" ]]; then
    echo "==> Resetting IRSA ARNs in values (from terraform output)..."
  else
    echo "==> Resetting IRSA ARNs in values (terraform output unavailable; using pattern fallback)..."
  fi

  python - "$VALUES_DIR" "$cnpg_arn" "$ext_arn" <<'PY'
import sys
import re
from pathlib import Path

values_dir = Path(sys.argv[1])
cnpg_tf = sys.argv[2]
ext_tf = sys.argv[3]

# IAM role ARN (supports optional path segments after role/)
arn_re = re.compile(r"arn:aws:iam::\d+:role/[\w/+=,.@-]+")


def reset_file(path: Path, placeholder: str, tf_arn: str) -> None:
    if not path.is_file():
        return
    txt = path.read_text(encoding="utf-8")
    if tf_arn and tf_arn in txt:
        txt = txt.replace(tf_arn, placeholder)
    else:
        txt = arn_re.sub(placeholder, txt)
    path.write_text(txt, encoding="utf-8")


reset_file(values_dir / "cnpg-values.yaml", "__CNPG_ROLE_ARN__", cnpg_tf)
reset_file(values_dir / "plugin-barman-cloud-values.yaml", "__CNPG_ROLE_ARN__", cnpg_tf)
reset_file(
    values_dir / "external-secrets-operator-values.yaml",
    "__EXTERNAL_SECRETS_OPERATOR_ROLE_ARN__",
    ext_tf,
)
print("Values placeholders restored.")
PY
}

reset_values_placeholders

echo "==> Uninstalling platform components..."
kubectl delete ns postgres longhorn-system traefik cert-manager argocd --ignore-not-found

echo "Done."
