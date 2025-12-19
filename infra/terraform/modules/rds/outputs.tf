output "db_instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.postgres.identifier
}

output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.postgres.port
}

output "db_instance_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.postgres.arn
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.postgres.db_name
}

output "db_username" {
  description = "Database master username"
  value       = aws_db_instance.postgres.username
  sensitive   = true
}

output "security_group_id" {
  description = "Security group ID for RDS"
  value       = aws_security_group.postgres.id
}

output "subnet_group_name" {
  description = "DB subnet group name"
  value       = aws_db_subnet_group.postgres.name
}

output "secrets_manager_secret_id" {
  description = "Secrets Manager secret ID containing database credentials"
  value       = aws_secretsmanager_secret.postgres_credentials.id
}

output "secrets_manager_secret_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.postgres_credentials.arn
}
