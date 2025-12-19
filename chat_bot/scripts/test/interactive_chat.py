"""
Script de test interactif pour le chatbot Kidjamo
Permet de tester les conversations en mode CLI
"""

import boto3
import json
import argparse
import logging
from datetime import datetime
import uuid

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotTester:
    def __init__(self, environment: str, region: str = 'eu-west-1'):
        self.environment = environment
        self.region = region
        self.lexv2 = boto3.client('lexv2-runtime', region_name=region)
        self.bot_id = None
        self.bot_alias_id = 'TestBotAlias'
        self.locale_id = 'fr_FR'
        self.session_id = str(uuid.uuid4())

        # Récupération de l'ID du bot
        self._get_bot_id()

    def _get_bot_id(self):
        """Récupère l'ID du bot depuis AWS"""
        try:
            lexv2_models = boto3.client('lexv2-models', region_name=self.region)
            bots = lexv2_models.list_bots()

            bot_name = f"kidjamo-{self.environment}-health-bot"
            for bot in bots['botSummaries']:
                if bot['botName'] == bot_name:
                    self.bot_id = bot['botId']
                    logger.info(f"Bot trouvé: {bot_name} (ID: {self.bot_id})")
                    return

            raise Exception(f"Bot {bot_name} non trouvé")

        except Exception as e:
            logger.error(f"Erreur récupération bot ID: {str(e)}")
            raise

    def send_message(self, message: str) -> dict:
        """Envoie un message au chatbot et retourne la réponse"""
        try:
            response = self.lexv2.recognize_text(
                botId=self.bot_id,
                botAliasId=self.bot_alias_id,
                localeId=self.locale_id,
                sessionId=self.session_id,
                text=message
            )

            return response

        except Exception as e:
            logger.error(f"Erreur envoi message: {str(e)}")
            return {'error': str(e)}

    def format_response(self, response: dict) -> str:
        """Formate la réponse du chatbot pour l'affichage"""
        if 'error' in response:
            return f"❌ Erreur: {response['error']}"

        messages = response.get('messages', [])
        if not messages:
            return "🤖 Aucune réponse du chatbot"

        # Assemblage des messages
        bot_response = ""
        for message in messages:
            content = message.get('content', '')
            if content:
                bot_response += content + "\n"

        # Informations de debug si nécessaire
        intent_name = response.get('sessionState', {}).get('intent', {}).get('name', 'Unknown')
        confidence = response.get('interpretations', [{}])[0].get('nluConfidence', {}).get('score', 0)

        debug_info = f"\n🔍 Intent: {intent_name} (confiance: {confidence:.2f})"

        return bot_response.strip() + debug_info

    def interactive_chat(self):
        """Lance une session de chat interactive"""
        print("🤖 Chatbot Santé Kidjamo - Mode Test Interactif")
        print("=" * 50)
        print("Session ID:", self.session_id)
        print("Tapez 'quit' pour quitter, 'help' pour l'aide\n")

        while True:
            try:
                # Saisie utilisateur
                user_input = input("👤 Vous: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Au revoir ! Prenez soin de vous.")
                    break

                if user_input.lower() == 'help':
                    self.show_help()
                    continue

                if not user_input:
                    continue

                # Envoi au chatbot
                print("⏳ Traitement...")
                response = self.send_message(user_input)

                # Affichage de la réponse
                formatted_response = self.format_response(response)
                print(f"🤖 Kidjamo: {formatted_response}\n")

            except KeyboardInterrupt:
                print("\n👋 Session interrompue. Au revoir !")
                break
            except Exception as e:
                print(f"❌ Erreur: {str(e)}\n")

    def show_help(self):
        """Affiche l'aide pour les tests"""
        help_text = """
📋 AIDE - Exemples de phrases à tester :

🩺 Signalement de douleur :
  • "J'ai mal au ventre, intensité 8/10"
  • "Je ressens une douleur dans le dos"
  • "Ça fait très mal"

📊 Consultation des vitales :
  • "Montre-moi mes vitales"
  • "Comment va mon rythme cardiaque ?"
  • "Mes données récentes"

💊 Gestion des médicaments :
  • "J'ai pris mon Doliprane"
  • "Rappel pour mes médicaments"
  • "J'ai oublié mon traitement"

🚨 Urgences :
  • "C'est urgent"
  • "J'ai besoin d'aide rapidement"
  • "Appelez les secours"

❓ Aide générale :
  • "Aide"
  • "Que peux-tu faire ?"
  • "Comment ça marche ?"

Commandes spéciales :
  • 'quit' - Quitter
  • 'help' - Afficher cette aide
        """
        print(help_text)

    def run_test_suite(self):
        """Lance une suite de tests automatisés"""
        test_cases = [
            {
                'input': "J'ai mal au ventre intensité 7",
                'expected_intent': 'SignalerDouleur',
                'description': 'Test signalement douleur avec intensité'
            },
            {
                'input': "Montre-moi mes vitales",
                'expected_intent': 'ConsulterVitales',
                'description': 'Test consultation données vitales'
            },
            {
                'input': "J'ai pris mon Doliprane",
                'expected_intent': 'GererMedicaments',
                'description': 'Test gestion médicaments'
            },
            {
                'input': "C'est urgent",
                'expected_intent': 'SignalerUrgence',
                'description': 'Test signalement urgence'
            },
            {
                'input': "Aide",
                'expected_intent': 'DemanderAide',
                'description': 'Test demande aide'
            }
        ]

        print("🧪 Lancement de la suite de tests automatisés")
        print("=" * 50)

        passed = 0
        failed = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📝 Test {i}: {test_case['description']}")
            print(f"Input: '{test_case['input']}'")

            response = self.send_message(test_case['input'])

            if 'error' in response:
                print(f"❌ ÉCHEC - Erreur: {response['error']}")
                failed += 1
                continue

            detected_intent = response.get('sessionState', {}).get('intent', {}).get('name', 'Unknown')

            if detected_intent == test_case['expected_intent']:
                print(f"✅ SUCCÈS - Intent détecté: {detected_intent}")
                passed += 1
            else:
                print(f"❌ ÉCHEC - Intent attendu: {test_case['expected_intent']}, obtenu: {detected_intent}")
                failed += 1

        print(f"\n📊 Résultats des tests:")
        print(f"✅ Réussis: {passed}")
        print(f"❌ Échoués: {failed}")
        print(f"📈 Taux de réussite: {passed/(passed+failed)*100:.1f}%")

def main():
    parser = argparse.ArgumentParser(description='Test interactif du chatbot Kidjamo')
    parser.add_argument('--environment', required=True, help='Environnement (dev, stg, prod)')
    parser.add_argument('--region', default='eu-west-1', help='Région AWS')
    parser.add_argument('--mode', choices=['interactive', 'test'], default='interactive',
                        help='Mode de fonctionnement')

    args = parser.parse_args()

    try:
        tester = ChatbotTester(args.environment, args.region)

        if args.mode == 'interactive':
            tester.interactive_chat()
        else:
            tester.run_test_suite()

    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
