"""
Test de diagnostic Bedrock AWS - Identification des problèmes
"""

import os
import boto3
from dotenv import load_dotenv

# Charger la configuration avec le chemin absolu
load_dotenv(os.path.join(os.path.dirname(__file__), '.env.bedrock'))

def test_bedrock_connection():
    print("🔧 DIAGNOSTIC BEDROCK AWS")
    print("="*50)
    
    # 1. Vérifier les variables d'environnement
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    print(f"✅ AWS_ACCESS_KEY_ID: {aws_key[:12] if aws_key else 'NON CONFIGURÉ'}...")
    print(f"✅ AWS_SECRET_ACCESS_KEY: {'Configuré' if aws_secret else 'NON CONFIGURÉ'}")
    print(f"✅ AWS_REGION: {aws_region}")
    
    if not aws_key or not aws_secret:
        print("❌ ERREUR: Clés AWS manquantes")
        return False
    
    # 2. Test de connexion Bedrock
    try:
        print("\n🔍 Test connexion Bedrock...")
        bedrock_client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )
        print("✅ Client Bedrock créé avec succès")
        
        # 3. Test simple d'appel Bedrock Titan (maintenant activé)
        print("\n🧪 Test appel Bedrock Titan...")
        import json

        body = {
            "inputText": "Bonjour, vous fonctionnez ?",
            "textGenerationConfig": {
                "maxTokenCount": 50,
                "temperature": 0.3,
                "topP": 0.8
            }
        }
        
        response = bedrock_client.invoke_model(
            modelId="amazon.titan-text-express-v1",
            body=json.dumps(body)
        )
        
        print("✅ Appel Bedrock réussi !")

        # Lire la réponse
        response_body = json.loads(response['body'].read())
        print(f"📊 Réponse reçue: {response_body}")

        return True
        
    except Exception as e:
        print(f"❌ ERREUR Bedrock: {e}")
        print(f"❌ Type erreur: {type(e).__name__}")
        return False

if __name__ == "__main__":
    test_bedrock_connection()
