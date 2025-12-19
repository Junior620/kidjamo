"""
Diagnostic et test de votre token Amazon Bedrock
Identifie pourquoi l'API timeout et propose des solutions
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.bedrock')

def diagnose_bedrock_connection():
    """Diagnostique la connexion à Amazon Bedrock"""

    print("🔍 DIAGNOSTIC AMAZON BEDROCK")
    print("="*60)

    # 1. Vérifier la configuration
    token = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
    endpoint = os.getenv('BEDROCK_API_ENDPOINT', 'https://bedrock-runtime.us-east-1.amazonaws.com')

    print(f"✅ Token Bearer: {token[:25] if token else 'NON CONFIGURÉ'}...")
    print(f"✅ Endpoint: {endpoint}")

    if not token:
        print("❌ ERREUR: Token Bearer non trouvé dans .env.bedrock")
        return False

    # 2. Test de connectivité réseau de base
    print(f"\n🌐 TEST CONNECTIVITÉ RÉSEAU...")
    try:
        response = requests.get("https://httpbin.org/ip", timeout=5)
        print(f"✅ Connexion Internet OK - IP: {response.json().get('origin', 'unknown')}")
    except Exception as e:
        print(f"❌ Problème connexion Internet: {e}")
        return False

    # 3. Test ping vers AWS
    print(f"\n🔗 TEST CONNEXION AWS...")
    try:
        response = requests.get("https://aws.amazon.com", timeout=5)
        print(f"✅ AWS accessible - Status: {response.status_code}")
    except Exception as e:
        print(f"❌ AWS inaccessible: {e}")
        return False

    # 4. Test endpoint Bedrock spécifique
    print(f"\n🤖 TEST ENDPOINT BEDROCK...")

    # Test 1: Vérification de l'endpoint sans authentification
    try:
        response = requests.get(endpoint, timeout=10)
        print(f"✅ Endpoint Bedrock accessible - Status: {response.status_code}")
        if response.status_code == 403:
            print("ℹ️  403 Forbidden normal sans authentification")
        elif response.status_code == 404:
            print("⚠️  404 Not Found - Endpoint peut-être incorrect")
    except Exception as e:
        print(f"❌ Endpoint Bedrock inaccessible: {e}")
        return False

    # 5. Test authentification Bearer Token
    print(f"\n🔑 TEST AUTHENTIFICATION BEARER TOKEN...")

    # Test avec différents modèles et endpoints
    test_models = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-v2",
        "amazon.titan-text-express-v1"
    ]

    for model_id in test_models:
        print(f"\nTest modèle: {model_id}")

        url = f"{endpoint}/model/{model_id}/invoke"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Payload minimal pour Claude
        if "claude" in model_id:
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Bonjour"}]
            }
        else:  # Titan
            payload = {
                "inputText": "Bonjour",
                "textGenerationConfig": {"maxTokenCount": 100}
            }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCÈS! Modèle {model_id} fonctionne")
                data = response.json()
                if "claude" in model_id and "content" in data:
                    content = data["content"][0]["text"][:50]
                    print(f"   Réponse: {content}...")
                elif "titan" in model_id and "results" in data:
                    content = data["results"][0]["outputText"][:50]
                    print(f"   Réponse: {content}...")
                return True

            elif response.status_code == 401:
                print(f"   ❌ 401 Unauthorized - Token invalide ou expiré")
            elif response.status_code == 403:
                print(f"   ❌ 403 Forbidden - Pas d'accès au modèle {model_id}")
            elif response.status_code == 404:
                print(f"   ❌ 404 Not Found - Modèle {model_id} inexistant")
            elif response.status_code == 429:
                print(f"   ⚠️  429 Rate Limited - Trop de requêtes")
            else:
                print(f"   ❌ Erreur {response.status_code}: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"   ❌ TIMEOUT après 15s - Connexion trop lente")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

    return False

def test_alternative_endpoints():
    """Teste différents endpoints Bedrock"""

    print(f"\n🔄 TEST ENDPOINTS ALTERNATIFS...")

    token = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
    alternative_endpoints = [
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        "https://bedrock-runtime.us-west-2.amazonaws.com",
        "https://bedrock-runtime.eu-west-1.amazonaws.com",
        "https://bedrock.us-east-1.amazonaws.com"
    ]

    for endpoint in alternative_endpoints:
        print(f"\nTest endpoint: {endpoint}")

        try:
            # Test simple de connectivité
            response = requests.get(endpoint, timeout=5)
            print(f"   Connectivité: {response.status_code}")

            # Test avec authentification
            url = f"{endpoint}/model/anthropic.claude-v2/invoke"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": "Test"}]
            }

            auth_response = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"   Auth test: {auth_response.status_code}")

            if auth_response.status_code == 200:
                print(f"   ✅ ENDPOINT FONCTIONNEL: {endpoint}")
                return endpoint

        except Exception as e:
            print(f"   ❌ Erreur: {e}")

    return None

def main():
    """Diagnostic complet"""

    print("🚀 DIAGNOSTIC TOKEN AMAZON BEDROCK")
    print("Analyse pourquoi votre API timeout...")
    print("="*80)

    # Diagnostic principal
    if diagnose_bedrock_connection():
        print("\n🎉 CONNEXION BEDROCK RÉUSSIE!")
        print("Votre token fonctionne, le problème était temporaire.")
        return True

    # Tests alternatifs
    working_endpoint = test_alternative_endpoints()
    if working_endpoint:
        print(f"\n✅ SOLUTION TROUVÉE!")
        print(f"Utilisez cet endpoint: {working_endpoint}")

        # Mettre à jour le fichier .env.bedrock
        print("\n🔧 Mise à jour automatique de la configuration...")
        try:
            with open('.env.bedrock', 'r', encoding='utf-8') as f:
                content = f.read()

            # Remplacer l'endpoint
            new_content = content.replace(
                os.getenv('BEDROCK_API_ENDPOINT', 'https://bedrock-runtime.us-east-1.amazonaws.com'),
                working_endpoint
            )

            with open('.env.bedrock', 'w', encoding='utf-8') as f:
                f.write(new_content)

            print("✅ Configuration mise à jour!")
            print("Redémarrez votre serveur pour appliquer les changements.")

        except Exception as e:
            print(f"❌ Erreur mise à jour config: {e}")

        return True

    # Suggestions de résolution
    print(f"\n🔧 SUGGESTIONS DE RÉSOLUTION:")
    print("="*50)

    print("1️⃣ VÉRIFIER LE TOKEN:")
    print("   - Votre token Bearer est-il encore valide ?")
    print("   - A-t-il expiré ?")
    print("   - Avez-vous les bonnes permissions Bedrock ?")

    print("\n2️⃣ VÉRIFIER LA RÉGION:")
    print("   - Votre token est-il configuré pour us-east-1 ?")
    print("   - Essayez une autre région AWS")

    print("\n3️⃣ VÉRIFIER LES PERMISSIONS:")
    print("   - Votre token a-t-il accès aux modèles Bedrock ?")
    print("   - Politique IAM correcte ?")

    print("\n4️⃣ ALTERNATIVE TEMPORAIRE:")
    print("   - Continuez avec le fallback intelligent")
    print("   - Votre chatbot fonctionne déjà sans l'API Bedrock")

    print("\n5️⃣ CONTACT SUPPORT:")
    print("   - Vérifiez avec votre fournisseur de token Bedrock")
    print("   - Le service Bedrock est-il actif dans votre région ?")

    return False

if __name__ == "__main__":
    main()
