#!/usr/bin/env python3
"""
Fonction Lambda pour partitionnement S3 intelligent
Gère le partitionnement par date des données IoT MPU Christian
"""

import json
import boto3
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class S3DatePartitioner:
    """Gestionnaire de partitionnement S3 par date"""

    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = "kidjamo-dev-datalake-e75d5213"

    def lambda_handler(self, event, context):
        """Point d'entrée Lambda - reçoit les données IoT et les organise par date"""

        logger.info("🔄 Traitement partitionnement S3 MPU Christian")

        try:
            # Parser l'événement IoT Core
            if 'Records' in event:
                # Événement Kinesis
                for record in event['Records']:
                    if record.get('eventSource') == 'aws:kinesis':
                        # Décoder les données Kinesis
                        import base64
                        data = json.loads(base64.b64decode(record['kinesis']['data']).decode('utf-8'))
                        self._partition_and_store(data)
            else:
                # Événement direct depuis IoT Core
                self._partition_and_store(event)

            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Partitionnement réussi'})
            }

        except Exception as e:
            logger.error(f"❌ Erreur partitionnement: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

    def _partition_and_store(self, data):
        """Partitionne et stocke les données avec la bonne structure date"""

        # Utiliser l'heure actuelle pour le partitionnement
        now = datetime.now(timezone.utc)

        # Générer la structure de partitionnement correcte
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        hour = now.strftime("%H")

        # Créer la clé S3 avec la bonne structure
        timestamp = int(now.timestamp() * 1000)  # Timestamp en millisecondes
        s3_key = f"raw/iot-measurements/year={year}/month={month}/day={day}/hour={hour}/mpu_christian_{timestamp}.json"

        # Enrichir les données avec métadonnées
        enriched_data = {
            **data,
            'partition_year': year,
            'partition_month': month,
            'partition_day': day,
            'partition_hour': hour,
            'processed_timestamp': now.isoformat(),
            'device_id': data.get('device_id', 'MPU_Christian_8266MOD')
        }

        # Stocker dans S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(enriched_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'device_id': enriched_data['device_id'],
                    'year': year,
                    'month': month,
                    'day': day,
                    'hour': hour,
                    'source': 'iot-core-partitioner'
                }
            )

            logger.info(f"✅ Stocké: s3://{self.bucket_name}/{s3_key}")

        except Exception as e:
            logger.error(f"❌ Erreur stockage S3: {e}")
            raise

# Instance globale pour AWS Lambda
partitioner = S3DatePartitioner()

def lambda_handler(event, context):
    """Point d'entrée AWS Lambda"""
    return partitioner.lambda_handler(event, context)
