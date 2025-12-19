#!/bin/bash
# Script de recréation complète de l'index Kendra
# Pour résoudre définitivement le problème AWS SSO

echo "🚨 RECRÉATION COMPLÈTE DE L'INDEX KENDRA"
echo "========================================"
echo ""
echo "⚠️  ATTENTION: Cette opération va:"
echo "   - Détruire l'index Kendra actuel"
echo "   - Recréer un nouvel index sans AWS SSO"
echo "   - Re-indexer tous les documents"
echo ""

read -p "🔴 Êtes-vous sûr de vouloir continuer ? (oui/NON): " confirm

if [ "$confirm" != "oui" ]; then
    echo "❌ Opération annulée"
    exit 0
fi

echo ""
echo "🔄 Destruction de l'index actuel..."

# Étape 1: Détruire les ressources Kendra
terraform destroy -target=aws_kendra_data_source.s3_medical_docs -auto-approve
terraform destroy -target=aws_kendra_index.medical_knowledge -auto-approve

echo ""
echo "✅ Index détruit"
echo ""
echo "🚀 Recréation avec la nouvelle configuration..."

# Étape 2: Recréer avec la bonne configuration
terraform apply -target=aws_kendra_index.medical_knowledge -auto-approve
terraform apply -target=aws_kendra_data_source.s3_medical_docs -auto-approve

echo ""
echo "✅ Nouvel index créé !"
echo ""
echo "🔄 Lancement de la synchronisation..."

# Étape 3: Déclencher la synchronisation
python ../test/immediate_sync.py

echo ""
echo "🎉 RECRÉATION TERMINÉE !"
echo "📊 Attendez 5-10 minutes pour la synchronisation"
echo "🧪 Puis testez: python kendra_sync_manager.py --test"
