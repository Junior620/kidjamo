#!/usr/bin/env python3
"""
🤖 SIMULATION DE CONVERSATION INTELLIGENTE - CHATBOT KIDJAMO
===========================================================

Simulation avec IA Gemini Flash intégrée pour des réponses contextuelles
et intelligentes remplaçant les réponses statiques.

Usage:
    python simulation_conversation_ai.py
    python simulation_conversation_ai.py --scenario=crise
    python simulation_conversation_ai.py --scenario=urgence
"""

import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiFlashChatbot:
    """Chatbot médical avec Gemini Flash intégré"""

    def __init__(self):
        # Votre clé API Gemini Flash
        self.api_key = "AIzaSyCM7YXGLREXa1w7r9RwqOHWn4Ywd2ZLHRE"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        self.conversation_context = []

    def generate_response(self, user_message: str, conversation_type: str = "general") -> Dict:
        """Génère une réponse intelligente avec Gemini Flash"""

        # Construire le prompt médical contextualisé
        system_prompt = self._build_medical_prompt(conversation_type, user_message)

        # Inclure l'historique récent pour le contexte
        context_messages = ""
        if self.conversation_context:
            recent_context = self.conversation_context[-3:]  # 3 derniers échanges
            context_messages = "\n\nCONTEXTE CONVERSATION RÉCENTE:\n"
            for ctx in recent_context:
                context_messages += f"Patient: {ctx['user']}\nAssistant: {ctx['bot'][:100]}...\n"

        full_prompt = f"{system_prompt}{context_messages}\n\nQUESTION ACTUELLE: {user_message}\n\nRéponds de manière empathique et médicalement appropriée:"

        try:
            payload = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 600,
                    "topP": 0.8
                }
            }

            response = requests.post(self.url, json=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                ai_response = data["candidates"][0]["content"]["parts"][0]["text"]

                # Sauvegarder le contexte
                self.conversation_context.append({
                    "user": user_message,
                    "bot": ai_response
                })

                # Limiter le contexte à 10 échanges
                if len(self.conversation_context) > 10:
                    self.conversation_context = self.conversation_context[-10:]

                return {
                    "success": True,
                    "response": ai_response,
                    "conversation_type": self._detect_conversation_type(user_message),
                    "model_used": "gemini-1.5-flash",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Fallback en cas d'erreur API
                return self._fallback_response(user_message, conversation_type)

        except Exception as e:
            logger.error(f"Erreur Gemini Flash: {e}")
            return self._fallback_response(user_message, conversation_type)

    def _build_medical_prompt(self, conversation_type: str, user_message: str) -> str:
        """Construit un prompt médical contextualisé"""

        base_prompt = """Tu es Kidjamo Assistant, un assistant médical spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun.

PERSONNALITÉ ET APPROCHE:
- Empathique, rassurant mais prudent médicalement
- Tu utilises un ton chaleureux et professionnel
- Tu personnalises selon l'historique de conversation
- Tu utilises des émojis pour structurer et clarifier
- Tu adaptes ton langage (simple, accessible)

RÈGLES MÉDICALES CRITIQUES:
- Tu ne remplaces JAMAIS un médecin
- Urgence si: douleur >7/10, difficultés respiratoires, fièvre élevée
- En urgence: recommande TOUJOURS d'appeler les secours
- Tu restes dans le domaine de la drépanocytose
- Tu demandes des précisions si nécessaire

NUMÉROS D'URGENCE CAMEROUN:
- 1510 (Numéro d'urgence national camerounais)
- Hôpital Central de Yaoundé - Service d'urgences
- Hôpital Général de Douala - Urgences médicales
- Centre Hospitalier Universitaire (CHU) - Service hématologie

CENTRES SPÉCIALISÉS CAMEROUN:
- CHU de Yaoundé - Centre de référence drépanocytose
- Hôpital Laquintinie Douala - Service hématologie
- Centre Pasteur Cameroun - Suivi drépanocytose

DOMAINES D'EXPERTISE:
🩺 Gestion de la douleur et crises
💊 Médicaments (Hydroxyurée, antalgiques)
🚨 Protocoles d'urgence
📚 Éducation sur la drépanocytose
🤗 Soutien psychologique"""

        # Adaptation selon le type de conversation
        if conversation_type == "emergency":
            base_prompt += """

MODE URGENCE ACTIVÉ:
- Priorise ABSOLUMENT la sécurité du patient
- Structure: 🚨 URGENCE → Numéros → Actions immédiates → Infos à communiquer
- Sois ferme sur la nécessité d'aide médicale
- Reste calme mais directif"""

        elif self._is_pain_related(user_message):
            base_prompt += """

MODE GESTION DOULEUR:
- Évalue d'abord l'intensité (échelle 1-10)
- Si >7/10: protocole urgence immédiat
- Sinon: conseils de gestion + surveillance
- Propose techniques non-médicamenteuses"""

        elif self._is_medication_related(user_message):
            base_prompt += """

MODE MÉDICAMENTS:
- Focus sur observance et sécurité
- Horaires, interactions, effets secondaires
- Ne modifie jamais les prescriptions
- Renvoie vers le médecin si nécessaire"""

        return base_prompt

    def _detect_conversation_type(self, message: str) -> str:
        """Détecte le type de conversation selon le message"""
        message_lower = message.lower()

        urgency_keywords = ["aide", "urgent", "secours", "respirer", "souffle", "grave"]
        pain_keywords = ["mal", "douleur", "souffre", "crise", "intense", "/10"]
        medication_keywords = ["médicament", "traitement", "siklos", "paracétamol", "pilule"]

        if any(keyword in message_lower for keyword in urgency_keywords):
            return "emergency"
        elif any(keyword in message_lower for keyword in pain_keywords):
            return "pain_management"
        elif any(keyword in message_lower for keyword in medication_keywords):
            return "medication"
        else:
            return "general"

    def _is_pain_related(self, message: str) -> bool:
        """Vérifie si le message concerne la douleur"""
        pain_keywords = ["mal", "douleur", "souffre", "crise", "intense", "/10", "échelle"]
        return any(keyword in message.lower() for keyword in pain_keywords)

    def _is_medication_related(self, message: str) -> bool:
        """Vérifie si le message concerne les médicaments"""
        med_keywords = ["médicament", "traitement", "siklos", "paracétamol", "pilule", "dose", "rappel"]
        return any(keyword in message.lower() for keyword in med_keywords)

    def _fallback_response(self, user_message: str, conversation_type: str) -> Dict:
        """Réponse de secours si Gemini Flash échoue"""

        message_lower = user_message.lower()

        if any(word in message_lower for word in ["aide", "urgent", "mal", "respire"]):
            response = """🚨 URGENCE DÉTECTÉE

Si vous ressentez:
• Douleur >7/10
• Difficultés respiratoires
• Fièvre élevée

APPELEZ IMMÉDIATEMENT:
📞 115 (SAMU Cameroun)
📞 112 (Urgences européennes)

⚠️ Mentionnez "patient drépanocytaire"

En attendant:
✅ Restez calme
✅ Position confortable
✅ Préparez vos documents médicaux"""
        else:
            response = """👋 Assistant Kidjamo

Je suis spécialisé dans l'accompagnement drépanocytose:

🩺 Gestion douleur - "J'ai mal"
💊 Médicaments - "Rappel traitement"  
🚨 Urgences - "Aide urgent"
📚 Questions - "Qu'est-ce que..."

Comment puis-je vous aider?"""

        return {
            "success": True,
            "response": response,
            "conversation_type": conversation_type,
            "model_used": "fallback-intelligent",
            "timestamp": datetime.now().isoformat()
        }

class IntelligentConversationSimulator:
    """Simulateur avec IA intégrée"""

    def __init__(self):
        self.chatbot = GeminiFlashChatbot()
        self.session_id = f"ai_simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.conversation_history = []

    def send_message(self, message: str) -> Dict:
        """Envoie un message au chatbot IA"""
        print(f"\n🧑 UTILISATEUR: {message}")
        print("⏳ Gemini Flash analyse...")

        # Générer la réponse avec Gemini Flash
        response_data = self.chatbot.generate_response(message)

        if response_data["success"]:
            print(f"\n🤖 KIDJAMO ASSISTANT:")
            print("=" * 60)
            print(response_data["response"])
            print("=" * 60)

            # Sauvegarder dans l'historique
            self.conversation_history.append({
                'timestamp': datetime.now().isoformat(),
                'user_message': message,
                'bot_response': response_data["response"],
                'conversation_type': response_data["conversation_type"],
                'model_used': response_data["model_used"],
                'success': True
            })
        else:
            print(f"❌ Erreur: {response_data.get('error', 'Erreur inconnue')}")

        return response_data

    def run_scenario_simulation(self, scenario_name: str):
        """Lance une simulation de scénario prédéfini avec IA"""

        scenarios = {
            'urgence': [
                "Aide moi",
                "J'ai une douleur atroce dans la poitrine",
                "Je n'arrive plus à respirer correctement",
                "Que faire ?",
                "Merci"
            ],
            'crise': [
                "Bonjour",
                "J'ai très mal au dos depuis 2 heures",
                "La douleur est à 8/10",
                "Je prends déjà du paracétamol mais ça ne passe pas",
                "Qu'est-ce que je dois faire ?",
                "Est-ce que je dois aller aux urgences ?"
            ],
            'medication': [
                "Bonjour",
                "J'ai oublié de prendre mon siklos ce matin",
                "Est-ce que je peux le prendre maintenant ?",
                "Quels sont les effets secondaires ?",
                "Merci pour l'aide"
            ]
        }

        if scenario_name not in scenarios:
            print(f"❌ Scénario '{scenario_name}' non trouvé")
            return

        messages = scenarios[scenario_name]

        print(f"\n🎭 SIMULATION SCÉNARIO: {scenario_name.upper()}")
        print("=" * 60)

        for i, message in enumerate(messages, 1):
            print(f"\n[ÉTAPE {i}/{len(messages)}]")

            response = self.send_message(message)

            # Pause entre les messages
            if i < len(messages):
                time.sleep(2)

        print(f"\n🎬 SCÉNARIO '{scenario_name}' TERMINÉ")

        # Proposer de sauvegarder
        save_choice = input(f"\n💾 Sauvegarder la conversation ? (o/n): ").strip().lower()
        if save_choice in ['o', 'oui', 'y', 'yes']:
            self.save_conversation(f"scenario_{scenario_name}")

    def run_interactive_simulation(self):
        """Lance une simulation interactive avec IA"""
        print("\n" + "="*80)
        print("🏥 SIMULATION IA - KIDJAMO HEALTH ASSISTANT")
        print("🚀 Propulsé par Gemini Flash pour des réponses intelligentes")
        print("="*80)
        print("Tapez vos messages comme si vous parliez vraiment au chatbot.")
        print("Commandes spéciales:")
        print("  'quit' ou 'exit' - Terminer")
        print("  'history' - Voir l'historique")
        print("  'stats' - Statistiques de la session")
        print("="*80)

        while True:
            try:
                user_input = input(f"\n💬 Votre message: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'sortir']:
                    print("\n👋 Au revoir ! Simulation terminée.")
                    break
                elif user_input.lower() == 'history':
                    self._show_conversation_history()
                    continue
                elif user_input.lower() == 'stats':
                    self._show_session_stats()
                    continue

                # Envoyer le message au chatbot IA
                self.send_message(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Simulation interrompue par l'utilisateur.")
                break
            except Exception as e:
                print(f"\n❌ Erreur: {e}")

    def _show_conversation_history(self):
        """Affiche l'historique de conversation"""
        if not self.conversation_history:
            print("\n📝 Aucun historique disponible")
            return

        print(f"\n📝 HISTORIQUE CONVERSATION ({len(self.conversation_history)} échanges)")
        print("=" * 60)

        for i, entry in enumerate(self.conversation_history, 1):
            print(f"\n[{i}] {entry['timestamp']}")
            print(f"🧑 USER: {entry['user_message']}")
            print(f"🤖 BOT: {entry['bot_response'][:100]}...")
            print(f"🔧 Type: {entry['conversation_type']} | Model: {entry['model_used']}")

    def _show_session_stats(self):
        """Affiche les statistiques de la session"""
        if not self.conversation_history:
            print("\n📊 Aucune statistique disponible")
            return

        total_exchanges = len(self.conversation_history)
        conversation_types = {}
        models_used = {}

        for entry in self.conversation_history:
            conv_type = entry['conversation_type']
            model = entry['model_used']

            conversation_types[conv_type] = conversation_types.get(conv_type, 0) + 1
            models_used[model] = models_used.get(model, 0) + 1

        print(f"\n📊 STATISTIQUES SESSION")
        print("=" * 40)
        print(f"💬 Total échanges: {total_exchanges}")
        print(f"🕐 Durée session: {(datetime.now() - datetime.fromisoformat(self.conversation_history[0]['timestamp'].replace('Z', '+00:00'))).seconds // 60} min")

        print(f"\n📋 Types de conversation:")
        for conv_type, count in conversation_types.items():
            print(f"   • {conv_type}: {count}")

        print(f"\n🔧 Modèles utilisés:")
        for model, count in models_used.items():
            print(f"   • {model}: {count}")

    def save_conversation(self, filename_prefix: str = "conversation"):
        """Sauvegarde la conversation"""
        if not self.conversation_history:
            print("❌ Aucune conversation à sauvegarder")
            return

        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'total_exchanges': len(self.conversation_history),
                'conversation': self.conversation_history
            }, f, ensure_ascii=False, indent=2)

        print(f"💾 Conversation sauvegardée: {filename}")

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Simulation conversation IA Kidjamo')
    parser.add_argument('--scenario', choices=['urgence', 'crise', 'medication'],
                       help='Lance un scénario prédéfini')
    parser.add_argument('--auto', action='store_true',
                       help='Mode automatique (tous les scénarios)')

    args = parser.parse_args()

    simulator = IntelligentConversationSimulator()

    if args.auto:
        # Lancer tous les scénarios
        for scenario in ['urgence', 'crise', 'medication']:
            simulator.run_scenario_simulation(scenario)
            print("\n" + "="*60)
    elif args.scenario:
        # Lancer un scénario spécifique
        simulator.run_scenario_simulation(args.scenario)
    else:
        # Mode interactif
        simulator.run_interactive_simulation()

if __name__ == "__main__":
    main()
