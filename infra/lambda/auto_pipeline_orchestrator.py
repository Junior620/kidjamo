                        '--input_path': f's3://{self.bucket_name}/raw/',
                        '--quarantine_output_path': f's3://{self.bucket_name}/quarantine/',
                        '--bronze_output_path': f's3://{self.bucket_name}/bronze/',
                        '--raw_input_path': f's3://{self.bucket_name}/raw/'
                    })
                elif job_config['name'] == 'kidjamo-dev-bronze-to-silver':
                    job_params.update({
                        '--input_path': f's3://{self.bucket_name}/bronze/',
                        '--bronze_input_path': f's3://{self.bucket_name}/bronze/',
                        '--silver_output_path': f's3://{self.bucket_name}/silver/'
                    })
                elif job_config['name'] == 'kidjamo-dev-silver-to-gold':
                    job_params.update({
                        '--input_path': f's3://{self.bucket_name}/silver/',
                        '--silver_input_path': f's3://{self.bucket_name}/silver/',
                        '--gold_output_path': f's3://{self.bucket_name}/gold/',
                        '--rds_secret_name': 'kidjamo-dev-rds-credentials'
                    })
#!/usr/bin/env python3
"""
Fonction Lambda d'orchestration automatique - Pipeline MPU Christian
Déclenche automatiquement tous les jobs de la pipeline quand de nouvelles données arrivent
"""

import json
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class AutoPipelineOrchestrator:
    """Orchestrateur automatique de la pipeline MPU Christian"""

    def __init__(self):
        self.region = "eu-west-1"
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.glue_client = boto3.client('glue', region_name=self.region)
        self.sns_client = boto3.client('sns', region_name=self.region)

        # Configuration pipeline
        self.bucket_name = "kidjamo-dev-datalake-e75d5213"
        self.jobs = [
            "kidjamo-dev-raw-to-bronze",      # Nom correct du job existant
            "kidjamo-dev-bronze-to-silver",   # Nom correct du job existant
            "kidjamo-dev-silver-to-gold"      # Nom correct du job existant
        ]

    def lambda_handler(self, event, context):
        """Point d'entrée Lambda - déclenché par S3 ou EventBridge"""

        logger.info("🚀 DÉCLENCHEMENT AUTO PIPELINE MPU CHRISTIAN")
        logger.info(f"Event: {json.dumps(event, indent=2)}")

        try:
            # Identifier le type de déclencheur
            trigger_type = self._identify_trigger(event)

            if trigger_type == "s3_raw":
                # Nouvelles données dans S3 raw → déclencher pipeline complète
                return self._handle_new_raw_data(event)

            elif trigger_type == "schedule":
                # Déclenchement programmé → traitement batch périodique
                return self._handle_scheduled_processing()

            elif trigger_type == "manual":
                # Déclenchement manuel → traitement immédiat
                return self._handle_manual_trigger(event)

            elif trigger_type == "batch_ready":
                # Déclenchement par lot haute fréquence
                return self._handle_new_raw_data(event)

            elif trigger_type == "streaming_ready":
                # Déclenchement par streaming direct
                return self._handle_new_raw_data(event)

            else:
                logger.warning(f"Type de trigger non reconnu: {trigger_type}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Trigger ignoré', 'type': trigger_type})
                }

        except Exception as e:
            logger.error(f"❌ Erreur orchestrateur: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

    def _identify_trigger(self, event: Dict) -> str:
        """Identifie le type de déclencheur"""

        # Déclenchement direct depuis le processeur MPU en mode streaming (nouveau)
        if event.get('trigger_type') == 's3_streaming_ready':
            return "streaming_ready"

        # Déclenchement direct depuis le processeur MPU (batch mode)
        if event.get('trigger_type') == 's3_batch_ready':
            return "batch_ready"

        # S3 Event (nouvelles données raw)
        if 'Records' in event and event['Records']:
            record = event['Records'][0]
            if record.get('eventSource') == 'aws:s3':
                s3_key = record['s3']['object']['key']
                if s3_key.startswith('raw/iot-measurements/') and 'mpu_christian' in s3_key.lower():
                    return "s3_raw"

        # EventBridge scheduled event
        if event.get('source') == 'aws.events' and event.get('detail-type') == 'Scheduled Event':
            return "schedule"

        # Manual trigger avec paramètres
        if event.get('trigger_type'):
            return "manual"

        return "unknown"

    def _handle_new_raw_data(self, event: Dict) -> Dict:
        """Traite l'arrivée de nouvelles données MPU Christian dans S3 raw"""

        logger.info("📦 NOUVELLES DONNÉES MPU CHRISTIAN DÉTECTÉES")

        # Vérifier si c'est un streaming direct haute fréquence
        if event.get('trigger_type') == 's3_streaming_ready':
            return self._handle_streaming_ready(event)

        # Vérifier si c'est un batch haute fréquence
        if event.get('trigger_type') == 's3_batch_ready':
            return self._handle_batch_ready(event)

        # Traitement classique pour fichiers individuels via S3 events
        if 'Records' in event:
            record = event['Records'][0]
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            logger.info(f"Fichier: s3://{bucket}/{key}")

            # Vérifier si c'est bien des données MPU Christian
            if not self._is_mpu_christian_file(key):
                logger.info("Fichier ignoré - pas de données MPU Christian")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Fichier ignoré', 'file': key})
                }

            # Déclencher la pipeline automatiquement
            return self._trigger_complete_pipeline(
                trigger_reason=f"Nouvelles données MPU: {key}",
                immediate=True
            )

        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Event format non reconnu'})
        }

    def _handle_streaming_ready(self, event: Dict) -> Dict:
        """Traite l'arrivée d'un fichier streaming direct haute fréquence"""

        logger.info("⚡ STREAMING DIRECT MPU CHRISTIAN PRÊT")

        s3_key = event.get('s3_key', '')
        device_id = event.get('device_id', 'MPU_Christian_8266MOD')
        streaming_mode = event.get('streaming_mode', False)

        logger.info(f"Fichier streaming: {s3_key}")
        logger.info(f"Device: {device_id}")
        logger.info(f"Mode streaming direct: {streaming_mode}")

        # Pour le streaming direct, traitement différé et optimisé
        if streaming_mode:
            return self._trigger_complete_pipeline(
                trigger_reason=f"Streaming direct: {device_id}",
                immediate=False,  # Pas immédiat pour éviter surcharge
                streaming_mode=True
            )
        else:
            return self._trigger_complete_pipeline(
                trigger_reason=f"Fichier MPU: {device_id}",
                immediate=True
            )

    def _handle_batch_ready(self, event: Dict) -> Dict:
        """Traite l'arrivée d'un batch haute fréquence"""

        logger.info("🔄 BATCH HAUTE FRÉQUENCE MPU CHRISTIAN PRÊT")

        s3_key = event.get('s3_key', '')
        batch_size = event.get('batch_size', 0)
        high_frequency = event.get('high_frequency_mode', False)

        logger.info(f"Batch: {s3_key}")
        logger.info(f"Taille: {batch_size} échantillons")
        logger.info(f"Mode haute fréquence: {high_frequency}")

        # Pour les batches haute fréquence, traitement différé et optimisé
        if high_frequency:
            return self._trigger_complete_pipeline(
                trigger_reason=f"Batch haute fréquence: {batch_size} échantillons",
                immediate=False,  # Pas immédiat pour éviter surcharge
                batch_mode=True
            )
        else:
            return self._trigger_complete_pipeline(
                trigger_reason=f"Batch MPU: {batch_size} échantillons",
                immediate=True
            )

    def _handle_scheduled_processing(self) -> Dict:
        """Traite le déclenchement programmé (toutes les heures par exemple)"""

        logger.info("⏰ TRAITEMENT PROGRAMMÉ DÉCLENCHÉ")

        # Vérifier s'il y a de nouvelles données à traiter
        new_files = self._check_for_new_raw_files()

        if not new_files:
            logger.info("Aucune nouvelle donnée à traiter")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Aucune nouvelle donnée'})
            }

        logger.info(f"Trouvé {len(new_files)} nouveaux fichiers à traiter")

        # Déclencher la pipeline
        return self._trigger_complete_pipeline(
            trigger_reason=f"Traitement programmé: {len(new_files)} fichiers",
            immediate=False
        )

    def _handle_manual_trigger(self, event: Dict) -> Dict:
        """Traite le déclenchement manuel"""

        logger.info("👤 DÉCLENCHEMENT MANUEL")

        # Paramètres optionnels
        params = event.get('parameters', {})
        force_reprocess = params.get('force_reprocess', False)

        return self._trigger_complete_pipeline(
            trigger_reason="Déclenchement manuel",
            immediate=True,
            force_reprocess=force_reprocess
        )

    def _trigger_complete_pipeline(self, trigger_reason: str, immediate: bool = True, force_reprocess: bool = False) -> Dict:
        """Déclenche la pipeline complète raw→bronze→silver→gold"""

        logger.info(f"🔄 DÉCLENCHEMENT PIPELINE COMPLÈTE: {trigger_reason}")

        results = {
            'trigger_reason': trigger_reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'jobs_triggered': [],
            'errors': []
        }

        # Jobs Glue dans l'ordre (noms corrects des jobs existants)
        pipeline_jobs = [
            {
                'name': 'kidjamo-dev-raw-to-bronze',     # Nom correct du job existant
                'script': 'raw_to_bronze.py',
                'description': 'RAW → BRONZE: Nettoyage et validation'
            },
            {
                'name': 'kidjamo-dev-bronze-to-silver',  # Nom correct du job existant
                'script': 'bronze_to_silver.py',
                'description': 'BRONZE → SILVER: Enrichissement et transformation'
            },
            {
                'name': 'kidjamo-dev-silver-to-gold',    # Nom correct du job existant
                'script': 'silver_to_gold.py',
                'description': 'SILVER → GOLD: Agrégation et analytics'
            }
        ]

        # Déclencher chaque job dans l'ordre avec délais
        for i, job_config in enumerate(pipeline_jobs):
            try:
                logger.info(f"🚀 Déclenchement job {i+1}/3: {job_config['description']}")

                # Paramètres du job adaptés à vos scripts Glue
                job_params = {
                    '--trigger-reason': trigger_reason,
                    '--immediate': str(immediate),
                    '--force-reprocess': str(force_reprocess),
                    '--bucket': self.bucket_name,
                    '--region': self.region
                }

                # Ajouter les paramètres spécifiques selon le job
                if job_config['name'] == 'kidjamo-dev-raw-to-bronze':
                    job_params.update({

                # Démarrer le job Glue
                response = self.glue_client.start_job_run(
                    JobName=job_config['name'],
                    Arguments=job_params
                )

                job_run_id = response['JobRunId']
                results['jobs_triggered'].append({
                    'job_name': job_config['name'],
                    'job_run_id': job_run_id,
                    'script': job_config['script'],
                    'description': job_config['description'],
                    'status': 'STARTED'
                })

                logger.info(f"✅ Job {job_config['name']} démarré: {job_run_id}")

                # Délai entre jobs pour éviter les conflits (sauf pour le dernier)
                if i < len(pipeline_jobs) - 1 and immediate:
                    import time
                    time.sleep(30)  # 30 secondes entre chaque job

            except Exception as e:
                logger.error(f"❌ Erreur job {job_config['name']}: {e}")
                results['errors'].append({
                    'job_name': job_config['name'],
                    'script': job_config['script'],
                    'error': str(e)
                })

        # Déclencher aussi le moteur d'alertes offline si nécessaire
        if len(results['jobs_triggered']) > 0:
            try:
                logger.info("🚨 Déclenchement moteur d'alertes offline...")

                alerts_response = self.glue_client.start_job_run(
                    JobName='kidjamo-offline-alerts-job',
                    Arguments={
                        '--trigger-reason': f"Post-pipeline: {trigger_reason}",
                        '--bucket': self.bucket_name
                    }
                )

                results['jobs_triggered'].append({
                    'job_name': 'kidjamo-offline-alerts-job',
                    'job_run_id': alerts_response['JobRunId'],
                    'script': 'offline_alerts_engine.py',
                    'description': 'Moteur d\'alertes offline',
                    'status': 'STARTED'
                })

                logger.info(f"✅ Moteur alertes démarré: {alerts_response['JobRunId']}")

            except Exception as e:
                logger.warning(f"⚠️ Moteur alertes non disponible: {e}")

        # Envoyer notification des résultats
        self._send_notification(results)

        # Retour de la fonction Lambda
        status_code = 200 if not results['errors'] else 207  # 207 = Partial Success

        logger.info(f"📊 Pipeline déclenchée: {len(results['jobs_triggered'])} jobs, {len(results['errors'])} erreurs")

        return {
            'statusCode': status_code,
            'body': json.dumps(results, indent=2)
        }

    def _is_mpu_christian_file(self, s3_key: str) -> bool:
        """Vérifie si le fichier S3 contient des données MPU Christian"""

        key_lower = s3_key.lower()

        # Vérifier les patterns de nommage
        mpu_patterns = ['mpu_christian', 'christian', '8266mod', 'mpu6050']

        return any(pattern in key_lower for pattern in mpu_patterns)

    def _check_for_new_raw_files(self, hours_back: int = 1) -> list:
        """Vérifie s'il y a de nouveaux fichiers raw MPU Christian"""

        try:
            # Lister les fichiers raw récents
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='raw/iot-measurements/'
            )

            new_files = []

            if 'Contents' in response:
                for obj in response['Contents']:
                    # Vérifier si c'est un fichier MPU Christian récent
                    if (self._is_mpu_christian_file(obj['Key']) and
                        obj['LastModified'] > cutoff_time):
                        new_files.append(obj)

            return new_files

        except Exception as e:
            logger.error(f"❌ Erreur vérification fichiers: {e}")
            return []

    def _send_notification(self, results: Dict):
        """Envoie une notification des résultats"""

        try:
            # Vous pouvez configurer un topic SNS pour les notifications
            # topic_arn = "arn:aws:sns:eu-west-1:123456789012:kidjamo-pipeline-notifications"

            message = f"""
🔄 Pipeline MPU Christian exécutée

Déclencheur: {results['trigger_reason']}
Timestamp: {results['timestamp']}

Jobs démarrés: {len(results['jobs_triggered'])}
Erreurs: {len(results['errors'])}

Détails:
{json.dumps(results, indent=2)}
            """

            logger.info("📧 Notification préparée (SNS non configuré)")
            # self.sns_client.publish(TopicArn=topic_arn, Message=message)

        except Exception as e:
            logger.debug(f"⚠️ Erreur notification: {e}")

# Instance globale pour AWS Lambda
orchestrator = AutoPipelineOrchestrator()

def lambda_handler(event, context):
    """Point d'entrée AWS Lambda"""
    return orchestrator.lambda_handler(event, context)
