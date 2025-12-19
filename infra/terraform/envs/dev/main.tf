# Main Terraform configuration for dev environment
# Calls all the modules below

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  vpc_name               = "kidjamo-dev-vpc"
  vpc_cidr              = "10.0.0.0/16"
  availability_zones    = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  public_subnet_cidrs   = ["10.0.0.0/24", "10.0.1.0/24"]
  private_subnet_cidrs  = ["10.0.10.0/24", "10.0.11.0/24"]
  enable_nat_gateway    = true

  tags = var.common_tags
}

# S3 Module
module "s3" {
  source = "../../modules/s3"

  environment = var.environment
  project     = var.project

  tags = var.common_tags
}

# KMS Module
module "kms" {
  source = "../../modules/kms"

  environment = var.environment
  project     = var.project

  tags = var.common_tags
}

# IAM Module
module "iam" {
  source = "../../modules/iam"

  environment = var.environment
  project     = var.project

  tags = var.common_tags
}

# Secrets Manager Module
module "secrets" {
  source = "../../modules/secrets"

  environment = var.environment
  project     = var.project
  kms_key_id  = module.kms.key_id

  tags = var.common_tags
}

# Kinesis Module
module "kinesis" {
  source = "../../modules/kinesis"

  environment    = var.environment
  project        = var.project
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  s3_bucket_arn  = module.s3.bucket_arns.data_lake_raw

  tags = var.common_tags
}

# API Gateway + Lambda Module
module "apigw_lambda" {
  source = "../../modules/apigw_lambda"

  environment         = var.environment
  project            = var.project
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  tags = var.common_tags
}

# RDS PostgreSQL Module
module "rds" {
  source = "../../modules/rds"

  environment         = var.environment
  project            = var.project
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr_block  # Correction: utiliser vpc_cidr_block
  private_subnet_ids = module.vpc.private_subnet_ids

  # PostgreSQL configuration
  postgres_version       = "15.4"
  instance_class        = "db.t3.micro"  # Free tier
  allocated_storage     = 20
  database_name         = "kidjamo"
  db_username          = "kidjamo_admin"
  publicly_accessible   = true
  deletion_protection   = false  # Dev environment

  # Security - Allow access from anywhere for dev (adjust for production)
  allowed_cidr_blocks = ["0.0.0.0/0"]

  tags = var.common_tags
}

# Outputs
output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.db_instance_endpoint
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = module.rds.db_instance_port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.rds.db_name
}

output "rds_username" {
  description = "RDS username"
  value       = module.rds.db_username
  sensitive   = true
}

output "rds_secret_arn" {
  description = "ARN of the RDS credentials secret"
  value       = module.rds.secrets_manager_secret_arn
}
