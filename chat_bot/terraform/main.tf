# Infrastructure Terraform pour le Chatbot Santé Kidjamo
# =========================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "kidjamo"
      Environment = var.environment
      Component   = "chatbot"
      Owner       = "kidjamo-team"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment (dev, stg, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "kidjamo"
}

variable "kendra_index_id" {
  description = "ID de l'index Amazon Kendra pour la recherche documentaire"
  type        = string
  default     = ""
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Locals
locals {
  name_prefix = "${var.project_name}-${var.environment}-chatbot"
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
}
