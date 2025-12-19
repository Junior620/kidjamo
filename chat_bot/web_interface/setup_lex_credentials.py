#!/usr/bin/env python3
"""
Script pour générer des credentials AWS temporaires et les intégrer automatiquement
dans l'interface web du chatbot Kidjamo
"""

import boto3
import json
import os
import re
from pathlib import Path

def get_temporary_credentials():
    """Obtient des credentials temporaires AWS via STS"""
    try:
        # Utiliser les credentials configurés localement
        sts = boto3.client('sts')

        # Obtenir l'identité actuelle
        identity = sts.get_caller_identity()
        print(f"✅ Identité AWS: {identity['Arn']}")

        # Obtenir des credentials temporaires (durée de 1 heure)
        response = sts.get_session_token(DurationSeconds=3600)

        credentials = response['Credentials']

        return {
            'accessKeyId': credentials['AccessKeyId'],
            'secretAccessKey': credentials['SecretAccessKey'],
            'sessionToken': credentials['SessionToken'],
            'expiration': credentials['Expiration'].isoformat()
        }

    except Exception as e:
        print(f"❌ Erreur obtention credentials: {str(e)}")
        print("💡 Solutions:")
        print("   1. Configurez AWS CLI: aws configure")
        print("   2. Ou utilisez: aws sso login")
        print("   3. Ou définissez les variables d'environnement AWS")
        return None

def update_html_interface(credentials):
    """Met à jour l'interface HTML avec les nouveaux credentials"""
    try:
        html_file = Path('D:/kidjamo-workspace/chat_bot/web_interface/kidjamo_chatbot_interface_clean.html')

        if not html_file.exists():
            print(f"❌ Fichier HTML non trouvé: {html_file}")
            return False

        # Lire le fichier HTML
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pattern pour trouver la section des credentials temporaires
        pattern = r"const tempCredentials = \{[^}]+\};"

        # Nouveau contenu des credentials
        new_credentials = f"""const tempCredentials = {{
                    accessKeyId: '{credentials['accessKeyId']}',
                    secretAccessKey: '{credentials['secretAccessKey']}',
                    sessionToken: '{credentials['sessionToken']}',
                    region: LEX_CONFIG.region
                }};"""

        # Remplacer les credentials
        updated_content = re.sub(pattern, new_credentials, content, flags=re.DOTALL)

        # Vérifier que le remplacement a eu lieu
        if updated_content == content:
            print("⚠️ Pattern de credentials non trouvé dans le fichier HTML")
            return False

        # Sauvegarder le fichier mis à jour
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"✅ Fichier HTML mis à jour avec succès")
        print(f"⏰ Credentials valides jusqu'à: {credentials['expiration']}")

        return True

    except Exception as e:
        print(f"❌ Erreur mise à jour HTML: {str(e)}")
        return False

def create_credentials_backup(credentials):
    """Crée une sauvegarde des credentials pour référence"""
    try:
        backup_file = Path('D:/kidjamo-workspace/chat_bot/web_interface/credentials_backup.json')

        backup_data = {
            'credentials': credentials,
            'generated_at': credentials['expiration'],
            'note': 'Credentials temporaires générés automatiquement - NE PAS COMMITER'
        }

        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        print(f"✅ Sauvegarde créée: {backup_file}")

    except Exception as e:
        print(f"⚠️ Erreur sauvegarde: {str(e)}")

def main():
    print("🔐 GÉNÉRATEUR DE CREDENTIALS AWS TEMPORAIRES POUR LEX")
    print("=" * 60)

    # Étape 1: Obtenir les credentials temporaires
    print("\n1️⃣ Génération des credentials temporaires...")
    credentials = get_temporary_credentials()

    if not credentials:
        print("\n❌ Impossible d'obtenir les credentials AWS")
        print("🔧 Vérifiez votre configuration AWS:")
        print("   aws configure list")
        print("   aws sts get-caller-identity")
        return

    print(f"✅ Credentials temporaires générés")
    print(f"   Access Key: {credentials['accessKeyId'][:10]}...")
    print(f"   Expiration: {credentials['expiration']}")

    # Étape 2: Mettre à jour l'interface HTML
    print("\n2️⃣ Mise à jour de l'interface HTML...")
    success = update_html_interface(credentials)

    if not success:
        print("❌ Échec mise à jour HTML")
        return

    # Étape 3: Créer une sauvegarde
    print("\n3️⃣ Création de la sauvegarde...")
    create_credentials_backup(credentials)

    print("\n🎉 CONFIGURATION TERMINÉE AVEC SUCCÈS!")
    print("=" * 60)
    print("✅ Votre chatbot peut maintenant utiliser Lex réel!")
    print("📝 Prochaines étapes:")
    print("   1. Rechargez votre fichier HTML dans le navigateur")
    print("   2. Ouvrez la console développeur (F12)")
    print("   3. Vérifiez les logs: devrait dire 'SUCCESS! Réponse Lex reçue'")
    print("   4. Testez en envoyant un message")
    print(f"\n⏰ ATTENTION: Credentials valides pendant 1 heure jusqu'à {credentials['expiration']}")
    print("🔄 Relancez ce script quand ils expirent")

    # Instructions de test
    print("\n🧪 INSTRUCTIONS DE TEST:")
    print("   1. Ouvrez: D:/kidjamo-workspace/chat_bot/web_interface/kidjamo_chatbot_interface.html")
    print("   2. Dans la console, vous devriez voir: '✅ SUCCESS! Réponse Lex reçue'")
    print("   3. L'indicateur de statut devrait être VERT: 'Lex Réel Connecté'")
    print("   4. Envoyez un message - il utilisera votre bot Lex déployé!")

if __name__ == "__main__":
    main()
