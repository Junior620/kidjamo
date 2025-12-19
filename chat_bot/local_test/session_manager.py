"""
Gestionnaire de sessions pour maintenir le contexte conversationnel
"""
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json

class SessionManager:
    """Gestionnaire de sessions avec contexte conversationnel"""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 1800  # 30 minutes

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Récupère ou crée une session"""
        current_time = datetime.now()

        # Nettoyer les sessions expirées
        self._cleanup_expired_sessions()

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'id': session_id,
                'created_at': current_time,
                'last_activity': current_time,
                'conversation_history': [],
                'context': {
                    'current_crisis': False,
                    'pain_level': None,
                    'last_topic': None,
                    'medications_discussed': [],
                    'emergency_context': False
                },
                'user_profile': {
                    'name': None,
                    'age': None,
                    'medical_history': [],
                    'current_medications': []
                }
            }
        else:
            # Mettre à jour l'activité
            self.sessions[session_id]['last_activity'] = current_time

        return self.sessions[session_id]

    def update_context(self, session_id: str, key: str, value: Any):
        """Met à jour le contexte de la session"""
        session = self.get_session(session_id)
        session['context'][key] = value

    def add_message(self, session_id: str, user_message: str, bot_response: str, message_type: str):
        """Ajoute un message à l'historique"""
        session = self.get_session(session_id)
        session['conversation_history'].append({
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'bot_response': bot_response,
            'type': message_type
        })

        # Garder seulement les 20 derniers messages
        if len(session['conversation_history']) > 20:
            session['conversation_history'] = session['conversation_history'][-20:]

        # Analyser le contexte
        self._analyze_context(session_id, user_message, message_type)

    def _analyze_context(self, session_id: str, message: str, message_type: str):
        """Analyse le contexte pour améliorer les futures réponses"""
        session = self.get_session(session_id)

        # Détecter une crise en cours
        if message_type == 'emergency':
            session['context']['emergency_context'] = True
            session['context']['current_crisis'] = True

        # Détecter le niveau de douleur
        import re
        pain_match = re.search(r'([0-9]|10)/10', message.lower())
        if pain_match:
            session['context']['pain_level'] = int(pain_match.group(1))

        # Mémoriser le dernier sujet
        session['context']['last_topic'] = message_type

    def get_context_for_ai(self, session_id: str) -> Dict[str, Any]:
        """Récupère le contexte formaté pour l'IA"""
        session = self.get_session(session_id)
        recent_messages = session['conversation_history'][-5:] if session['conversation_history'] else []

        return {
            'emergency_context': session['context']['emergency_context'],
            'current_crisis': session['context']['current_crisis'],
            'pain_level': session['context']['pain_level'],
            'last_topic': session['context']['last_topic'],
            'recent_conversation': recent_messages,
            'session_duration': (datetime.now() - session['created_at']).seconds // 60
        }

    def get_recent_messages(self, session_id: str, limit: int = 3) -> List[Dict]:
        """Récupère les messages récents formatés pour l'IA"""
        session = self.get_session(session_id)
        messages = session['conversation_history'][-limit:] if session['conversation_history'] else []

        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'role': 'user',
                'content': msg['user_message'],
                'timestamp': msg['timestamp']
            })
            formatted_messages.append({
                'role': 'assistant',
                'content': msg['bot_response'],
                'timestamp': msg['timestamp']
            })

        return formatted_messages

    def set_emergency_context(self, session_id: str, active: bool):
        """Active ou désactive le contexte d'urgence"""
        session = self.get_session(session_id)
        session['context']['emergency_context'] = active

    def set_crisis_context(self, session_id: str, active: bool):
        """Active ou désactive le contexte de crise"""
        session = self.get_session(session_id)
        session['context']['current_crisis'] = active

    def reset_crisis_context(self, session_id: str):
        """Remet à zéro le contexte de crise"""
        session = self.get_session(session_id)
        session['context']['current_crisis'] = False
        session['context']['pain_level'] = None

    def update_pain_level(self, session_id: str, level: int):
        """Met à jour le niveau de douleur"""
        session = self.get_session(session_id)
        session['context']['pain_level'] = level

    def set_last_conversation_type(self, session_id: str, conversation_type: str):
        """Enregistre le dernier type de conversation"""
        session = self.get_session(session_id)
        session['context']['last_conversation_type'] = conversation_type

    def _cleanup_expired_sessions(self):
        """Nettoie les sessions expirées"""
        current_time = datetime.now()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if (current_time - session['last_activity']).seconds > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.sessions[session_id]

# Instance globale
session_manager = SessionManager()
