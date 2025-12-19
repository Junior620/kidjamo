"""
Testeur simple pour dialoguer avec votre chatbot Amazon Bedrock
Interface en ligne de commande pour tester facilement
"""

import requests
import json
from datetime import datetime

class BedrockChatTester:
    """Testeur interactif pour votre chatbot Bedrock"""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def test_connection(self):
        """Teste la connexion au serveur Bedrock"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("✅ CONNEXION RÉUSSIE AU SERVEUR BEDROCK")
                print(f"   Service: {data.get('service', 'unknown')}")
                print(f"   Version: {data.get('version', 'unknown')}")
                print(f"   Status: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Erreur connexion: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Impossible de se connecter au serveur: {e}")
            print("Assurez-vous que le serveur Bedrock est démarré sur http://localhost:5000")
            return False

    def send_message(self, message: str):
        """Envoie un message au chatbot Bedrock"""
        try:
            payload = {
                "message": message,
                "session_id": self.session_id,
                "is_voice": False,
                "patient_info": {
                    "age": "25",
                    "condition": "drépanocytose"
                }
            }

            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"❌ Erreur HTTP: {response.status_code}")
                print(f"Réponse: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Erreur envoi message: {e}")
            return None

    def format_response(self, response_data):
        """Formate et affiche la réponse du chatbot"""
        if not response_data:
            return

        # Extraire le texte de la réponse HTML
        html_response = response_data.get('response', '')

        # Supprimer les balises HTML basiques pour affichage console
        import re
        text_response = re.sub(r'<[^>]+>', '', html_response)
        text_response = text_response.replace('&nbsp;', ' ')
        text_response = text_response.replace('&amp;', '&')
        text_response = text_response.replace('&lt;', '<')
        text_response = text_response.replace('&gt;', '>')
        text_response = re.sub(r'\s+', ' ', text_response).strip()

        print(f"\n🤖 KIDJAMO BEDROCK:")
        print("=" * 70)
        print(text_response)
        print("=" * 70)

        # Afficher les métadonnées
        print(f"📊 Modèle utilisé: {response_data.get('model_used', 'inconnu')}")
        print(f"📊 Type conversation: {response_data.get('conversation_type', 'inconnu')}")
        print(f"📊 Source: {response_data.get('source', 'inconnu')}")
        if response_data.get('cost_estimate'):
            print(f"💰 Coût estimé: ${response_data.get('cost_estimate', 0):.6f}")

    def run_interactive(self):
        """Lance le mode interactif"""
        print("\n" + "="*80)
        print("🤖 TESTEUR CHATBOT AMAZON BEDROCK - KIDJAMO")
        print("="*80)
        print("Tapez vos messages pour dialoguer avec le chatbot médical")
        print("Commandes spéciales:")
        print("  'quit' ou 'exit' - Quitter")
        print("  'health' - Vérifier le status du serveur")
        print("  'clear' - Nouvelle session")
        print("="*80)

        # Test initial de connexion
        if not self.test_connection():
            print("\n❌ Impossible de continuer sans connexion au serveur")
            return

        while True:
            try:
                user_input = input(f"\n💬 Vous: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'sortir']:
                    print("\n👋 Au revoir !")
                    break
                elif user_input.lower() == 'health':
                    self.test_connection()
                    continue
                elif user_input.lower() == 'clear':
                    self.session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    print(f"🔄 Nouvelle session créée: {self.session_id}")
                    continue

                print("⏳ Envoi à Amazon Bedrock...")
                response_data = self.send_message(user_input)
                self.format_response(response_data)

            except KeyboardInterrupt:
                print("\n\n👋 Session interrompue.")
                break
            except Exception as e:
                print(f"\n❌ Erreur: {e}")

    def run_quick_tests(self):
        """Lance une série de tests rapides"""
        print("\n🧪 TESTS RAPIDES AMAZON BEDROCK")
        print("="*50)

        if not self.test_connection():
            return

        test_messages = [
            "Bonjour",
            "J'ai mal à la poitrine",
            "La douleur est à 8/10",
            "Comment prendre mon siklos ?",
            "Qu'est-ce que la drépanocytose ?"
        ]

        for i, message in enumerate(test_messages, 1):
            print(f"\n[TEST {i}/{len(test_messages)}]")
            print(f"🧑 Message: {message}")

            response_data = self.send_message(message)
            if response_data:
                print(f"✅ Réponse reçue - Modèle: {response_data.get('model_used', 'inconnu')}")
                print(f"   Type: {response_data.get('conversation_type', 'inconnu')}")
            else:
                print("❌ Échec de la réponse")

        print(f"\n✅ Tests terminés avec session: {self.session_id}")

def main():
    """Point d'entrée principal"""
    import sys

    tester = BedrockChatTester()

    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        tester.run_quick_tests()
    else:
        tester.run_interactive()

if __name__ == "__main__":
    main()
