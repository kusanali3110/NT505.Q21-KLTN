# ==========================================
# AWS Load Balancer Controller
# ==========================================
module "aws_load_balancer_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_aws_load_balancer_controller ? 1 : 0

  role_name = "${var.eks_cluster_name}-AWSLoadBalancerControllerRole"

  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = var.eks_cluster_oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  count = var.enable_aws_load_balancer_controller ? 1 : 0

  name             = "aws-load-balancer-controller"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  namespace        = "kube-system"
  create_namespace = true
  depends_on       = [module.aws_load_balancer_controller_irsa]

  set = [
    {
      name  = "region"
      value = var.aws_region
    },
    {
      name  = "vpcId"
      value = var.vpc_id
    },
    {
      name  = "clusterName"
      value = var.eks_cluster_name
    },
    {
      name  = "serviceAccount.create"
      value = true
    },
    {
      name  = "serviceAccount.name"
      value = "aws-load-balancer-controller"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = module.aws_load_balancer_controller_irsa[0].iam_role_arn
    }
  ]
}

# ==========================================
# Cert Manager
# ==========================================
resource "helm_release" "cert_manager" {
  count = var.enable_cert_manager ? 1 : 0

  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  depends_on = [helm_release.aws_load_balancer_controller]
  
  set = [
    {
      name  = "installCRDs"
      value = true
    }
  ]
}

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
# Velero
# ==========================================
# Velero S3 Policy
resource "aws_iam_policy" "velero_s3" {
  count = var.enable_velero ? 1 : 0

  name        = "${var.eks_cluster_name}-velero-s3-policy"
  description = "Policy for velero to create backup and snapshot"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        Resource = [
          "${var.velero_backup_bucket_arn}",
          "${var.velero_backup_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:CreateTags",
          "ec2:CreateVolume",
          "ec2:CreateSnapshot",
          "ec2:DeleteSnapshot",
          "ec2:DescribeImageAttribute",
          "ec2:DescribeImages",
          "ec2:DescribeKeyPairs",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs",
          "ec2:DescribeInstances",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploads"
        ],
        Resource = ["*"]
      },
    ]
  })
}

# Velero IRSA
module "velero_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_velero ? 1 : 0

  role_name = "${var.eks_cluster_name}-VeleroRole"

  role_policy_arns = {
    velero_s3 = aws_iam_policy.velero_s3[0].arn
  }

  oidc_providers = {
    main = {
      provider_arn               = var.eks_cluster_oidc_provider_arn
      namespace_service_accounts = ["velero:velero-server"]
    }
  }
}

# Install Velero
resource "helm_release" "velero" {
  count = var.enable_velero ? 1 : 0

  name             = "velero"
  repository       = "https://vmware-tanzu.github.io/helm-charts"
  chart            = "velero"
  namespace        = "velero"
  create_namespace = true
  depends_on       = [
    module.velero_irsa,
    helm_release.aws_load_balancer_controller
  ]

  values = [
    yamlencode({
      configuration = {
        backupStorageLocation = [
          {
            name     = var.velero_backup_storage_location_name
            provider = "aws"
            bucket   = split(":", var.velero_backup_bucket_arn)[length(split(":", var.velero_backup_bucket_arn)) - 1]
            config = {
              region = var.aws_region
              s3ForcePathStyle = true
            }
          }
        ]
        volumeSnapshotLocation = [
          {
            name     = var.velero_volume_snapshot_location_name
            provider = "aws"
            config = {
              region = var.aws_region
            }
          }
        ]
      }
      serviceAccount = {
        server = {
          create = true
          annotations = {
            "eks.amazonaws.com/role-arn" = module.velero_irsa[0].iam_role_arn
          }
        }
      }
      credentials = {
        useSecret = false
      }
      useVolumeSnapshot = true
    })
  ]
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

# Install CloudNative PostgreSQL
resource "helm_release" "cnpg" {
  count = var.enable_cloudnative_postgresql ? 1 : 0

  name             = "cnpg"
  repository       = "https://cloudnative-pg.github.io/charts"
  chart            = "cloudnative-pg"
  namespace        = "postgres"
  create_namespace = true
  depends_on       = [module.cnpg_irsa, helm_release.aws_load_balancer_controller]
}

# Install Plugin Barman Cloud
resource "helm_release" "plugin_barman_cloud" {
  count = var.enable_cloudnative_postgresql ? 1 : 0

  name             = "plugin-barman-cloud"
  repository       = "https://cloudnative-pg.github.io/charts"
  chart            = "plugin-barman-cloud"
  namespace        = "postgres"
  create_namespace = true
  depends_on       = [module.cnpg_irsa, helm_release.cert_manager]
}

# ==========================================
# External Secrets Operator
# ==========================================
# AWS Secrets Manager for EKS
resource "aws_secretsmanager_secret" "aws_secrets_manager_for_eks" {
  count = var.enable_external_secrets_operator ? 1 : 0

  name = "${var.eks_cluster_name}-external-secrets-operator"
  description = "External Secrets Operator for EKS"
  recovery_window_in_days = 7
}

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
        Resource = [
          "${aws_secretsmanager_secret.aws_secrets_manager_for_eks[0].arn}"
        ]
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

# Install External Secrets Operator
resource "helm_release" "external_secrets_operator" {
  count = var.enable_external_secrets_operator ? 1 : 0

  name             = "external-secrets-operator"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "kube-system"

  depends_on       = [
    module.external_secrets_operator_irsa,
    helm_release.aws_load_balancer_controller
  ]

  values = [
    yamlencode({
      serviceAccount = {
        name = "external-secrets-operator"
        annotations = {
          "eks.amazonaws.com/role-arn" = module.external_secrets_operator_irsa[0].iam_role_arn
        }
      }
    })
  ]
}