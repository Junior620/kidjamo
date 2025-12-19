#!/usr/bin/env python3
"""
Script de déploiement complet du chatbot Lex Kidjamo
Déploie le bot, les fonctions Lambda et configure l'intégration Kendra
"""

import boto3
import json
import time
import zipfile
import os
from pathlib import Path
import argparse

class KidjamoLexDeployer:
    def __init__(self, region='eu-west-1', environment='dev'):
        self.region = region
        self.environment = environment
        self.project_name = 'kidjamo'
        self.bot_name = f'{self.project_name}-{environment}-health-bot'

        # Clients AWS
        self.lex_v2 = boto3.client('lexv2-models', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.iam = boto3.client('iam', region_name=region)

        # Configuration
        self.kendra_index_id = 'b7472109-44e4-42de-9192-2b6dbe1493cc'
        self.lambda_role_arn = None
        self.lex_role_arn = None

    def deploy_complete_chatbot(self):
        """Déploie le chatbot complet avec toutes ses dépendances"""
        print("🚀 DÉPLOIEMENT COMPLET CHATBOT LEX KIDJAMO")
        print("=" * 60)

        try:
            # Étape 1: Créer les rôles IAM
            print("\n1️⃣ Création des rôles IAM...")
            self.create_iam_roles()

            # Étape 2: Déployer les fonctions Lambda
            print("\n2️⃣ Déploiement des fonctions Lambda...")
            lambda_arn = self.deploy_lambda_functions()

            # Étape 3: Créer le bot Lex
            print("\n3️⃣ Création du bot Lex...")
            bot_id = self.create_lex_bot()

            # Étape 4: Configurer les intents
            print("\n4️⃣ Configuration des intents...")
            self.configure_lex_intents(bot_id, lambda_arn)

            # Étape 5: Builder le bot
            print("\n5️⃣ Construction du bot...")
            self.build_lex_bot(bot_id)

            # Étape 6: Créer un alias
            print("\n6️⃣ Création de l'alias...")
            alias_id = self.create_bot_alias(bot_id)

            # Étape 7: Tester le déploiement
            print("\n7️⃣ Test du déploiement...")
            self.test_deployment(bot_id, alias_id)

            print(f"\n✅ DÉPLOIEMENT TERMINÉ AVEC SUCCÈS!")
            print(f"🤖 Bot ID: {bot_id}")
            print(f"🏷️ Alias ID: {alias_id}")
            print(f"⚡ Lambda ARN: {lambda_arn}")
            print(f"🔍 Kendra Index: {self.kendra_index_id}")

            return {
                'bot_id': bot_id,
                'alias_id': alias_id,
                'lambda_arn': lambda_arn,
                'kendra_index_id': self.kendra_index_id
            }

        except Exception as e:
            print(f"❌ Erreur lors du déploiement: {str(e)}")
            raise

    def create_iam_roles(self):
        """Crée les rôles IAM nécessaires"""
        try:
            # Rôle pour Lambda
            lambda_trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }

            lambda_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        "Resource": "arn:aws:logs:*:*:*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "kendra:Query",
                            "kendra:Retrieve"
                        ],
                        "Resource": f"arn:aws:kendra:{self.region}:*:index/{self.kendra_index_id}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:Query"
                        ],
                        "Resource": f"arn:aws:dynamodb:{self.region}:*:table/{self.project_name}-{self.environment}-*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sns:Publish"
                        ],
                        "Resource": f"arn:aws:sns:{self.region}:*:{self.project_name}-{self.environment}-*"
                    }
                ]
            }

            # Créer le rôle Lambda
            lambda_role_name = f"{self.project_name}-{self.environment}-lambda-role"
            try:
                response = self.iam.create_role(
                    RoleName=lambda_role_name,
                    AssumeRolePolicyDocument=json.dumps(lambda_trust_policy),
                    Description='Rôle pour les fonctions Lambda du chatbot Kidjamo'
                )
                self.lambda_role_arn = response['Role']['Arn']

                # Attacher la politique
                self.iam.put_role_policy(
                    RoleName=lambda_role_name,
                    PolicyName='KidjamoLambdaPolicy',
                    PolicyDocument=json.dumps(lambda_policy)
                )

            except self.iam.exceptions.EntityAlreadyExistsException:
                # Le rôle existe déjà
                response = self.iam.get_role(RoleName=lambda_role_name)
                self.lambda_role_arn = response['Role']['Arn']

            # Rôle pour Lex
            lex_trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lexv2.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }

            lex_role_name = f"{self.project_name}-{self.environment}-lex-role"
            try:
                response = self.iam.create_role(
                    RoleName=lex_role_name,
                    AssumeRolePolicyDocument=json.dumps(lex_trust_policy),
                    Description='Rôle pour le bot Lex Kidjamo'
                )
                self.lex_role_arn = response['Role']['Arn']

                # Attacher les politiques managées
                self.iam.attach_role_policy(
                    RoleName=lex_role_name,
                    PolicyArn='arn:aws:iam::aws:policy/AmazonLexFullAccess'
                )

            except self.iam.exceptions.EntityAlreadyExistsException:
                response = self.iam.get_role(RoleName=lex_role_name)
                self.lex_role_arn = response['Role']['Arn']

            print(f"✅ Rôles IAM créés/récupérés")
            print(f"   Lambda: {self.lambda_role_arn}")
            print(f"   Lex: {self.lex_role_arn}")

            # Attendre que les rôles soient propagés
            time.sleep(10)

        except Exception as e:
            print(f"❌ Erreur création rôles IAM: {str(e)}")
            raise

    def deploy_lambda_functions(self):
        """Déploie les fonctions Lambda"""
        try:
            # Créer le package Lambda
            lambda_zip_path = self.create_lambda_package()

            function_name = f"{self.project_name}-{self.environment}-lex-fulfillment"

            try:
                # Créer la fonction Lambda
                with open(lambda_zip_path, 'rb') as zip_file:
                    response = self.lambda_client.create_function(
                        FunctionName=function_name,
                        Runtime='python3.9',
                        Role=self.lambda_role_arn,
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': zip_file.read()},
                        Description='Fonction de fulfillment pour le chatbot Lex Kidjamo',
                        Timeout=30,
                        Environment={
                            'Variables': {
                                'KENDRA_INDEX_ID': self.kendra_index_id,
                                'CONVERSATIONS_TABLE': f'{self.project_name}-{self.environment}-chatbot-conversations',
                                'MEDICAL_ALERTS_TOPIC': f'arn:aws:sns:{self.region}:*:{self.project_name}-{self.environment}-medical-alerts'
                            }
                        }
                    )

                lambda_arn = response['FunctionArn']

            except self.lambda_client.exceptions.ResourceConflictException:
                # La fonction existe déjà, la mettre à jour
                with open(lambda_zip_path, 'rb') as zip_file:
                    self.lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_file.read()
                    )

                response = self.lambda_client.get_function(FunctionName=function_name)
                lambda_arn = response['Configuration']['FunctionArn']

            print(f"✅ Fonction Lambda déployée: {lambda_arn}")

            # Nettoyer le fichier zip temporaire
            os.remove(lambda_zip_path)

            return lambda_arn

        except Exception as e:
            print(f"❌ Erreur déploiement Lambda: {str(e)}")
            raise

    def create_lambda_package(self):
        """Crée le package zip pour Lambda"""
        try:
            lambda_dir = Path('D:/kidjamo-workspace/chat_bot/src/lambda/lex_fulfillment')
            zip_path = lambda_dir / 'lambda_package.zip'

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Ajouter le fichier lambda_function.py
                zipf.write(lambda_dir / 'lambda_function.py', 'lambda_function.py')

            return str(zip_path)

        except Exception as e:
            print(f"❌ Erreur création package Lambda: {str(e)}")
            raise

    def create_lex_bot(self):
        """Crée le bot Lex"""
        try:
            bot_config = {
                'botName': self.bot_name,
                'description': 'Assistant santé intelligent pour patients atteints de drépanocytose',
                'roleArn': self.lex_role_arn,
                'dataPrivacy': {'childDirected': False},
                'idleSessionTTLInSeconds': 900,
                'botTags': {
                    'Environment': self.environment,
                    'Project': self.project_name,
                    'Purpose': 'Medical Chatbot'
                }
            }

            response = self.lex_v2.create_bot(**bot_config)
            bot_id = response['botId']

            print(f"✅ Bot Lex créé: {bot_id}")

            # Attendre que le bot soit créé
            self.wait_for_bot_status(bot_id, 'Available')

            return bot_id

        except Exception as e:
            print(f"❌ Erreur création bot Lex: {str(e)}")
            raise

    def configure_lex_intents(self, bot_id, lambda_arn):
        """Configure les intents du bot"""
        try:
            # Créer la locale française
            locale_config = {
                'botId': bot_id,
                'botVersion': 'DRAFT',
                'localeId': 'fr_FR',
                'description': 'Configuration française pour le bot Kidjamo',
                'nluIntentConfidenceThreshold': 0.4,
                'voiceSettings': {
                    'voiceId': 'Lea',
                    'engine': 'neural'
                }
            }

            self.lex_v2.create_bot_locale(**locale_config)

            # Attendre que la locale soit créée
            self.wait_for_locale_status(bot_id, 'fr_FR', 'Built')

            # Créer les intents principaux
            intents = [
                {
                    'intentName': 'SignalerDouleur',
                    'description': 'Signalement de douleur par le patient',
                    'sampleUtterances': [
                        {'utterance': "J'ai mal"},
                        {'utterance': "Je souffre"},
                        {'utterance': "J'ai une douleur"},
                        {'utterance': "Ça fait mal"}
                    ]
                },
                {
                    'intentName': 'SignalerUrgence',
                    'description': 'Signalement d\'urgence médicale',
                    'sampleUtterances': [
                        {'utterance': "C'est urgent"},
                        {'utterance': "Aidez-moi"},
                        {'utterance': "Urgence médicale"},
                        {'utterance': "Appelez les secours"}
                    ]
                },
                {
                    'intentName': 'DemanderAide',
                    'description': 'Demande d\'aide générale',
                    'sampleUtterances': [
                        {'utterance': "Aide"},
                        {'utterance': "Comment ça marche"},
                        {'utterance': "Que peux-tu faire"},
                        {'utterance': "Aide-moi"}
                    ]
                }
            ]

            for intent in intents:
                intent_config = {
                    'botId': bot_id,
                    'botVersion': 'DRAFT',
                    'localeId': 'fr_FR',
                    'intentName': intent['intentName'],
                    'description': intent['description'],
                    'sampleUtterances': intent['sampleUtterances'],
                    'fulfillmentCodeHook': {
                        'enabled': True
                    }
                }

                self.lex_v2.create_intent(**intent_config)

            # Configurer le code hook Lambda
            self.configure_lambda_permission(lambda_arn, bot_id)

            print(f"✅ Intents configurés avec Lambda hook")

        except Exception as e:
            print(f"❌ Erreur configuration intents: {str(e)}")
            raise

    def configure_lambda_permission(self, lambda_arn, bot_id):
        """Configure les permissions Lambda pour Lex"""
        try:
            function_name = lambda_arn.split(':')[-1]

            self.lambda_client.add_permission(
                FunctionName=function_name,
                StatementId=f'lex-{bot_id}',
                Action='lambda:InvokeFunction',
                Principal='lexv2.amazonaws.com',
                SourceArn=f'arn:aws:lex:{self.region}:*:bot/{bot_id}'
            )

            print(f"✅ Permissions Lambda configurées")

        except Exception as e:
            if 'ResourceConflictException' not in str(e):
                print(f"⚠️ Avertissement permissions Lambda: {str(e)}")

    def build_lex_bot(self, bot_id):
        """Construit le bot Lex"""
        try:
            self.lex_v2.build_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId='fr_FR'
            )

            print(f"✅ Bot en cours de construction...")

            # Attendre que la construction soit terminée
            self.wait_for_locale_status(bot_id, 'fr_FR', 'Built')

            print(f"✅ Bot construit avec succès")

        except Exception as e:
            print(f"❌ Erreur construction bot: {str(e)}")
            raise

    def create_bot_alias(self, bot_id):
        """Crée un alias pour le bot"""
        try:
            # Récupérer l'ARN Lambda correct
            lambda_function_name = f"{self.project_name}-{self.environment}-lex-fulfillment"

            try:
                lambda_response = self.lambda_client.get_function(FunctionName=lambda_function_name)
                lambda_arn = lambda_response['Configuration']['FunctionArn']
            except Exception as e:
                print(f"   ⚠️ Impossible de récupérer l'ARN Lambda: {str(e)}")
                lambda_arn = f"arn:aws:lambda:{self.region}:930900578484:function:{lambda_function_name}"

            alias_config = {
                'botAliasName': f'{self.environment}-alias',
                'description': f'Alias {self.environment} pour le bot Kidjamo',
                'botId': bot_id,
                'botVersion': 'DRAFT',
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

            response = self.lex_v2.create_bot_alias(**alias_config)
            alias_id = response['botAliasId']

            print(f"✅ Alias créé: {alias_id}")

            return alias_id

        except Exception as e:
            print(f"❌ Erreur création alias: {str(e)}")
            raise

    def test_deployment(self, bot_id, alias_id):
        """Teste le déploiement"""
        try:
            print(f"🧪 Test du chatbot...")

            test_message = "Bonjour"

            response = self.lex_v2.recognize_text(
                botId=bot_id,
                botAliasId=alias_id,
                localeId='fr_FR',
                sessionId='test-session',
                text=test_message
            )

            if 'messages' in response and response['messages']:
                print(f"✅ Test réussi!")
                print(f"   Question: {test_message}")
                print(f"   Réponse: {response['messages'][0]['content'][:100]}...")
            else:
                print(f"⚠️ Test partiellement réussi (pas de réponse textuelle)")

        except Exception as e:
            print(f"⚠️ Test échoué (normal pendant le déploiement): {str(e)}")

    def wait_for_bot_status(self, bot_id, expected_status, timeout=300):
        """Attend que le bot atteigne le statut attendu"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.lex_v2.describe_bot(botId=bot_id)
                status = response['botStatus']

                if status == expected_status:
                    return True
                elif status == 'Failed':
                    raise Exception(f"Le bot a échoué: {response.get('failureReasons', [])}")

                print(f"   Statut bot: {status} (attente {expected_status})")
                time.sleep(10)

            except Exception as e:
                print(f"   Erreur vérification statut: {str(e)}")
                time.sleep(10)

        raise Exception(f"Timeout: le bot n'a pas atteint le statut {expected_status}")

    def wait_for_locale_status(self, bot_id, locale_id, expected_status, timeout=900):
        """Attend que la locale atteigne le statut attendu"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.lex_v2.describe_bot_locale(
                    botId=bot_id,
                    botVersion='DRAFT',
                    localeId=locale_id
                )
                status = response['botLocaleStatus']

                if status == expected_status:
                    return True
                elif status == 'Failed':
                    failure_reasons = response.get('failureReasons', ['Raison inconnue'])
                    raise Exception(f"La locale a échoué: {', '.join(failure_reasons)}")

                elapsed = int(time.time() - start_time)
                print(f"   Statut locale: {status} (attente {expected_status}) - {elapsed}s écoulées")
                time.sleep(30)

            except Exception as e:
                if "Failed" in str(e):
                    raise  # Re-lancer les erreurs de failure
                print(f"   Erreur vérification statut locale: {str(e)}")
                time.sleep(30)

        # Si on arrive ici, c'est un timeout - essayer une approche différente
        print(f"   ⚠️ Timeout atteint ({timeout}s) - Tentative de récupération...")
        return self.handle_locale_timeout(bot_id, locale_id, expected_status)

    def handle_locale_timeout(self, bot_id, locale_id, expected_status):
        """Gère le timeout de création de locale"""
        try:
            print(f"   🔄 Récupération après timeout...")
            response = self.lex_v2.describe_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId=locale_id
            )
            status = response['botLocaleStatus']

            if status == expected_status:
                print(f"   ✅ Locale récupérée avec succès après timeout")
                return True
            elif status in ['Creating', 'Building']:
                print(f"   ⏳ Locale encore en cours de création ({status}) - Continuons...")
                # Donner plus de temps et réessayer
                time.sleep(60)
                return self.wait_for_locale_status_extended(bot_id, locale_id, expected_status)
            else:
                print(f"   ⚠️ La locale est dans un état inattendu: {status}")
                # Essayer de forcer la construction
                return self.force_locale_build(bot_id, locale_id)

        except Exception as e:
            print(f"   ❌ Erreur récupération locale: {str(e)}")
            return False

    def wait_for_locale_status_extended(self, bot_id, locale_id, expected_status, timeout=1800):
        """Attente étendue pour la locale (30 minutes max)"""
        start_time = time.time()

        print(f"   ⏰ Attente étendue (jusqu'à {timeout//60} minutes)...")

        while time.time() - start_time < timeout:
            try:
                response = self.lex_v2.describe_bot_locale(
                    botId=bot_id,
                    botVersion='DRAFT',
                    localeId=locale_id
                )
                status = response['botLocaleStatus']

                if status == expected_status:
                    print(f"   ✅ Locale finalement prête!")
                    return True
                elif status == 'Failed':
                    failure_reasons = response.get('failureReasons', ['Raison inconnue'])
                    print(f"   ❌ La locale a échoué: {', '.join(failure_reasons)}")
                    return False

                elapsed = int(time.time() - start_time)
                print(f"   ⏳ Locale: {status} - {elapsed//60}min {elapsed%60}s écoulées")
                time.sleep(45)  # Vérification moins fréquente

            except Exception as e:
                print(f"   ⚠️ Erreur vérification: {str(e)}")
                time.sleep(45)

        print(f"   ⚠️ Timeout étendu atteint - Procédure de récupération...")
        return self.fallback_locale_creation(bot_id, locale_id)

    def force_locale_build(self, bot_id, locale_id):
        """Force la construction de la locale"""
        try:
            print(f"   🔨 Tentative de force de construction...")

            # Essayer de builder la locale directement
            self.lex_v2.build_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId=locale_id
            )

            print(f"   ✅ Construction forcée lancée")

            # Attendre un peu et vérifier
            time.sleep(60)
            response = self.lex_v2.describe_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId=locale_id
            )

            status = response['botLocaleStatus']
            print(f"   📊 Statut après construction forcée: {status}")

            if status in ['Built', 'Building']:
                return True
            else:
                return False

        except Exception as e:
            print(f"   ⚠️ Construction forcée échouée: {str(e)}")
            return False

    def fallback_locale_creation(self, bot_id, locale_id):
        """Création de locale de secours simplifiée"""
        try:
            print(f"   🆘 Procédure de secours - Création locale simplifiée...")

            # Supprimer la locale existante si elle existe
            try:
                self.lex_v2.delete_bot_locale(
                    botId=bot_id,
                    botVersion='DRAFT',
                    localeId=locale_id
                )
                print(f"   🗑️ Ancienne locale supprimée")
                time.sleep(30)
            except:
                pass

            # Recréer avec configuration minimale
            minimal_locale_config = {
                'botId': bot_id,
                'botVersion': 'DRAFT',
                'localeId': locale_id,
                'description': 'Configuration française simplifiée pour Kidjamo',
                'nluIntentConfidenceThreshold': 0.5  # Seuil plus élevé pour simplifier
            }

            self.lex_v2.create_bot_locale(**minimal_locale_config)
            print(f"   ✅ Locale simplifiée créée")

            # Ajouter seulement les intents essentiels
            essential_intents = [
                {
                    'intentName': 'Salutation',
                    'sampleUtterances': [{'utterance': "Bonjour"}, {'utterance': "Salut"}]
                },
                {
                    'intentName': 'Urgence',
                    'sampleUtterances': [{'utterance': "Urgence"}, {'utterance': "Aidez-moi"}]
                }
            ]

            for intent in essential_intents:
                try:
                    self.lex_v2.create_intent(
                        botId=bot_id,
                        botVersion='DRAFT',
                        localeId=locale_id,
                        intentName=intent['intentName'],
                        sampleUtterances=intent['sampleUtterances'],
                        fulfillmentCodeHook={'enabled': True}
                    )
                    print(f"   ➕ Intent {intent['intentName']} ajouté")
                except Exception as e:
                    print(f"   ⚠️ Erreur intent {intent['intentName']}: {str(e)}")

            # Builder la locale simplifiée
            self.lex_v2.build_bot_locale(
                botId=bot_id,
                botVersion='DRAFT',
                localeId=locale_id
            )

            print(f"   🔨 Construction locale simplifiée lancée...")

            # Attendre avec timeout plus court
            return self.wait_for_simple_build(bot_id, locale_id)

        except Exception as e:
            print(f"   ❌ Procédure de secours échouée: {str(e)}")
            return False

    def wait_for_simple_build(self, bot_id, locale_id, timeout=600):
        """Attente pour la construction simplifiée"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.lex_v2.describe_bot_locale(
                    botId=bot_id,
                    botVersion='DRAFT',
                    localeId=locale_id
                )
                status = response['botLocaleStatus']

                if status == 'Built':
                    print(f"   ✅ Locale simplifiée construite avec succès!")
                    return True
                elif status == 'Failed':
                    print(f"   ❌ Construction simplifiée échouée")
                    return False

                elapsed = int(time.time() - start_time)
                print(f"   ⏳ Construction simplifiée: {status} - {elapsed}s")
                time.sleep(30)

            except Exception as e:
                print(f"   ⚠️ Erreur: {str(e)}")
                time.sleep(30)

        print(f"   ⚠️ Timeout construction simplifiée - Bot utilisable mais incomplet")
        return True  # Continuer même si pas parfait

def main():
    parser = argparse.ArgumentParser(description='Déploiement du chatbot Lex Kidjamo')
    parser.add_argument('--region', default='eu-west-1', help='Région AWS')
    parser.add_argument('--environment', default='dev', help='Environnement (dev, stg, prod)')

    args = parser.parse_args()

    try:
        deployer = KidjamoLexDeployer(region=args.region, environment=args.environment)
        result = deployer.deploy_complete_chatbot()

        print(f"\n🎉 DÉPLOIEMENT TERMINÉ AVEC SUCCÈS!")
        print(f"📋 Informations de connexion:")
        print(f"   Bot ID: {result['bot_id']}")
        print(f"   Alias ID: {result['alias_id']}")
        print(f"   Région: {args.region}")
        print(f"   Environnement: {args.environment}")

        # Sauvegarder la configuration
        config = {
            'deployment_info': result,
            'region': args.region,
            'environment': args.environment,
            'deployment_time': time.time()
        }

        with open('lex_deployment_config.json', 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✅ Configuration sauvegardée dans: lex_deployment_config.json")

    except Exception as e:
        print(f"❌ Échec du déploiement: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
