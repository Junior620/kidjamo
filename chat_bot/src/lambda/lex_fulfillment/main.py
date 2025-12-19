"""
Fonction Lambda principale pour le traitement des intentions Amazon Lex
Chatbot Santé Kidjamo - MVP
"""

import json
import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
comprehend_medical = boto3.client('comprehendmedical')
lambda_client = boto3.client('lambda')

# Variables d'environnement
CONVERSATION_TABLE = os.environ['CONVERSATION_TABLE']
PATIENT_CONTEXT_TABLE = os.environ['PATIENT_CONTEXT_TABLE']
MEDICAL_ALERTS_TOPIC = os.environ['MEDICAL_ALERTS_TOPIC']
PATIENT_NOTIFICATIONS_TOPIC = os.environ['PATIENT_NOTIFICATIONS_TOPIC']
IOT_KINESIS_STREAM = os.environ['IOT_KINESIS_STREAM']

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Point d'entrée principal pour le traitement des intentions Lex
    """
    try:
        logger.info(f"Événement reçu: {json.dumps(event, ensure_ascii=False)}")

        # Extraction des informations de la requête Lex
        intent_name = event['sessionState']['intent']['name']
        user_id = event.get('userId', 'anonymous')
        session_id = event['sessionId']
        input_text = event['inputTranscript']

        # Sauvegarde de l'interaction
        save_conversation(session_id, user_id, input_text, intent_name)

        # Routage selon l'intention
        if intent_name == 'SignalerDouleur':
            return handle_pain_report(event)
        elif intent_name == 'ConsulterVitales':
            return handle_vitals_query(event)
        elif intent_name == 'GererMedicaments':
            return handle_medication_management(event)
        elif intent_name == 'DemanderAide':
            return handle_help_request(event)
        elif intent_name == 'SignalerUrgence':
            return handle_emergency(event)
        elif intent_name == 'ConversationGenerale':
            return handle_general_conversation(event)
        elif intent_name == 'QuestionsGenerales':
            return handle_general_questions(event)
        elif intent_name == 'DiscussionLibre':
            return handle_free_discussion(event)
        elif intent_name == 'ConseilsVieQuotidienne':
            return handle_life_advice(event)
        elif intent_name == 'CultureEducation':
            return handle_culture_education(event)
        else:
            return handle_fallback(event)

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler: {str(e)}")
        return create_response(
            "Je rencontre une difficulté technique. Pouvez-vous reformuler votre demande ?",
            intent_name=event.get('sessionState', {}).get('intent', {}).get('name', 'Unknown')
        )

def handle_pain_report(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite le signalement de douleur par le patient
    """
    try:
        slots = event['sessionState']['intent']['slots']
        input_text = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Extraction des entités médicales avec Comprehend Medical
        medical_entities = extract_medical_entities(input_text)

        # Extraction des slots Lex
        intensity = slots.get('IntensiteDouleur', {}).get('value', {}).get('interpretedValue')
        location = slots.get('LocalisationDouleur', {}).get('value', {}).get('interpretedValue')

        # Construction du contexte médical
        pain_context = {
            'intensity': intensity,
            'location': location,
            'description': input_text,
            'medical_entities': medical_entities,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'user_id': user_id
        }

        # Évaluation du risque et recommandations
        risk_assessment = assess_pain_risk(pain_context)

        # Récupération des vitales récentes depuis IoT
        recent_vitals = get_recent_vitals(user_id)

        # Génération de la réponse
        response_text = generate_pain_response(pain_context, risk_assessment, recent_vitals)

        # Envoi d'alertes si nécessaire
        if risk_assessment.get('urgent', False):
            send_medical_alert(pain_context, risk_assessment)

        return create_response(response_text, 'SignalerDouleur')

    except Exception as e:
        logger.error(f"Erreur dans handle_pain_report: {str(e)}")
        return create_response(
            "J'ai bien noté votre signalement de douleur. Je vous recommande de contacter votre médecin pour un suivi approprié.",
            'SignalerDouleur'
        )

def handle_vitals_query(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les demandes de consultation des données vitales
    """
    try:
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction d'intégration IoT
        vitals_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-iot-integration",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'get_recent_vitals',
                'user_id': user_id,
                'timeframe': '24h'
            })
        )

        vitals_data = json.loads(vitals_response['Payload'].read())

        # Génération de la réponse
        if vitals_data.get('success'):
            vitals = vitals_data['data']
            response_text = format_vitals_response(vitals)
        else:
            response_text = "Je ne trouve pas de données récentes de votre bracelet. Vérifiez qu'il est bien connecté."

        return create_response(response_text, 'ConsulterVitales')

    except Exception as e:
        logger.error(f"Erreur dans handle_vitals_query: {str(e)}")
        return create_response(
            "Je rencontre une difficulté pour accéder à vos données vitales. Réessayez dans quelques instants.",
            'ConsulterVitales'
        )

def handle_medication_management(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite la gestion des médicaments
    """
    try:
        slots = event['sessionState']['intent']['slots']
        action = slots.get('ActionMedicament', {}).get('value', {}).get('interpretedValue')
        medication = slots.get('NomMedicament', {}).get('value', {}).get('interpretedValue')

        user_id = event.get('userId', 'anonymous')

        if action == 'prendre':
            # Enregistrer la prise de médicament
            response_text = f"J'ai enregistré votre prise de {medication}. N'oubliez pas de prendre vos médicaments selon la prescription."
        elif action == 'rappel':
            # Configurer un rappel
            response_text = f"Je vais vous rappeler de prendre {medication}. À quelle heure souhaitez-vous être rappelé ?"
        else:
            response_text = "Comment puis-je vous aider avec vos médicaments ? Je peux enregistrer une prise ou configurer des rappels."

        return create_response(response_text, 'GererMedicaments')

    except Exception as e:
        logger.error(f"Erreur dans handle_medication_management: {str(e)}")
        return create_response(
            "Je peux vous aider avec vos médicaments. Que souhaitez-vous faire ?",
            'GererMedicaments'
        )

def handle_emergency(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les signalements d'urgence
    """
    try:
        user_id = event.get('userId', 'anonymous')
        input_text = event['inputTranscript']

        # Création d'une alerte d'urgence
        emergency_alert = {
            'type': 'EMERGENCY',
            'user_id': user_id,
            'description': input_text,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'severity': 'CRITICAL'
        }

        # Envoi de l'alerte
        send_emergency_alert(emergency_alert)

        response_text = """ URGENCE DÉTECTÉE 

J'ai alerté l'équipe médicale. En attendant :

1. Si vous ressentez une douleur thoracique intense, appelez le 115
2. Prenez votre traitement de crise si prescrit
3. Allongez-vous et restez calme
4. Quelqu'un va vous contacter rapidement

Numéros d'urgence :
- KIDJAMO   : 115
- Pompiers : 118
- Urgences camerounais : 102"""

        return create_response(response_text, 'SignalerUrgence')

    except Exception as e:
        logger.error(f"Erreur dans handle_emergency: {str(e)}")
        return create_response(
            " En cas d'urgence vitale, appelez immédiatement le 115 ou le 112.",
            'SignalerUrgence'
        )

def handle_help_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les demandes d'aide générale
    """
    response_text = """Je suis votre assistant santé Kidjamo. Je peux vous aider avec :

 **Signaler des symptômes**
"J'ai mal au ventre, intensité 7/10"

 **Consulter vos données**
"Montre-moi mes vitales récentes"

 **Gérer vos médicaments**
"J'ai pris mon Doliprane"

 **Urgences**
"C'est urgent, j'ai besoin d'aide"

 **Conseils santé**
"Comment gérer une crise ?"

Que puis-je faire pour vous aujourd'hui ?"""

    return create_response(response_text, 'DemanderAide')

def handle_general_conversation(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les intentions de conversation générale avec IA conversationnelle
    """
    try:
        user_input = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction de conversation générale
        conversation_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-general-conversation",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'intent_name': 'ConversationGenerale',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            })
        )

        result = json.loads(conversation_response['Payload'].read())

        if result.get('success'):
            response_text = result['response']
        else:
            response_text = "Bonjour ! Je suis ravi de vous parler. Comment allez-vous aujourd'hui ? 😊"

        return create_response(response_text, 'ConversationGenerale')

    except Exception as e:
        logger.error(f"Erreur conversation générale: {str(e)}")
        return create_response(
            "Bonjour ! Je suis là pour discuter avec vous. De quoi aimeriez-vous parler ?",
            'ConversationGenerale'
        )

def handle_general_questions(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les questions générales avec IA conversationnelle
    """
    try:
        user_input = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction de conversation générale
        conversation_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-general-conversation",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'intent_name': 'QuestionsGenerales',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            })
        )

        result = json.loads(conversation_response['Payload'].read())

        if result.get('success'):
            response_text = result['response']
        else:
            response_text = "C'est une excellente question ! Pouvez-vous me donner plus de détails pour que je puisse mieux vous aider ?"

        return create_response(response_text, 'QuestionsGenerales')

    except Exception as e:
        logger.error(f"Erreur questions générales: {str(e)}")
        return create_response(
            "Je peux répondre à vos questions sur de nombreux sujets. Que voulez-vous savoir ?",
            'QuestionsGenerales'
        )

def handle_free_discussion(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les discussions libres avec IA conversationnelle
    """
    try:
        user_input = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction de conversation générale
        conversation_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-general-conversation",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'intent_name': 'DiscussionLibre',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            })
        )

        result = json.loads(conversation_response['Payload'].read())

        if result.get('success'):
            response_text = result['response']
        else:
            response_text = "J'adore bavarder ! De quoi voulez-vous discuter ? Je suis tout ouïe ! 😊"

        return create_response(response_text, 'DiscussionLibre')

    except Exception as e:
        logger.error(f"Erreur discussion libre: {str(e)}")
        return create_response(
            "Parlons de ce qui vous intéresse ! Qu'avez-vous en tête ?",
            'DiscussionLibre'
        )

def handle_life_advice(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Donne des conseils sur la vie quotidienne avec IA
    """
    try:
        user_input = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction de conversation générale
        conversation_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-general-conversation",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'intent_name': 'ConseilsVieQuotidienne',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            })
        )

        result = json.loads(conversation_response['Payload'].read())

        if result.get('success'):
            response_text = result['response']
        else:
            response_text = "Je peux vous donner des conseils pour bien vivre avec votre maladie. Que voulez-vous savoir ?"

        return create_response(response_text, 'ConseilsVieQuotidienne')

    except Exception as e:
        logger.error(f"Erreur conseils vie: {str(e)}")
        return create_response(
            "Pour une vie épanouie, l'équilibre est essentiel. Parlez-moi de ce qui vous préoccupe !",
            'ConseilsVieQuotidienne'
        )

def handle_culture_education(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fournit des informations culturelles et éducatives avec IA
    """
    try:
        user_input = event['inputTranscript']
        user_id = event.get('userId', 'anonymous')

        # Appel de la fonction de conversation générale
        conversation_response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-general-conversation",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'intent_name': 'CultureEducation',
                'user_input': user_input,
                'user_id': user_id,
                'conversation_context': {}
            })
        )

        result = json.loads(conversation_response['Payload'].read())

        if result.get('success'):
            response_text = result['response']
        else:
            response_text = "J'adore parler de culture et d'éducation ! Quel sujet vous intéresse ?"

        return create_response(response_text, 'CultureEducation')

    except Exception as e:
        logger.error(f"Erreur culture/éducation: {str(e)}")
        return create_response(
            "La culture enrichit l'esprit ! Sur quoi voulez-vous en apprendre plus ?",
            'CultureEducation'
        )

def handle_fallback(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite les intentions non reconnues
    """
    response_text = """Je n'ai pas bien compris votre demande. 

Voici ce que je peux faire pour vous :
- Signaler des douleurs ou symptômes
- Consulter vos données vitales
- Gérer vos médicaments
- Répondre aux urgences
- Donner des conseils santé

Pouvez-vous reformuler votre question ?"""

    return create_response(response_text, 'FallbackIntent')

def extract_medical_entities(text: str) -> Dict[str, Any]:
    """
    Extrait les entités médicales du texte avec Comprehend Medical
    """
    try:
        response = comprehend_medical.detect_entities_v2(Text=text)

        entities = {
            'symptoms': [],
            'medications': [],
            'anatomy': [],
            'medical_condition': []
        }

        for entity in response.get('Entities', []):
            category = entity.get('Category', '').lower()
            text_entity = entity.get('Text', '')
            confidence = entity.get('Score', 0)

            if confidence > 0.7:  # Seuil de confiance
                if category == 'symptom':
                    entities['symptoms'].append(text_entity)
                elif category == 'medication':
                    entities['medications'].append(text_entity)
                elif category == 'anatomy':
                    entities['anatomy'].append(text_entity)
                elif category == 'medical_condition':
                    entities['medical_condition'].append(text_entity)

        return entities

    except Exception as e:
        logger.error(f"Erreur extraction entités médicales: {str(e)}")
        return {}

def assess_pain_risk(pain_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Évalue le risque basé sur le signalement de douleur
    """
    try:
        intensity = pain_context.get('intensity')
        location = pain_context.get('location', '').lower()
        symptoms = pain_context.get('medical_entities', {}).get('symptoms', [])

        risk_level = 'LOW'
        urgent = False
        recommendations = []

        # Évaluation basée sur l'intensité
        if intensity:
            intensity_num = int(intensity) if intensity.isdigit() else 0
            if intensity_num >= 8:
                risk_level = 'HIGH'
                urgent = True
                recommendations.append("Contactez immédiatement votre médecin")
            elif intensity_num >= 6:
                risk_level = 'MEDIUM'
                recommendations.append("Consultez votre médecin dans la journée")
            else:
                recommendations.append("Surveillez l'évolution de la douleur")

        # Évaluation basée sur la localisation
        if any(loc in location for loc in ['thorax', 'poitrine', 'coeur']):
            risk_level = 'HIGH'
            urgent = True
            recommendations.append("Douleur thoracique - Appelez le 115")

        # Évaluation basée sur les symptômes associés
        danger_symptoms = ['dyspnée', 'essoufflement', 'malaise', 'palpitations']
        if any(symptom.lower() in ' '.join(symptoms).lower() for symptom in danger_symptoms):
            risk_level = 'HIGH'
            urgent = True

        return {
            'risk_level': risk_level,
            'urgent': urgent,
            'recommendations': recommendations,
            'assessment_time': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Erreur évaluation risque: {str(e)}")
        return {'risk_level': 'UNKNOWN', 'urgent': False, 'recommendations': []}

def get_recent_vitals(user_id: str) -> Dict[str, Any]:
    """
    Récupère les vitales récentes depuis le pipeline IoT
    """
    try:
        # Appel à la fonction d'intégration IoT
        response = lambda_client.invoke(
            FunctionName=f"kidjamo-{os.environ['ENVIRONMENT']}-chatbot-iot-integration",
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'action': 'get_recent_vitals',
                'user_id': user_id
            })
        )

        result = json.loads(response['Payload'].read())
        return result.get('data', {})

    except Exception as e:
        logger.error(f"Erreur récupération vitales: {str(e)}")
        return {}

def generate_pain_response(pain_context: Dict[str, Any], risk_assessment: Dict[str, Any], recent_vitals: Dict[str, Any]) -> str:
    """
    Génère une réponse personnalisée pour le signalement de douleur
    """
    try:
        intensity = pain_context.get('intensity', 'non spécifiée')
        location = pain_context.get('location', 'non spécifiée')
        risk_level = risk_assessment.get('risk_level', 'LOW')
        recommendations = risk_assessment.get('recommendations', [])

        response = f"J'ai bien noté votre douleur "
        if location != 'non spécifiée':
            response += f"au niveau {location} "
        if intensity != 'non spécifiée':
            response += f"d'intensité {intensity}/10.\n\n"

        # Ajout des vitales si disponibles
        if recent_vitals:
            hr = recent_vitals.get('heart_rate')
            if hr:
                response += f"Vos dernières mesures montrent un rythme cardiaque de {hr} bpm.\n\n"

        # Ajout des recommandations
        if recommendations:
            response += "**Recommandations :**\n"
            for rec in recommendations:
                response += f"• {rec}\n"

        # Message de soutien
        response += "\nJe reste disponible pour vous accompagner. N'hésitez pas à me tenir informé de l'évolution."

        return response

    except Exception as e:
        logger.error(f"Erreur génération réponse: {str(e)}")
        return "J'ai bien noté votre signalement de douleur. Je vous recommande de contacter votre médecin."

def format_vitals_response(vitals: Dict[str, Any]) -> str:
    """
    Formate la réponse pour l'affichage des vitales
    """
    if not vitals:
        return "Aucune donnée vitale récente disponible. Vérifiez que votre bracelet est bien connecté."

    response = " **Vos données vitales récentes :**\n\n"

    if 'heart_rate' in vitals:
        hr = vitals['heart_rate']
        response += f"❤ Rythme cardiaque : {hr} bpm\n"
        if hr > 100:
            response += "   ️ Fréquence élevée détectée\n"
        elif hr < 60:
            response += "   ️ Fréquence basse\n"

    if 'spo2' in vitals:
        spo2 = vitals['spo2']
        response += f" Saturation O₂ : {spo2}%\n"
        if spo2 < 95:
            response += "   ️ Saturation basse - Consultez rapidement\n"

    if 'temperature' in vitals:
        temp = vitals['temperature']
        response += f" Température : {temp}°C\n"
        if temp > 38:
            response += "    Fièvre détectée\n"

    if 'timestamp' in vitals:
        timestamp = vitals['timestamp']
        response += f"\n Dernière mesure : {timestamp}"

    return response

def send_medical_alert(pain_context: Dict[str, Any], risk_assessment: Dict[str, Any]):
    """
    Envoie une alerte médicale
    """
    try:
        alert_message = {
            'type': 'MEDICAL_ALERT',
            'severity': risk_assessment.get('risk_level', 'MEDIUM'),
            'patient_id': pain_context.get('user_id'),
            'description': pain_context.get('description'),
            'intensity': pain_context.get('intensity'),
            'location': pain_context.get('location'),
            'timestamp': pain_context.get('timestamp'),
            'urgent': risk_assessment.get('urgent', False)
        }

        sns.publish(
            TopicArn=MEDICAL_ALERTS_TOPIC,
            Message=json.dumps(alert_message, ensure_ascii=False),
            Subject=f"Alerte médicale - Patient {pain_context.get('user_id')}"
        )

        logger.info(f"Alerte médicale envoyée pour {pain_context.get('user_id')}")

    except Exception as e:
        logger.error(f"Erreur envoi alerte médicale: {str(e)}")

def send_emergency_alert(emergency_data: Dict[str, Any]):
    """
    Envoie une alerte d'urgence
    """
    try:
        sns.publish(
            TopicArn=MEDICAL_ALERTS_TOPIC,
            Message=json.dumps(emergency_data, ensure_ascii=False),
            Subject=f" URGENCE - Patient {emergency_data.get('user_id')}"
        )

        logger.critical(f"Alerte d'urgence envoyée pour {emergency_data.get('user_id')}")

    except Exception as e:
        logger.error(f"Erreur envoi alerte urgence: {str(e)}")

def save_conversation(session_id: str, user_id: str, input_text: str, intent_name: str):
    """
    Sauvegarde l'interaction dans DynamoDB
    """
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)

        table.put_item(
            Item={
                'conversation_id': session_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': user_id,
                'input_text': input_text,
                'intent_name': intent_name,
                'expires_at': int((datetime.now(timezone.utc).timestamp() + 86400 * 30))  # 30 jours
            }
        )

    except Exception as e:
        logger.error(f"Erreur sauvegarde conversation: {str(e)}")

def create_response(message: str, intent_name: str = None) -> Dict[str, Any]:
    """
    Crée une réponse formatée pour Amazon Lex
    """
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Close'
            },
            'intent': {
                'name': intent_name or 'Unknown',
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
