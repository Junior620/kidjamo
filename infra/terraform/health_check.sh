#!/bin/bash
# Script de vérification rapide de l'infrastructure Terraform
# Usage: ./health_check.sh [environment] [region]

set -e

ENVIRONMENT=${1:-dev}
REGION=${2:-eu-west-1}
PROJECT="kidjamo"

echo "🔍 Vérification rapide de l'infrastructure $PROJECT-$ENVIRONMENT"
echo "================================================"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI non installé${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ AWS CLI disponible${NC}"
}

check_terraform() {
    if ! command -v terraform &> /dev/null; then
        echo -e "${RED}❌ Terraform non installé${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Terraform disponible${NC}"
}

check_aws_credentials() {
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}❌ Credentials AWS non configurés${NC}"
        exit 1
    fi

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✅ Connecté au compte AWS: $ACCOUNT_ID${NC}"
}

check_terraform_state() {
    echo -e "${YELLOW}📋 Vérification de l'état Terraform...${NC}"

    cd "$(dirname "$0")/envs/$ENVIRONMENT"

    if terraform state list &> /dev/null; then
        RESOURCE_COUNT=$(terraform state list | wc -l)
        echo -e "${GREEN}✅ État Terraform: $RESOURCE_COUNT ressources déployées${NC}"
    else
        echo -e "${RED}❌ Aucun état Terraform trouvé${NC}"
        return 1
    fi
}

check_s3_buckets() {
    echo -e "${YELLOW}📦 Vérification des buckets S3...${NC}"

    BUCKETS=(
        "$PROJECT-$ENVIRONMENT-data-lake-raw"
        "$PROJECT-$ENVIRONMENT-data-lake-bronze"
        "$PROJECT-$ENVIRONMENT-data-lake-silver"
        "$PROJECT-$ENVIRONMENT-data-lake-gold"
        "$PROJECT-$ENVIRONMENT-app-assets"
    )

    for bucket in "${BUCKETS[@]}"; do
        if aws s3api head-bucket --bucket "$bucket" --region "$REGION" 2>/dev/null; then
            echo -e "${GREEN}✅ Bucket $bucket existe${NC}"
        else
            echo -e "${RED}❌ Bucket $bucket manquant${NC}"
        fi
    done
}

check_kinesis_stream() {
    echo -e "${YELLOW}🌊 Vérification du stream Kinesis...${NC}"

    STREAM_NAME="$PROJECT-$ENVIRONMENT-iot-data-stream"

    if aws kinesis describe-stream --stream-name "$STREAM_NAME" --region "$REGION" &> /dev/null; then
        STATUS=$(aws kinesis describe-stream --stream-name "$STREAM_NAME" --region "$REGION" --query 'StreamDescription.StreamStatus' --output text)
        echo -e "${GREEN}✅ Stream Kinesis $STREAM_NAME: $STATUS${NC}"
    else
        echo -e "${RED}❌ Stream Kinesis $STREAM_NAME manquant${NC}"
    fi
}

check_lambda_functions() {
    echo -e "${YELLOW}⚡ Vérification des fonctions Lambda...${NC}"

    FUNCTION_NAME="$PROJECT-$ENVIRONMENT-health-check"

    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &> /dev/null; then
        STATE=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --query 'Configuration.State' --output text)
        echo -e "${GREEN}✅ Lambda $FUNCTION_NAME: $STATE${NC}"
    else
        echo -e "${RED}❌ Lambda $FUNCTION_NAME manquant${NC}"
    fi
}

check_api_gateway() {
    echo -e "${YELLOW}🌐 Vérification de l'API Gateway...${NC}"

    API_NAME="$PROJECT-$ENVIRONMENT-api"

    API_ID=$(aws apigateway get-rest-apis --region "$REGION" --query "items[?name=='$API_NAME'].id" --output text)

    if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
        echo -e "${GREEN}✅ API Gateway $API_NAME: $API_ID${NC}"

        # Test de l'endpoint
        API_URL="https://$API_ID.execute-api.$REGION.amazonaws.com/$ENVIRONMENT/health"
        echo -e "${YELLOW}🔗 Test de l'endpoint: $API_URL${NC}"

        if curl -s -o /dev/null -w "%{http_code}" "$API_URL" | grep -q "200"; then
            echo -e "${GREEN}✅ Endpoint API accessible${NC}"
        else
            echo -e "${RED}❌ Endpoint API non accessible${NC}"
        fi
    else
        echo -e "${RED}❌ API Gateway $API_NAME manquant${NC}"
    fi
}

check_secrets() {
    echo -e "${YELLOW}🔐 Vérification des secrets...${NC}"

    SECRETS=(
        "$PROJECT/$ENVIRONMENT/mongodb/connection"
        "$PROJECT/$ENVIRONMENT/database/credentials"
        "$PROJECT/$ENVIRONMENT/api/keys"
        "$PROJECT/$ENVIRONMENT/jwt/secret"
    )

    for secret in "${SECRETS[@]}"; do
        if aws secretsmanager describe-secret --secret-id "$secret" --region "$REGION" &> /dev/null; then
            echo -e "${GREEN}✅ Secret $secret existe${NC}"
        else
            echo -e "${RED}❌ Secret $secret manquant${NC}"
        fi
    done
}

# Exécution des vérifications
main() {
    check_aws_cli
    check_terraform
    check_aws_credentials
    check_terraform_state
    echo ""
    check_s3_buckets
    echo ""
    check_kinesis_stream
    echo ""
    check_lambda_functions
    echo ""
    check_api_gateway
    echo ""
    check_secrets

    echo ""
    echo -e "${GREEN}🎉 Vérification terminée!${NC}"
    echo -e "${YELLOW}💡 Pour une validation complète, exécutez: python validate_infrastructure.py --env $ENVIRONMENT --region $REGION${NC}"
}

main
