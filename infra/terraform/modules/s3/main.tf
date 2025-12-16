# S3 Buckets for data lake and application storage

# Data Lake Raw Bucket
resource "aws_s3_bucket" "data_lake_raw" {
  bucket = "${var.project}-${var.environment}-data-lake-raw"

  tags = merge(var.tags, {
    Name        = "${var.project}-${var.environment}-data-lake-raw"
    Purpose     = "Data Lake Raw Layer"
    DataClass   = "raw"
  })
}

# Data Lake Bronze Bucket
resource "aws_s3_bucket" "data_lake_bronze" {
  bucket = "${var.project}-${var.environment}-data-lake-bronze"

  tags = merge(var.tags, {
    Name        = "${var.project}-${var.environment}-data-lake-bronze"
    Purpose     = "Data Lake Bronze Layer"
    DataClass   = "bronze"
  })
}

# Data Lake Silver Bucket
resource "aws_s3_bucket" "data_lake_silver" {
  bucket = "${var.project}-${var.environment}-data-lake-silver"

  tags = merge(var.tags, {
    Name        = "${var.project}-${var.environment}-data-lake-silver"
    Purpose     = "Data Lake Silver Layer"
    DataClass   = "silver"
  })
}

# Data Lake Gold Bucket
resource "aws_s3_bucket" "data_lake_gold" {
  bucket = "${var.project}-${var.environment}-data-lake-gold"

  tags = merge(var.tags, {
    Name        = "${var.project}-${var.environment}-data-lake-gold"
    Purpose     = "Data Lake Gold Layer"
    DataClass   = "gold"
  })
}

# Application Assets Bucket
resource "aws_s3_bucket" "app_assets" {
  bucket = "${var.project}-${var.environment}-app-assets"

  tags = merge(var.tags, {
    Name        = "${var.project}-${var.environment}-app-assets"
    Purpose     = "Application Assets Storage"
    DataClass   = "assets"
  })
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "data_lake_versioning" {
  for_each = {
    raw    = aws_s3_bucket.data_lake_raw.id
    bronze = aws_s3_bucket.data_lake_bronze.id
    silver = aws_s3_bucket.data_lake_silver.id
    gold   = aws_s3_bucket.data_lake_gold.id
  }

  bucket = each.value
  versioning_configuration {
    status = "Enabled"
  }
}
