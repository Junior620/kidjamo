# Kinesis Data Stream for IoT measurements
resource "aws_kinesis_stream" "iot_measurements" {
  name             = "${var.project}-${var.environment}-iot-measurements"
  shard_count      = var.shard_count
  retention_period = var.retention_period

  encryption_type = "KMS"
  kms_key_id      = var.kms_key_id

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-iot-data-stream"
    Purpose = "IoT data streaming"
  })
}

# IAM role for Firehose
resource "aws_iam_role" "firehose_delivery_role" {
  name = "${var.project}-${var.environment}-firehose-delivery-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "firehose.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM policy for Firehose to write to S3
resource "aws_iam_role_policy" "firehose_delivery_policy" {
  name = "${var.project}-${var.environment}-firehose-delivery-policy"
  role = aws_iam_role.firehose_delivery_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Kinesis Firehose for data delivery to S3
resource "aws_kinesis_firehose_delivery_stream" "iot_measurements" {
  name        = "${var.project}-${var.environment}-iot-firehose"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.iot_measurements.arn
    role_arn          = aws_iam_role.firehose_delivery_role.arn
  }

  extended_s3_configuration {
    role_arn           = aws_iam_role.firehose_delivery_role.arn
    bucket_arn         = var.s3_bucket_arn
    prefix             = "raw/iot-measurements/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/"
    buffer_size         = 5
    buffer_interval     = 300
    compression_format  = "GZIP"
  }

  tags = var.tags
}
