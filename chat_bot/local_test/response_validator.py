"""
Système de validation des réponses et collecte de feedback
"""
from typing import Dict, Any, List
from datetime import datetime
import json

class ResponseValidator:
    """Validateur de réponses pour améliorer la qualité du chatbot"""

    def __init__(self):
        self.feedback_log = []
        self.quality_metrics = {
            'total_responses': 0,
            'positive_feedback': 0,
            'negative_feedback': 0,
            'emergency_responses': 0,
            'response_times': []
        }

    def validate_response_quality(self, user_message: str, bot_response: str, conversation_type: str) -> Dict[str, Any]:
        """Valide la qualité de la réponse automatiquement"""
        validation_result = {
            'is_valid': True,
            'quality_score': 0.8,  # Score par défaut
            'issues': [],
            'suggestions': []
        }

        # Vérifications de base
        if len(bot_response) < 50:
            validation_result['issues'].append('Réponse trop courte')
            validation_result['quality_score'] -= 0.2

        if conversation_type == 'emergency':
            # Vérifications spécifiques pour les urgences
            if 'APPELEZ IMMÉDIATEMENT' not in bot_response:
                validation_result['issues'].append('Instruction d\'urgence manquante')
                validation_result['quality_score'] -= 0.3

            if '115' not in bot_response and '112' not in bot_response:
                validation_result['issues'].append('Numéros d\'urgence manquants')
                validation_result['quality_score'] -= 0.2

        # Score final
        validation_result['quality_score'] = max(0.1, validation_result['quality_score'])
        validation_result['is_valid'] = validation_result['quality_score'] >= 0.6

        return validation_result

    def log_feedback(self, session_id: str, message_id: str, feedback_type: str, user_comment: str = None):
        """Enregistre le feedback utilisateur"""
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'message_id': message_id,
            'feedback_type': feedback_type,  # 'positive', 'negative', 'helpful', 'not_helpful'
            'user_comment': user_comment
        }

        self.feedback_log.append(feedback_entry)

        # Mise à jour des métriques
        self.quality_metrics['total_responses'] += 1
        if feedback_type in ['positive', 'helpful']:
            self.quality_metrics['positive_feedback'] += 1
        elif feedback_type in ['negative', 'not_helpful']:
            self.quality_metrics['negative_feedback'] += 1

    def get_quality_report(self) -> Dict[str, Any]:
        """Génère un rapport de qualité"""
        total = self.quality_metrics['total_responses']
        if total == 0:
            return {'message': 'Aucune donnée disponible'}

        positive_rate = (self.quality_metrics['positive_feedback'] / total) * 100
        negative_rate = (self.quality_metrics['negative_feedback'] / total) * 100

        return {
            'total_responses': total,
            'positive_feedback_rate': round(positive_rate, 2),
            'negative_feedback_rate': round(negative_rate, 2),
            'emergency_responses': self.quality_metrics['emergency_responses'],
            'recent_feedback': self.feedback_log[-10:]  # 10 derniers feedbacks
        }

# Instance globale
response_validator = ResponseValidator()
