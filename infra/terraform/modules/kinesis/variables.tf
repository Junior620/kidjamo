variable "project" {
  description = "Subnet IDs for Kinesis"
  type        = list(string)
}

variable "shard_count" {
  description = "Number of shards for Kinesis stream"
  type        = number
  default     = 1
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

variable "s3_bucket_arn" {
  description = "S3 bucket ARN for Firehose delivery"
  type        = string
}

variable "firehose_buffer_size" {
  description = "Buffer size in MBs for Firehose"
  type        = number
  default     = 5
}

variable "firehose_buffer_interval" {
  description = "Buffer interval in seconds for Firehose"
  type        = number
  default     = 300
}

variable "firehose_compression" {
  description = "Compression format for Firehose"
  type        = string
  default     = "GZIP"
}
