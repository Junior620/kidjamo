import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Handler simplifié pour le fulfillment Lex - Réponses directes optimisées
    """
    try:
        logger.info(f"Événement reçu: {json.dumps(event)}")

        # Extraire les informations de la session Lex
        intent_name = event['sessionState']['intent']['name']
        user_input = event['inputTranscript']
        slots = event['sessionState']['intent'].get('slots', {})

        # Router vers la fonction appropriée selon l'intent avec logique simplifiée
        if intent_name == 'SignalerDouleur':
            return handle_pain_report_simple(event, slots)
        elif intent_name == 'ConsulterVitales':
            return handle_vitals_simple(event)
        elif intent_name == 'GererMedicaments':
            return handle_medication_simple(event, slots)
        elif intent_name == 'SignalerUrgence':
            return handle_emergency_simple(event)
        elif intent_name == 'DemanderAide':
            return handle_help_simple(event)
        elif intent_name == 'ConversationGenerale':
            return handle_conversation_simple(event, user_input)
        elif intent_name == 'QuestionsGenerales':
            return handle_questions_simple(event, user_input)
        elif intent_name == 'DiscussionLibre':
            return handle_discussion_simple(event, user_input)
        elif intent_name == 'ConseilsVieQuotidienne':
            return handle_advice_simple(event, user_input)
        elif intent_name == 'CultureEducation':
            return handle_culture_simple(event, user_input)
        elif intent_name == 'FallbackIntent':
            return handle_fallback_simple(event, user_input)
        else:
            return handle_fallback_simple(event, user_input)

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler: {str(e)}")
        return create_lex_response(
            "Désolé, je rencontre une petite difficulté. Pouvez-vous reformuler votre demande ?",
            event
        )

def handle_pain_report_simple(event, slots):
    """Gestion simplifiée des signalements de douleur"""
    try:
        intensite = slots.get('IntensiteDouleur', {}).get('value', {}).get('interpretedValue')
        localisation = slots.get('LocalisationDouleur', {}).get('value', {}).get('interpretedValue')

        # Réponses directes selon l'intensité
        if intensite and int(intensite) >= 8:
            response = f""" **DOULEUR SÉVÈRE** - {intensite}/10 au niveau {localisation or 'non précisé'}

**Actions immédiates:**
• Prenez vos antalgiques prescrits
• Hydratez-vous abondamment
• Repos complet
• Si pas d'amélioration en 30 min → Contactez votre médecin

**Numéros d'urgence:** 115  • 112 (Urgences)

Tenez-moi informé de l'évolution ! """

        elif intensite and int(intensite) >= 5:
            response = f""" **Douleur modérée** - {intensite}/10 au niveau {localisation or 'non précisé'}

**Recommandations:**
• Antalgiques habituels
• Chaleur locale si possible
• Hydratation importante
• Surveillance de l'évolution

Comment vous sentez-vous maintenant ?"""

        else:
            response = f""" **Douleur enregistrée** - {intensite or '?'}/10 au niveau {localisation or 'non précisé'}

**Conseils:**
• Surveillez l'évolution
• Restez bien hydraté(e)
• Recontactez-moi si aggravation

Autre chose pour vous aider ?"""

        return create_lex_response(response, event)

    except Exception as e:
        logger.error(f"Erreur signalement douleur: {str(e)}")
        return create_lex_response(
            "J'ai noté votre douleur. Prenez vos antalgiques et hydratez-vous bien !",
            event
        )

def handle_vitals_simple(event):
    """Gestion simplifiée des données vitales"""
    response = """ **Vos données vitales**

🔄 **Connexion au bracelet IoT...**

**Données simulées pour démo:**
 Rythme cardiaque: 78 bpm (Normal)
 Saturation O₂: 98% (Excellent)
 Température: 36.8°C (Normal)
 Activité: Modérée

*Les données réelles de votre bracelet seront bientôt intégrées.*

Tout semble normal ! Comment vous sentez-vous ?"""

    return create_lex_response(response, event)

def handle_medication_simple(event, slots):
    """Gestion simplifiée des médicaments"""
    action = slots.get('ActionMedicament', {}).get('value', {}).get('interpretedValue')
    medicament = slots.get('NomMedicament', {}).get('value', {}).get('interpretedValue')

    if action == 'prendre' and medicament:
        response = f""" **Prise de {medicament} enregistrée**

 Bien noté ! N'oubliez pas :
• Respecter les doses prescrites
• Prendre avec un verre d'eau
• Noter les effets ressentis

Prochaine prise à quelle heure ?"""

    elif action == 'rappel':
        response = f""" **Rappel médicament configuré**

Je peux vous rappeler de prendre {medicament or 'vos médicaments'}.

**Médicaments courants drépanocytose:**
• Hydroxyurée (quotidien)
• Acide folique (quotidien)
• Antalgiques (si besoin)

À quelle heure voulez-vous être rappelé ?"""

    else:
        response = """ **Gestion des médicaments**

**Je peux vous aider avec:**
• Enregistrer une prise
• Configurer des rappels
• Informations sur les traitements

**Dites-moi par exemple:**
"J'ai pris mon Doliprane"
"Rappel pour Hydroxyurée"

Que souhaitez-vous faire ?"""

    return create_lex_response(response, event)

def handle_emergency_simple(event):
    """Gestion simplifiée des urgences"""
    response = """ **URGENCE ACTIVÉE**

**NUMÉROS D'URGENCE IMMÉDIATE:**
• 115  - Urgences médicales
• 112 - Urgences 
• 18 - Pompiers

**CENTRES SPÉCIALISÉS CAMEROUN:**
• CHU Yaoundé - Hématologie
• Hôpital Laquintinie Douala

**EN ATTENDANT LES SECOURS:**
• Restez calme
• Ne bougez pas si possible
• Hydratez-vous si conscient

Quelqu'un peut-il vous assister ?"""

    return create_lex_response(response, event)

def handle_help_simple(event):
    """Guide d'aide simplifié"""
    response = """ **Guide Kidjamo Health Assistant**

** SIGNALER DOULEUR:**
"J'ai mal au dos intensité 7"

** MÉDICAMENTS:**
"J'ai pris mon Doliprane"
"Rappel Hydroxyurée"

** DONNÉES VITALES:**
"Mes vitales" ou "État bracelet"

** URGENCE:**
"C'est urgent" ou "Aidez-moi"

** DISCUSSION:**
"Bonjour" ou "Comment ça va"

** QUESTIONS:**
"Qu'est-ce que la drépanocytose ?"

Que voulez-vous essayer ?"""

    return create_lex_response(response, event)

def handle_conversation_simple(event, user_input):
    """Conversations générales simplifiées"""
    input_lower = user_input.lower()

    if any(greeting in input_lower for greeting in ['bonjour', 'salut', 'hello', 'bonsoir']):
        response = """👋 **Bonjour !** 

Je suis votre assistant santé Kidjamo, spécialisé dans la drépanocytose.

**Comment allez-vous aujourd'hui ?** 😊

Je peux vous aider avec vos douleurs, médicaments, questions de santé ou simplement discuter !

Que puis-je faire pour vous ?"""

    elif any(thanks in input_lower for thanks in ['merci', 'thanks']):
        response = """😊 **Avec plaisir !**

C'est un bonheur de vous aider. Votre bien-être est ma priorité !

N'hésitez jamais à me contacter pour :
• Vos questions de santé
• Moments difficiles
• Simple bavardage

Prenez bien soin de vous ! """

    elif any(feeling in input_lower for feeling in ['ça va', 'comment allez-vous', 'comment tu vas']):
        response = """😊 **Je vais très bien, merci !**

Et vous, comment vous sentez-vous ?
• Avez-vous eu des douleurs récemment ?
• Vos médicaments se passent bien ?
• Moral au beau fixe ?

Racontez-moi un peu ! """

    else:
        response = """😊 **Je suis là pour vous !**

Que se passe-t-il aujourd'hui ?
• Besoin de parler santé ?
• Envie de discuter ?
• Questions particulières ?

Je vous écoute ! """

    return create_lex_response(response, event)

def handle_questions_simple(event, user_input):
    """Questions générales simplifiées"""
    input_lower = user_input.lower()

    if any(time_q in input_lower for time_q in ['heure', 'temps']):
        current_time = datetime.now().strftime("%H:%M")
        response = f""" **Il est {current_time}**

N'oubliez pas vos médicaments !
• Hydroxyurée (si prescrite)
• Acide folique
• Hydratation régulière

Comment vous sentez-vous en ce moment ?"""

    elif any(date_q in input_lower for date_q in ['jour', 'date', 'aujourd\'hui']):
        current_date = datetime.now().strftime("%A %d %B %Y")
        response = f""" **Nous sommes {current_date}**

Belle journée pour prendre soin de vous !
• Avez-vous pris vos médicaments ?
• Bien hydraté(e) ?
• Comment va votre moral ?

Racontez-moi votre journée ! """

    elif any(who in input_lower for who in ['qui es-tu', 'ton nom', 'tu es qui']):
        response = """ **Je suis Kidjamo !**

Votre assistant santé personnel spécialisé en drépanocytose.

**Ma mission :** Vous accompagner au quotidien
**Mes spécialités :** 
• Gestion de la douleur
• Suivi des traitements  
• Support émotionnel
• Éducation santé

**Et je sais aussi bien discuter !** 😉

Que voulez-vous savoir d'autre ?"""

    elif any(drepa in input_lower for drepa in ['drépanocytose', 'maladie', 'anémie']):
        response = """ **La drépanocytose expliquée simplement**

**C'est quoi ?**
Une maladie génétique qui déforme les globules rouges

**Symptômes principaux :**
• Douleurs (crises vaso-occlusives)
• Fatigue (anémie)
• Infections fréquentes

**Traitements actuels :**
• Hydroxyurée (réduit les crises)
• Hydratation importante
• Antalgiques selon besoin

**Bonne nouvelle :** On peut très bien vivre avec !

Des questions spécifiques ?"""

    else:
        response = """ **Excellente question !**

Je peux vous parler de :
• La drépanocytose et ses traitements
• Gestion de la douleur
• Conseils de vie quotidienne
• Aspects psychologiques
• Recherches récentes

**Ou alors :** Posez-moi votre question directement !

Qu'est-ce qui vous intéresse le plus ?"""

    return create_lex_response(response, event)

def handle_discussion_simple(event, user_input):
    """Discussion libre simplifiée"""
    input_lower = user_input.lower()

    if any(bored in input_lower for bored in ['ennuie', 'seul', 'triste']):
        response = """🤗 **Je suis là pour vous tenir compagnie !**

**Idées pour passer le temps :**
 Lecture (romans, BD, magazines)
 Musique relaxante
 Dessin, coloriage, créativité
 Appel à un proche
‍️ Petite balade si vous vous sentez bien

**Parlons un peu :**
• Quel est votre film préféré ?
• Qu'est-ce qui vous fait sourire ?
• Un beau souvenir à partager ?

Je vous écoute ! """

    elif any(company in input_lower for company in ['discuter', 'parler', 'bavarder']):
        response = """😊 **Avec grand plaisir !**

**Sujets de conversation :**
 Films et séries du moment
 Recettes de cuisine
 Voyages de rêve
 Livres passionnants
 Projets et rêves
 Musique qui vous plaît

**Ou alors :** Racontez-moi votre journée !

De quoi avez-vous envie de parler ?"""

    else:
        response = """ **Bavardons ensemble !**

J'adore les conversations ! 

• Comment s'est passée votre journée ?
• Qu'est-ce qui vous rend heureux ?
• Des projets excitants en vue ?
• Un sujet qui vous passionne ?

Racontez-moi tout ! Je suis tout ouïe """

    return create_lex_response(response, event)

def handle_advice_simple(event, user_input):
    """Conseils de vie simplifiés"""
    input_lower = user_input.lower()

    if any(sleep in input_lower for sleep in ['dormir', 'sommeil']):
        response = """ **Conseils pour bien dormir**

**Routine du soir :**
• Coucher à heure fixe
• Écrans éteints 1h avant
• Lecture ou relaxation
• Chambre fraîche (18-20°C)

**À éviter :**
• Caféine après 14h
• Gros repas le soir
• Sport intense tardif

**Pour la drépanocytose :**
Un bon sommeil aide à prévenir les crises !

Comment dormez-vous en ce moment ?"""

    elif any(stress in input_lower for stress in ['stress', 'angoisse']):
        response = """ **Anti-stress naturel**

**Respiration magique :**
• Inspirez 4 secondes
• Retenez 4 secondes
• Expirez 6 secondes
• Répétez 5 fois

**Autres techniques :**
• Marche en nature
• Musique douce
• Parler à un proche
• Écriture libre

Le stress peut déclencher des crises. Prenez soin de vous ! 

Qu'est-ce qui vous stresse en ce moment ?"""

    elif any(food in input_lower for food in ['manger', 'alimentation']):
        response = """ **Alimentation et drépanocytose**

**CRUCIAL - Hydratation :**
• 2-3 litres d'eau/jour minimum
• Éviter l'alcool

**Nutriments importants :**
• Acide folique (légumes verts)
• Fer (viandes, légumineuses)
• Vitamine C (agrumes)

**À limiter :**
• Sel excessif
• Fritures
• Boissons glacées

Une bonne nutrition = moins de crises !

Comment mangez-vous actuellement ?"""

    else:
        response = """ **Conseils de vie avec la drépanocytose**

**Les 3 piliers :**
 **Hydratation** (2-3L/jour)
 **Médicaments** (régularité)
 **Repos** (sommeil qualité)

**Activité physique :** Douce et régulière
**Gestion stress :** Relaxation, respiration
**Social :** Garder le contact avec proches

Sur quoi voulez-vous des conseils spécifiques ?"""

    return create_lex_response(response, event)

def handle_culture_simple(event, user_input):
    """Culture et éducation simplifiées"""
    input_lower = user_input.lower()

    if any(science in input_lower for science in ['science', 'recherche']):
        response = """ **Avancées scientifiques passionnantes**

**Médecine personnalisée :**
• Traitements sur mesure selon l'ADN
• Thérapies géniques prometteuses

**Drépanocytose - Nouveautés :**
• Thérapie génique : résultats encourageants
• Nouveaux médicaments en développement
• IA pour prédire les crises

**Autres domaines :**
• Espace : missions vers Mars
• Environnement : énergies propres

Quel domaine vous passionne le plus ?"""

    elif any(art in input_lower for art in ['art', 'musique', 'livre']):
        response = """ **Culture et bien-être**

**Livres apaisants :**
• Romans français contemporains
• Développement personnel
• Biographies inspirantes

**Musique thérapeutique :**
• Classique (Mozart, Debussy)
• Jazz doux
• Musiques du monde

**Art-thérapie :**
• Coloriage (très relaxant !)
• Peinture libre
• Écriture créative

La culture, c'est excellent pour le moral !

Qu'est-ce qui vous attire le plus ?"""

    else:
        response = """ **Culture générale**

**Sujets passionnants :**
 Histoire des civilisations
 Arts et littérature
 Découvertes scientifiques
 Langues du monde
 Philosophie accessible

**Effet bonus :** La curiosité intellectuelle est excellente pour le moral et aide à mieux vivre avec la maladie !

Quel sujet vous tente ?"""

    return create_lex_response(response, event)

def handle_fallback_simple(event, user_input):
    """Fallback simplifié et utile"""
    response = f""" **Je n'ai pas bien saisi "{user_input[:30]}..."**

**Mais je peux vous aider avec :**
 Signaler douleurs/symptômes
 Gérer vos médicaments  
 Consulter vos données vitales
 Situations d'urgence
 Simple conversation
 Questions sur la drépanocytose

**Exemples de ce que vous pouvez dire :**
• "J'ai mal au ventre"
• "Mes vitales"
• "J'ai pris mon médicament"
• "Comment ça va ?"

Que souhaitez-vous faire ?"""

    return create_lex_response(response, event)

def create_lex_response(message: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Crée une réponse formatée pour Lex"""
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Close'
            },
            'intent': {
                'name': event['sessionState']['intent']['name'],
                'state': 'Fulfilled'
            }
        },
        'messages': [
            {
                'contentType': 'PlainText',
                'content': message
            }
        ]
    }
