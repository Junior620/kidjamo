#!/usr/bin/env python3
"""
Récupération des identifiants du bot Lex déployé avec succès
"""

import boto3
import json
from datetime import datetime

def get_bot_identifiers():
    """Récupère les identifiants du bot Lex déployé"""
    print("🔍 RÉCUPÉRATION DES IDENTIFIANTS DU BOT LEX")
    print("=" * 50)
    
    lex_v2 = boto3.client('lexv2-models', region_name='eu-west-1')
    
    try:
        # Lister les bots Kidjamo
        bots_response = lex_v2.list_bots()
        
        for bot in bots_response.get('botSummaries', []):
            if 'kidjamo' in bot['botName'].lower() and 'health' in bot['botName'].lower():
                bot_id = bot['botId']
                bot_name = bot['botName']
                bot_status = bot['botStatus']
                
                print(f"🤖 Bot trouvé: {bot_name}")
                print(f"🆔 Bot ID: {bot_id}")
                print(f"📊 Statut: {bot_status}")
                
                if bot_status == 'Available':
                    # Récupérer les alias
                    try:
                        aliases_response = lex_v2.list_bot_aliases(
                            botId=bot_id
                        )
                        
                        for alias in aliases_response.get('botAliasSummaries', []):
                            if 'dev' in alias['botAliasName'].lower():
                                alias_id = alias['botAliasId']
                                alias_name = alias['botAliasName']
                                alias_status = alias['botAliasStatus']
                                
                                print(f"🏷️ Alias trouvé: {alias_name}")
                                print(f"🆔 Alias ID: {alias_id}")
                                print(f"📊 Statut alias: {alias_status}")
                                
                                # Récupérer l'ARN Lambda
                                lambda_arn = get_lambda_arn()
                                
                                # Créer la configuration
                                config = {
                                    'deployment_info': {
                                        'bot_id': bot_id,
                                        'bot_name': bot_name,
                                        'alias_id': alias_id,
                                        'alias_name': alias_name,
                                        'lambda_arn': lambda_arn,
                                        'kendra_index_id': 'b7472109-44e4-42de-9192-2b6dbe1493cc'
                                    },
                                    'region': 'eu-west-1',
                                    'environment': 'dev',
                                    'deployment_time': datetime.now().timestamp(),
                                    'status': 'SUCCESS'
                                }
                                
                                # Sauvegarder la configuration
                                with open('lex_deployment_config.json', 'w') as f:
                                    json.dump(config, f, indent=2)
                                
                                print(f"\n✅ CONFIGURATION SAUVEGARDÉE")
                                print(f"📁 Fichier: lex_deployment_config.json")
                                
                                # Afficher le résumé
                                print(f"\n🎯 RÉSUMÉ DÉPLOIEMENT RÉUSSI")
                                print(f"=" * 40)
                                print(f"🤖 Bot ID: {bot_id}")
                                print(f"🏷️ Alias ID: {alias_id}")
                                print(f"⚡ Lambda ARN: {lambda_arn}")
                                print(f"🔍 Kendra Index: b7472109-44e4-42de-9192-2b6dbe1493cc")
                                print(f"🌐 Région: eu-west-1")
                                print(f"🏷️ Environnement: dev")
                                
                                return config
                    
                    except Exception as e:
                        print(f"❌ Erreur récupération alias: {str(e)}")
                
                break
        
        print("❌ Aucun bot Kidjamo health trouvé")
        return None
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return None

def get_lambda_arn():
    """Récupère l'ARN de la fonction Lambda de fulfillment"""
    lambda_client = boto3.client('lambda', region_name='eu-west-1')
    
    try:
        response = lambda_client.get_function(
            FunctionName='kidjamo-dev-lex-fulfillment'
        )
        return response['Configuration']['FunctionArn']
    except Exception as e:
        print(f"⚠️ Impossible de récupérer l'ARN Lambda: {str(e)}")
        return "arn:aws:lambda:eu-west-1:930900578484:function:kidjamo-dev-lex-fulfillment"

if __name__ == "__main__":
    get_bot_identifiers()
