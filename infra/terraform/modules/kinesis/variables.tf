variable "project" {
  description = "Project name"
  type        = string
  default     = "kidjamo"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "vpc_id" {
  description = "VPC ID where resources will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for Kinesis"
  type        = list(string)
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN for Firehose delivery"
  type        = string
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = "alias/aws/kinesis"
}

variable "shard_count" {
  description = "Number of shards for Kinesis stream"
  type        = number
  default     = 2
}

variable "retention_period" {
  description = "Data retention period in hours"
  type        = number
  default     = 24
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
