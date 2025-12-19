# Configuration Amazon Kendra pour le Chatbot Kidjamo
# ===================================================

# Rôle IAM pour Amazon Kendra
resource "aws_iam_role" "kendra_role" {
  name = "${local.name_prefix}-kendra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "kendra.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-kendra-role"
  }
}

# Policy pour Kendra - CloudWatch et S3
resource "aws_iam_role_policy_attachment" "kendra_cloudwatch_logs" {
  role       = aws_iam_role.kendra_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# Policy personnalisée pour Kendra
resource "aws_iam_role_policy" "kendra_policy" {
  name = "${local.name_prefix}-kendra-policy"
  role = aws_iam_role.kendra_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.kendra_documents.arn,
          "${aws_s3_bucket.kendra_documents.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.chatbot_encryption.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Bucket S3 pour les documents Kendra
resource "aws_s3_bucket" "kendra_documents" {
  bucket = "${local.name_prefix}-documents-${random_string.kendra_suffix.result}"

  tags = {
    Name = "${local.name_prefix}-kendra-documents"
  }
}

resource "random_string" "kendra_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kendra_documents" {
  bucket = aws_s3_bucket.kendra_documents.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.chatbot_encryption.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "kendra_documents" {
  bucket = aws_s3_bucket.kendra_documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "kendra_documents" {
  bucket = aws_s3_bucket.kendra_documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload de documents de test avec noms propres
resource "aws_s3_object" "test_guide_drepanocytose" {
  bucket = aws_s3_bucket.kendra_documents.bucket
  key    = "test/guide_drepanocytose_simple.md"
  source = "./guide_drepanocytose.md"

  server_side_encryption = "aws:kms"
  kms_key_id            = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "Guide Drepanocytose Test"
    Type = "Medical Guide"
  }
}

# Document de test basique
resource "aws_s3_object" "test_medical_basic" {
  bucket = aws_s3_bucket.kendra_documents.bucket
  key    = "test/medical_basic_info.txt"
  content = <<-EOT
GUIDE MEDICAL DREPANOCYTOSE

La drepanocytose est une maladie genetique hereditaire.

SYMPTOMES PRINCIPAUX:
- Douleurs dans les os et articulations
- Fatigue chronique due a l'anemie
- Infections frequentes
- Crises vaso-occlusives douloureuses

TRAITEMENTS DISPONIBLES:
- Hydroxyuree pour reduire les crises
- Transfusions sanguines si necessaire
- Gestion de la douleur avec analgesiques
- Prevention des infections

URGENCES MEDICALES:
En cas de fievre elevee, douleurs thoraciques ou difficultes respiratoires, consulter immediatement un medecin.

PREVENTION:
- Maintenir une bonne hydratation
- Eviter le stress et les changements de temperature
- Suivre le traitement medical prescrit
EOT

  server_side_encryption = "aws:kms"
  kms_key_id            = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "Medical Basic Info"
    Type = "Medical Text"
  }
}

# Index Amazon Kendra
resource "aws_kendra_index" "medical_knowledge" {
  name        = "${local.name_prefix}-medical-knowledge"
  description = "Base de connaissances médicales pour la drépanocytose - Kidjamo"
  edition     = "DEVELOPER_EDITION"
  role_arn    = aws_iam_role.kendra_role.arn

  # Configuration sans restriction d'utilisateur
  # user_context_policy supprimé pour permettre l'accès libre

  document_metadata_configuration_updates {
    name = "category"
    type = "STRING_VALUE"
    search {
      displayable = true
      facetable   = true
      searchable  = true
      sortable    = false
    }
  }

  document_metadata_configuration_updates {
    name = "document_type"
    type = "STRING_VALUE"
    search {
      displayable = true
      facetable   = true
      searchable  = true
      sortable    = false
    }
  }

  document_metadata_configuration_updates {
    name = "medical_specialty"
    type = "STRING_VALUE"
    search {
      displayable = true
      facetable   = true
      searchable  = true
      sortable    = false
    }
  }

  document_metadata_configuration_updates {
    name = "last_updated"
    type = "DATE_VALUE"
    search {
      displayable = true
      facetable   = false
      searchable  = false
      sortable    = true
    }
  }

  document_metadata_configuration_updates {
    name = "author"
    type = "STRING_VALUE"
    search {
      displayable = true
      facetable   = false
      searchable  = true
      sortable    = false
    }
  }

  server_side_encryption_configuration {
    kms_key_id = aws_kms_key.chatbot_encryption.arn
  }

  tags = {
    Name = "${local.name_prefix}-medical-knowledge"
  }
}

# Source de données S3 pour Kendra
resource "aws_kendra_data_source" "s3_medical_docs" {
  index_id     = aws_kendra_index.medical_knowledge.id
  name         = "medical-documents-s3"
  type         = "S3"
  role_arn     = aws_iam_role.kendra_role.arn
  language_code = "fr"  # Configuration française pour vos documents

  configuration {
    s3_configuration {
      bucket_name = aws_s3_bucket.kendra_documents.bucket

      inclusion_patterns = [
        "medical/*.pdf",
        "medical/*.docx",
        "medical/*.txt",
        "medical/*.html",
        "medical/*.md",
        "test/*.pdf",
        "test/*.docx",
        "test/*.txt",
        "test/*.html",
        "test/*.md"
      ]

      exclusion_patterns = [
        "*/.DS_Store",
        "*/Thumbs.db",
        "*/.git/*",
        "*.csv",
        "faq/*",
        "**/*()*",  # Exclure fichiers avec parenthèses
        "**/*–*",   # Exclure fichiers avec tirets spéciaux
        "**/*__*"   # Exclure fichiers avec double underscores
      ]

      documents_metadata_configuration {
        s3_prefix = "metadata/"
      }
    }
  }

  description = "Documents médicaux français stockés dans S3"
  schedule    = "cron(0 2 * * ? *)" # Synchronisation quotidienne à 2h du matin

  tags = {
    Name = "${local.name_prefix}-s3-medical-docs"
  }

  depends_on = [
    aws_s3_bucket.kendra_documents,
    aws_kendra_index.medical_knowledge
  ]
}

# Outputs
output "kendra_index_id" {
  description = "ID de l'index Amazon Kendra"
  value       = aws_kendra_index.medical_knowledge.id
}

output "kendra_index_arn" {
  description = "ARN de l'index Amazon Kendra"
  value       = aws_kendra_index.medical_knowledge.arn
}

output "kendra_documents_bucket" {
  description = "Bucket S3 pour les documents Kendra"
  value       = aws_s3_bucket.kendra_documents.bucket
}

output "kendra_index_status" {
  description = "Statut de l'index Kendra"
  value       = aws_kendra_index.medical_knowledge.status
}
