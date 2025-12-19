terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "Région AWS"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Nom du projet"
  type        = string
  default     = "kidjamo"
}

variable "environment" {
  description = "Environnement (dev/staging/prod)"
  type        = string
  default     = "dev"
}

# =====================================================
# AWS IoT Core - Configuration pour vos bracelets
# =====================================================

# Policy IoT pour vos bracelets
resource "aws_iot_policy" "bracelet_policy" {
  name = "${var.project_name}-bracelet-policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iot:Connect"
        ]
        Resource = "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:client/kidjamo-bracelet-*"
      },
      {
        Effect = "Allow"
        Action = [
          "iot:Publish"
        ]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/kidjamo/bracelet/*/vitals",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/kidjamo/bracelet/*/accelerometer",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/kidjamo/bracelet/*/status",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/kidjamo/bracelet/*/alerts"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iot:Subscribe",
          "iot:Receive"
        ]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/kidjamo/bracelet/*/vitals",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/kidjamo/bracelet/*/accelerometer",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/kidjamo/bracelet/*/status",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/kidjamo/bracelet/*/alerts"
        ]
      }
    ]
  })
}

# Certificat pour le connecteur principal
resource "aws_iot_certificate" "connector_cert" {
  active = true
}

# Attacher la policy au certificat
resource "aws_iot_policy_attachment" "connector_attachment" {
  policy = aws_iot_policy.bracelet_policy.name
  target = aws_iot_certificate.connector_cert.arn
}

# =====================================================
# Kinesis Data Streams - Pour le streaming temps réel
# =====================================================

resource "aws_kinesis_stream" "iot_stream" {
  name             = "${var.project_name}-iot-stream-${var.environment}"
  shard_count      = 2  # Ajustez selon votre volume
  retention_period = 24  # 24 heures de rétention

  shard_level_metrics = [
    "IncomingRecords",
    "OutgoingRecords"
  ]

  tags = {
    Name        = "${var.project_name}-iot-stream"
    Environment = var.environment
    Purpose     = "bracelet-iot-streaming"
  }
}

# =====================================================
# IoT Rules - Routage MQTT → Kinesis + S3 Direct
# =====================================================

# Rôle pour la règle IoT
resource "aws_iam_role" "iot_kinesis_role" {
  name = "${var.project_name}-iot-kinesis-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
      }
    ]
  })
}

# Policy pour écrire dans Kinesis
resource "aws_iam_role_policy" "iot_kinesis_policy" {
  name = "${var.project_name}-iot-kinesis-policy"
  role = aws_iam_role.iot_kinesis_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords"
        ]
        Resource = aws_kinesis_stream.iot_stream.arn
      }
    ]
  })
}

# Rôle IAM pour écrire directement dans S3
resource "aws_iam_role" "iot_s3_role" {
  name = "${var.project_name}-iot-s3-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
      }
    ]
  })
}

# Policy pour écrire dans S3
resource "aws_iam_role_policy" "iot_s3_policy" {
  name = "${var.project_name}-iot-s3-policy"
  role = aws_iam_role.iot_s3_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "arn:aws:s3:::kidjamo-dev-datalake-e75d5213/*"
      }
    ]
  })
}

# Règle IoT pour topic sdk/test/java (votre Arduino)
resource "aws_iot_topic_rule" "mpu_christian_sdk_java" {
  name        = "mpu_christian_sdk_java_rule"
  description = "Route données MPU Christian depuis topic sdk/test/java vers Kinesis et S3"
  enabled     = true

  # SQL pour filtrer et transformer les données
  sql = "SELECT *, timestamp() as aws_timestamp, 'MPU_Christian_8266MOD' as device_id FROM 'sdk/test/java'"
  sql_version = "2016-03-23"

  # Action 1: Envoyer vers Kinesis pour streaming temps réel
  kinesis {
    role_arn      = aws_iam_role.iot_kinesis_role.arn
    stream_name   = aws_kinesis_stream.iot_stream.name
    partition_key = "mpu_christian_$${newuuid()}"
  }

  # Action 2: CORRIGÉ - Envoyer directement vers S3 Raw avec timestamps dynamiques
  s3 {
    role_arn   = aws_iam_role.iot_s3_role.arn
    bucket_name = "kidjamo-dev-datalake-e75d5213"
    # CORRECTION: Utiliser des fonctions de date dynamiques au lieu de valeurs codées en dur
    key        = "raw/iot-measurements/year=$${parse_time(\"yyyy\", timestamp())}/month=$${parse_time(\"MM\", timestamp())}/day=$${parse_time(\"dd\", timestamp())}/hour=$${parse_time(\"HH\", timestamp())}/mpu_christian_$${timestamp()}.json"
  }

  tags = {
    Name        = "MPU Christian SDK Java Topic Rule"
    Environment = var.environment
    Device      = "MPU_Christian_8266MOD"
    Topic       = "sdk/test/java"
  }
}

# Policy IoT mise à jour pour le topic sdk/test/java
resource "aws_iot_policy" "bracelet_sdk_java_policy" {
  name = "${var.project_name}-bracelet-sdk-java-policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iot:Connect"
        ]
        Resource = "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:client/MPU_Christian_8266MOD"
      },
      {
        Effect = "Allow"
        Action = [
          "iot:Publish"
        ]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/sdk/test/java"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iot:Subscribe",
          "iot:Receive"
        ]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/sdk/test/java"
        ]
      }
    ]
  })
}

# =====================================================
# CloudWatch - Monitoring et logs
# =====================================================

resource "aws_cloudwatch_log_group" "iot_errors" {
  name              = "/aws/iot/${var.project_name}-bracelet-errors-${var.environment}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "connector_logs" {
  name              = "/aws/iot/${var.project_name}-bracelet-connector-${var.environment}"
  retention_in_days = 7
}

# Rôle pour les logs CloudWatch
resource "aws_iam_role" "iot_logs_role" {
  name = "${var.project_name}-iot-logs-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "iot_logs_policy" {
  name = "${var.project_name}-iot-logs-policy"
  role = aws_iam_role.iot_logs_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# =====================================================
# Outputs - Informations importantes
# =====================================================

data "aws_caller_identity" "current" {}

output "iot_endpoint" {
  description = "AWS IoT Core endpoint"
  value       = data.aws_iot_endpoint.endpoint.endpoint_address
}

output "certificate_arn" {
  description = "ARN du certificat du connecteur"
  value       = aws_iot_certificate.connector_cert.arn
}

output "certificate_pem" {
  description = "Certificat PEM (à sauvegarder)"
  value       = aws_iot_certificate.connector_cert.certificate_pem
  sensitive   = true
}

output "private_key" {
  description = "Clé privée (à sauvegarder)"
  value       = aws_iot_certificate.connector_cert.private_key
  sensitive   = true
}

output "kinesis_stream_name" {
  description = "Nom du stream Kinesis"
  value       = aws_kinesis_stream.iot_stream.name
}

output "kinesis_stream_arn" {
  description = "ARN du stream Kinesis"
  value       = aws_kinesis_stream.iot_stream.arn
}

output "sdk_java_topic_rule_arn" {
  description = "ARN de la règle IoT pour le topic sdk/test/java"
  value       = aws_iot_topic_rule.mpu_christian_sdk_java.arn
}

data "aws_iot_endpoint" "endpoint" {
  endpoint_type = "iot:Data-ATS"
}
