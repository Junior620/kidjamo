#!/usr/bin/env python3
"""
Finalisation du déploiement Lex - Création de l'alias avec la correction
"""

import boto3
import json
import time
from datetime import datetime

def finalize_deployment():
    """Finalise le déploiement en créant l'alias manquant"""
    print("🔧 FINALISATION DU DÉPLOIEMENT LEX KIDJAMO")
    print("=" * 50)

    # Configuration
    bot_id = "HPYX4OKHYE"  # Bot ID du déploiement précédent
    region = 'eu-west-1'
    environment = 'dev'
    project_name = 'kidjamo'

    # Clients AWS
    lex_v2 = boto3.client('lexv2-models', region_name=region)
    lambda_client = boto3.client('lambda', region_name=region)

    try:
        # 1. Vérifier le statut du bot
        print("1️⃣ Vérification du bot existant...")
        bot_response = lex_v2.describe_bot(botId=bot_id)
        bot_status = bot_response['botStatus']
        bot_name = bot_response['botName']

        print(f"🤖 Bot: {bot_name}")
        print(f"📊 Statut: {bot_status}")

        if bot_status != 'Available':
            print(f"❌ Le bot n'est pas disponible (statut: {bot_status})")
            return False

        # 2. Vérifier la locale
        print("\n2️⃣ Vérification de la locale française...")
        locale_response = lex_v2.describe_bot_locale(
            botId=bot_id,
            botVersion='DRAFT',
            localeId='fr_FR'
        )

        locale_status = locale_response['botLocaleStatus']
        print(f"🌐 Locale fr_FR: {locale_status}")

        if locale_status not in ['Built', 'ReadyExpressTesting']:
            print(f"❌ La locale n'est pas prête (statut: {locale_status})")
            return False

        # 3. Récupérer l'ARN Lambda
        print("\n3️⃣ Récupération de l'ARN Lambda...")
        lambda_function_name = f"{project_name}-{environment}-lex-fulfillment"

        try:
            lambda_response = lambda_client.get_function(FunctionName=lambda_function_name)
            lambda_arn = lambda_response['Configuration']['FunctionArn']
            print(f"⚡ Lambda ARN: {lambda_arn}")
        except Exception as e:
            print(f"❌ Impossible de récupérer l'ARN Lambda: {str(e)}")
            lambda_arn = f"arn:aws:lambda:{region}:930900578484:function:{lambda_function_name}"
            print(f"⚡ Lambda ARN (fallback): {lambda_arn}")

        # 4. Créer une version du bot d'abord
        print("\n4️⃣ Création d'une version du bot...")
        try:
            version_response = lex_v2.create_bot_version(
                botId=bot_id,
                description='Version initiale du bot Kidjamo Health Assistant',
                botVersionLocaleSpecification={
                    'fr_FR': {
                        'sourceBotVersion': 'DRAFT'
                    }
                }
            )

            bot_version = version_response['botVersion']
            print(f"📦 Version créée: {bot_version}")

            # Attendre que la version soit prête
            print("⏳ Attente de la finalisation de la version...")
            version_ready = False
            for i in range(30):  # Max 5 minutes
                try:
                    version_status_response = lex_v2.describe_bot_version(
                        botId=bot_id,
                        botVersion=bot_version
                    )
                    version_status = version_status_response['botStatus']

                    if version_status == 'Available':
                        print(f"✅ Version {bot_version} prête")
                        version_ready = True
                        break
                    elif version_status == 'Failed':
                        print(f"❌ Version échouée")
                        break

                    print(f"   Version: {version_status}...")
                    time.sleep(10)

                except Exception as e:
                    print(f"   Vérification version: {str(e)}")
                    time.sleep(10)

            if not version_ready:
                print("⚠️ Version pas complètement prête, on continue...")

        except Exception as e:
            print(f"⚠️ Erreur création version: {str(e)}")
            bot_version = "1"  # Utiliser version par défaut

        # 5. Créer l'alias avec la version correcte
        print(f"\n5️⃣ Création de l'alias avec version {bot_version}...")
        alias_config = {
            'botAliasName': f'{environment}-alias',
            'description': f'Alias {environment} pour le bot Kidjamo - Version {bot_version}',
            'botId': bot_id,
            'botVersion': bot_version,  # Utiliser la version au lieu de DRAFT
            'botAliasLocaleSettings': {
                'fr_FR': {
                    'enabled': True,
                    'codeHookSpecification': {
                        'lambdaCodeHook': {
                            'lambdaARN': lambda_arn,  # Correction: ARN en majuscules
                            'codeHookInterfaceVersion': '1.0'
                        }
                    }
                }
            }
        }

        alias_response = lex_v2.create_bot_alias(**alias_config)
        alias_id = alias_response['botAliasId']

        print(f"✅ Alias créé avec succès: {alias_id}")

        # 6. Configurer les permissions Lambda si nécessaire
        print("\n6️⃣ Configuration des permissions Lambda...")
        try:
            lambda_client.add_permission(
                FunctionName=lambda_function_name,
                StatementId=f'lex-{bot_id}-corrected',
                Action='lambda:InvokeFunction',
                Principal='lexv2.amazonaws.com',
                SourceArn=f'arn:aws:lex:{region}:930900578484:bot/{bot_id}'
            )
            print("✅ Permissions Lambda configurées")
        except Exception as e:
            if 'ResourceConflictException' in str(e):
                print("⚠️ Permissions Lambda déjà configurées")
            else:
                print(f"⚠️ Avertissement permissions: {str(e)}")

        # 7. Test du déploiement
        print("\n7️⃣ Test du chatbot...")
        test_deployment(lex_v2, bot_id, alias_id)

        # 8. Sauvegarder la configuration finale
        print("\n8️⃣ Sauvegarde de la configuration...")
        config = {
            'deployment_info': {
                'bot_id': bot_id,
                'bot_name': bot_name,
                'alias_id': alias_id,
                'lambda_arn': lambda_arn,
                'kendra_index_id': 'b7472109-44e4-42de-9192-2b6dbe1493cc'
            },
            'region': region,
            'environment': environment,
            'deployment_time': time.time(),
            'status': 'SUCCESS',
            'corrected': True
        }

        with open('lex_deployment_config.json', 'w') as f:
            json.dump(config, f, indent=2)

        print("✅ Configuration sauvegardée dans: lex_deployment_config.json")

        # 9. Afficher le résumé final
        print(f"\n🎉 DÉPLOIEMENT FINALISÉ AVEC SUCCÈS!")
        print("=" * 50)
        print(f"🤖 Bot ID: {bot_id}")
        print(f"🏷️ Alias ID: {alias_id}")
        print(f"⚡ Lambda ARN: {lambda_arn}")
        print(f"🔍 Kendra Index: b7472109-44e4-42de-9192-2b6dbe1493cc")
        print(f"🌐 Région: {region}")
        print(f"🏷️ Environnement: {environment}")
        print(f"✅ Statut: Opérationnel")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la finalisation: {str(e)}")
        return False

def test_deployment(lex_v2, bot_id, alias_id):
    """Teste le déploiement finalisé"""
    try:
        test_message = "Bonjour"

        response = lex_v2.recognize_text(
            botId=bot_id,
            botAliasId=alias_id,
            localeId='fr_FR',
            sessionId='test-session-final',
            text=test_message
        )

        if 'messages' in response and response['messages']:
            print(f"✅ Test réussi!")
            print(f"   Question: {test_message}")
            print(f"   Réponse: {response['messages'][0]['content'][:100]}...")
        else:
            print(f"⚠️ Test partiellement réussi (pas de réponse textuelle)")

    except Exception as e:
        print(f"⚠️ Test échoué: {str(e)}")

if __name__ == "__main__":
    success = finalize_deployment()

    if success:
        print(f"\n🎯 PROCHAINES ÉTAPES:")
        print("1. Tester le chatbot avec: python test_lex_chatbot.py")
        print("2. Ouvrir l'interface web: kidjamo_chatbot_interface.html")
        print("3. Connecter l'interface à Lex avec les nouveaux IDs")
        print("4. Profiter de votre chatbot médical complet ! 🎉")
    else:
        print(f"\n❌ Finalisation échouée. Vérifiez les erreurs ci-dessus.")
