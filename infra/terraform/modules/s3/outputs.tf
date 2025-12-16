output "bucket_names" {
  description = "Names of all S3 buckets"
  value = {
    data_lake_raw    = aws_s3_bucket.data_lake_raw.bucket
    data_lake_bronze = aws_s3_bucket.data_lake_bronze.bucket
    data_lake_silver = aws_s3_bucket.data_lake_silver.bucket
    data_lake_gold   = aws_s3_bucket.data_lake_gold.bucket
    app_assets       = aws_s3_bucket.app_assets.bucket
  }
}

output "bucket_arns" {
  description = "ARNs of all S3 buckets"
  value = {
    data_lake_raw    = aws_s3_bucket.data_lake_raw.arn
    data_lake_bronze = aws_s3_bucket.data_lake_bronze.arn
    data_lake_silver = aws_s3_bucket.data_lake_silver.arn
    data_lake_gold   = aws_s3_bucket.data_lake_gold.arn
    app_assets       = aws_s3_bucket.app_assets.arn
  }
}
