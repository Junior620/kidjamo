"""
Système de suggestions intelligentes basées sur le contexte
"""
from typing import List, Dict, Any
import re

class SmartSuggestions:
    """Générateur de suggestions contextuelles pour améliorer l'UX"""

    def __init__(self):
        self.suggestions_map = {
            'greeting': [
                "J'ai mal au dos",
                "Rappel médicaments",
                "Qu'est-ce que la drépanocytose ?",
                "Comment éviter les crises ?",
                "Urgence médicale"
            ],
            'emergency': [
                "Appeler les secours maintenant",
                "Que faire en attendant ?",
                "Symptômes actuels",
                "Historique de la crise"
            ],
            'pain_management': [
                "Évaluer la douleur (1-10)",
                "Localiser la douleur",
                "Médicaments pris",
                "Depuis combien de temps ?",
                "Ça s'aggrave ou s'améliore ?"
            ],
            'medication': [
                "Horaires de prise",
                "Effets secondaires",
                "Oubli de médicament",
                "Interactions médicamenteuses",
                "Rappels automatiques"
            ],
            'medical_info': [
                "Symptômes de la drépanocytose",
                "Prévention des crises",
                "Traitements disponibles",
                "Complications possibles",
                "Vie quotidienne avec la maladie"
            ]
        }

    def get_suggestions(self, conversation_type: str, session_context: Dict[str, Any]) -> List[str]:
        """Génère des suggestions basées sur le contexte"""
        base_suggestions = self.suggestions_map.get(conversation_type, [])

        # Suggestions contextuelles intelligentes
        contextual_suggestions = []

        # Si en crise, prioriser les urgences
        if session_context.get('current_crisis'):
            contextual_suggestions.extend([
                "La douleur s'améliore-t-elle ?",
                "Avez-vous contacté les secours ?",
                "Besoin d'aide supplémentaire ?"
            ])

        # Si niveau de douleur connu
        pain_level = session_context.get('pain_level')
        if pain_level and pain_level >= 7:
            contextual_suggestions.extend([
                "Douleur toujours intense ?",
                "Médicaments pris efficaces ?",
                "Consultation d'urgence ?"
            ])

        # Combiner et limiter à 5 suggestions
        all_suggestions = contextual_suggestions + base_suggestions
        return all_suggestions[:5]

    def get_quick_actions(self, conversation_type: str) -> List[Dict[str, str]]:
        """Génère des actions rapides avec icônes"""
        actions_map = {
            'greeting': [
                {'text': '🚨 Urgence', 'action': 'emergency'},
                {'text': '😣 J\'ai mal', 'action': 'pain'},
                {'text': '💊 Médicaments', 'action': 'medication'},
                {'text': '❓ Informations', 'action': 'info'}
            ],
            'emergency': [
                {'text': '📞 Appeler 115', 'action': 'call_emergency'},
                {'text': '📍 Ma position', 'action': 'location'},
                {'text': '🆔 Mes infos médicales', 'action': 'medical_id'},
                {'text': '👥 Contacter proche', 'action': 'contact_family'}
            ],
            'pain_management': [
                {'text': '🔢 Niveau douleur', 'action': 'pain_scale'},
                {'text': '📍 Localisation', 'action': 'pain_location'},
                {'text': '💊 Antidouleurs', 'action': 'pain_medication'},
                {'text': '🚨 C\'est urgent', 'action': 'escalate_emergency'}
            ]
        }

        return actions_map.get(conversation_type, [])

# Instance globale
smart_suggestions = SmartSuggestions()
