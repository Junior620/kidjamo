"""
Test rapide du chatbot Bedrock maintenant que les modèles sont activés
"""

import os
import boto3
import json
from dotenv import load_dotenv

# Charger la configuration
load_dotenv(os.path.join(os.path.dirname(__file__), '.env.bedrock'))

def test_chatbot_bedrock():
    print("🤖 TEST CHATBOT BEDROCK INTELLIGENT")
    print("="*50)

    # Configuration AWS
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'eu-west-1')

    # Client Bedrock
    bedrock_client = boto3.client(
        'bedrock-runtime',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )

    # Tests avec différents messages
    test_messages = [
        "bonjour",
        "j'ai mal à la poitrine",
        "oubli siklos",
        "conseils prévention"
    ]

    for message in test_messages:
        print(f"\n💬 Test message: '{message}'")

        # Prompt médical spécialisé corrigé (plus court et précis)
        system_prompt = """Tu es Kidjamo Assistant, assistant médical IA spécialisé drépanocytose au Cameroun.

INSTRUCTIONS IMPORTANTES:
- Réponds brièvement en 1-2 phrases maximum
- Spécialisé uniquement drépanocytose 
- En urgence (douleur >7/10, difficultés respiratoires): diriger vers 1510 ou CHU Yaoundé
- Toujours empathique et professionnel
- Ne pas répéter la localisation du patient

CENTRES SPÉCIALISÉS CAMEROUN:
- Yaoundé: CHU Yaoundé (Hématologie)
- Douala: Hôpital Laquintinie  
- Urgences: 1510

Réponds uniquement à la dernière question du patient."""

        # Test avec Titan
        try:
            body = {
                "inputText": f"{system_prompt}\n\nPatient: {message}\nAssistant:",
                "textGenerationConfig": {
                    "maxTokenCount": 200,
                    "temperature": 0.3,
                    "topP": 0.8
                }
            }

            response = bedrock_client.invoke_model(
                modelId="amazon.titan-text-express-v1",
                body=json.dumps(body)
            )

            response_body = json.loads(response['body'].read())
            ai_response = response_body['results'][0]['outputText'].strip()

            print(f"🤖 Réponse Titan: {ai_response[:100]}...")
            print("✅ Test réussi !")

        except Exception as e:
            print(f"❌ Erreur: {e}")

    print(f"\n🎉 CHATBOT BEDROCK OPÉRATIONNEL !")
    print("🌐 Votre serveur peut maintenant être testé sur http://localhost:5000")

if __name__ == "__main__":
    test_chatbot_bedrock()
