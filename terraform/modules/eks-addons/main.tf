# ==========================================
# Cluster Autoscaler
# ==========================================
module "cluster_autoscaler_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_cluster_autoscaler ? 1 : 0

  role_name = "${var.eks_cluster_name}-ClusterAutoscalerRole"

  attach_cluster_autoscaler_policy = true

  cluster_autoscaler_cluster_names = [var.eks_cluster_name]

  oidc_providers = {
    main = {
      provider_arn               = var.eks_cluster_oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }
}

resource "helm_release" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  name             = "cluster-autoscaler"
  repository       = "https://kubernetes.github.io/autoscaler"
  chart            = "cluster-autoscaler"
  namespace        = "kube-system"
  create_namespace = true

  depends_on = [module.cluster_autoscaler_irsa]

  set = [
    {
      name  = "autoDiscovery.clusterName"
      value = var.eks_cluster_name
    },
    {
      name  = "awsRegion"
      value = var.aws_region
    },
    {
      name  = "rbac.serviceAccount.name"
      value = "cluster-autoscaler"
    },
    {
      name  = "rbac.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = module.cluster_autoscaler_irsa[0].iam_role_arn
    },
    {
      name  = "extraArgs.balance-similar-node-groups"
      value = true
    }
  ]
}

# ==========================================
# Metrics Server
# ==========================================
resource "helm_release" "metrics_server" {
  count = var.enable_metrics_server ? 1 : 0

  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  namespace  = "kube-system"
}

# ==========================================
# CloudNative PostgreSQL
# ==========================================
# CloudNative PostgreSQL S3 Policy
resource "aws_iam_policy" "cnpg_backup_s3" {
  count = var.enable_cloudnative_postgresql ? 1 : 0

  name        = "${var.eks_cluster_name}-cnpg-s3-policy"
  description = "Policy for cnpg to create backup and snapshot"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ],
        Resource = [
          "${var.cnpg_backup_bucket_arn}"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload"
        ],
        Resource = [
          "${var.cnpg_backup_bucket_arn}/*"
        ]
      }
    ]
  })
}

# CloudNative PostgreSQL IRSA
module "cnpg_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_cloudnative_postgresql ? 1 : 0

  role_name = "${var.eks_cluster_name}-CNPGRole"

  role_policy_arns = {
    cnpg_s3 = aws_iam_policy.cnpg_backup_s3[0].arn
  }

  oidc_providers = {
    main = {
      provider_arn               = var.eks_cluster_oidc_provider_arn
      namespace_service_accounts = ["postgres:postgres-cluster"]
    }
  }
}

# ==========================================
# External Secrets Operator
# ==========================================
# IAM Policy for External Secrets Operator
resource "aws_iam_policy" "external_secrets_operator" {
  count = var.enable_external_secrets_operator ? 1 : 0

  name = "${var.eks_cluster_name}-external-secrets-operator-policy"
  description = "Policy for external secrets operator"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecretVersionIds"
        ],
        # Lab-friendly: allow operator to read any secret.
        # If you want least privilege, replace with a scoped list of secret ARNs.
        Resource = ["*"]
      }
    ]
  })
}

# External Secrets Operator IRSA
module "external_secrets_operator_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_external_secrets_operator ? 1 : 0

  role_name = "${var.eks_cluster_name}-ExternalSecretsOperatorRole"
  role_policy_arns = {
    external_secrets_operator = aws_iam_policy.external_secrets_operator[0].arn
  }

  oidc_providers = {
    main = {
      provider_arn               = var.eks_cluster_oidc_provider_arn
      namespace_service_accounts = ["kube-system:external-secrets-operator"]
    }
  }
}