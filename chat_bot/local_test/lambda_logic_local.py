"""
Version locale des fonctions Lambda Kidjamo
Extrait la vraie logique métier sans les dépendances AWS
VERSION AMÉLIORÉE AVEC GESTION DE CONTEXTE
"""

import random
import logging
from datetime import datetime
from typing import Dict, Any, List
import re
from session_manager import session_manager

logger = logging.getLogger(__name__)

# ========== FONCTION PRINCIPALE DE ROUTING AMÉLIORÉE ==========

def process_message(user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Fonction principale qui route les messages vers la bonne logique
    VERSION AMÉLIORÉE avec gestion de contexte et sessions
    """
    try:
        if not user_input or not user_input.strip():
            return {
                'success': False,
                'response': "Je n'ai pas bien saisi votre message. Pouvez-vous reformuler ?",
                'conversation_type': 'error'
            }

        # Récupérer ou créer la session
        session_id = context.get('session_id', 'default') if context else 'default'
        session_context = session_manager.get_context_for_ai(session_id)

        input_lower = user_input.lower().strip()
        logger.info(f"Traitement du message: {input_lower} (Session: {session_id})")

        # LOGIQUE CONTEXTUELLE AMÉLIORÉE

        # Si on est déjà dans un contexte de crise, prioriser les urgences
        if session_context.get('emergency_context') or session_context.get('current_crisis'):
            if detect_emergency_contextual(input_lower, session_context):
                response = handle_emergency({'inputTranscript': user_input}, session_context)
                session_manager.add_message(session_id, user_input, response['response'], 'emergency')
                return response

        # 1. SALUTATIONS (priorité haute pour accueil)
        if detect_greeting(input_lower):
            response = handle_greeting(user_input, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'greeting')
            return response

        # 2. URGENCES (priorité absolue)
        if detect_emergency(input_lower):
            response = handle_emergency({'inputTranscript': user_input}, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'emergency')
            return response

        # 3. REMERCIEMENTS (avec contexte)
        if detect_gratitude(input_lower):
            # Si on était en crise, réinitialiser le contexte
            if session_context.get('current_crisis'):
                session_manager.reset_crisis_context(session_id)
            response = handle_gratitude(user_input, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'gratitude')
            return response

        # 4. DOULEUR ET SYMPTÔMES (avec suivi de l'évolution)
        if detect_pain(input_lower):
            response = handle_pain_report({'inputTranscript': user_input}, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'pain_management')
            return response

        # 5. MÉDICAMENTS (avec historique)
        if detect_medication(input_lower):
            response = handle_medication_management({'inputTranscript': user_input}, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'medication')
            return response

        # 6. QUESTIONS SUR LA DRÉPANOCYTOSE
        if detect_medical_question(input_lower):
            response = handle_medical_knowledge(user_input, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'medical_info')
            return response

        # 7. QUESTIONS SUR L'APPLICATION
        if detect_app_question(input_lower):
            response = handle_app_information(user_input, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'app_info')
            return response

        # 8. IDENTITÉ DU BOT
        if detect_identity_question(input_lower):
            response = handle_identity_question(user_input, session_context)
            session_manager.add_message(session_id, user_input, response['response'], 'identity')
            return response

        # 9. CONVERSATION GÉNÉRALE (avec suggestions contextuelles)
        response = handle_general_conversation(user_input, session_context)
        session_manager.add_message(session_id, user_input, response['response'], 'general')
        return response

    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {e}")
        return {
            'success': False,
            'response': "Désolé, j'ai rencontré une erreur technique. Pouvez-vous reformuler votre question ?",
            'conversation_type': 'error'
        }

# ========== NOUVELLES FONCTIONS DE DÉTECTION CONTEXTUELLE ==========

def detect_emergency_contextual(text: str, context: Dict[str, Any]) -> bool:
    """Détection d'urgence améliorée avec contexte"""
    # Si on a déjà un niveau de douleur élevé, des questions vagues deviennent urgentes
    if context.get('pain_level', 0) >= 7:
        contextual_patterns = [
            r'\b(que.*faire|quoi.*faire|comment.*faire)\b',
            r'\b(ça.*empire|pire|plus.*mal)\b',
            r'\b(toujours.*mal|encore.*mal)\b'
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in contextual_patterns):
            return True

    # Si on était déjà en contexte d'urgence
    if context.get('emergency_context'):
        simple_questions = [
            r'\b(et.*maintenant|après|suite)\b',
            r'\b(combien.*temps|quand.*venir)\b'
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in simple_questions):
            return True

    return False

# ========== FONCTIONS DE ROUTING ET GESTION DES RÉPONSES ==========

def detect_greeting(text: str) -> bool:
    """Détecte les salutations"""
    greeting_patterns = [
        r'\b(bonjour|bonsoir|salut|hello|coucou|hey)\b',
        r'\b(comment ça va|comment allez-vous)\b',
        r'\b(bonne (matinée|journée|soirée))\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in greeting_patterns)

def detect_emergency(text: str) -> bool:
    """Détecte les situations d'urgence - VERSION AMÉLIORÉE"""
    emergency_patterns = [
        # Demandes d'aide directes
        r'\b(aide(-moi)?|aidez-moi|help|au secours)\b',
        r'\b(urgence|urgent|très urgent)\b',
        r'\b(samu|pompiers|ambulance|hôpital)\b',

        # Douleurs intenses
        r'\b(douleur (intense|atroce|insupportable|terrible))\b',
        r'\b(très mal|mal terrible|souffrance atroce)\b',
        r'\b(je meurs|je vais mourir|je crève)\b',

        # Symptômes respiratoires critiques
        r'\b(ne peux (plus|pas) respirer|n\'arrive plus à respirer)\b',
        r'\b(souffle|suffoque|étoffe|respiration difficile)\b',
        r'\b(essoufflement sévère|dyspnée)\b',

        # Échelle de douleur élevée (nouveau)
        r'\b(douleur.*[8-9]|[8-9].*/.*10|douleur.*10)\b',
        r'\b([8-9]/10|10/10)\b',

        # Questions d'urgence contextuelle (amélioré)
        r'\b(dois.*aller.*urgences?|dois.*consulter.*urgence)\b',
        r'\b(que.*dois.*faire|quoi.*faire|qu\'est-ce.*dois.*faire)\b',
        r'\b(ça ne passe pas|ne passe plus|inefficace|ne marche pas|sans effet)\b',

        # Échec de traitement (nouveau)
        r'\b(paracétamol.*ne.*passe.*pas|antidouleur.*inefficace)\b',
        r'\b(traitement.*ne.*marche.*pas|médicament.*sans.*effet)\b',
        r'\b(déjà.*pris.*mais|déjà.*pris.*ça.*ne)\b',

        # Crises et complications
        r'\b(crise (grave|sévère)|syndrome thoracique)\b',
        r'\b(syncope|évanouir|perte de connaissance)\b',
        r'\b(convulsion|spasme|paralysie)\b',

        # États critiques
        r'\b(ne peux (plus|pas) bouger|paralysé)\b',
        r'\b(saignement|hémorragie|sang)\b',
        r'\b(fièvre très élevée|température très haute)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in emergency_patterns)

def detect_pain(text: str) -> bool:
    """Détecte les signalements de douleur - VERSION AMÉLIORÉE"""
    pain_patterns = [
        # Expressions directes de douleur
        r'\b(j\'ai mal|ça fait mal|j\'ai des douleurs?|je souffre)\b',
        r'\b(mal (au|à la|aux|dans le|dans la))\b',
        r'\b(douleur|douloureux|douloureuse)\b',
        r'\b(souffre|souffrir|souffrance)\b',

        # Types de douleurs spécifiques
        r'\b(crampe|crampes|élancement|élancements)\b',
        r'\b(tiraillement|tiraillements|picotement|picotements)\b',
        r'\b(brûlure|brûlures|sensation de brûlure)\b',
        r'\b(pincement|pincements|serrement|serrements)\b',

        # Localisations anatomiques avec douleur
        r'\b(dos|ventre|tête|jambe|bras|poitrine|abdomen)\b.*\b(mal|douleur|fait mal)\b',
        r'\b(mal|douleur|fait mal)\b.*\b(dos|ventre|tête|jambe|bras|poitrine|abdomen)\b',

        # Expressions familières
        r'\b(ça me fait mal|c\'est douloureux|ça tire|ça lance)\b',
        r'\b(j\'ai une douleur|je ressens une douleur)\b',
        r'\b(ça me fait souffrir|c\'est insupportable)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in pain_patterns)

def detect_medication(text: str) -> bool:
    """Détecte les questions sur les médicaments - VERSION AMÉLIORÉE"""
    medication_patterns = [
        # Médicaments spécifiques
        r'\b(médicament|traitement|pilule|comprimé|sirop)\b',
        r'\b(hydroxyurée|siklos|acide folique|paracétamol)\b',
        r'\b(antalgique|antidouleur|morphine|tramadol)\b',

        # Actions liées aux médicaments
        r'\b(rappel|prendre|oublié|dose|posologie)\b',
        r'\b(prescription|ordonnance|pharmacie)\b',
        r'\b(j\'ai oublié|oublié de prendre)\b',

        # Questions sur effets et utilisation - AMÉLIORÉES
        r'\b(effets? secondaires?|effet indésirable)\b',
        r'\b(que faire|quoi faire|comment faire)\b',
        r'\b(à quelle heure|quand prendre|horaire|moment)\b',
        r'\b(combien|quelle dose|dosage|quantité)\b',

        # Questions générales dans contexte médical
        r'\b(contre-indication|interaction|précaution)\b',
        r'\b(arrêter|stopper|modifier|changer).*\b(traitement|médicament)\b',

        # Expressions courantes avec médicaments
        r'\b(prendre (le|la|les|mon|ma|mes))\b',
        r'\b(avaler|ingérer|administrer)\b',
        r'\b(surdosage|sous-dosage|manqué|raté)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in medication_patterns)

def detect_medical_question(text: str) -> bool:
    """Détecte les questions médicales sur la drépanocytose - VERSION AMÉLIORÉE"""
    medical_patterns = [
        # Questions directes sur la maladie
        r'\b(drépanocytose|anémie falciforme|sicklémie)\b',

        # Questions explicatives
        r'\b(qu\'est-ce que c\'est|qu est-ce que c est|c\'est quoi|c est quoi)\b',
        r'\b(expliquez(-moi)?|expliquer|définition|définir)\b',
        r'\b(comment ça marche|comment ca marche|qu\'est-ce qui se passe)\b',

        # Questions sur gravité et pronostic
        r'\b(grave|gravité|sérieux|sévère|dangereux)\b',
        r'\b(pronostic|évolution|espérance de vie|mortel)\b',
        r'\b(est-ce que c\'est|est ce que c est).*\b(grave|sérieux|important)\b',

        # Questions sur traitements
        r'\b(traitement|traitements|soigner|guérir|guérison)\b',
        r'\b(médicament|médicaments|remède|thérapie)\b',
        r'\b(comment (traiter|soigner))\b',
        r'\b(quels? (traitement|médicament)s?)\b',

        # Questions sur prévention
        r'\b(éviter|prévenir|prévention|empêcher)\b.*\b(crise|crises|douleur)\b',
        r'\b(comment (éviter|prévenir|empêcher))\b',
        r'\b(conseils?|recommandation|que faire pour)\b',

        # Questions sur causes et symptômes
        r'\b(symptôme|symptômes|signes?|manifeste)\b',
        r'\b(cause|causes|pourquoi|comment on l?\'?attrape)\b',
        r'\b(transmission|héréditaire|génétique|hérédité)\b',
        r'\b(se transmet|transmis|contagieux)\b',

        # Questions sur complications
        r'\b(complication|complications|conséquence|risque)\b',
        r'\b(peut arriver|que se passe|dangereux)\b',

        # Termes médicaux spécifiques
        r'\b(globule|hémoglobine|faucille|vaso-occlusif)\b',
        r'\b(hémoglobine s|hbs|homozygote|hétérozygote)\b',
        r'\b(crise|crises|douleur|anémie)\b.*\b(pourquoi|comment|quoi)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in medical_patterns)

def detect_app_question(text: str) -> bool:
    """Détecte les questions sur l'application"""
    app_patterns = [
        r'\b(application|app|kidjamo)\b',
        r'\b(comment (ça marche|utiliser))\b',
        r'\b(bracelet|iot|connecté)\b',
        r'\b(fonctionnalité|feature)\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in app_patterns)

def detect_identity_question(text: str) -> bool:
    """Détecte les questions sur l'identité du bot"""
    identity_patterns = [
        r'\b(qui (es-tu|êtes-vous|est-tu))\b',
        r'\b((ton|votre) nom)\b',
        r'\b(présente(-toi|-vous))\b',
        r'\b(tu es (qui|quoi))\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in identity_patterns)

def detect_gratitude(text: str) -> bool:
    """Détecte les remerciements et expressions de gratitude"""
    gratitude_patterns = [
        r'\b(merci|merci beaucoup|je vous remercie)\b',
        r'\b(c\'est gentil|très gentil|sympa)\b',
        r'\b(parfait|excellent|super|génial)\b.*\b(merci|conseil)\b',
        r'\b(au revoir|à bientôt|bonne (journée|soirée))\b'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in gratitude_patterns)

# ========== GESTIONNAIRES DE RÉPONSES AMÉLIORÉES ==========

def handle_greeting(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les salutations avec une réponse personnalisée"""
    return {
        'success': True,
        'response': """<div class="response-section medical-info">
            <h3><i class="fas fa-user-md"></i> Bonjour ! Je suis votre assistant santé Kidjamo</h3>
            <p>Je suis spécialisé dans l'accompagnement des patients atteints de drépanocytose. Je peux vous aider avec :</p>
            <ul class="help-list">
                <li><strong>🩺 Gestion de la douleur</strong> - Évaluation et conseils personnalisés</li>
                <li><strong>💊 Suivi des médicaments</strong> - Rappels et interactions</li>
                <li><strong>📊 Données vitales</strong> - Analyse de vos mesures IoT</li>
                <li><strong>🚨 Urgences médicales</strong> - Protocoles et contacts d'urgence</li>
                <li><strong>📚 Éducation thérapeutique</strong> - Informations sur votre maladie</li>
            </ul>
            <p><strong>Comment puis-je vous aider aujourd'hui ?</strong></p>
        </div>""",
        'conversation_type': 'greeting'
    }

def handle_emergency(event: Dict[str, Any], session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les situations d'urgence avec réponses contextuelles"""
    user_input = event.get('inputTranscript', '').lower()

    # Analyser le type d'urgence pour donner une réponse plus spécifique
    emergency_type = ""
    specific_advice = ""

    # Problèmes respiratoires
    if any(word in user_input for word in ['respirer', 'souffle', 'suffoque', 'étoffe', 'essoufflement', 'dyspnée']):
        emergency_type = "PROBLÈME RESPIRATOIRE URGENT"
        specific_advice = """
        <div class="response-section emergency-specific">
            <h4><i class="fas fa-lungs"></i> Actions immédiates pour problèmes respiratoires</h4>
            <ul class="urgent-list">
                <li><strong>Asseyez-vous bien droit</strong> - facilitez la respiration</li>
                <li><strong>Desserrez vos vêtements</strong> - libérez le thorax</li>
                <li><strong>Fenêtre ouverte</strong> - aérez la pièce</li>
                <li><strong>Respirez lentement et profondément</strong> - calmez-vous</li>
                <li><strong>Si vous avez de l'oxygène</strong> - utilisez-le maintenant</li>
            </ul>
            <p><strong>⚠️ SYNDROME THORACIQUE AIGU POSSIBLE - URGENCE ABSOLUE</strong></p>
        </div>"""

    # Douleurs thoraciques intenses
    elif any(word in user_input for word in ['poitrine', 'thorax', 'cœur', 'sternum']) and any(word in user_input for word in ['douleur', 'mal', 'atroce', 'intense']):
        emergency_type = "DOULEUR THORACIQUE SÉVÈRE"
        specific_advice = """
        <div class="response-section emergency-specific">
            <h4><i class="fas fa-heart-broken"></i> Actions pour douleur thoracique</h4>
            <ul class="urgent-list">
                <li><strong>Asseyez-vous en position confortable</strong> - évitez de vous allonger</li>
                <li><strong>Prenez vos antidouleurs habituels</strong> - doses prescrites</li>
                <li><strong>Surveillez votre respiration</strong> - signalez si difficultés</li>
                <li><strong>Restez calme</strong> - le stress aggrave la douleur</li>
            </ul>
            <p><strong>⚠️ RISQUE DE SYNDROME THORACIQUE AIGU - NE PAS ATTENDRE</strong></p>
        </div>"""

    # Demande d'aide générale
    elif any(word in user_input for word in ['aide', 'help', 'secours']):
        emergency_type = "DEMANDE D'AIDE URGENTE"
        specific_advice = """
        <div class="response-section emergency-specific">
            <h4><i class="fas fa-hand-holding-heart"></i> Je suis là pour vous aider</h4>
            <ul class="urgent-list">
                <li><strong>Décrivez vos symptômes précisément</strong> - aux secours</li>
                <li><strong>Mentionnez "DRÉPANOCYTE"</strong> - information cruciale</li>
                <li><strong>Gardez votre téléphone près de vous</strong> - restez joignable</li>
                <li><strong>Si possible, contactez un proche</strong> - pour vous accompagner</li>
            </ul>
            <p><strong>🆘 AIDE MÉDICALE SPÉCIALISÉE EN ROUTE</strong></p>
        </div>"""

    # Autres douleurs intenses
    elif any(word in user_input for word in ['douleur', 'mal', 'atroce', 'insupportable', 'terrible']):
        emergency_type = "CRISE DOULOUREUSE SÉVÈRE"
        specific_advice = """
        <div class="response-section emergency-specific">
            <h4><i class="fas fa-bolt"></i> Gestion crise douloureuse sévère</h4>
            <ul class="urgent-list">
                <li><strong>Prenez vos antidouleurs</strong> - doses prescrites maximum</li>
                <li><strong>Hydratez-vous abondamment</strong> - eau tiède</li>
                <li><strong>Position confortable</strong> - évitez compressions</li>
                <li><strong>Source de chaleur douce</strong> - si disponible</li>
                <li><strong>Évaluez douleur 1-10</strong> - communiquez aux secours</li>
            </ul>
            <p><strong>⚠️ CRISE SÉVÈRE - PRISE EN CHARGE HOSPITALIÈRE NÉCESSAIRE</strong></p>
        </div>"""

    else:
        emergency_type = "URGENCE MÉDICALE"
        specific_advice = """
        <div class="response-section emergency-specific">
            <h4><i class="fas fa-exclamation-triangle"></i> Protocole d'urgence général</h4>
            <ul class="urgent-list">
                <li><strong>Restez calme</strong> - les secours arrivent</li>
                <li><strong>Ne vous déplacez pas seul</strong> - attendez assistance</li>
                <li><strong>Préparez vos papiers</strong> - carte vitale, ordonnances</li>
                <li><strong>Listez vos symptômes</strong> - pour l'équipe médicale</li>
            </ul>
        </div>"""

    return {
        'success': True,
        'response': f"""<div class="response-section emergency-alert">
            <h3><i class="fas fa-exclamation-triangle"></i> {emergency_type}</h3>
            <p><strong>Situation d'urgence médicale identifiée !</strong></p>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-phone"></i> APPELEZ IMMÉDIATEMENT</h4>
            <ul class="urgent-list">
                <li><strong>115 (KIDJAMO)</strong> - Urgences médicales</li>
                <li><strong>112</strong> - Numéro d'urgence camerounais</li>
                <li><strong>118 (Pompiers)</strong> - Si nécessaire</li>
            </ul>
        </div>

        {specific_advice}

        <div class="response-section">
            <h4><i class="fas fa-hospital"></i> CENTRES SPÉCIALISÉS</h4>
            <ul class="help-list">
                <li><strong>CHU - Service hématologie</strong> - centre de référence</li>
                <li><strong>Centre de référence drépanocytose</strong> - expertise spécialisée</li>
                <li><strong>Urgences hospitalières</strong> - prise en charge immédiate</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-clipboard-list"></i> INFORMATIONS À COMMUNIQUER</h4>
            <ul class="info-list">
                <li><strong>Votre identité complète</strong> - nom, prénom, âge</li>
                <li><strong>"Patient drépanocytaire"</strong> - information médicale cruciale</li>
                <li><strong>Symptômes précis actuels</strong> - description détaillée</li>
                <li><strong>Votre localisation exacte</strong> - adresse complète</li>
                <li><strong>Traitements en cours</strong> - liste de vos médicaments</li>
            </ul>
        </div>

        <div class="response-section emergency-alert">
            <p><strong>⚠️ En attendant les secours, suivez leurs instructions par téléphone.</strong></p>
        </div>""",
        'conversation_type': 'emergency'
    }

def handle_pain_report(event: Dict[str, Any], session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les signalements de douleur"""
    responses = [
        """<div class="response-section pain-management">
            <h3><i class="fas fa-heartbeat"></i> Gestion de la douleur</h3>
            
            <h4><i class="fas fa-bolt"></i> Actions immédiates</h4>
            <ul class="urgent-list">
                <li><strong>Prenez vos antidouleurs habituels</strong> - selon prescription médicale</li>
                <li><strong>Hydratez-vous abondamment</strong> - eau tiède de préférence</li>
                <li><strong>Reposez-vous dans un endroit calme</strong> - évitez les stimulations</li>
                <li><strong>Appliquez une source de chaleur douce</strong> - bouillotte, bain chaud</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-thermometer-half"></i> Évaluez votre douleur</h4>
            <ul class="info-list">
                <li><strong>Échelle de 1 à 10 ?</strong> - notez l'intensité précisément</li>
                <li><strong>Localisation précise ?</strong> - où exactement avez-vous mal ?</li>
                <li><strong>Depuis combien de temps ?</strong> - durée de la douleur</li>
                <li><strong>Type de douleur ?</strong> - brûlure, crampe, élancement</li>
            </ul>
        </div>

        <div class="response-section emergency-alert">
            <h4><i class="fas fa-ambulance"></i> Consultez si</h4>
            <ul class="urgent-list">
                <li><strong>Douleur > 7/10</strong> - douleur sévère nécessitant une consultation</li>
                <li><strong>Durée > 2 heures</strong> - crise prolongée</li>
                <li><strong>Accompagnée de fièvre</strong> - signe d'infection possible</li>
                <li><strong>Difficultés respiratoires</strong> - urgence immédiate</li>
            </ul>
        </div>""",

        """<div class="response-section pain-management">
            <h3><i class="fas fa-clipboard-list"></i> Suivi de votre douleur</h3>
            
            <h4><i class="fas fa-edit"></i> Notez dans votre journal</h4>
            <ul class="help-list">
                <li><strong>Intensité (1-10)</strong> - échelle de douleur objective</li>
                <li><strong>Localisation</strong> - zones du corps affectées</li>
                <li><strong>Déclencheurs possibles</strong> - activités, stress, temps</li>
                <li><strong>Médicaments pris</strong> - doses et heures de prise</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-spa"></i> Conseils de gestion</h4>
            <ul class="info-list">
                <li><strong>Techniques de relaxation</strong> - respiration profonde, méditation</li>
                <li><strong>Position confortable</strong> - évitez les positions qui compriment</li>
                <li><strong>Distraction mentale</strong> - musique, lecture, films</li>
                <li><strong>Évitez le stress</strong> - environnement calme et apaisant</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-mobile-alt"></i> Surveillance IoT</h4>
            <p>Votre bracelet connecté surveille automatiquement vos constantes vitales et peut détecter les signes précurseurs d'une crise.</p>
        </div>"""
    ]

    return {
        'success': True,
        'response': random.choice(responses),
        'conversation_type': 'pain_management'
    }

def handle_medication_management(event: Dict[str, Any], session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les questions sur les médicaments - VERSION AMÉLIORÉE"""
    user_input = event.get('inputTranscript', '').lower()

    # Réponses spécifiques selon le type de question
    if any(word in user_input for word in ['oublié', 'raté', 'manqué']):
        response = """<div class="response-section medication-section">
            <h3><i class="fas fa-clock"></i> Oubli de médicament</h3>
            
            <h4><i class="fas fa-exclamation-circle"></i> Que faire maintenant ?</h4>
            <ul class="urgent-list">
                <li><strong>Si moins de 12h de retard</strong> - Prenez votre dose maintenant</li>
                <li><strong>Si plus de 12h de retard</strong> - Sautez cette dose, reprenez demain</li>
                <li><strong>Ne doublez jamais la dose</strong> - risque de surdosage</li>
                <li><strong>Notez l'oubli</strong> - informez votre médecin</li>
            </ul>
            
            <h4><i class="fas fa-lightbulb"></i> Prévenir les oublis</h4>
            <ul class="help-list">
                <li><strong>Alarmes téléphone</strong> - même heure chaque jour</li>
                <li><strong>Pilulier hebdomadaire</strong> - organisation visuelle</li>
                <li><strong>Application de rappel</strong> - notifications automatiques</li>
                <li><strong>Routine quotidienne</strong> - associer à un moment fixe</li>
            </ul>
        </div>"""

    elif any(word in user_input for word in ['effets secondaires', 'effet indésirable']):
        response = """<div class="response-section medication-section">
            <h3><i class="fas fa-exclamation-triangle"></i> Effets secondaires des médicaments</h3>
            
            <h4><i class="fas fa-pills"></i> Hydroxyurée (Siklos)</h4>
            <ul class="info-list">
                <li><strong>Fréquents</strong> - Nausées, fatigue, maux de tête légers</li>
                <li><strong>Surveillance nécessaire</strong> - Baisse des globules blancs</li>
                <li><strong>Rares mais sérieux</strong> - Ulcères de jambe, cancer (très rare)</li>
            </ul>
            
            <h4><i class="fas fa-heart"></i> Acide folique</h4>
            <ul class="help-list">
                <li><strong>Très bien toléré</strong> - Peu d'effets secondaires</li>
                <li><strong>Parfois</strong> - Troubles digestifs légers</li>
            </ul>
            
            <h4><i class="fas fa-ambulance"></i> Contactez votre médecin si</h4>
            <ul class="urgent-list">
                <li><strong>Fièvre persistante</strong> - possible infection</li>
                <li><strong>Ulcères inhabituels</strong> - jambes, bouche</li>
                <li><strong>Fatigue extrême</strong> - possible anémie sévère</li>
                <li><strong>Saignements anormaux</strong> - nez, gencives</li>
            </ul>
        </div>"""

    elif any(word in user_input for word in ['heure', 'quand', 'horaire', 'moment']):
        response = """<div class="response-section medication-section">
            <h3><i class="fas fa-clock"></i> Horaires de prise des médicaments</h3>
            
            <h4><i class="fas fa-sun"></i> Hydroxyurée (Siklos)</h4>
            <ul class="info-list">
                <li><strong>Moment idéal</strong> - Le matin, toujours à la même heure</li>
                <li><strong>Avec les repas</strong> - Petit-déjeuner pour réduire les nausées</li>
                <li><strong>Régularité cruciale</strong> - Même heure tous les jours</li>
                <li><strong>Si oubli</strong> - Voir conseils spécifiques ci-dessus</li>
            </ul>
            
            <h4><i class="fas fa-leaf"></i> Acide folique</h4>
            <ul class="help-list">
                <li><strong>Flexible</strong> - Matin ou soir, selon préférence</li>
                <li><strong>Avec ou sans repas</strong> - Bien toléré</li>
                <li><strong>Simultané possible</strong> - Peut être pris avec l'hydroxyurée</li>
            </ul>
            
            <h4><i class="fas fa-calendar"></i> Conseils pratiques</h4>
            <ul class="urgent-list">
                <li><strong>Choisissez un moment fixe</strong> - 8h ou 9h par exemple</li>
                <li><strong>Associez à une routine</strong> - petit-déjeuner, brossage des dents</li>
                <li><strong>Préparez à l'avance</strong> - pilulier pour la semaine</li>
            </ul>
        </div>"""

    elif any(word in user_input for word in ['que faire', 'quoi faire', 'comment faire']):
        response = """<div class="response-section medication-section">
            <h3><i class="fas fa-question-circle"></i> Gestion pratique des médicaments</h3>
            
            <h4><i class="fas fa-list-check"></i> Actions recommandées</h4>
            <ul class="help-list">
                <li><strong>Respectez les horaires</strong> - Régularité essentielle</li>
                <li><strong>Ne modifiez jamais seul</strong> - Consultez avant tout changement</li>
                <li><strong>Surveillez votre état</strong> - Notez effets et améliorations</li>
                <li><strong>Communiquez</strong> - Informez votre équipe médicale</li>
            </ul>
            
            <h4><i class="fas fa-shield-alt"></i> Précautions importantes</h4>
            <ul class="urgent-list">
                <li><strong>Stock suffisant</strong> - Ne jamais être en rupture</li>
                <li><strong>Voyage</strong> - Emportez plus que nécessaire</li>
                <li><strong>Interactions</strong> - Signalez tous vos traitements</li>
                <li><strong>Conservation</strong> - Lieu sec, température ambiante</li>
            </ul>
        </div>"""

    else:
        # Réponse générale sur les médicaments
        response = """<div class="response-section medication-section">
            <h3><i class="fas fa-pills"></i> Gestion des médicaments drépanocytose</h3>
            
            <h4><i class="fas fa-prescription"></i> Traitements principaux</h4>
            <ul class="info-list">
                <li><strong>Hydroxyurée (Siklos)</strong> - traitement de fond quotidien</li>
                <li><strong>Acide folique</strong> - supplément vitaminique essentiel</li>
                <li><strong>Antalgiques</strong> - paracétamol, anti-inflammatoires</li>
                <li><strong>Antibiotiques préventifs</strong> - protection infections</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-clock"></i> Conseils de prise</h4>
            <ul class="help-list">
                <li><strong>Horaires fixes</strong> - même heure chaque jour</li>
                <li><strong>Avec un grand verre d'eau</strong> - facilite l'absorption</li>
                <li><strong>Pendant ou après les repas</strong> - réduit les effets secondaires</li>
                <li><strong>Ne jamais arrêter brutalement</strong> - consultez avant modification</li>
            </ul>
        </div>

        <div class="response-section emergency-alert">
            <h4><i class="fas fa-exclamation-triangle"></i> Surveillez</h4>
            <ul class="urgent-list">
                <li><strong>Effets secondaires</strong> - nausées, maux de tête persistants</li>
                <li><strong>Interactions médicamenteuses</strong> - informez tous vos médecins</li>
                <li><strong>Oublis répétés</strong> - utilisez un pilulier ou des rappels</li>
            </ul>
        </div>"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'medication'
    }

def handle_medical_knowledge(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les questions sur la drépanocytose - VERSION AMÉLIORÉE"""
    input_lower = user_input.lower()

    # Questions sur la définition/nature de la maladie
    if any(word in input_lower for word in ['qu\'est-ce que c\'est', 'c\'est quoi', 'qu est-ce que c est', 'définition', 'expliquez']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-dna"></i> La drépanocytose expliquée</h3>
            <p><strong>La drépanocytose est une maladie génétique héréditaire</strong> qui affecte l'hémoglobine des globules rouges.</p>
            
            <h4><i class="fas fa-microscope"></i> En termes simples</h4>
            <ul class="info-list">
                <li><strong>Votre sang transporte moins bien l'oxygène</strong> - les globules rouges sont déformés</li>
                <li><strong>Forme en faucille</strong> - au lieu d'être ronds, ils deviennent rigides</li>
                <li><strong>Blocages dans les vaisseaux</strong> - causent douleurs et complications</li>
                <li><strong>Maladie présente dès la naissance</strong> - transmise par les parents</li>
            </ul>
            
            <h4><i class="fas fa-heartbeat"></i> Principales manifestations</h4>
            <ul class="urgent-list">
                <li><strong>Crises douloureuses</strong> - épisodes de douleur intense</li>
                <li><strong>Fatigue chronique</strong> - due au manque d'oxygène</li>
                <li><strong>Infections plus fréquentes</strong> - défenses immunitaires affaiblies</li>
                <li><strong>Anémie</strong> - pâleur, essoufflement</li>
            </ul>
        </div>"""

    # Questions sur la gravité
    elif any(word in input_lower for word in ['grave', 'gravité', 'sérieux', 'dangereux', 'mortel', 'est-ce que c\'est']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-balance-scale"></i> Gravité de la drépanocytose</h3>
            <p><strong>La drépanocytose est une maladie sérieuse mais gérable</strong> avec un suivi médical approprié.</p>
            
            <h4><i class="fas fa-chart-line"></i> Niveaux de gravité</h4>
            <ul class="info-list">
                <li><strong>Forme SS (homozygote)</strong> - la plus sévère, nécessite un suivi régulier</li>
                <li><strong>Forme SC</strong> - modérée, moins de complications</li>
                <li><strong>Trait AS</strong> - forme légère, vie quasi normale</li>
            </ul>
            
            <h4><i class="fas fa-heart"></i> Pronostic actuel</h4>
            <ul class="help-list">
                <li><strong>Espérance de vie augmentée</strong> - 40-60 ans avec bon suivi</li>
                <li><strong>Qualité de vie améliorée</strong> - nouveaux traitements disponibles</li>
                <li><strong>Vie active possible</strong> - travail, famille, loisirs adaptés</li>
                <li><strong>Prise en charge précoce</strong> - meilleur pronostic</li>
            </ul>
            
            <div class="response-section emergency-alert">
                <p><strong>🌟 L'important est un suivi médical régulier et le respect du traitement !</strong></p>
            </div>
        </div>"""

    # Questions sur les traitements
    elif any(word in input_lower for word in ['traitement', 'traitements', 'soigner', 'guérir', 'médicament', 'quels']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-pills"></i> Traitements de la drépanocytose</h3>
            <p><strong>Plusieurs traitements existent pour améliorer votre qualité de vie</strong> et réduire les complications.</p>
            
            <h4><i class="fas fa-prescription"></i> Traitements de fond</h4>
            <ul class="info-list">
                <li><strong>Hydroxyurée (Siklos)</strong> - réduit la fréquence des crises</li>
                <li><strong>Acide folique</strong> - aide à la production de globules rouges</li>
                <li><strong>Antibiotiques préventifs</strong> - protection contre infections</li>
                <li><strong>Vaccinations renforcées</strong> - protection supplémentaire</li>
            </ul>
            
            <h4><i class="fas fa-hospital"></i> Traitements des crises</h4>
            <ul class="urgent-list">
                <li><strong>Antidouleurs</strong> - paracétamol, morphiniques si besoin</li>
                <li><strong>Hydratation intraveineuse</strong> - fluidifie le sang</li>
                <li><strong>Oxygénothérapie</strong> - améliore l'oxygénation</li>
                <li><strong>Transfusions sanguines</strong> - dans certains cas</li>
            </ul>
            
            <h4><i class="fas fa-star"></i> Traitements avancés</h4>
            <ul class="help-list">
                <li><strong>Greffe de moelle osseuse</strong> - peut guérir définitivement</li>
                <li><strong>Thérapie génique</strong> - en développement prometteur</li>
                <li><strong>Échanges transfusionnels</strong> - prévention complications</li>
            </ul>
        </div>"""

    # Questions sur la prévention des crises
    elif any(word in input_lower for word in ['éviter', 'prévenir', 'empêcher', 'conseils', 'comment']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-shield-alt"></i> Prévention des crises</h3>
            <p><strong>De nombreuses mesures peuvent réduire le risque de crises</strong> et améliorer votre bien-être.</p>
            
            <h4><i class="fas fa-tint"></i> Hydratation</h4>
            <ul class="urgent-list">
                <li><strong>Boire 2-3 litres d'eau par jour</strong> - fluidifie le sang</li>
                <li><strong>Éviter la déshydratation</strong> - attention chaleur, sport</li>
                <li><strong>Eau tiède préférée</strong> - éviter trop froid ou chaud</li>
            </ul>
            
            <h4><i class="fas fa-thermometer-half"></i> Éviter les déclencheurs</h4>
            <ul class="info-list">
                <li><strong>Températures extrêmes</strong> - froid intense, chaleur excessive</li>
                <li><strong>Altitude élevée</strong> - manque d'oxygène</li>
                <li><strong>Stress important</strong> - techniques de relaxation</li>
                <li><strong>Fatigue excessive</strong> - respecter son rythme</li>
                <li><strong>Infections</strong> - se soigner rapidement</li>
            </ul>
            
            <h4><i class="fas fa-heart"></i> Mode de vie sain</h4>
            <ul class="help-list">
                <li><strong>Activité physique adaptée</strong> - marche, natation douce</li>
                <li><strong>Alimentation équilibrée</strong> - riche en fer et vitamines</li>
                <li><strong>Sommeil régulier</strong> - 7-8h par nuit</li>
                <li><strong>Suivi médical régulier</strong> - tous les 3-6 mois</li>
            </ul>
        </div>"""

    # Questions sur symptômes
    elif any(word in input_lower for word in ['symptôme', 'symptômes', 'signes', 'manifeste']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-stethoscope"></i> Symptômes de la drépanocytose</h3>
            
            <h4><i class="fas fa-bolt"></i> Symptômes de crise (aigus)</h4>
            <ul class="urgent-list">
                <li><strong>Douleur intense</strong> - os, articulations, abdomen, dos</li>
                <li><strong>Fièvre</strong> - signe d'infection possible</li>
                <li><strong>Difficultés respiratoires</strong> - essoufflement anormal</li>
                <li><strong>Gonflement</strong> - mains, pieds chez l'enfant</li>
            </ul>
            
            <h4><i class="fas fa-calendar-day"></i> Symptômes chroniques</h4>
            <ul class="info-list">
                <li><strong>Fatigue persistante</strong> - due à l'anémie</li>
                <li><strong>Pâleur</strong> - peau, lèvres, ongles</li>
                <li><strong>Jaunisse légère</strong> - yeux et peau jaunâtres</li>
                <li><strong>Retard de croissance</strong> - chez les enfants</li>
                <li><strong>Infections fréquentes</strong> - rhumes, pneumonies</li>
            </ul>
        </div>"""

    # Questions sur transmission/génétique
    elif any(word in input_lower for word in ['transmission', 'hérédité', 'génétique', 'transmet', 'attrape']):
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-dna"></i> Transmission génétique</h3>
            
            <h4><i class="fas fa-users"></i> Comment ça se transmet</h4>
            <ul class="info-list">
                <li><strong>Maladie héréditaire</strong> - transmise par les deux parents</li>
                <li><strong>Pas contagieuse</strong> - on ne peut pas l'attraper</li>
                <li><strong>Présente dès la naissance</strong> - détectable très tôt</li>
                <li><strong>25% de risque</strong> - si les deux parents sont porteurs</li>
            </ul>
            
            <h4><i class="fas fa-baby"></i> Dépistage et conseil</h4>
            <ul class="help-list">
                <li><strong>Test néonatal</strong> - systématique à la naissance</li>
                <li><strong>Conseil génétique</strong> - avant d'avoir des enfants</li>
                <li><strong>Test prénatal possible</strong> - pendant la grossesse</li>
                <li><strong>Information famille</strong> - frères, sœurs, cousins</li>
            </ul>
        </div>"""

    # Réponse générale pour autres questions
    else:
        response = """<div class="response-section medical-info">
            <h3><i class="fas fa-book-medical"></i> Informations sur la drépanocytose</h3>
            <p>Je peux vous donner des informations détaillées sur tous les aspects de la drépanocytose :</p>
            
            <h4><i class="fas fa-question-circle"></i> Questions fréquentes</h4>
            <ul class="help-list">
                <li><strong>"Qu'est-ce que c'est exactement ?"</strong> - définition simple</li>
                <li><strong>"Est-ce que c'est grave ?"</strong> - pronostic et gravité</li>
                <li><strong>"Quels traitements existent ?"</strong> - options thérapeutiques</li>
                <li><strong>"Comment éviter les crises ?"</strong> - prévention au quotidien</li>
                <li><strong>"Quels sont les symptômes ?"</strong> - signes à surveiller</li>
                <li><strong>"Comment ça se transmet ?"</strong> - aspect génétique</li>
            </ul>
            
            <p><strong>N'hésitez pas à reformuler votre question de façon plus précise !</strong></p>
        </div>"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'medical_info'
    }

def handle_app_information(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les questions sur l'application"""
    return {
        'success': True,
        'response': """<div class="response-section medical-info">
            <h3><i class="fas fa-mobile-alt"></i> Kidjamo Health Assistant</h3>
            <p>Je suis votre assistant santé intelligent spécialisé dans l'accompagnement des patients atteints de drépanocytose.</p>
            
            <h4><i class="fas fa-cogs"></i> Mes fonctionnalités</h4>
            <ul class="help-list">
                <li><strong>Gestion de la douleur</strong> - évaluation et conseils personnalisés</li>
                <li><strong>Suivi des médicaments</strong> - rappels et informations</li>
                <li><strong>Données vitales IoT</strong> - analyse de vos mesures (en développement)</li>
                <li><strong>Urgences médicales</strong> - protocoles et contacts d'urgence</li>
                <li><strong>Éducation thérapeutique</strong> - informations fiables sur la maladie</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-headset"></i> Support vocal</h4>
            <ul class="info-list">
                <li><strong>Reconnaissance vocale</strong> - parlez directement</li>
                <li><strong>Synthèse vocale</strong> - réponses audio automatiques</li>
                <li><strong>Interface intuitive</strong> - facile à utiliser</li>
                <li><strong>Questions suggérées</strong> - assistance contextuelle</li>
            </ul>
        </div>

        <div class="response-section">
            <h4><i class="fas fa-shield-alt"></i> Confidentialité</h4>
            <ul class="urgent-list">
                <li><strong>Données sécurisées</strong> - chiffrement et protection</li>
                <li><strong>Conformité RGPD</strong> - respect de la vie privée</li>
                <li><strong>Pas de stockage permanent</strong> - sessions temporaires</li>
                <li><strong>Usage médical uniquement</strong> - ne remplace pas un médecin</li>
            </ul>
        </div>""",
        'conversation_type': 'app_info'
    }

def handle_identity_question(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les questions sur l'identité du bot"""
    return {
        'success': True,
        'response': """<div class="response-section medical-info">
            <h3><i class="fas fa-robot"></i> Je suis Kidjamo Assistant</h3>
            <p>Je suis un assistant virtuel spécialisé dans l'accompagnement des patients atteints de drépanocytose.</p>
            
            <h4><i class="fas fa-heart"></i> Ma mission</h4>
            <ul class="help-list">
                <li><strong>Accompagnement quotidien</strong> - Support 24h/24 pour vos questions</li>
                <li><strong>Expertise médicale</strong> - Informations validées sur la drépanocytose</li>
                <li><strong>Gestion des crises</strong> - Protocoles d'urgence et conseils</li>
                <li><strong>Suivi personnalisé</strong> - Adaptation à votre profil médical</li>
            </ul>
            
            <h4><i class="fas fa-shield-alt"></i> Confidentialité</h4>
            <p>Toutes nos conversations sont sécurisées et confidentielles. Je respecte le secret médical.</p>
        </div>""",
        'conversation_type': 'identity'
    }

def handle_gratitude(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère les remerciements"""
    return {
        'success': True,
        'response': """<div class="response-section medical-info">
            <h3><i class="fas fa-thumbs-up"></i> Merci !</h3>
            <p>Je suis ravi d'avoir pu vous aider. N'hésitez pas à revenir si vous avez d'autres questions.</p>
            
            <h4><i class="fas fa-heart"></i> Prenez soin de vous</h4>
            <p>Rappelez-vous, je suis là 24/7 pour vous accompagner dans votre parcours de santé.</p>
        </div>""",
        'conversation_type': 'gratitude'
    }

def handle_general_conversation(user_input: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Gère la conversation générale avec redirection vers les sujets médicaux"""
    general_responses = [
        """<div class="response-section medical-info">
            <h3><i class="fas fa-comment"></i> Je suis là pour vous aider</h3>
            <p>Je ne suis pas sûr de bien comprendre votre question. Voici les domaines dans lesquels je peux vous accompagner :</p>
            
            <ul class="help-list">
                <li><strong>💭 Questions sur la drépanocytose</strong> - "Qu'est-ce que la drépanocytose ?"</li>
                <li><strong>🤕 Gestion de la douleur</strong> - "J'ai mal" ou "Comment gérer une crise ?"</li>
                <li><strong>💊 Médicaments</strong> - "Rappel traitement" ou "Effets secondaires"</li>
                <li><strong>🚨 Urgences</strong> - "Aide urgent" ou "Douleur intense"</li>
                <li><strong>📱 Application</strong> - "Comment utiliser Kidjamo ?"</li>
            </ul>
            
            <p><strong>Reformulez votre question ou choisissez un de ces sujets !</strong></p>
        </div>""",
        
        """<div class="response-section medical-info">
            <h3><i class="fas fa-lightbulb"></i> Besoin d'aide ?</h3>
            <p>Je suis spécialisé dans l'accompagnement des patients drépanocytaires. Voici quelques exemples de ce que vous pouvez me demander :</p>
            
            <div class="example-questions">
                <h4><i class="fas fa-question-circle"></i> Exemples de questions</h4>
                <ul class="info-list">
                    <li><em>"J'ai mal au dos, que faire ?"</em></li>
                    <li><em>"Quand prendre mon hydroxyurée ?"</em></li>
                    <li><em>"Qu'est-ce qui déclenche les crises ?"</em></li>
                    <li><em>"Comment fonctionne le bracelet ?"</em></li>
                    <li><em>"Que faire en cas d'urgence ?"</em></li>
                </ul>
            </div>
            
            <p><strong>N'hésitez pas à me poser vos questions !</strong></p>
        </div>"""
    ]
    
    return {
        'success': True,
        'response': random.choice(general_responses),
        'conversation_type': 'general'
    }
