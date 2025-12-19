#!/bin/bash

# Script de déploiement automatisé du chatbot Kidjamo
# =====================================================

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-eu-west-1}
PROJECT_NAME="kidjamo"

echo "🚀 Déploiement du chatbot Kidjamo - Environnement: $ENVIRONMENT"

# Vérification des prérequis
echo "✅ Vérification des prérequis..."
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI requis"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform requis"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 requis"; exit 1; }

# Configuration AWS
echo "🔧 Configuration AWS..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"

# Variables d'environnement
export TF_VAR_environment=$ENVIRONMENT
export TF_VAR_aws_region=$AWS_REGION
export TF_VAR_project_name=$PROJECT_NAME

# Création des packages Lambda
echo "📦 Création des packages Lambda..."

# Package principal Lex fulfillment
cd src/lambda/lex_fulfillment
pip install -r requirements.txt --target .
cd ../../../

# Package NLP médical
cd src/lambda/medical_nlp
pip install -r requirements.txt --target .
cd ../../../

# Package intégration IoT
cd src/lambda/iot_integration
pip install -r requirements.txt --target .
cd ../../../

# Déploiement Terraform
echo "🏗️ Déploiement de l'infrastructure..."
cd terraform

terraform init \
  -backend-config="bucket=$PROJECT_NAME-$ENVIRONMENT-terraform-state" \
  -backend-config="key=chatbot/terraform.tfstate" \
  -backend-config="region=$AWS_REGION"

terraform plan -var-file="$ENVIRONMENT.tfvars"

read -p "Continuer le déploiement ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    terraform apply -var-file="$ENVIRONMENT.tfvars" -auto-approve
else
    echo "Déploiement annulé"
    exit 1
fi

# Récupération des outputs Terraform
BOT_ID=$(terraform output -raw lex_bot_id)
FULFILLMENT_FUNCTION_ARN=$(terraform output -raw lex_fulfillment_function_arn)

cd ..

# Configuration du bot Lex
echo "🤖 Configuration du bot Amazon Lex..."
python3 scripts/deploy/configure_lex_bot.py \
  --bot-definition src/lex/bot_definition/kidjamo_health_bot.json \
  --fulfillment-arn $FULFILLMENT_FUNCTION_ARN \
  --environment $ENVIRONMENT

# Tests de déploiement
echo "🧪 Tests de validation..."
python3 scripts/test/test_chatbot_deployment.py \
  --environment $ENVIRONMENT \
  --bot-id $BOT_ID

# Configuration des alertes CloudWatch
echo "📊 Configuration du monitoring..."
aws cloudwatch put-metric-alarm \
  --alarm-name "$PROJECT_NAME-$ENVIRONMENT-chatbot-errors" \
  --alarm-description "Erreurs du chatbot Kidjamo" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=$PROJECT_NAME-$ENVIRONMENT-chatbot-lex-fulfillment \
  --evaluation-periods 2

echo "✅ Déploiement terminé avec succès !"
echo ""
echo "📋 Informations de déploiement :"
echo "  Bot ID: $BOT_ID"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $AWS_REGION"
echo ""
echo "🔗 Liens utiles :"
echo "  CloudWatch Logs: https://$AWS_REGION.console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups"
echo "  Lex Console: https://$AWS_REGION.console.aws.amazon.com/lexv2/home?region=$AWS_REGION#bots"
echo ""
echo "🧪 Pour tester le chatbot :"
echo "  python3 scripts/test/interactive_chat.py --environment $ENVIRONMENT"
