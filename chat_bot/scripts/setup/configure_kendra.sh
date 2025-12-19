#!/bin/bash

# Script de configuration et activation d'Amazon Kendra
# =====================================================

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-eu-west-1}

echo "🔍 Configuration d'Amazon Kendra pour l'environnement: $ENVIRONMENT"

# Vérification des prérequis
echo "✅ Vérification des prérequis..."
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI requis"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform requis"; exit 1; }

# Configuration AWS
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"

# Variables d'environnement
export TF_VAR_environment=$ENVIRONMENT
export TF_VAR_aws_region=$AWS_REGION

echo "🏗️ Déploiement de l'infrastructure Kendra..."
cd ../terraform

# Initialisation et planification
terraform init
terraform plan -target=aws_kendra_index.medical_knowledge

read -p "Continuer le déploiement de Kendra ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Déploiement des ressources Kendra
    terraform apply -target=aws_kendra_index.medical_knowledge -auto-approve
    terraform apply -target=aws_s3_bucket.kendra_documents -auto-approve
    terraform apply -target=aws_kendra_data_source.s3_medical_docs -auto-approve

    echo "✅ Infrastructure Kendra déployée"
else
    echo "Déploiement annulé"
    exit 1
fi

# Récupération des informations de déploiement
KENDRA_INDEX_ID=$(terraform output -raw kendra_index_id)
KENDRA_BUCKET=$(terraform output -raw kendra_documents_bucket)

echo "📋 Informations Kendra :"
echo "  Index ID: $KENDRA_INDEX_ID"
echo "  Bucket S3: $KENDRA_BUCKET"

# Mise à jour de la configuration Lambda avec l'ID Kendra
echo "🔧 Mise à jour des fonctions Lambda..."
terraform apply -var="kendra_index_id=$KENDRA_INDEX_ID" -auto-approve

echo "📚 Téléchargement des documents médicaux de base..."
cd ../scripts/setup

# Création des documents de base
python3 create_medical_documents.py --bucket $KENDRA_BUCKET --environment $ENVIRONMENT

echo "🔄 Démarrage de la synchronisation Kendra..."
aws kendra start-data-source-sync-job \
    --id $(aws kendra list-data-sources --index-id $KENDRA_INDEX_ID --query 'SummaryItems[0].Id' --output text) \
    --index-id $KENDRA_INDEX_ID

echo "⏳ Attente de la fin de l'indexation (cela peut prendre 10-15 minutes)..."
sleep 30

# Vérification du statut
SYNC_STATUS=""
while [[ "$SYNC_STATUS" != "SUCCEEDED" && "$SYNC_STATUS" != "FAILED" ]]; do
    SYNC_STATUS=$(aws kendra list-data-source-sync-jobs \
        --id $(aws kendra list-data-sources --index-id $KENDRA_INDEX_ID --query 'SummaryItems[0].Id' --output text) \
        --index-id $KENDRA_INDEX_ID \
        --max-results 1 \
        --query 'History[0].Status' --output text)

    echo "Status: $SYNC_STATUS"

    if [[ "$SYNC_STATUS" == "SYNCING" ]]; then
        sleep 60
    fi
done

if [[ "$SYNC_STATUS" == "SUCCEEDED" ]]; then
    echo "✅ Indexation Kendra terminée avec succès !"
else
    echo "❌ Erreur lors de l'indexation"
    exit 1
fi

echo "🧪 Test de recherche..."
python3 test_kendra_search.py --index-id $KENDRA_INDEX_ID --query "drépanocytose"

echo "🎉 Configuration Kendra terminée !"
echo ""
echo "📋 Résumé :"
echo "  ✅ Index Kendra créé: $KENDRA_INDEX_ID"
echo "  ✅ Documents médicaux indexés"
echo "  ✅ Fonctions Lambda mises à jour"
echo "  ✅ Tests de recherche validés"
echo ""
echo "🚀 Votre chatbot peut maintenant faire des recherches intelligentes !"
echo "   Exemples de questions :"
echo "   - 'Qu'est-ce que la drépanocytose ?'"
echo "   - 'Comment gérer une crise ?'"
echo "   - 'Recherche sur les traitements'"
