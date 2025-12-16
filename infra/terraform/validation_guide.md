# Infrastructure Validation and Testing Guide

## 1. Tests de validation Terraform

### Validation syntaxique
```bash
# Vérifier la syntaxe Terraform
terraform fmt -check -recursive
terraform validate

# Planifier sans appliquer
terraform plan -out=plan.out
```

### Tests unitaires avec Terratest
```bash
# Installer Terratest (Go requis)
go mod init terraform-tests
go get github.com/gruntwork-io/terratest/modules/terraform
```

## 2. Tests d'infrastructure déployée

### Health checks automatisés
- API Gateway endpoints
- Lambda functions
- S3 buckets accessibility
- Kinesis streams status
- Secrets Manager access

### Tests de connectivité
- VPC networking
- Security groups
- IAM permissions

## 3. Tests de bout en bout

### Pipeline de données
- Ingestion IoT → Kinesis → S3
- MongoDB collections
- API responses

### Monitoring et alertes
- CloudWatch dashboards
- Métriques custom
- Notifications SNS

## 4. Scripts de validation

Voir les scripts dans ce dossier :
- `validate_infrastructure.py` - Tests automatisés
- `health_check.sh` - Vérifications rapides
- `terraform_test.go` - Tests Terratest
