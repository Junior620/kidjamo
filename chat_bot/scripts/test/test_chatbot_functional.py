#!/usr/bin/env python3
"""
Script de test fonctionnel du chatbot Kidjamo
Teste les fonctionnalités de recherche Kendra et d'interaction
"""

import boto3
import json
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatbotFunctionalTester:
    def __init__(self, kendra_index_id="b7472109-44e4-42de-9192-2b6dbe1493cc", region="eu-west-1"):
        self.kendra_index_id = kendra_index_id
        self.region = region
        self.kendra = boto3.client('kendra', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)

    def test_kendra_search(self):
        """Test des fonctionnalités de recherche Kendra"""
        logger.info("🔍 Test des capacités de recherche Kendra...")

        test_queries = [
            "Qu'est-ce que la drépanocytose ?",
            "symptômes drépanocytose",
            "traitement sickle cell",
            "crise vaso-occlusive",
            "hydroxyurée"
        ]

        for query in test_queries:
            try:
                logger.info(f"📝 Recherche: '{query}'")

                response = self.kendra.query(
                    IndexId=self.kendra_index_id,
                    QueryText=query,
                    PageSize=5
                )

                result_items = response.get('ResultItems', [])
                logger.info(f"   → {len(result_items)} résultat(s) trouvé(s)")

                for i, item in enumerate(result_items[:2]):  # Afficher max 2 résultats
                    score = item.get('ScoreAttributes', {}).get('ScoreConfidence', 'Unknown')
                    title = item.get('DocumentTitle', {}).get('Text', 'Sans titre')
                    snippet = item.get('DocumentExcerpt', {}).get('Text', '')[:100] + "..."

                    logger.info(f"   [{i+1}] Score: {score} | {title}")
                    logger.info(f"       {snippet}")

            except Exception as e:
                logger.error(f"   ❌ Erreur pour la requête '{query}': {str(e)}")

    def test_lambda_medical_nlp(self):
        """Test de la fonction Lambda NLP médicale"""
        logger.info("🧠 Test de la fonction NLP médicale...")

        test_texts = [
            "Le patient présente des douleurs abdominales récurrentes",
            "Crise vaso-occlusive sévère avec hospitalisation",
            "Traitement par hydroxyurée depuis 6 mois"
        ]

        for text in test_texts:
            try:
                logger.info(f"📝 Analyse: '{text}'")

                payload = {
                    "text": text,
                    "analysis_type": "medical_entity_extraction"
                }

                response = self.lambda_client.invoke(
                    FunctionName="kidjamo-dev-chatbot-medical-nlp",
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )

                if response['StatusCode'] == 200:
                    result = json.loads(response['Payload'].read())
                    logger.info(f"   ✅ Analyse réussie: {result}")
                else:
                    logger.warning(f"   ⚠️ Statut: {response['StatusCode']}")

            except Exception as e:
                logger.error(f"   ❌ Erreur pour l'analyse: {str(e)}")

    def test_conversation_flow(self):
        """Test du flux de conversation"""
        logger.info("💬 Test du flux de conversation...")

        conversation_scenarios = [
            {
                "message": "Bonjour, j'ai des questions sur la drépanocytose",
                "expected_keywords": ["bonjour", "drépanocytose", "questions"]
            },
            {
                "message": "Quels sont les symptômes principaux ?",
                "expected_keywords": ["symptômes", "douleur", "anémie"]
            },
            {
                "message": "Comment gérer une crise ?",
                "expected_keywords": ["crise", "gestion", "traitement"]
            }
        ]

        session_id = f"test-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        for i, scenario in enumerate(conversation_scenarios):
            try:
                logger.info(f"💭 Scénario {i+1}: '{scenario['message']}'")

                payload = {
                    "message": scenario["message"],
                    "user_id": "test-user",
                    "session_id": session_id,
                    "context": {
                        "medical_condition": "drepanocytose",
                        "language": "fr"
                    }
                }

                response = self.lambda_client.invoke(
                    FunctionName="kidjamo-dev-chatbot-general-conversation",
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )

                if response['StatusCode'] == 200:
                    result = json.loads(response['Payload'].read())
                    logger.info(f"   ✅ Réponse générée")
                    logger.info(f"   📨 {str(result)[:150]}...")
                else:
                    logger.warning(f"   ⚠️ Statut: {response['StatusCode']}")

            except Exception as e:
                logger.error(f"   ❌ Erreur pour le scénario: {str(e)}")

    def add_sample_documents(self):
        """Ajoute des documents d'exemple à Kendra pour enrichir les tests"""
        logger.info("📚 Ajout de documents d'exemple...")

        # Note: Cette fonction nécessiterait d'uploader des documents dans S3
        # et de déclencher une synchronisation Kendra
        logger.info("   ℹ️ Pour ajouter des documents, uploadez des fichiers PDF/DOCX")
        logger.info("   ℹ️ dans le bucket S3: kidjamo-dev-chatbot-documents-cpcua9dm")
        logger.info("   ℹ️ La synchronisation se fera automatiquement selon le planning")

def main():
    """Fonction principale de test"""
    logger.info("🚀 Démarrage des tests fonctionnels du chatbot Kidjamo")
    logger.info("=" * 60)

    tester = ChatbotFunctionalTester()

    # Tests de recherche Kendra
    tester.test_kendra_search()
    logger.info("")

    # Tests de la fonction NLP
    tester.test_lambda_medical_nlp()
    logger.info("")

    # Tests de conversation
    tester.test_conversation_flow()
    logger.info("")

    # Informations sur l'ajout de documents
    tester.add_sample_documents()

    logger.info("=" * 60)
    logger.info("✅ Tests fonctionnels terminés")
    logger.info("")
    logger.info("📋 Prochaines étapes recommandées:")
    logger.info("   1. Ajoutez des documents médicaux dans S3")
    logger.info("   2. Attendez la synchronisation Kendra (2h du matin)")
    logger.info("   3. Configurez Amazon Lex pour l'interface utilisateur")
    logger.info("   4. Testez l'intégration IoT avec vos capteurs")

if __name__ == "__main__":
    main()
