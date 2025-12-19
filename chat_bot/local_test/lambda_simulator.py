"""
Simulateur local des fonctions Lambda Kidjamo
Utilise la VRAIE logique des Lambda adaptée pour le mode local
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import re

# Import des VRAIES fonctions Lambda adaptées pour le local
from lambda_real_logic import (
    lambda_handler_general_conversation,
    lambda_handler_lex_fulfillment
)

logger = logging.getLogger(__name__)

def detect_intent_and_route(user_input: str, user_id: str = 'local-user') -> Dict[str, Any]:
    """
    Détecte l'intention et route vers la VRAIE fonction Lambda appropriée
    """
    input_lower = user_input.lower()

    # Détection d'intention sophistiquée
    intent_detection = analyze_user_intent(input_lower)
    intent_name = intent_detection['intent']
    confidence = intent_detection['confidence']

    logger.info(f"Intent détecté: {intent_name} (confiance: {confidence})")

    try:
        # Routage vers les VRAIES fonctions Lambda
        if intent_name in ['ConversationGenerale', 'QuestionsGenerales', 'DiscussionLibre',
                          'ConseilsVieQuotidienne', 'CultureEducation']:
            # Utilisation de la VRAIE fonction general_conversation
            event = {
                'intent_name': intent_name,
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {
                    'timestamp': datetime.now().isoformat(),
                    'confidence': confidence
                }
            }
            return lambda_handler_general_conversation(event)

        elif intent_name in ['SignalerDouleur', 'GestionMedicaments', 'Urgence',
                           'ConsulterDonneesVitales', 'DemandeAide']:
            # Utilisation de la VRAIE fonction lex_fulfillment
            slots = extract_slots_from_input(user_input, intent_name)
            event = {
                'intent_name': intent_name,
                'user_input': user_input,
                'user_id': user_id,
                'slots': slots
            }
            return lambda_handler_lex_fulfillment(event)

        else:
            # Fallback vers conversation générale
            event = {
                'intent_name': 'ConversationGenerale',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            }
            return lambda_handler_general_conversation(event)

    except Exception as e:
        logger.error(f"Erreur lors du routage: {str(e)}")
        return {
            'success': False,
            'response': f"Désolé, je rencontre un problème technique. Pouvez-vous reformuler ? (Erreur: {str(e)})",
            'conversation_type': 'error',
            'error': str(e)
        }

def analyze_user_intent(input_lower: str) -> Dict[str, Any]:
    """
    Analyse sophistiquée de l'intention utilisateur
    """

    # Patterns d'intention avec scores de confiance
    intent_patterns = {
        'SignalerDouleur': {
            'keywords': ['mal', 'douleur', 'souffre', 'fait mal', 'intense', 'douloureux'],
            'patterns': [r'j\'ai mal', r'mal au', r'douleur', r'intensité \d+', r'ça fait mal'],
            'confidence_boost': 0.3
        },
        'GestionMedicaments': {
            'keywords': ['médicament', 'traitement', 'pilule', 'hydroxyurée', 'acide folique', 'rappel'],
            'patterns': [r'mes médicaments', r'rappel', r'traitement', r'pilule'],
            'confidence_boost': 0.2
        },
        'Urgence': {
            'keywords': ['urgence', 'urgent', 'aide urgente', 'emergency', 'critique'],
            'patterns': [r'urgence', r'urgent', r'aide d\'urgence'],
            'confidence_boost': 0.4
        },
        'ConsulterDonneesVitales': {
            'keywords': ['données', 'vitales', 'mesures', 'bracelet', 'capteur', 'rythme cardiaque'],
            'patterns': [r'mes données', r'données vitales', r'mesures', r'bracelet'],
            'confidence_boost': 0.3
        },
        'DemandeAide': {
            'keywords': ['aide', 'help', 'comment', 'guide', 'utilisation'],
            'patterns': [r'aide', r'comment utiliser', r'guide', r'help'],
            'confidence_boost': 0.2
        },
        'QuestionsGenerales': {
            'keywords': ['qu\'est-ce que', 'comment', 'pourquoi', 'qui es-tu', 'ton nom', 'kidjamo', 'drépanocytose', 'blague', 'rigolo', 'drôle', 'humour', 'raconte', 'truc rigolo'],
            'patterns': [r'qu\'est-ce que', r'qui es-tu', r'qui êtes-vous', r'ton nom', r'comment', r'blague', r'rigolo', r'drôle', r'humour', r'raconte.*blague', r'truc rigolo', r'donne.*rigolo'],
            'confidence_boost': 0.3
        },
        'DiscussionLibre': {
            'keywords': ['ennuie', 'seul', 'discuter', 'parler', 'bavarder', 'tenir compagnie', 'm\'ennuie', 'je m\'ennuie'],
            'patterns': [r'm\'ennuie', r'je m\'ennuie', r'discuter', r'parler', r'bavarder', r'je suis seul', r'j\'ennuie'],
            'confidence_boost': 0.3
        },
        'ConseilsVieQuotidienne': {
            'keywords': ['conseils', 'dormir', 'sommeil', 'stress', 'motivation', 'alimentation'],
            'patterns': [r'conseils', r'comment dormir', r'stress', r'motivation'],
            'confidence_boost': 0.2
        },
        'CultureEducation': {
            'keywords': ['science', 'histoire', 'art', 'musique', 'langue', 'apprendre'],
            'patterns': [r'science', r'histoire', r'art', r'apprendre'],
            'confidence_boost': 0.1
        },
        'ConversationGenerale': {
            'keywords': ['bonjour', 'salut', 'hello', 'bonsoir', 'ça va', 'ca va', 'comment allez-vous', 'comment tu vas', 'comment vous allez', 'merci', 'tu vas bien', 'vous allez bien'],
            'patterns': [r'bonjour', r'salut', r'hello', r'ça va', r'ca va', r'comment ça va', r'comment ca va', r'comment tu vas', r'comment allez-vous', r'comment vous allez'],
            'confidence_boost': 0.3
        }
    }

    # Calcul des scores pour chaque intention
    intent_scores = {}

    for intent, config in intent_patterns.items():
        score = 0.0

        # Score basé sur les mots-clés
        for keyword in config['keywords']:
            if keyword in input_lower:
                score += 0.15  # Augmenté pour mieux détecter

        # Score basé sur les patterns regex
        for pattern in config['patterns']:
            if re.search(pattern, input_lower):
                score += config['confidence_boost']

        intent_scores[intent] = score

    # Détection spéciale pour les combinaisons
    # Si on détecte "blague" ET "ennuie", on privilégie QuestionsGenerales pour les blagues
    if any(word in input_lower for word in ['blague', 'rigolo', 'drôle', 'humour', 'raconte']) and \
       any(word in input_lower for word in ['ennuie', 'm\'ennuie']):
        intent_scores['QuestionsGenerales'] += 0.4  # Boost pour les blagues

    # Intention avec le score le plus élevé
    if intent_scores:
        best_intent = max(intent_scores, key=intent_scores.get)
        best_score = intent_scores[best_intent]

        # Si score trop faible, fallback vers conversation générale
        if best_score < 0.1:
            best_intent = 'ConversationGenerale'
            best_score = 0.5

        return {
            'intent': best_intent,
            'confidence': min(best_score, 1.0),
            'all_scores': intent_scores
        }

    # Fallback par défaut
    return {
        'intent': 'ConversationGenerale',
        'confidence': 0.5,
        'all_scores': {}
    }

def extract_slots_from_input(user_input: str, intent_name: str) -> Dict[str, Any]:
    """
    Extrait les slots spécifiques selon l'intention
    """
    slots = {}

    if intent_name == 'SignalerDouleur':
        slots.update(extract_pain_slots(user_input))
    elif intent_name == 'GestionMedicaments':
        slots.update(extract_medication_slots(user_input))
    elif intent_name == 'ConsulterDonneesVitales':
        slots.update(extract_vitals_slots(user_input))

    return slots

def extract_pain_slots(user_input: str) -> Dict[str, Any]:
    """Extrait les slots pour les signalements de douleur"""
    slots = {}

    # Extraction de l'intensité (1-10)
    intensite_match = re.search(r'\b([1-9]|10)\b', user_input)
    if intensite_match:
        slots['IntensiteDouleur'] = {
            'value': {
                'interpretedValue': intensite_match.group(1)
            }
        }

    # Extraction de la localisation
    user_input_lower = user_input.lower()
    localisation = None

    if any(loc in user_input_lower for loc in ['dos', 'back']):
        localisation = "dos"
    elif any(loc in user_input_lower for loc in ['ventre', 'abdomen', 'abdominal']):
        localisation = "abdomen"
    elif any(loc in user_input_lower for loc in ['jambe', 'bras', 'membre']):
        localisation = "membres"
    elif any(loc in user_input_lower for loc in ['tête', 'crâne', 'migraine']):
        localisation = "tête"
    elif any(loc in user_input_lower for loc in ['poitrine', 'thorax', 'poumon']):
        localisation = "thorax"

    if localisation:
        slots['LocalisationDouleur'] = {
            'value': {
                'interpretedValue': localisation
            }
        }

    # Extraction de la durée
    duree_patterns = [
        (r'depuis (\d+) heure', 'heures'),
        (r'depuis (\d+) jour', 'jours'),
        (r'(\d+)h', 'heures'),
        (r'depuis ce matin', 'depuis ce matin'),
        (r'depuis hier', 'depuis hier')
    ]

    for pattern, unit in duree_patterns:
        match = re.search(pattern, user_input_lower)
        if match:
            if unit in ['heures', 'jours']:
                duree_value = f"{match.group(1)} {unit}"
            else:
                duree_value = unit

            slots['DureeDouleur'] = {
                'value': {
                    'interpretedValue': duree_value
                }
            }
            break

    return slots

def extract_medication_slots(user_input: str) -> Dict[str, Any]:
    """Extrait les slots pour la gestion des médicaments"""
    slots = {}
    user_input_lower = user_input.lower()

    # Détection du médicament
    medications = {
        'hydroxyuree': ['hydroxyurée', 'hydrea', 'hydroxyuree'],
        'acide_folique': ['acide folique', 'spéciafoldine', 'folique'],
        'paracetamol': ['paracétamol', 'doliprane', 'efferalgan']
    }

    for med_key, med_names in medications.items():
        if any(name in user_input_lower for name in med_names):
            slots['NomMedicament'] = {
                'value': {
                    'interpretedValue': med_key
                }
            }
            break

    # Détection de l'action
    if any(action in user_input_lower for action in ['rappel', 'rappeler', 'alarme']):
        slots['ActionMedicament'] = {
            'value': {
                'interpretedValue': 'rappel'
            }
        }
    elif any(action in user_input_lower for action in ['information', 'info', 'qu\'est-ce']):
        slots['ActionMedicament'] = {
            'value': {
                'interpretedValue': 'information'
            }
        }

    return slots

def extract_vitals_slots(user_input: str) -> Dict[str, Any]:
    """Extrait les slots pour la consultation des données vitales"""
    slots = {}
    user_input_lower = user_input.lower()

    # Type de données demandées
    if any(vital in user_input_lower for vital in ['cardiaque', 'coeur', 'pouls']):
        slots['TypeDonnees'] = {
            'value': {
                'interpretedValue': 'rythme_cardiaque'
            }
        }
    elif any(vital in user_input_lower for vital in ['température', 'fièvre']):
        slots['TypeDonnees'] = {
            'value': {
                'interpretedValue': 'température'
            }
        }
    elif any(vital in user_input_lower for vital in ['oxygène', 'saturation', 'spo2']):
        slots['TypeDonnees'] = {
            'value': {
                'interpretedValue': 'saturation_oxygene'
            }
        }

    return slots

# Fonction de compatibilité pour l'ancien système
def lambda_simulator(*args, **kwargs):
    """Fonction de compatibilité - redirige vers detect_intent_and_route"""
    if args:
        user_input = args[0] if len(args) > 0 else kwargs.get('user_input', '')
    else:
        user_input = kwargs.get('user_input', '')

    return detect_intent_and_route(user_input)
