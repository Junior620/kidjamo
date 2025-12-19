output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "data_pipeline_role_arn" {
  description = "ARN of the data pipeline role"
  value       = aws_iam_role.data_pipeline_role.arn
}

output "kinesis_role_arn" {
  description = "ARN of the Kinesis role"
  value       = aws_iam_role.kinesis_role.arn
}

output "s3_access_policy_arn" {
  description = "ARN of the S3 access policy"
  value       = aws_iam_policy.s3_access_policy.arn
}
