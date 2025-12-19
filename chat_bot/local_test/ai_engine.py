"""
Moteur d'IA générative pour le chatbot Kidjamo
Support local (Ollama) et cloud (OpenAI/Claude) avec fallback intelligent
"""

import requests
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AIEngine:
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')

        # Configuration des modèles
        self.local_model = "llama3.1:8b"  # Ou "mistral:7b", "medllama2:7b"
        self.fallback_enabled = True

        # Vérifier la disponibilité d'Ollama
        self.ollama_available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Vérifie si Ollama est disponible localement"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            logger.warning("Ollama non disponible - utilisation du fallback cloud")
            return False

    def generate_response(self,
                         user_message: str,
                         context: Dict[str, Any],
                         conversation_type: str = "general") -> Dict[str, Any]:
        """
        Génère une réponse intelligente basée sur le contexte médical
        """
        try:
            # Construire le prompt médical contextualisé
            system_prompt = self._build_medical_prompt(conversation_type, context)

            # Essayer Ollama d'abord (local)
            if self.ollama_available:
                response = self._generate_with_ollama(user_message, system_prompt, context)
                if response:
                    return response

            # Fallback vers OpenAI si disponible
            if self.openai_api_key and self.fallback_enabled:
                return self._generate_with_openai(user_message, system_prompt, context)

            # Fallback vers Claude si disponible
            if self.claude_api_key and self.fallback_enabled:
                return self._generate_with_claude(user_message, system_prompt, context)

            # Dernier fallback : réponse de base
            return self._fallback_response(conversation_type)

        except Exception as e:
            logger.error(f"Erreur génération IA: {e}")
            return self._fallback_response("error")

    def _build_medical_prompt(self, conversation_type: str, context: Dict[str, Any]) -> str:
        """Construit un prompt médical contextualisé pour la drépanocytose"""

        base_prompt = """Tu es Kidjamo Assistant, un assistant médical spécialisé dans l'accompagnement des patients atteints de drépanocytose.

RÈGLES IMPORTANTES:
- Tu es empathique, rassurant mais prudent médicalement
- Tu ne remplaces JAMAIS un médecin
- En cas d'urgence (douleur >7/10, difficultés respiratoires), tu recommandes TOUJOURS d'appeler les secours
- Tu personnalises tes réponses selon l'historique de conversation
- Tu utilises un langage simple et accessible
- Tu restes dans le domaine de la drépanocytose
- ADAPTE ta réponse au contexte conversationnel précis

NUMÉROS D'URGENCE À RAPPELER:
- 115 (SAMU Cameroun)
- 112 (Urgences européennes)
- 118 (Pompiers)"""

        # Ajouter du contexte spécifique selon le type de conversation
        if conversation_type == "emergency":
            base_prompt += """

CONTEXTE URGENCE CRITIQUE:
- Priorise ABSOLUMENT la sécurité du patient
- Recommande l'appel immédiat aux secours
- Donne des conseils pratiques d'attente
- Reste calme mais ferme sur la nécessité d'aide médicale
- Structure: 🚨 URGENCE → Numéros → Actions immédiates → Informations à communiquer"""

        elif conversation_type == "emergency_followup":
            base_prompt += """

CONTEXTE SUIVI D'URGENCE:
- Le patient a déjà reçu des conseils d'urgence
- Il pose une question de suivi (que faire, dois-je aller aux urgences, etc.)
- Réponds de manière SPÉCIFIQUE à sa question
- Ne répète PAS les mêmes conseils d'urgence
- Adapte selon son état actuel"""

        elif conversation_type == "pain_evolution":
            base_prompt += """

CONTEXTE ÉVOLUTION DOULEUR:
- Le patient était déjà en crise douloureuse
- Il rapporte une évolution (amélioration/aggravation)
- Évalue le changement et adapte les conseils
- Si amélioration: encourage et surveillance
- Si aggravation: réévalue l'urgence"""

        elif conversation_type == "contextual_help":
            base_prompt += """

CONTEXTE AIDE CONTEXTUELLE:
- Le patient pose une question vague ("que faire?") mais il y a un contexte médical actif
- Utilise le contexte (douleur, crise, urgence) pour personnaliser ta réponse
- Sois SPÉCIFIQUE selon sa situation actuelle"""

        elif conversation_type == "pain":
            base_prompt += """

CONTEXTE DOULEUR:
- Évalue le niveau de douleur (échelle 1-10)
- Propose des stratégies de gestion selon l'intensité
- Si >7/10 ou échec des antalgiques habituels = URGENCE
- Encourage la tenue d'un journal de douleur"""

        elif conversation_type == "medication":
            base_prompt += """

CONTEXTE MÉDICAMENTS:
- Rappelle l'importance de l'observance
- Explique les interactions possibles
- Encourage à ne jamais arrêter sans avis médical
- Propose des stratégies de rappel"""

        elif conversation_type == "greeting":
            base_prompt += """

CONTEXTE ACCUEIL:
- Accueille chaleureusement le patient
- Présente tes capacités spécialisées
- Propose des exemples concrets d'aide
- Reste professionnel mais bienveillant"""

        elif conversation_type == "gratitude":
            base_prompt += """

CONTEXTE REMERCIEMENT:
- Le patient te remercie
- Réagis naturellement aux remerciements
- Rappelle ta disponibilité
- Termine sur une note positive et rassurante"""

        elif conversation_type == "general_help":
            base_prompt += """

CONTEXTE AIDE GÉNÉRALE:
- Question vague sans contexte médical urgent
- Oriente vers les domaines d'expertise
- Propose des exemples concrets
- Encourage à être plus spécifique"""

        # Ajouter l'historique récent si disponible
        if context.get('recent_messages'):
            base_prompt += f"""

HISTORIQUE RÉCENT DE CONVERSATION:
{self._format_conversation_history(context['recent_messages'])}

IMPORTANT: Tiens compte de cet historique pour personnaliser ta réponse et éviter les répétitions."""

        # Ajouter le contexte de session
        if context.get('pain_level'):
            base_prompt += f"\n\nDouleur actuelle rapportée: {context['pain_level']}/10"

        if context.get('current_crisis'):
            base_prompt += "\n\nPatient actuellement en crise - surveillance renforcée"

        if context.get('emergency_context'):
            base_prompt += "\n\nCONTEXTE D'URGENCE ACTIF - Le patient a déjà reçu des conseils d'urgence"

        if context.get('pain_evolution'):
            evolution = context['pain_evolution']
            base_prompt += f"\n\nÉvolution douleur: {evolution['previous']}/10 → {evolution['current']}/10 ({evolution['trend']})"

        return base_prompt

    def _format_conversation_history(self, messages: list) -> str:
        """Formate l'historique pour le contexte"""
        if not messages or len(messages) == 0:
            return "Aucun historique"

        formatted = []
        for msg in messages[-3:]:  # Derniers 3 messages
            role = "Patient" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '')[:100]  # Limite à 100 caractères
            formatted.append(f"- {role}: {content}")

        return '\n'.join(formatted)

    def _generate_with_ollama(self, user_message: str, system_prompt: str, context: Dict) -> Optional[Dict]:
        """Génération avec Ollama (local)"""
        try:
            payload = {
                "model": self.local_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 500
                }
            }

            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('message', {}).get('content', '')

                return {
                    'success': True,
                    'response': ai_response.strip(),
                    'source': 'ollama_local',
                    'model': self.local_model,
                    'conversation_type': context.get('conversation_type', 'general')
                }
        except Exception as e:
            logger.error(f"Erreur Ollama: {e}")

        return None

    def _generate_with_openai(self, user_message: str, system_prompt: str, context: Dict) -> Dict:
        """Génération avec OpenAI GPT"""
        try:
            import openai

            client = openai.OpenAI(api_key=self.openai_api_key)

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Plus économique
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )

            return {
                'success': True,
                'response': response.choices[0].message.content.strip(),
                'source': 'openai_cloud',
                'model': 'gpt-4o-mini',
                'conversation_type': context.get('conversation_type', 'general')
            }

        except Exception as e:
            logger.error(f"Erreur OpenAI: {e}")
            return self._fallback_response("error")

    def _generate_with_claude(self, user_message: str, system_prompt: str, context: Dict) -> Dict:
        """Génération avec Anthropic Claude"""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.claude_api_key)

            message = client.messages.create(
                model="claude-3-haiku-20240307",  # Plus rapide et économique
                max_tokens=500,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            return {
                'success': True,
                'response': message.content[0].text.strip(),
                'source': 'claude_cloud',
                'model': 'claude-3-haiku',
                'conversation_type': context.get('conversation_type', 'general')
            }

        except Exception as e:
            logger.error(f"Erreur Claude: {e}")
            return self._fallback_response("error")

    def _fallback_response(self, conversation_type: str) -> Dict:
        """Réponses de fallback contextualisées"""
        fallbacks = {
            "emergency": {
                'response': """🚨 URGENCE MÉDICALE DÉTECTÉE

Je ne peux pas générer de réponse personnalisée actuellement, mais votre sécurité est prioritaire :

APPELEZ IMMÉDIATEMENT:
- 115 (SAMU Cameroun)
- 112 (Urgences européennes)

EN ATTENDANT LES SECOURS:
- Restez calme
- Ne bougez pas si possible
- Préparez vos papiers d'identité
- Mentionnez "patient drépanocytaire"

⚠️ Cette situation nécessite une prise en charge médicale immédiate.""",
                'conversation_type': 'emergency'
            },
            "greeting": {
                'response': """Bonjour ! Je suis votre assistant Kidjamo, spécialisé dans l'accompagnement des patients drépanocytaires.

Je peux vous aider avec :
🩺 Gestion de la douleur
💊 Questions sur vos médicaments  
🚨 Situations d'urgence
📚 Informations sur la drépanocytose

Comment puis-je vous accompagner aujourd'hui ?""",
                'conversation_type': 'greeting'
            },
            "error": {
                'response': """Je rencontre actuellement des difficultés techniques pour générer une réponse personnalisée.

Cependant, je reste disponible pour vous aider. Pouvez-vous reformuler votre question ?

Si c'est urgent, n'hésitez pas à contacter directement les services médicaux.""",
                'conversation_type': 'error'
            }
        }

        return {
            'success': True,
            'response': fallbacks.get(conversation_type, fallbacks['error'])['response'],
            'source': 'fallback_local',
            'conversation_type': conversation_type
        }

# Instance globale
ai_engine = AIEngine()
