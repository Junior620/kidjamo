"""
Script de configuration automatique du bot Amazon Lex
Chatbot Santé Kidjamo - MVP
"""

import json
import boto3
import argparse
import logging
import time
from typing import Dict, Any

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Configuration du bot Amazon Lex')
    parser.add_argument('--bot-definition', required=True, help='Fichier JSON de définition du bot')
    parser.add_argument('--fulfillment-arn', required=True, help='ARN de la fonction Lambda de fulfillment')
    parser.add_argument('--environment', required=True, help='Environnement (dev, stg, prod)')
    parser.add_argument('--region', default='eu-west-1', help='Région AWS')

    args = parser.parse_args()

    # Initialisation des clients AWS
    lexv2 = boto3.client('lexv2-models', region_name=args.region)

    try:
        # Chargement de la définition du bot
        with open(args.bot_definition, 'r', encoding='utf-8') as f:
            bot_definition = json.load(f)

        # Mise à jour de la configuration avec les paramètres d'environnement
        bot_name = f"kidjamo-{args.environment}-health-bot"
        bot_definition['bot']['name'] = bot_name

        # Mise à jour de l'ARN de fulfillment
        for locale in bot_definition['bot']['botLocales']:
            for intent in locale['intents']:
                if 'fulfillmentCodeHook' in intent:
                    intent['fulfillmentCodeHook']['lambdaCodeHook'] = {
                        'lambdaArn': args.fulfillment_arn,
                        'codeHookInterfaceVersion': '1.0'
                    }

        # Création du bot
        logger.info(f"Création du bot {bot_name}...")
        bot_response = create_bot(lexv2, bot_definition['bot'])
        bot_id = bot_response['botId']

        logger.info(f"Bot créé avec l'ID: {bot_id}")

        # Attente que le bot soit prêt
        wait_for_bot_available(lexv2, bot_id)

        # Configuration des locales
        logger.info("Configuration des locales...")
        for locale_config in bot_definition['bot']['botLocales']:
            configure_bot_locale(lexv2, bot_id, locale_config)

        # Construction du bot
        logger.info("Construction du bot...")
        build_bot(lexv2, bot_id, 'fr_FR')

        # Création des alias
        logger.info("Création des alias...")
        for alias_config in bot_definition['bot'].get('testBotAliases', []):
            create_bot_alias(lexv2, bot_id, alias_config)

        logger.info("✅ Configuration du bot terminée avec succès !")
        logger.info(f"Bot ID: {bot_id}")

        return bot_id

    except Exception as e:
        logger.error(f"Erreur lors de la configuration du bot: {str(e)}")
        raise

def create_bot(lexv2_client, bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Crée le bot Amazon Lex"""
    try:
        response = lexv2_client.create_bot(
            botName=bot_config['name'],
            description=bot_config['description'],
            roleArn=bot_config['roleArn'],
            dataPrivacy=bot_config['dataPrivacy'],
            idleSessionTTLInSeconds=bot_config['idleSessionTTLInSeconds']
        )
        return response
    except lexv2_client.exceptions.ConflictException:
        # Le bot existe déjà, récupération de l'ID
        logger.warning(f"Le bot {bot_config['name']} existe déjà")
        bots = lexv2_client.list_bots()
        for bot in bots['botSummaries']:
            if bot['botName'] == bot_config['name']:
                return {'botId': bot['botId']}
        raise

def wait_for_bot_available(lexv2_client, bot_id: str, max_wait: int = 300):
    """Attend que le bot soit disponible"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = lexv2_client.describe_bot(botId=bot_id)
        status = response['botStatus']

        if status == 'Available':
            logger.info("Bot disponible")
            return
        elif status == 'Failed':
            raise Exception("La création du bot a échoué")

        logger.info(f"Statut du bot: {status}. Attente...")
        time.sleep(10)

    raise Exception("Timeout: le bot n'est pas devenu disponible")

def configure_bot_locale(lexv2_client, bot_id: str, locale_config: Dict[str, Any]):
    """Configure une locale pour le bot"""
    locale_id = locale_config['localeId']

    try:
        # Création de la locale
        lexv2_client.create_bot_locale(
            botId=bot_id,
            botVersion='DRAFT',
            localeId=locale_id,
            description=locale_config['description'],
            nluIntentConfidenceThreshold=locale_config['nluIntentConfidenceThreshold'],
            voiceSettings=locale_config.get('voiceSettings', {})
        )

        # Attente que la locale soit prête
        wait_for_bot_locale_built(lexv2_client, bot_id, locale_id)

        # Création des types de slots
        for slot_type in locale_config.get('slotTypes', []):
            create_slot_type(lexv2_client, bot_id, locale_id, slot_type)

        # Création des intentions
        for intent in locale_config.get('intents', []):
            create_intent(lexv2_client, bot_id, locale_id, intent)

    except lexv2_client.exceptions.ConflictException:
        logger.warning(f"La locale {locale_id} existe déjà")

def wait_for_bot_locale_built(lexv2_client, bot_id: str, locale_id: str, max_wait: int = 300):
    """Attend que la locale soit construite"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = lexv2_client.describe_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId=locale_id
            )
            status = response['botLocaleStatus']

            if status == 'Built':
                return
            elif status == 'Failed':
                raise Exception(f"La construction de la locale {locale_id} a échoué")

            time.sleep(5)
        except lexv2_client.exceptions.ResourceNotFoundException:
            time.sleep(5)

    raise Exception(f"Timeout: la locale {locale_id} n'est pas devenue disponible")

def create_slot_type(lexv2_client, bot_id: str, locale_id: str, slot_type_config: Dict[str, Any]):
    """Crée un type de slot personnalisé"""
    try:
        lexv2_client.create_slot_type(
            botId=bot_id,
            botVersion='DRAFT',
            localeId=locale_id,
            slotTypeName=slot_type_config['slotTypeName'],
            description=slot_type_config['description'],
            slotTypeValues=slot_type_config['slotTypeValues'],
            valueSelectionStrategy=slot_type_config['valueSelectionStrategy']
        )
        logger.info(f"Type de slot créé: {slot_type_config['slotTypeName']}")
    except lexv2_client.exceptions.ConflictException:
        logger.warning(f"Le type de slot {slot_type_config['slotTypeName']} existe déjà")

def create_intent(lexv2_client, bot_id: str, locale_id: str, intent_config: Dict[str, Any]):
    """Crée une intention"""
    try:
        # Préparation des paramètres d'intention
        intent_params = {
            'botId': bot_id,
            'botVersion': 'DRAFT',
            'localeId': locale_id,
            'intentName': intent_config['intentName'],
            'description': intent_config['description']
        }

        # Ajout des exemples d'énoncés
        if 'sampleUtterances' in intent_config:
            intent_params['sampleUtterances'] = intent_config['sampleUtterances']

        # Ajout des slots
        if 'slots' in intent_config:
            intent_params['slotPriorities'] = []
            for i, slot in enumerate(intent_config['slots']):
                intent_params['slotPriorities'].append({
                    'priority': i + 1,
                    'slotName': slot['slotName']
                })

        # Ajout du fulfillment hook
        if 'fulfillmentCodeHook' in intent_config:
            intent_params['fulfillmentCodeHook'] = intent_config['fulfillmentCodeHook']

        # Gestion des intentions parentes (comme FallbackIntent)
        if 'parentIntentSignature' in intent_config:
            intent_params['parentIntentSignature'] = intent_config['parentIntentSignature']

        # Création de l'intention
        response = lexv2_client.create_intent(**intent_params)
        intent_id = response['intentId']

        # Création des slots pour cette intention
        if 'slots' in intent_config:
            for slot in intent_config['slots']:
                create_slot(lexv2_client, bot_id, locale_id, intent_id, slot)

        logger.info(f"Intention créée: {intent_config['intentName']}")

    except lexv2_client.exceptions.ConflictException:
        logger.warning(f"L'intention {intent_config['intentName']} existe déjà")

def create_slot(lexv2_client, bot_id: str, locale_id: str, intent_id: str, slot_config: Dict[str, Any]):
    """Crée un slot pour une intention"""
    try:
        lexv2_client.create_slot(
            botId=bot_id,
            botVersion='DRAFT',
            localeId=locale_id,
            intentId=intent_id,
            slotName=slot_config['slotName'],
            description=slot_config['description'],
            slotTypeId=slot_config['slotTypeName'],  # Référence au type de slot
            valueElicitationPrompt=slot_config.get('valueElicitationPrompt', {})
        )
        logger.info(f"Slot créé: {slot_config['slotName']}")
    except lexv2_client.exceptions.ConflictException:
        logger.warning(f"Le slot {slot_config['slotName']} existe déjà")

def build_bot(lexv2_client, bot_id: str, locale_id: str):
    """Lance la construction du bot"""
    try:
        lexv2_client.build_bot_locale(
            botId=bot_id,
            botVersion='DRAFT',
            localeId=locale_id
        )

        # Attente de la fin de construction
        wait_for_bot_locale_built(lexv2_client, bot_id, locale_id)
        logger.info("Construction du bot terminée")

    except Exception as e:
        logger.error(f"Erreur lors de la construction du bot: {str(e)}")
        raise

def create_bot_alias(lexv2_client, bot_id: str, alias_config: Dict[str, Any]):
    """Crée un alias pour le bot"""
    try:
        lexv2_client.create_bot_alias(
            botId=bot_id,
            botAliasName=alias_config['botAliasName'],
            description=alias_config['description'],
            botVersion=alias_config['botVersion']
        )
        logger.info(f"Alias créé: {alias_config['botAliasName']}")
    except lexv2_client.exceptions.ConflictException:
        logger.warning(f"L'alias {alias_config['botAliasName']} existe déjà")

if __name__ == '__main__':
    main()
