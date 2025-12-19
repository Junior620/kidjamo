#!/usr/bin/env python3
"""
🤖 SIMULATION DE CONVERSATION RÉELLE - CHATBOT KIDJAMO
====================================================

Simulation interactive d'une conversation concrète entre un utilisateur
et le chatbot Kidjamo pour tester ses réponses en conditions réelles.

Usage:
    python simulation_conversation.py
    python simulation_conversation.py --scenario=crise
    python simulation_conversation.py --auto
"""

import json
import logging
import random
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatbotConversationSimulator:
    """Simulateur de conversation avec le chatbot Kidjamo"""

    def __init__(self, chatbot_url: str = "http://localhost:5000"):
        self.chatbot_url = chatbot_url
        self.session_id = f"simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.conversation_history = []

    def send_message(self, message: str) -> Dict:
        """Envoie un message au chatbot et récupère la réponse"""
        try:
            payload = {
                "message": message,
                "session_id": self.session_id,
                "is_voice": False
            }

            print(f"\n🧑 UTILISATEUR: {message}")
            print("⏳ Envoi au chatbot...")

            response = requests.post(
                f"{self.chatbot_url}/chat",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Extraire le texte de la réponse HTML
                response_text = self._extract_text_from_html(data.get('response', ''))

                print(f"\n🤖 KIDJAMO ASSISTANT:")
                print("=" * 60)
                print(response_text)
                print("=" * 60)

                # Sauvegarder dans l'historique
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'user_message': message,
                    'bot_response': response_text,
                    'conversation_type': data.get('conversation_type', 'unknown'),
                    'success': data.get('success', False)
                })

                return data
            else:
                error_msg = f"Erreur HTTP {response.status_code}"
                print(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}

        except requests.exceptions.ConnectionError:
            error_msg = "Impossible de se connecter au chatbot. Assurez-vous qu'il est démarré sur http://localhost:5000"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Erreur: {e}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}

    def _extract_text_from_html(self, html_response: str) -> str:
        """Extrait le texte lisible d'une réponse HTML"""
        # Simplification pour affichage console
        import re

        # Supprimer les balises HTML
        text = re.sub(r'<[^>]+>', '', html_response)

        # Remplacer les entités HTML
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')

        # Nettoyer les espaces multiples
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def run_interactive_simulation(self):
        """Lance une simulation interactive"""
        print("\n" + "="*80)
        print("🏥 SIMULATION CONVERSATION KIDJAMO HEALTH ASSISTANT")
        print("="*80)
        print("Tapez vos messages comme si vous parliez vraiment au chatbot.")
        print("Commandes spéciales:")
        print("  'quit' ou 'exit' - Terminer la simulation")
        print("  'history' - Voir l'historique de conversation")
        print("  'test' - Lancer des tests automatiques")
        print("="*80)

        while True:
            try:
                # Attendre l'input utilisateur
                user_input = input(f"\n💬 Votre message: ").strip()

                if not user_input:
                    continue

                # Commandes spéciales
                if user_input.lower() in ['quit', 'exit', 'sortir']:
                    print("\n👋 Au revoir ! Simulation terminée.")
                    break
                elif user_input.lower() == 'history':
                    self._show_conversation_history()
                    continue
                elif user_input.lower() == 'test':
                    self.run_automated_tests()
                    continue

                # Envoyer le message au chatbot
                response = self.send_message(user_input)

                # Petite pause pour rendre la conversation plus naturelle
                time.sleep(1)

            except KeyboardInterrupt:
                print("\n\n👋 Simulation interrompue par l'utilisateur.")
                break
            except Exception as e:
                print(f"\n❌ Erreur: {e}")

    def _show_conversation_history(self):
        """Affiche l'historique de conversation"""
        print("\n📚 HISTORIQUE DE CONVERSATION")
        print("-" * 50)

        if not self.conversation_history:
            print("Aucune conversation encore.")
            return

        for i, entry in enumerate(self.conversation_history, 1):
            timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M:%S")
            print(f"\n[{i}] {timestamp} - Type: {entry['conversation_type']}")
            print(f"👤 Vous: {entry['user_message']}")
            print(f"🤖 Bot: {entry['bot_response'][:100]}...")

    def run_automated_tests(self):
        """Lance une série de tests automatisés"""
        print("\n🧪 LANCEMENT DES TESTS AUTOMATISÉS")
        print("-" * 50)

        test_scenarios = [
            # Test 1: Salutation
            {
                "name": "Salutation basique",
                "message": "Bonjour",
                "expected_type": "greeting"
            },

            # Test 2: Douleur (le problème qu'on a corrigé)
            {
                "name": "Signalement douleur dos",
                "message": "J'ai des douleurs dans le dos",
                "expected_type": "pain_management"
            },

            # Test 3: Variation douleur
            {
                "name": "Douleur alternative",
                "message": "Ça fait mal au ventre",
                "expected_type": "pain_management"
            },

            # Test 4: Urgence
            {
                "name": "Situation urgence",
                "message": "Aide urgent, je ne peux plus respirer",
                "expected_type": "emergency"
            },

            # Test 5: Médicaments
            {
                "name": "Question médicaments",
                "message": "Quand prendre mon hydroxyurée ?",
                "expected_type": "medication"
            },

            # Test 6: Question médicale
            {
                "name": "Information maladie",
                "message": "Qu'est-ce que la drépanocytose ?",
                "expected_type": "medical_info"
            },

            # Test 7: Identité bot
            {
                "name": "Identité du bot",
                "message": "Qui es-tu ?",
                "expected_type": "identity"
            },

            # Test 8: Message non reconnu
            {
                "name": "Message aléatoire",
                "message": "Test blabla random",
                "expected_type": "general"
            }
        ]

        results = {"success": 0, "failed": 0, "details": []}

        for i, test in enumerate(test_scenarios, 1):
            print(f"\n[TEST {i}/{len(test_scenarios)}] {test['name']}")
            print(f"Message: '{test['message']}'")

            response = self.send_message(test['message'])

            if response.get('success'):
                actual_type = response.get('conversation_type', 'unknown')
                expected_type = test['expected_type']

                if actual_type == expected_type:
                    print(f"✅ SUCCÈS - Type détecté: {actual_type}")
                    results["success"] += 1
                    results["details"].append(f"✅ {test['name']}: {actual_type}")
                else:
                    print(f"❌ ÉCHEC - Attendu: {expected_type}, Reçu: {actual_type}")
                    results["failed"] += 1
                    results["details"].append(f"❌ {test['name']}: attendu {expected_type}, reçu {actual_type}")
            else:
                print(f"❌ ERREUR - {response.get('error', 'Erreur inconnue')}")
                results["failed"] += 1
                results["details"].append(f"❌ {test['name']}: erreur technique")

            time.sleep(0.5)  # Pause entre tests

        # Résumé des tests
        print(f"\n📊 RÉSULTATS DES TESTS")
        print(f"✅ Succès: {results['success']}/{len(test_scenarios)}")
        print(f"❌ Échecs: {results['failed']}/{len(test_scenarios)}")
        print(f"📈 Taux de réussite: {(results['success']/len(test_scenarios)*100):.1f}%")

        if results['failed'] > 0:
            print(f"\n🔍 DÉTAILS DES PROBLÈMES:")
            for detail in results['details']:
                if detail.startswith('❌'):
                    print(f"  {detail}")

    def run_scenario_simulation(self, scenario: str):
        """Lance un scénario de conversation prédéfini"""
        scenarios = {
            "crise": [
                "Bonjour",
                "J'ai très mal au dos depuis 2 heures",
                "La douleur est à 8/10",
                "Je prends déjà du paracétamol mais ça ne passe pas",
                "Qu'est-ce que je dois faire ?",
                "Est-ce que je dois aller aux urgences ?"
            ],

            "decouverte": [
                "Salut",
                "Je viens d'apprendre que j'ai la drépanocytose",
                "Qu'est-ce que c'est exactement ?",
                "Est-ce que c'est grave ?",
                "Quels traitements existent ?",
                "Comment je peux éviter les crises ?"
            ],

            "medicaments": [
                "Bonjour",
                "J'ai oublié de prendre mon hydroxyurée ce matin",
                "Que faire ?",
                "À quelle heure je dois la prendre normalement ?",
                "Quels sont les effets secondaires ?",
                "Merci pour les conseils"
            ],

            "urgence": [
                "Aide moi",
                "J'ai une douleur atroce dans la poitrine",
                "Je n'arrive plus à respirer correctement",
                "Que faire ?",
                "Merci"
            ]
        }

        if scenario not in scenarios:
            print(f"❌ Scénario '{scenario}' non trouvé. Scénarios disponibles: {list(scenarios.keys())}")
            return

        print(f"\n🎭 SIMULATION SCÉNARIO: {scenario.upper()}")
        print("=" * 60)

        messages = scenarios[scenario]

        for i, message in enumerate(messages, 1):
            print(f"\n[ÉTAPE {i}/{len(messages)}]")
            self.send_message(message)

            # Pause pour simulation réaliste
            time.sleep(2)

        print(f"\n🎬 SCÉNARIO '{scenario}' TERMINÉ")

    def save_conversation_log(self, filename: str = None):
        """Sauvegarde l'historique de conversation"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_log_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'total_messages': len(self.conversation_history),
                'conversation': self.conversation_history
            }, f, indent=2, ensure_ascii=False)

        print(f"💾 Conversation sauvegardée: {filename}")

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description='Simulation de conversation avec Kidjamo')
    parser.add_argument('--scenario', type=str,
                       choices=['crise', 'decouverte', 'medicaments', 'urgence'],
                       help='Scénario prédéfini à lancer')
    parser.add_argument('--auto', action='store_true',
                       help='Lancer les tests automatiques')
    parser.add_argument('--url', type=str, default='http://localhost:5000',
                       help='URL du chatbot')

    args = parser.parse_args()

    # Créer le simulateur
    simulator = ChatbotConversationSimulator(chatbot_url=args.url)

    try:
        if args.auto:
            # Tests automatiques
            simulator.run_automated_tests()
        elif args.scenario:
            # Scénario prédéfini
            simulator.run_scenario_simulation(args.scenario)
        else:
            # Mode interactif
            simulator.run_interactive_simulation()

        # Proposer de sauvegarder
        if simulator.conversation_history:
            save = input(f"\n💾 Sauvegarder la conversation ? (o/n): ").lower()
            if save in ['o', 'oui', 'y', 'yes']:
                simulator.save_conversation_log()

    except Exception as e:
        logger.error(f"Erreur simulation: {e}")

if __name__ == "__main__":
    main()
