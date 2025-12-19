# IAM Roles et Policies pour le Chatbot
# ====================================

# Rôle pour les fonctions Lambda
resource "aws_iam_role" "lambda_execution_role" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy pour Lambda - Logs CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Policy personnalisée pour Lambda
resource "aws_iam_role_policy" "lambda_chatbot_policy" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "comprehendmedical:DetectEntitiesV2",
          "comprehendmedical:InferICD10CM",
          "comprehendmedical:InferRxNorm",
          "comprehendmedical:DetectPHI"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "polly:SynthesizeSpeech"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:DescribeStream",
          "kinesis:ListStreams"
        ]
        Resource = "arn:aws:kinesis:${local.region}:${local.account_id}:stream/kidjamo-*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.conversation_history.arn,
          aws_dynamodb_table.patient_context.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.medical_alerts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.chatbot_encryption.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kendra:Query",
          "kendra:DescribeIndex",
          "kendra:ListDataSources"
        ]
        Resource = "arn:aws:kendra:${local.region}:${local.account_id}:index/*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      }
    ]
  })
}

# Rôle pour Amazon Lex
resource "aws_iam_role" "lex_execution_role" {
  name = "${local.name_prefix}-lex-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lexv2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lex_chatbot_policy" {
  name = "${local.name_prefix}-lex-policy"
  role = aws_iam_role.lex_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "${aws_lambda_function.lex_fulfillment.arn}*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:*"
      }
    ]
  })
}
