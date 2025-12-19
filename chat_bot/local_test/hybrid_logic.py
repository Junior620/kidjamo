"""
Logique hybride : Détection règles + IA générative
Combine la précision médicale avec des réponses naturelles
"""

import logging
from typing import Dict, Any
from datetime import datetime
from session_manager import session_manager
from ai_engine import ai_engine
import re

logger = logging.getLogger(__name__)

def process_message_with_ai(user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Version hybride : utilise les règles pour la classification et l'IA pour les réponses
    """
    try:
        if not user_input or not user_input.strip():
            return ai_engine.generate_response(
                "L'utilisateur a envoyé un message vide",
                context or {},
                "error"
            )

        # Récupérer le contexte de session
        session_id = context.get('session_id', 'default') if context else 'default'
        session_context = session_manager.get_context_for_ai(session_id)

        # Enrichir le contexte avec l'historique récent
        enhanced_context = {
            **session_context,
            **(context or {}),
            'recent_messages': session_manager.get_recent_messages(session_id, limit=3)
        }

        input_lower = user_input.lower().strip()
        logger.info(f"Message traité avec IA: {user_input[:50]}... (Session: {session_id})")

        # === CLASSIFICATION INTELLIGENTE ===
        conversation_type, priority_level = classify_message_with_context(input_lower, enhanced_context)

        # Ajouter le type détecté au contexte
        enhanced_context['conversation_type'] = conversation_type
        enhanced_context['priority_level'] = priority_level

        # === GESTION DES URGENCES ABSOLUES ===
        if priority_level == "CRITICAL" and conversation_type == "emergency":
            # Pour les urgences critiques, on force une réponse d'urgence même avec l'IA
            response_data = ai_engine.generate_response(
                user_input,
                enhanced_context,
                "emergency"
            )
            # Marquer le contexte d'urgence
            session_manager.set_emergency_context(session_id, True)
            session_manager.add_message(session_id, user_input, response_data['response'], 'emergency')
            return response_data

        # === GESTION CONTEXTUELLE INTELLIGENTE ===

        # Si on était en urgence et que l'utilisateur pose une question vague
        if enhanced_context.get('emergency_context') and conversation_type == "general":
            # Réinterpréter comme une question d'urgence contextuelle
            conversation_type = "emergency_followup"
            enhanced_context['conversation_type'] = conversation_type

        # Si on était en crise de douleur et nouveau message de douleur
        if enhanced_context.get('current_crisis') and conversation_type == "pain":
            # Suivre l'évolution de la douleur
            pain_level = extract_pain_level(input_lower)
            if pain_level:
                enhanced_context['pain_evolution'] = {
                    'previous': enhanced_context.get('pain_level', 0),
                    'current': pain_level,
                    'trend': 'improving' if pain_level < enhanced_context.get('pain_level', 0) else 'worsening'
                }

        # === GÉNÉRATION DE RÉPONSE AVEC IA ===
        response_data = ai_engine.generate_response(
            user_input,
            enhanced_context,
            conversation_type
        )

        # === MISE À JOUR DU CONTEXTE POST-RÉPONSE ===
        update_session_context_post_response(session_id, user_input, response_data, enhanced_context)

        # Enregistrer l'échange
        session_manager.add_message(
            session_id,
            user_input,
            response_data['response'],
            conversation_type
        )

        return response_data

    except Exception as e:
        logger.error(f"Erreur dans process_message_with_ai: {e}")
        return ai_engine.generate_response(
            f"Erreur technique lors du traitement de: {user_input}",
            context or {},
            "error"
        )

def classify_message_with_context(text: str, context: Dict[str, Any]) -> tuple:
    """
    Classification intelligente avec prise en compte du contexte
    Retourne (conversation_type, priority_level)
    """

    # === ANALYSE DU CONTEXTE CONVERSATIONNEL ===
    previous_type = context.get('last_conversation_type')
    emergency_active = context.get('emergency_context', False)
    crisis_active = context.get('current_crisis', False)

    # === URGENCES ABSOLUES (PRIORITY: CRITICAL) ===
    if detect_critical_emergency(text, context):
        return ("emergency", "CRITICAL")

    # === QUESTIONS DE SUIVI D'URGENCE ===
    # Si on était en urgence et que l'utilisateur pose une question de suivi
    if emergency_active and detect_followup_question(text):
        return ("emergency_followup", "HIGH")

    # === ÉVOLUTION DE DOULEUR ===
    # Si on était en crise et nouveau message sur douleur
    if crisis_active and detect_pain_general(text):
        return ("pain_evolution", "HIGH")

    # === URGENCES CONTEXTUELLES (PRIORITY: HIGH) ===
    if detect_contextual_emergency(text, context):
        return ("emergency", "HIGH")

    # === DOULEUR SÉVÈRE (PRIORITY: HIGH) ===
    if detect_severe_pain(text, context):
        return ("pain", "HIGH")

    # === SALUTATIONS (PRIORITY: NORMAL) ===
    if detect_greeting(text):
        return ("greeting", "NORMAL")

    # === REMERCIEMENTS - Réinitialise le contexte ===
    if detect_gratitude(text):
        return ("gratitude", "LOW")

    # === QUESTIONS VAGUES DANS CONTEXTE MÉDICAL ===
    if detect_vague_medical_question(text, context):
        if crisis_active or emergency_active:
            return ("contextual_help", "MEDIUM")
        else:
            return ("general_help", "LOW")

    # === DOULEUR MODÉRÉE (PRIORITY: MEDIUM) ===
    if detect_pain_general(text):
        return ("pain", "MEDIUM")

    # === MÉDICAMENTS (PRIORITY: MEDIUM) ===
    if detect_medication_topic(text):
        return ("medication", "MEDIUM")

    # === QUESTIONS MÉDICALES (PRIORITY: MEDIUM) ===
    if detect_medical_education(text):
        return ("medical_education", "MEDIUM")

    # === QUESTIONS APPLICATION (PRIORITY: LOW) ===
    if detect_app_usage(text):
        return ("app_help", "LOW")

    # === IDENTITÉ BOT (PRIORITY: LOW) ===
    if detect_bot_identity(text):
        return ("bot_identity", "LOW")

    # === CONVERSATION GÉNÉRALE (PRIORITY: LOW) ===
    return ("general", "LOW")

def detect_followup_question(text: str) -> bool:
    """Détecte les questions de suivi après une urgence"""
    followup_patterns = [
        r'\b(que.*faire|quoi.*faire|comment.*faire)\b',
        r'\b(dois.*aller|dois.*appeler|dois.*consulter)\b',
        r'\b(maintenant|après|ensuite)\b',
        r'\b(ça ne passe pas|toujours mal|encore mal)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in followup_patterns)

def detect_critical_emergency(text: str, context: Dict[str, Any]) -> bool:
    """Détecte les urgences critiques nécessitant une action immédiate"""
    critical_patterns = [
        # Détresse respiratoire
        r'\b(ne peux (plus|pas) respirer|n\'arrive plus à respirer)\b',
        r'\b(suffoque|étoffe|asphyxie)\b',

        # Douleur extrême avec échec de traitement
        r'\b(douleur.*([89]|10).*(sur|/).*10|([89]|10)/10)\b',
        r'\b(paracétamol.*ne.*marche.*pas|antidouleur.*inefficace)\b',

        # Perte de conscience
        r'\b(je (m\'évanouis|perds connaissance)|syncope)\b',

        # Appel direct aux secours
        r'\b(appelez.*samu|appelez.*115|appelez.*secours)\b'
    ]

    # Si déjà en contexte d'urgence et aggravation
    if context.get('emergency_context'):
        aggravation_patterns = [
            r'\b(empire|pire|plus mal|aggrave)\b',
            r'\b(toujours.*mal|encore.*mal)\b'
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in aggravation_patterns):
            return True

    return any(re.search(pattern, text, re.IGNORECASE) for pattern in critical_patterns)

def detect_contextual_emergency(text: str, context: Dict[str, Any]) -> bool:
    """Détecte les urgences basées sur le contexte conversationnel"""

    # Questions vagues mais dans un contexte de douleur sévère
    pain_level = context.get('pain_level')
    if pain_level is not None and pain_level >= 7:
        vague_emergency_patterns = [
            r'\b(que.*faire|quoi.*faire|comment.*faire)\b',
            r'\b(dois.*aller.*urgences?|dois.*consulter)\b',
            r'\b(ça ne passe pas|ne marche pas|inefficace)\b'
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in vague_emergency_patterns):
            return True

    # Demandes d'aide dans contexte de crise
    if context.get('current_crisis'):
        help_patterns = [
            r'\b(aide|aidez|help|au secours)\b',
            r'\b(que.*dois.*faire|qu\'est-ce.*faire)\b'
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in help_patterns):
            return True

    return False

def detect_severe_pain(text: str, context: Dict[str, Any]) -> bool:
    """Détecte les douleurs sévères (niveau 7+)"""
    severe_pain_patterns = [
        r'\b(douleur (intense|atroce|insupportable|terrible|sévère))\b',
        r'\b(très mal|mal terrible|mal atroce)\b',
        r'\b(([7-9]|10).*/.*10|([7-9]|10)/10)\b',
        r'\b(crise (grave|sévère))\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in severe_pain_patterns)

def extract_pain_level(text: str) -> int:
    """Extrait le niveau de douleur du texte (0-10)"""
    pain_patterns = [
        r'\b([0-9]|10).*/.*10\b',  # Format X/10
        r'\b([0-9]|10)/10\b',      # Format X/10 sans espace
        r'\bdouleur.*([0-9]|10)\b'  # "douleur 8", etc.
    ]

    for pattern in pain_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except:
                continue
    return 0

# Fonctions de détection simplifiées (reprendre les anciennes mais épurées)
def detect_greeting(text: str) -> bool:
    patterns = [r'\b(bonjour|bonsoir|salut|hello|coucou|hey)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_gratitude(text: str) -> bool:
    patterns = [r'\b(merci|thanks|thx|remercie)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_pain_general(text: str) -> bool:
    patterns = [r'\b(j\'ai mal|ça fait mal|douleur|mal (au|à la|aux))\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_medication_topic(text: str) -> bool:
    patterns = [r'\b(médicament|traitement|hydroxyurée|siklos|paracétamol|antalgique)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_medical_education(text: str) -> bool:
    patterns = [r'\b(drépanocytose|c\'est quoi|qu\'est-ce que|comment.*ça|pourquoi)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_app_usage(text: str) -> bool:
    patterns = [r'\b(application|app|kidjamo|utiliser|fonctionner|bracelet)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_bot_identity(text: str) -> bool:
    patterns = [r'\b(qui.*tu|tu es qui|votre nom|comment.*appelles)\b']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def detect_vague_medical_question(text: str, context: Dict[str, Any]) -> bool:
    """Détecte les questions vagues qui nécessitent une contextualisation"""
    vague_patterns = [
        r'^\b(que.*faire|quoi.*faire|comment)\b.*\?$',
        r'^\b(aide|aidez|help)\b\.?$',
        r'^\b(c\'est quoi|qu\'est-ce)\b.*\?$'
    ]
    return any(re.search(pattern, text.strip(), re.IGNORECASE) for pattern in vague_patterns)

def update_session_context_post_response(session_id: str, user_input: str, response_data: Dict, context: Dict):
    """Met à jour le contexte de session après génération de réponse"""

    conversation_type = response_data.get('conversation_type', 'general')

    # Sauvegarder le type de conversation précédent
    session_manager.set_last_conversation_type(session_id, conversation_type)

    # Mettre à jour le niveau de douleur si détecté
    pain_level = extract_pain_level(user_input.lower())
    if pain_level > 0:
        session_manager.update_pain_level(session_id, pain_level)

        # Marquer comme crise si douleur >= 7
        if pain_level >= 7:
            session_manager.set_crisis_context(session_id, True)

    # Gérer les contextes d'urgence
    if conversation_type in ["emergency", "emergency_followup"]:
        session_manager.set_emergency_context(session_id, True)

    # Réinitialiser les contextes si remerciement ou conversation terminée
    if conversation_type == "gratitude":
        session_manager.reset_crisis_context(session_id)
        session_manager.set_emergency_context(session_id, False)
