# Ressources de stockage et sécurité pour le Chatbot
# ==================================================

# Clé KMS pour le chiffrement des données sensibles
resource "aws_kms_key" "chatbot_encryption" {
  description             = "KMS key for chatbot encryption"
  deletion_window_in_days = 7

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow use of the key for chatbot services"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.lambda_execution_role.arn,
            aws_iam_role.lex_execution_role.arn
          ]
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/lambda/${local.name_prefix}-*"
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "chatbot_encryption" {
  name          = "alias/${local.name_prefix}-encryption"
  target_key_id = aws_kms_key.chatbot_encryption.key_id
}

# Table DynamoDB pour l'historique des conversations
resource "aws_dynamodb_table" "conversation_history" {
  name           = "${local.name_prefix}-conversations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "conversation_id"
  range_key      = "timestamp"

  attribute {
    name = "conversation_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name               = "user-index"
    hash_key           = "user_id"
    range_key          = "timestamp"
    projection_type    = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.chatbot_encryption.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "${local.name_prefix}-conversations"
  }
}

# Table DynamoDB pour le contexte patient
resource "aws_dynamodb_table" "patient_context" {
  name         = "${local.name_prefix}-patient-context"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "patient_id"

  attribute {
    name = "patient_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.chatbot_encryption.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${local.name_prefix}-patient-context"
  }
}

# Topic SNS pour les alertes médicales
resource "aws_sns_topic" "medical_alerts" {
  name         = "${local.name_prefix}-medical-alerts"
  display_name = "Kidjamo Medical Alerts"

  kms_master_key_id = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-medical-alerts"
  }
}

# Topic SNS pour les notifications patients
resource "aws_sns_topic" "patient_notifications" {
  name         = "${local.name_prefix}-patient-notifications"
  display_name = "Kidjamo Patient Notifications"

  kms_master_key_id = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-patient-notifications"
  }
}

# Bucket S3 pour les logs et données temporaires du chatbot
resource "aws_s3_bucket" "chatbot_data" {
  bucket = "${local.name_prefix}-data-${random_string.bucket_suffix.result}"

  tags = {
    Name = "${local.name_prefix}-data"
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "chatbot_data" {
  bucket = aws_s3_bucket.chatbot_data.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.chatbot_encryption.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "chatbot_data" {
  bucket = aws_s3_bucket.chatbot_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "chatbot_data" {
  bucket = aws_s3_bucket.chatbot_data.id

  rule {
    id     = "logs_lifecycle"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
