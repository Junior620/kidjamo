
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

# IAM policy for Firehose to access S3
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

# Kinesis Data Firehose Delivery Stream
resource "aws_kinesis_firehose_delivery_stream" "data_lake_delivery" {
  name        = "${var.project}-${var.environment}-data-lake-delivery"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_delivery_role.arn
    bucket_arn = var.s3_bucket_arn
    prefix     = "raw/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"

    buffering_size     = var.firehose_buffer_size
    buffering_interval = var.firehose_buffer_interval
    compression_format = var.firehose_compression

    error_output_prefix = "errors/"
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-data-lake-delivery"
    Purpose = "Data lake delivery"
  })
}
