# Fonctions Lambda pour le Chatbot
# =================================

# Package ZIP pour la fonction Lambda principale
data "archive_file" "lex_fulfillment_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda/lex_fulfillment"
  output_path = "${path.module}/lex_fulfillment.zip"
}

# Fonction Lambda principale - Traitement des intentions Lex
resource "aws_lambda_function" "lex_fulfillment" {
  filename         = data.archive_file.lex_fulfillment_zip.output_path
  function_name    = "${local.name_prefix}-lex-fulfillment"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "main.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 512

  source_code_hash = data.archive_file.lex_fulfillment_zip.output_base64sha256

  environment {
    variables = {
      ENVIRONMENT                = var.environment
      CONVERSATION_TABLE         = aws_dynamodb_table.conversation_history.name
      PATIENT_CONTEXT_TABLE      = aws_dynamodb_table.patient_context.name
      MEDICAL_ALERTS_TOPIC       = aws_sns_topic.medical_alerts.arn
      PATIENT_NOTIFICATIONS_TOPIC = aws_sns_topic.patient_notifications.arn
      KMS_KEY_ID                 = aws_kms_key.chatbot_encryption.arn
      IOT_KINESIS_STREAM         = "kidjamo-${var.environment}-vitals-stream"
      POSTGRES_SECRET_ARN        = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:kidjamo/${var.environment}/postgres"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lex_fulfillment,
  ]

  tags = {
    Name = "${local.name_prefix}-lex-fulfillment"
  }
}

# Package ZIP pour la fonction de traitement médical NLP
data "archive_file" "medical_nlp_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda/medical_nlp"
  output_path = "${path.module}/medical_nlp.zip"
}

# Fonction Lambda - Traitement NLP médical avec Comprehend Medical
resource "aws_lambda_function" "medical_nlp" {
  filename         = data.archive_file.medical_nlp_zip.output_path
  function_name    = "${local.name_prefix}-medical-nlp"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "main.lambda_handler"
  runtime         = "python3.9"
  timeout         = 60
  memory_size     = 1024

  source_code_hash = data.archive_file.medical_nlp_zip.output_base64sha256

  environment {
    variables = {
      ENVIRONMENT           = var.environment
      KMS_KEY_ID           = aws_kms_key.chatbot_encryption.arn
      MEDICAL_ALERTS_TOPIC = aws_sns_topic.medical_alerts.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.medical_nlp,
  ]

  tags = {
    Name = "${local.name_prefix}-medical-nlp"
  }
}

# Package ZIP pour la fonction d'intégration IoT
data "archive_file" "iot_integration_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda/iot_integration"
  output_path = "${path.module}/iot_integration.zip"
}

# Fonction Lambda - Intégration avec le pipeline IoT
resource "aws_lambda_function" "iot_integration" {
  filename         = data.archive_file.iot_integration_zip.output_path
  function_name    = "${local.name_prefix}-iot-integration"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "main.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 256

  source_code_hash = data.archive_file.iot_integration_zip.output_base64sha256

  environment {
    variables = {
      ENVIRONMENT               = var.environment
      IOT_KINESIS_STREAM       = "kidjamo-${var.environment}-vitals-stream"
      PATIENT_CONTEXT_TABLE    = aws_dynamodb_table.patient_context.name
      KMS_KEY_ID               = aws_kms_key.chatbot_encryption.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.iot_integration,
  ]

  tags = {
    Name = "${local.name_prefix}-iot-integration"
  }
}

# Package ZIP pour la fonction de conversation générale
data "archive_file" "general_conversation_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda/general_conversation"
  output_path = "${path.module}/general_conversation.zip"
}

# Fonction Lambda - Conversation générale intelligente
resource "aws_lambda_function" "general_conversation" {
  filename         = data.archive_file.general_conversation_zip.output_path
  function_name    = "${local.name_prefix}-general-conversation"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "main.lambda_handler"
  runtime         = "python3.9"
  timeout         = 45
  memory_size     = 1024

  source_code_hash = data.archive_file.general_conversation_zip.output_base64sha256

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      KMS_KEY_ID     = aws_kms_key.chatbot_encryption.arn
      KENDRA_INDEX_ID = var.kendra_index_id
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.general_conversation,
  ]

  tags = {
    Name = "${local.name_prefix}-general-conversation"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "lex_fulfillment" {
  name              = "/aws/lambda/${local.name_prefix}-lex-fulfillment"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-lex-fulfillment-logs"
  }
}

resource "aws_cloudwatch_log_group" "medical_nlp" {
  name              = "/aws/lambda/${local.name_prefix}-medical-nlp"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-medical-nlp-logs"
  }
}

resource "aws_cloudwatch_log_group" "iot_integration" {
  name              = "/aws/lambda/${local.name_prefix}-iot-integration"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-iot-integration-logs"
  }
}

resource "aws_cloudwatch_log_group" "general_conversation" {
  name              = "/aws/lambda/${local.name_prefix}-general-conversation"
  retention_in_days = 14
  kms_key_id        = aws_kms_key.chatbot_encryption.arn

  tags = {
    Name = "${local.name_prefix}-general-conversation-logs"
  }
}

# Permission pour Lex d'invoquer la fonction Lambda
resource "aws_lambda_permission" "allow_lex" {
  statement_id  = "AllowExecutionFromLex"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lex_fulfillment.function_name
  principal     = "lexv2.amazonaws.com"
  source_arn    = "arn:aws:lex:${local.region}:${local.account_id}:bot/*"
}
