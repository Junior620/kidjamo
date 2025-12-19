output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

output "s3_bucket_names" {
  description = "Names of the S3 buckets"
  value       = module.s3.bucket_names
}

output "kms_key_id" {
  description = "KMS key ID for encryption"
  value       = module.kms.key_id
}

output "kinesis_stream_name" {
  description = "Name of the Kinesis stream"
  value       = module.kinesis.stream_name
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = module.apigw_lambda.api_gateway_url
}
