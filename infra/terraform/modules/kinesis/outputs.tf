output "kinesis_stream_arn" {
  description = "ARN of the Kinesis data stream"
  value       = aws_kinesis_stream.iot_measurements.arn
}

output "kinesis_stream_name" {
  description = "Name of the Kinesis data stream"
  value       = aws_kinesis_stream.iot_measurements.name
}

output "firehose_delivery_stream_arn" {
  description = "ARN of the Kinesis Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.iot_measurements.arn
}

output "firehose_delivery_stream_name" {
  description = "Name of the Kinesis Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.iot_measurements.name
}

output "firehose_role_arn" {
  description = "ARN of the Firehose delivery role"
  value       = aws_iam_role.firehose_delivery_role.arn
}
