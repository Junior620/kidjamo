#!/usr/bin/env python3
"""
Surveillance en temps réel du déploiement Lex Kidjamo
"""

import boto3
import json
import time
from datetime import datetime

def check_deployment_status():
    """Vérifie l'état du déploiement en cours"""
    print("🔍 SURVEILLANCE DU DÉPLOIEMENT LEX KIDJAMO")
    print("=" * 50)

    lex_v2 = boto3.client('lexv2-models', region_name='eu-west-1')

    try:
        # Lister tous les bots Kidjamo
        bots_response = lex_v2.list_bots()

        kidjamo_bots = []
        for bot in bots_response.get('botSummaries', []):
            if 'kidjamo' in bot['botName'].lower():
                kidjamo_bots.append(bot)

        if not kidjamo_bots:
            print("❌ Aucun bot Kidjamo trouvé")
            print("💡 Le déploiement n'a peut-être pas encore créé le bot")
            return

        print(f"🤖 {len(kidjamo_bots)} bot(s) Kidjamo trouvé(s):")

        for bot in kidjamo_bots:
            bot_id = bot['botId']
            bot_name = bot['botName']
            bot_status = bot['botStatus']
            last_updated = bot.get('lastUpdatedDateTime', 'Inconnu')

            print(f"\n📋 Bot: {bot_name}")
            print(f"   🆔 ID: {bot_id}")
            print(f"   📊 Statut: {format_status(bot_status)}")
            print(f"   🕒 Dernière MAJ: {last_updated}")

            # Vérifier les détails du bot
            try:
                bot_details = lex_v2.describe_bot(botId=bot_id)

                if 'failureReasons' in bot_details:
                    print(f"   ❌ Erreurs: {bot_details['failureReasons']}")

                # Vérifier les locales
                try:
                    locales_response = lex_v2.list_bot_locales(
                        botId=bot_id,
                        botVersion='DRAFT'
                    )

                    locales = locales_response.get('botLocaleSummaries', [])
                    print(f"   🌐 Locales configurées: {len(locales)}")

                    for locale in locales:
                        locale_id = locale['localeId']
                        locale_status = locale['botLocaleStatus']
                        print(f"      • {locale_id}: {format_status(locale_status)}")

                        # Si la locale est en cours de création, surveiller
                        if locale_status in ['Creating', 'Building']:
                            print(f"        ⏳ Locale en cours de traitement...")

                except Exception as e:
                    print(f"   ⚠️ Impossible de vérifier les locales: {str(e)}")

            except Exception as e:
                print(f"   ❌ Erreur détails bot: {str(e)}")

    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {str(e)}")

def check_lambda_functions():
    """Vérifie les fonctions Lambda déployées"""
    print(f"\n⚡ FONCTIONS LAMBDA")
    print("-" * 30)

    lambda_client = boto3.client('lambda', region_name='eu-west-1')

    try:
        functions = lambda_client.list_functions()

        kidjamo_functions = []
        for func in functions['Functions']:
            if 'kidjamo' in func['FunctionName'].lower():
                kidjamo_functions.append(func)

        if kidjamo_functions:
            print(f"🔧 {len(kidjamo_functions)} fonction(s) Lambda Kidjamo:")

            for func in kidjamo_functions:
                name = func['FunctionName']
                state = func.get('State', 'Active')  # Valeur par défaut si State n'existe pas
                last_modified = func['LastModified']

                print(f"   • {name}")
                print(f"     État: {format_status(state)}")
                print(f"     MAJ: {last_modified}")
        else:
            print("❌ Aucune fonction Lambda Kidjamo trouvée")

    except Exception as e:
        print(f"❌ Erreur Lambda: {str(e)}")

def check_iam_roles():
    """Vérifie les rôles IAM créés"""
    print(f"\n🔐 RÔLES IAM")
    print("-" * 30)

    iam = boto3.client('iam', region_name='eu-west-1')

    try:
        roles = iam.list_roles()

        kidjamo_roles = []
        for role in roles['Roles']:
            if 'kidjamo' in role['RoleName'].lower():
                kidjamo_roles.append(role)

        if kidjamo_roles:
            print(f"👤 {len(kidjamo_roles)} rôle(s) IAM Kidjamo:")

            for role in kidjamo_roles:
                name = role['RoleName']
                created = role['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')

                print(f"   • {name}")
                print(f"     Créé: {created}")
        else:
            print("❌ Aucun rôle IAM Kidjamo trouvé")

    except Exception as e:
        print(f"❌ Erreur IAM: {str(e)}")

def format_status(status):
    """Formate le statut avec des émojis"""
    status_map = {
        'Available': '✅ DISPONIBLE',
        'Creating': '🔄 CRÉATION',
        'Building': '🔨 CONSTRUCTION',
        'Built': '✅ CONSTRUIT',
        'NotBuilt': '⏳ NON CONSTRUIT',
        'Updating': '🔄 MISE À JOUR',
        'Failed': '❌ ÉCHEC',
        'Deleting': '🗑️ SUPPRESSION',
        'Active': '✅ ACTIF',
        'Pending': '⏳ EN ATTENTE'
    }

    return status_map.get(status, f"❓ {status}")

def check_for_config_file():
    """Vérifie si le fichier de configuration a été généré"""
    print(f"\n📄 FICHIER DE CONFIGURATION")
    print("-" * 30)

    import os

    config_path = 'lex_deployment_config.json'

    if os.path.exists(config_path):
        print("✅ Fichier de configuration trouvé!")

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            deployment_info = config.get('deployment_info', {})
            deployment_time = config.get('deployment_time', 0)

            if deployment_time:
                deploy_date = datetime.fromtimestamp(deployment_time)
                print(f"🕒 Déployé le: {deploy_date.strftime('%Y-%m-%d %H:%M:%S')}")

            if deployment_info:
                print(f"🤖 Bot ID: {deployment_info.get('bot_id', 'N/A')}")
                print(f"🏷️ Alias ID: {deployment_info.get('alias_id', 'N/A')}")
                print(f"⚡ Lambda ARN: {deployment_info.get('lambda_arn', 'N/A')}")
                print(f"🔍 Kendra Index: {deployment_info.get('kendra_index_id', 'N/A')}")

        except Exception as e:
            print(f"⚠️ Erreur lecture config: {str(e)}")

    else:
        print("⏳ Fichier de configuration pas encore généré")
        print("💡 Le déploiement est probablement encore en cours")

def main():
    """Surveillance complète"""
    print(f"🕒 Surveillance à {datetime.now().strftime('%H:%M:%S')}")

    # Vérifier les ressources AWS
    check_deployment_status()
    check_lambda_functions()
    check_iam_roles()
    check_for_config_file()

    print(f"\n💡 CONSEILS:")
    print("• Si aucun bot n'est trouvé, le déploiement est encore en cours")
    print("• Si le statut est 'Creating' ou 'Building', patienter")
    print("• Si le statut est 'Failed', vérifier les logs")
    print("• Le processus complet peut prendre 15-30 minutes")

if __name__ == "__main__":
    main()
