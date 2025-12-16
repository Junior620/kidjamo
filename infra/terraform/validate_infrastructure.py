#!/usr/bin/env python3
"""
Script de validation de l'infrastructure Kidjamo
Teste tous les composants AWS déployés par Terraform
"""

import boto3
import json
import sys
import time
from typing import Dict, List, Optional
import requests
from botocore.exceptions import ClientError, NoCredentialsError

class InfrastructureValidator:
    def __init__(self, environment: str = "dev", region: str = "eu-west-1"):
        self.environment = environment
        self.region = region
        self.project = "kidjamo"

        self.results = []
        self.aws_configured = False

        # Vérification des credentials AWS avant d'initialiser les clients
        try:
            self._check_aws_credentials()
            self._initialize_aws_clients()
        except NoCredentialsError:
            self.log_error("❌ Credentials AWS non configurés. Exécutez 'aws configure' ou définissez les variables d'environnement AWS.")
            self.log_error("📋 Variables d'environnement requises: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION")
            return
        except Exception as e:
            self.log_error(f"❌ Erreur lors de l'initialisation AWS: {e}")
            return

    def _check_aws_credentials(self):
        """Vérifie que les credentials AWS sont configurés"""
        try:
            # Test simple avec STS pour vérifier les credentials
            sts = boto3.client('sts', region_name=self.region)
            response = sts.get_caller_identity()

            account_id = response.get('Account')
            user_arn = response.get('Arn')

            self.log_success(f"✅ Connecté au compte AWS: {account_id}")
            self.log_success(f"✅ Utilisateur: {user_arn}")
            self.aws_configured = True

        except NoCredentialsError:
            raise
        except Exception as e:
            self.log_error(f"❌ Erreur de connexion AWS: {e}")
            raise

    def _initialize_aws_clients(self):
        """Initialise les clients AWS après vérification des credentials"""
        try:
            self.s3 = boto3.client('s3', region_name=self.region)
            self.kinesis = boto3.client('kinesis', region_name=self.region)
            self.lambda_client = boto3.client('lambda', region_name=self.region)
            self.apigateway = boto3.client('apigateway', region_name=self.region)
            self.secrets = boto3.client('secretsmanager', region_name=self.region)
            self.kms = boto3.client('kms', region_name=self.region)

            self.log_success("✅ Clients AWS initialisés avec succès")
        except Exception as e:
            self.log_error(f"❌ Erreur lors de l'initialisation des clients AWS: {e}")
            raise

    def test_s3_buckets(self) -> bool:
        """Teste l'existence et l'accessibilité des buckets S3"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester S3")
            return False

        expected_buckets = [
            f"{self.project}-{self.environment}-data-lake-raw",
            f"{self.project}-{self.environment}-data-lake-bronze",
            f"{self.project}-{self.environment}-data-lake-silver",
            f"{self.project}-{self.environment}-data-lake-gold",
            f"{self.project}-{self.environment}-app-assets"
        ]

        success = True
        for bucket_name in expected_buckets:
            try:
                self.s3.head_bucket(Bucket=bucket_name)
                self.log_success(f"✅ Bucket S3 '{bucket_name}' accessible")

                # Test d'écriture/lecture
                test_key = "health-check/test.json"
                test_data = {"timestamp": time.time(), "status": "ok"}

                self.s3.put_object(
                    Bucket=bucket_name,
                    Key=test_key,
                    Body=json.dumps(test_data)
                )

                response = self.s3.get_object(Bucket=bucket_name, Key=test_key)
                retrieved_data = json.loads(response['Body'].read())

                if retrieved_data["status"] == "ok":
                    self.log_success(f"✅ Test écriture/lecture bucket '{bucket_name}' OK")
                else:
                    raise Exception("Données corrompues")

                # Nettoyage
                self.s3.delete_object(Bucket=bucket_name, Key=test_key)

            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchBucket':
                    self.log_error(f"❌ Bucket S3 '{bucket_name}' n'existe pas")
                elif error_code == 'AccessDenied':
                    self.log_error(f"❌ Accès refusé au bucket '{bucket_name}' - vérifiez les permissions")
                else:
                    self.log_error(f"❌ Bucket S3 '{bucket_name}' inaccessible: {e}")
                success = False
            except NoCredentialsError:
                self.log_error(f"❌ Credentials AWS manquants pour accéder au bucket '{bucket_name}'")
                success = False
            except Exception as e:
                self.log_error(f"❌ Test bucket '{bucket_name}' échoué: {e}")
                success = False

        return success

    def test_kinesis_streams(self) -> bool:
        """Teste les streams Kinesis"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester Kinesis")
            return False

        stream_name = f"{self.project}-{self.environment}-iot-data-stream"

        try:
            response = self.kinesis.describe_stream(StreamName=stream_name)
            stream_status = response['StreamDescription']['StreamStatus']

            if stream_status == 'ACTIVE':
                self.log_success(f"✅ Stream Kinesis '{stream_name}' actif")

                # Test d'envoi de données
                test_record = {
                    "device_id": "test-device-001",
                    "patient_id": "test-patient-001",
                    "timestamp": time.time(),
                    "status": "test_validation"
                }

                self.kinesis.put_record(
                    StreamName=stream_name,
                    Data=json.dumps(test_record),
                    PartitionKey="test-partition"
                )

                self.log_success(f"✅ Test envoi données Kinesis '{stream_name}' OK")
                return True
            else:
                self.log_error(f"❌ Stream Kinesis '{stream_name}' statut: {stream_status}")
                return False

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                self.log_error(f"❌ Stream Kinesis '{stream_name}' n'existe pas")
            else:
                self.log_error(f"❌ Stream Kinesis '{stream_name}' inaccessible: {e}")
            return False
        except NoCredentialsError:
            self.log_error(f"❌ Credentials AWS manquants pour Kinesis")
            return False
        except Exception as e:
            self.log_error(f"❌ Erreur inattendue Kinesis: {e}")
            return False

    def test_lambda_functions(self) -> bool:
        """Teste les fonctions Lambda"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester Lambda")
            return False

        function_name = f"{self.project}-{self.environment}-health-check"

        try:
            response = self.lambda_client.get_function(FunctionName=function_name)
            state = response['Configuration']['State']

            if state == 'Active':
                self.log_success(f"✅ Lambda '{function_name}' active")

                # Test d'invocation
                test_payload = {"test": True, "timestamp": time.time()}

                invoke_response = self.lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(test_payload)
                )

                if invoke_response['StatusCode'] == 200:
                    self.log_success(f"✅ Test invocation Lambda '{function_name}' OK")
                    return True
                else:
                    self.log_error(f"❌ Lambda '{function_name}' erreur invocation: {invoke_response['StatusCode']}")
                    return False
            else:
                self.log_error(f"❌ Lambda '{function_name}' statut: {state}")
                return False

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                self.log_error(f"❌ Lambda '{function_name}' n'existe pas")
            else:
                self.log_error(f"❌ Lambda '{function_name}' inaccessible: {e}")
            return False
        except NoCredentialsError:
            self.log_error(f"❌ Credentials AWS manquants pour Lambda")
            return False
        except Exception as e:
            self.log_error(f"❌ Erreur inattendue Lambda: {e}")
            return False

    def test_api_gateway(self) -> bool:
        """Teste l'API Gateway"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester API Gateway")
            return False

        try:
            apis = self.apigateway.get_rest_apis()
            api_name = f"{self.project}-{self.environment}-api"

            target_api = None
            for api in apis['items']:
                if api['name'] == api_name:
                    target_api = api
                    break

            if not target_api:
                self.log_error(f"❌ API Gateway '{api_name}' introuvable")
                return False

            api_id = target_api['id']
            api_url = f"https://{api_id}.execute-api.{self.region}.amazonaws.com/{self.environment}/health"

            self.log_success(f"✅ API Gateway '{api_name}' trouvé: {api_id}")

            # Test de l'endpoint
            try:
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    self.log_success(f"✅ Test endpoint API Gateway OK: {api_url}")
                    return True
                else:
                    self.log_error(f"❌ Endpoint API Gateway erreur {response.status_code}: {api_url}")
                    return False
            except requests.exceptions.RequestException as e:
                self.log_error(f"❌ Test endpoint API Gateway échoué: {e}")
                return False

        except ClientError as e:
            self.log_error(f"❌ API Gateway inaccessible: {e}")
            return False
        except NoCredentialsError:
            self.log_error(f"❌ Credentials AWS manquants pour API Gateway")
            return False
        except Exception as e:
            self.log_error(f"❌ Erreur inattendue API Gateway: {e}")
            return False

    def test_secrets_manager(self) -> bool:
        """Teste Secrets Manager"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester Secrets Manager")
            return False

        expected_secrets = [
            f"{self.project}/{self.environment}/mongodb/connection",
            f"{self.project}/{self.environment}/database/credentials",
            f"{self.project}/{self.environment}/api/keys",
            f"{self.project}/{self.environment}/jwt/secret"
        ]

        success = True
        for secret_name in expected_secrets:
            try:
                self.secrets.describe_secret(SecretId=secret_name)
                self.log_success(f"✅ Secret '{secret_name}' accessible")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ResourceNotFoundException':
                    self.log_error(f"❌ Secret '{secret_name}' n'existe pas")
                else:
                    self.log_error(f"❌ Secret '{secret_name}' inaccessible: {e}")
                success = False
            except NoCredentialsError:
                self.log_error(f"❌ Credentials AWS manquants pour Secrets Manager")
                success = False
            except Exception as e:
                self.log_error(f"❌ Erreur inattendue pour secret '{secret_name}': {e}")
                success = False

        return success

    def test_kms_keys(self) -> bool:
        """Teste les clés KMS"""
        if not self.aws_configured:
            self.log_error("❌ AWS non configuré, impossible de tester KMS")
            return False

        alias_name = f"alias/{self.project}-{self.environment}"

        try:
            response = self.kms.describe_key(KeyId=alias_name)
            key_state = response['KeyMetadata']['KeyState']

            if key_state == 'Enabled':
                self.log_success(f"✅ Clé KMS '{alias_name}' active")

                # Test de chiffrement/déchiffrement
                test_data = "test-encryption-data"

                encrypt_response = self.kms.encrypt(
                    KeyId=alias_name,
                    Plaintext=test_data
                )

                decrypt_response = self.kms.decrypt(
                    CiphertextBlob=encrypt_response['CiphertextBlob']
                )

                if decrypt_response['Plaintext'].decode() == test_data:
                    self.log_success(f"✅ Test chiffrement/déchiffrement KMS OK")
                    return True
                else:
                    self.log_error(f"❌ Test chiffrement/déchiffrement KMS échoué")
                    return False
            else:
                self.log_error(f"❌ Clé KMS '{alias_name}' statut: {key_state}")
                return False

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NotFoundException':
                self.log_error(f"❌ Clé KMS '{alias_name}' n'existe pas")
            else:
                self.log_error(f"❌ Clé KMS '{alias_name}' inaccessible: {e}")
            return False
        except NoCredentialsError:
            self.log_error(f"❌ Credentials AWS manquants pour KMS")
            return False
        except Exception as e:
            self.log_error(f"❌ Erreur inattendue KMS: {e}")
            return False

    def log_success(self, message: str):
        """Log un succès"""
        print(message)
        self.results.append({"status": "success", "message": message})

    def log_error(self, message: str):
        """Log une erreur"""
        print(message)
        self.results.append({"status": "error", "message": message})

    def run_all_tests(self) -> bool:
        """Exécute tous les tests"""
        print(f"\n🚀 Validation de l'infrastructure {self.project}-{self.environment}\n")

        # Vérification préliminaire des credentials
        if not self.aws_configured:
            print("❌ Impossible d'exécuter les tests sans credentials AWS valides")
            print("\n🔧 CONFIGURATION REQUISE:")
            print("1. Installer AWS CLI: https://aws.amazon.com/cli/")
            print("2. Configurer les credentials:")
            print("   aws configure")
            print("   ou définir les variables d'environnement:")
            print("   export AWS_ACCESS_KEY_ID=your_access_key")
            print("   export AWS_SECRET_ACCESS_KEY=your_secret_key")
            print("   export AWS_DEFAULT_REGION=eu-west-1")
            return False

        tests = [
            ("S3 Buckets", self.test_s3_buckets),
            ("Kinesis Streams", self.test_kinesis_streams),
            ("Lambda Functions", self.test_lambda_functions),
            ("API Gateway", self.test_api_gateway),
            ("Secrets Manager", self.test_secrets_manager),
            ("KMS Keys", self.test_kms_keys)
        ]

        all_success = True

        for test_name, test_func in tests:
            print(f"\n📋 Test: {test_name}")
            print("-" * 50)
            try:
                success = test_func()
                if not success:
                    all_success = False
            except Exception as e:
                self.log_error(f"❌ Erreur critique dans {test_name}: {e}")
                all_success = False

        # Résumé
        print(f"\n{'='*60}")
        print(f"📊 RÉSUMÉ DE LA VALIDATION")
        print(f"{'='*60}")

        successes = len([r for r in self.results if r["status"] == "success"])
        errors = len([r for r in self.results if r["status"] == "error"])

        print(f"✅ Succès: {successes}")
        print(f"❌ Erreurs: {errors}")

        if all_success:
            print(f"\n🎉 INFRASTRUCTURE VALIDÉE AVEC SUCCÈS!")
            return True
        else:
            print(f"\n⚠️  INFRASTRUCTURE PARTIELLEMENT FONCTIONNELLE")
            print(f"\n💡 PROCHAINES ÉTAPES:")
            if not self.aws_configured:
                print("   1. Configurer AWS CLI et credentials")
            print("   2. Déployer l'infrastructure avec Terraform:")
            print("      cd infra/terraform/envs/dev")
            print("      terraform init")
            print("      terraform plan")
            print("      terraform apply")
            return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Valider l'infrastructure Kidjamo")
    parser.add_argument("--env", default="dev", help="Environnement à tester (default: dev)")
    parser.add_argument("--region", default="eu-west-1", help="Région AWS (default: eu-west-1)")

    args = parser.parse_args()

    validator = InfrastructureValidator(args.env, args.region)
    success = validator.run_all_tests()

    sys.exit(0 if success else 1)
