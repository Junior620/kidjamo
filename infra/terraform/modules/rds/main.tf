# RDS PostgreSQL Module for Kidjamo
# Creates and configures PostgreSQL database instance

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.project}-${var.environment}-postgres-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-postgres-subnet-group"
  })
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.project}-${var.environment}-postgres-"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL access"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  # Allow access from specific IP if provided
  dynamic "ingress" {
    for_each = var.allowed_cidr_blocks
    content {
      description = "External PostgreSQL access"
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-postgres-sg"
  })
}

# Random password for PostgreSQL
resource "random_password" "postgres_password" {
  length  = 32
  special = true
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "postgres_credentials" {
  name                    = "${var.project}/postgres/${var.environment}"
  description             = "PostgreSQL credentials for ${var.project} ${var.environment}"
  recovery_window_in_days = var.deletion_protection ? 30 : 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "postgres_credentials" {
  secret_id = aws_secretsmanager_secret.postgres_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.postgres_password.result
    engine   = "postgres"
    host     = aws_db_instance.postgres.endpoint
    port     = aws_db_instance.postgres.port
    dbname   = aws_db_instance.postgres.db_name
  })
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier = "${var.project}-${var.environment}-postgres"

  # Engine configuration
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.instance_class

  # Database configuration
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type         = var.storage_type
  storage_encrypted    = true

  # Database name and credentials
  db_name  = var.database_name
  username = var.db_username
  password = random_password.postgres_password.result

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = var.publicly_accessible

  # Backup configuration
  backup_retention_period = var.backup_retention_period
  backup_window          = var.backup_window
  maintenance_window     = var.maintenance_window

  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Other settings
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  deletion_protection       = var.deletion_protection
  skip_final_snapshot      = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.project}-${var.environment}-postgres-final-snapshot" : null

  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7

  # Parameter group for optimizations
  parameter_group_name = aws_db_parameter_group.postgres.name

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-postgres"
  })
}

# RDS Parameter Group for optimizations
resource "aws_db_parameter_group" "postgres" {
  family = "postgres15"  # Adjust based on version
  name   = "${var.project}-${var.environment}-postgres-params"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking more than 1 second
  }

  tags = var.tags
}

# IAM role for RDS monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.project}-${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# CloudWatch Log Group for PostgreSQL logs
resource "aws_cloudwatch_log_group" "postgres" {
  name              = "/aws/rds/instance/${aws_db_instance.postgres.identifier}/postgresql"
  retention_in_days = 30

  tags = var.tags
}
