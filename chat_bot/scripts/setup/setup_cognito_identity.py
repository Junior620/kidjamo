#!/usr/bin/env python3
"""
Configuration AWS Cognito Identity Pool pour l'interface web Kidjamo
Permet l'authentification sécurisée pour utiliser Lex depuis le navigateur
"""

import boto3
import json
from datetime import datetime

def create_cognito_identity_pool():
    """Crée un Identity Pool Cognito pour l'authentification web"""
    print("🔐 CONFIGURATION COGNITO IDENTITY POOL")
    print("=" * 50)

    region = 'eu-west-1'
    project_name = 'kidjamo'
    environment = 'dev'

    # Clients AWS
    cognito_identity = boto3.client('cognito-identity', region_name=region)
    iam = boto3.client('iam', region_name=region)

    try:
        # 1. Créer l'Identity Pool
        print("1️⃣ Création de l'Identity Pool...")

        identity_pool_name = f"{project_name}-{environment}-web-identity-pool"

        identity_pool_response = cognito_identity.create_identity_pool(
            IdentityPoolName=identity_pool_name,
            AllowUnauthenticatedIdentities=True,  # Permet l'accès anonyme pour les tests
            SupportedLoginProviders={}
        )

        identity_pool_id = identity_pool_response['IdentityPoolId']
        print(f"✅ Identity Pool créé: {identity_pool_id}")

        # 2. Créer le rôle IAM pour les utilisateurs non authentifiés
        print("\n2️⃣ Création du rôle IAM pour utilisateurs anonymes...")

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Federated": "cognito-identity.amazonaws.com"
                    },
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            "cognito-identity.amazonaws.com:aud": identity_pool_id
                        },
                        "ForAnyValue:StringLike": {
                            "cognito-identity.amazonaws.com:amr": "unauthenticated"
                        }
                    }
                }
            ]
        }

        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "lex:RecognizeText",
                        "lex:RecognizeUtterance"
                    ],
                    "Resource": [
                        f"arn:aws:lex:{region}:*:bot/HPYX4OKHYE",
                        f"arn:aws:lex:{region}:*:bot-alias/HPYX4OKHYE/AS7DAYY4IY"
                    ]
                }
            ]
        }

        role_name = f"{project_name}-{environment}-cognito-unauth-role"

        # Créer le rôle
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Rôle pour utilisateurs non authentifiés Cognito - Kidjamo Web'
        )

        role_arn = role_response['Role']['Arn']
        print(f"✅ Rôle IAM créé: {role_arn}")

        # Attacher la politique de permissions
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='KidjamoLexAccess',
            PolicyDocument=json.dumps(permissions_policy)
        )

        print("✅ Permissions Lex attachées au rôle")

        # 3. Configurer les rôles dans l'Identity Pool
        print("\n3️⃣ Configuration des rôles dans l'Identity Pool...")

        cognito_identity.set_identity_pool_roles(
            IdentityPoolId=identity_pool_id,
            Roles={
                'unauthenticated': role_arn
            }
        )

        print("✅ Rôles configurés dans l'Identity Pool")

        # 4. Générer le fichier de configuration pour l'interface web
        print("\n4️⃣ Génération de la configuration web...")

        web_config = {
            "cognito": {
                "identityPoolId": identity_pool_id,
                "region": region
            },
            "lex": {
                "botId": "HPYX4OKHYE",
                "botAliasId": "AS7DAYY4IY",
                "region": region,
                "localeId": "fr_FR"
            },
            "deployment": {
                "environment": environment,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "ready"
            }
        }

        config_path = '../web_interface/aws-config.js'

        js_config = f"""// Configuration AWS pour Kidjamo Health Assistant
// Généré automatiquement le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

window.AWS_CONFIG = {json.dumps(web_config, indent=2)};

// Fonction d'initialisation AWS
function initializeAWSWithCognito() {{
    AWS.config.region = AWS_CONFIG.cognito.region;
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({{
        IdentityPoolId: AWS_CONFIG.cognito.identityPoolId
    }});
    
    console.log('✅ AWS Cognito configuré pour Kidjamo');
    return new AWS.LexRuntimeV2();
}}
"""

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(js_config)

        print(f"✅ Configuration sauvegardée: {config_path}")

        # 5. Afficher le résumé
        print(f"\n🎉 COGNITO IDENTITY POOL CONFIGURÉ AVEC SUCCÈS!")
        print("=" * 60)
        print(f"🆔 Identity Pool ID: {identity_pool_id}")
        print(f"👤 Rôle IAM: {role_arn}")
        print(f"🌐 Région: {region}")
        print(f"📁 Config générée: {config_path}")

        print(f"\n🔧 INSTRUCTIONS D'INTÉGRATION:")
        print("1. Ajoutez dans votre HTML (avant les autres scripts):")
        print('   <script src="aws-config.js"></script>')
        print()
        print("2. Remplacez la fonction initializeAWS() par:")
        print("   lexRuntime = initializeAWSWithCognito();")
        print()
        print("3. Testez votre interface web - Lex réel sera actif!")

        return {
            'identity_pool_id': identity_pool_id,
            'role_arn': role_arn,
            'config_file': config_path
        }

    except Exception as e:
        print(f"❌ Erreur lors de la configuration Cognito: {str(e)}")

        if "EntityAlreadyExistsException" in str(e):
            print("💡 L'Identity Pool existe peut-être déjà")
            print("🔄 Vérifiez dans la console AWS Cognito")

        return None

def list_existing_identity_pools():
    """Liste les Identity Pools existants"""
    print("\n🔍 IDENTITY POOLS EXISTANTS")
    print("-" * 30)

    try:
        cognito_identity = boto3.client('cognito-identity', region_name='eu-west-1')

        response = cognito_identity.list_identity_pools(MaxResults=10)

        pools = response.get('IdentityPools', [])

        if pools:
            for pool in pools:
                pool_id = pool['IdentityPoolId']
                pool_name = pool['IdentityPoolName']
                print(f"📋 {pool_name}")
                print(f"   ID: {pool_id}")
        else:
            print("❌ Aucun Identity Pool trouvé")

    except Exception as e:
        print(f"❌ Erreur: {str(e)}")

if __name__ == "__main__":
    # Lister les pools existants d'abord
    list_existing_identity_pools()

    # Créer le nouveau pool
    result = create_cognito_identity_pool()

    if result:
        print(f"\n✅ Configuration terminée avec succès!")
        print(f"🚀 Votre interface web peut maintenant utiliser Lex réel de manière sécurisée")
    else:
        print(f"\n❌ Configuration échouée")
        print(f"💡 Vérifiez vos permissions AWS et réessayez")
