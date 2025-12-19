"""
Script de test du déploiement du chatbot Kidjamo
Valide que tous les composants sont correctement déployés
"""

import boto3
import json
import argparse
import logging
import time
from typing import Dict, Any

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Test du déploiement du chatbot')
    parser.add_argument('--environment', default='dev', help='Environnement (dev, stg, prod)')
    parser.add_argument('--kendra-index-id', default='f45f7cc0-4c3c-4a01-9453-9003dc855a72', help='ID de l\'index Kendra')
    parser.add_argument('--region', default='eu-west-1', help='Région AWS')

    args = parser.parse_args()

    tester = DeploymentTester(args.environment, args.kendra_index_id, args.region)
    success = tester.run_all_tests()

    if success:
        logger.info("✅ Tous les tests de déploiement ont réussi")
        exit(0)
    else:
        logger.error("❌ Certains tests ont échoué")
        exit(1)

class DeploymentTester:
    def __init__(self, environment: str, kendra_index_id: str, region: str):
        self.environment = environment
        self.kendra_index_id = kendra_index_id
        self.region = region
        self.project_name = "kidjamo"
        self.name_prefix = f"{self.project_name}-{environment}-chatbot"

        # Clients AWS
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.kendra = boto3.client('kendra', region_name=region)
        self.kms = boto3.client('kms', region_name=region)

    def run_all_tests(self) -> bool:
        """Lance tous les tests de validation du déploiement"""
        tests = [
            self.test_lambda_functions,
            self.test_dynamodb_tables,
            self.test_s3_buckets,
            self.test_kendra_index,
            self.test_sns_topics,
            self.test_kms_key,
            self.test_lambda_integration,
        ]

        all_passed = True
        for test in tests:
            try:
                logger.info(f"🔄 Exécution de {test.__name__}...")
                if not test():
                    all_passed = False
                    logger.error(f"❌ Test {test.__name__} a échoué")
                else:
                    logger.info(f"✅ Test {test.__name__} réussi")
            except Exception as e:
                logger.error(f"❌ Erreur dans {test.__name__}: {str(e)}")
                all_passed = False

        return all_passed

    def test_lambda_functions(self) -> bool:
        """Test que toutes les fonctions Lambda sont déployées et actives"""
        expected_functions = [
            f"{self.name_prefix}-lex-fulfillment",
            f"{self.name_prefix}-medical-nlp",
            f"{self.name_prefix}-general-conversation",
            f"{self.name_prefix}-iot-integration"
        ]

        for function_name in expected_functions:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                state = response['Configuration']['State']
                if state != 'Active':
                    logger.error(f"Fonction Lambda {function_name} n'est pas Active: {state}")
                    return False
                logger.info(f"✓ Fonction Lambda {function_name} est active")
            except Exception as e:
                logger.error(f"Fonction Lambda {function_name} introuvable: {str(e)}")
                return False

        return True

    def test_dynamodb_tables(self) -> bool:
        """Test que les tables DynamoDB sont créées et actives"""
        expected_tables = [
            f"{self.name_prefix}-conversations",
            f"{self.name_prefix}-patient-context"
        ]

        for table_name in expected_tables:
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                status = response['Table']['TableStatus']
                if status != 'ACTIVE':
                    logger.error(f"Table DynamoDB {table_name} n'est pas ACTIVE: {status}")
                    return False
                logger.info(f"✓ Table DynamoDB {table_name} est active")
            except Exception as e:
                logger.error(f"Table DynamoDB {table_name} introuvable: {str(e)}")
                return False

        return True

    def test_s3_buckets(self) -> bool:
        """Test que les buckets S3 existent"""
        try:
            # Test du bucket de documents Kendra
            self.s3.head_bucket(Bucket="kidjamo-dev-chatbot-documents-cpcua9dm")
            logger.info("✓ Bucket S3 Kendra documents accessible")

            # Vérifier que le fichier FAQ est présent
            self.s3.head_object(Bucket="kidjamo-dev-chatbot-documents-cpcua9dm", Key="faq/drepanocytose-faq.csv")
            logger.info("✓ Fichier FAQ présent dans le bucket")

            return True
        except Exception as e:
            logger.error(f"Erreur avec les buckets S3: {str(e)}")
            return False

    def test_kendra_index(self) -> bool:
        """Test que l'index Kendra est actif et fonctionnel"""
        try:
            response = self.kendra.describe_index(Id=self.kendra_index_id)
            status = response['Status']
            if status != 'ACTIVE':
                logger.error(f"Index Kendra n'est pas ACTIVE: {status}")
                return False

            logger.info(f"✓ Index Kendra {self.kendra_index_id} est actif")

            # Test d'une requête simple
            try:
                query_response = self.kendra.query(
                    IndexId=self.kendra_index_id,
                    QueryText="drépanocytose",
                    PageSize=5
                )
                logger.info(f"✓ Requête Kendra réussie, {len(query_response.get('ResultItems', []))} résultats")
            except Exception as e:
                logger.warning(f"Requête Kendra échouée (normal si pas de documents indexés): {str(e)}")

            return True
        except Exception as e:
            logger.error(f"Erreur avec l'index Kendra: {str(e)}")
            return False

    def test_sns_topics(self) -> bool:
        """Test que les topics SNS existent"""
        expected_topics = [
            f"{self.name_prefix}-medical-alerts",
            f"{self.name_prefix}-patient-notifications"
        ]

        try:
            topics_response = self.sns.list_topics()
            topic_arns = [topic['TopicArn'] for topic in topics_response['Topics']]

            for expected_topic in expected_topics:
                found = any(expected_topic in arn for arn in topic_arns)
                if not found:
                    logger.error(f"Topic SNS {expected_topic} introuvable")
                    return False
                logger.info(f"✓ Topic SNS {expected_topic} trouvé")

            return True
        except Exception as e:
            logger.error(f"Erreur avec les topics SNS: {str(e)}")
            return False

    def test_kms_key(self) -> bool:
        """Test que la clé KMS existe et est activée"""
        try:
            aliases_response = self.kms.list_aliases()
            chatbot_alias = None

            for alias in aliases_response['Aliases']:
                if alias['AliasName'] == f"alias/{self.name_prefix}-encryption":
                    chatbot_alias = alias
                    break

            if not chatbot_alias:
                logger.error("Alias KMS chatbot introuvable")
                return False

            key_id = chatbot_alias['TargetKeyId']
            key_response = self.kms.describe_key(KeyId=key_id)

            if not key_response['KeyMetadata']['Enabled']:
                logger.error("Clé KMS chatbot n'est pas activée")
                return False

            logger.info("✓ Clé KMS chatbot active")
            return True
        except Exception as e:
            logger.error(f"Erreur avec la clé KMS: {str(e)}")
            return False

    def test_lambda_integration(self) -> bool:
        """Test d'intégration simple des fonctions Lambda"""
        try:
            # Test d'invocation de la fonction de conversation générale
            function_name = f"{self.name_prefix}-general-conversation"

            test_payload = {
                "message": "Bonjour, test de connexion",
                "user_id": "test-user",
                "session_id": "test-session"
            }

            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_payload)
            )

            if response['StatusCode'] == 200:
                logger.info("✓ Test d'invocation Lambda réussi")
                return True
            else:
                logger.error(f"Invocation Lambda a échoué: {response['StatusCode']}")
                return False

        except Exception as e:
            logger.error(f"Erreur lors du test d'intégration Lambda: {str(e)}")
            return False

if __name__ == "__main__":
    main()
