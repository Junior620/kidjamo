"""
Kidjamo Audio Processor - Reconnaissance et Synthèse Vocale
Gère la transcription audio (AWS Transcribe) et la synthèse vocale (AWS Polly)
avec détection automatique de langue et cache intelligent
"""

import os
import boto3
import hashlib
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from botocore.exceptions import ClientError
import tempfile

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Processeur audio avec AWS Transcribe, Polly et S3"""

    # Formats audio supportés
    SUPPORTED_FORMATS = ['mp3', 'wav', 'm4a', 'webm', 'ogg', 'flac']
    MAX_AUDIO_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DURATION = 240  # 4 minutes

    # Configuration voix Polly
    VOICES_CONFIG = {
        'fr-FR': {
            'primary': 'Lea',
            'engine': 'neural',
            'fallback': 'Celine',
            'fallback_engine': 'standard'
        },
        'en-US': {
            'primary': 'Joanna',
            'engine': 'neural',
            'fallback': 'Joanna',
            'fallback_engine': 'standard'
        }
    }

    def __init__(self, region_name: str = 'eu-west-1'):
        """Initialise les clients AWS"""
        self.region_name = region_name

        # Clients AWS
        self.transcribe_client = boto3.client('transcribe', region_name=region_name)
        self.polly_client = boto3.client('polly', region_name=region_name)
        self.s3_client = boto3.client('s3', region_name=region_name)

        # Configuration S3
        self.s3_bucket = os.getenv('KIDJAMO_AUDIO_BUCKET', 'kidjamo-audio-storage')
        self.s3_prefix_uploads = 'audio/uploads/'
        self.s3_prefix_responses = 'audio/responses/'

        # Cache audio (en mémoire pour réponses fréquentes)
        self.audio_cache = {}  # {question_hash: {url, timestamp, language}}
        self.cache_duration = timedelta(hours=24)

        logger.info("✅ AudioProcessor initialisé avec AWS Transcribe + Polly + S3")

    def validate_audio_file(self, audio_file) -> Tuple[bool, Optional[str]]:
        """Valide le fichier audio (format, taille)"""
        try:
            # Vérifier la taille
            audio_file.seek(0, 2)  # Aller à la fin
            size = audio_file.tell()
            audio_file.seek(0)  # Retour au début

            if size > self.MAX_AUDIO_SIZE:
                return False, f"Fichier trop volumineux ({size/1024/1024:.1f}MB). Maximum: 5MB"

            if size == 0:
                return False, "Fichier audio vide"

            # Vérifier le format via le nom de fichier
            filename = audio_file.filename.lower()
            extension = filename.split('.')[-1] if '.' in filename else ''

            if extension not in self.SUPPORTED_FORMATS:
                return False, f"Format non supporté. Formats acceptés: {', '.join(self.SUPPORTED_FORMATS)}"

            return True, None

        except Exception as e:
            logger.error(f"❌ Erreur validation audio: {e}")
            return False, f"Erreur validation: {str(e)}"

    def detect_language(self, audio_file_key: str) -> str:
        """Détecte automatiquement la langue de l'audio avec AWS Transcribe"""
        try:
            job_name = f"lang-detect-{int(time.time())}"
            audio_uri = f"s3://{self.s3_bucket}/{audio_file_key}"

            logger.info(f"🔍 Détection langue pour: {audio_uri}")

            # Lancer job Transcribe avec identification de langue
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': audio_uri},
                IdentifyLanguage=True,
                LanguageOptions=['fr-FR', 'en-US', 'en-GB']
            )

            # Attendre la fin (timeout 60s)
            max_wait = 60
            waited = 0

            while waited < max_wait:
                status = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )

                job_status = status['TranscriptionJob']['TranscriptionJobStatus']

                if job_status == 'COMPLETED':
                    identified_lang = status['TranscriptionJob'].get('IdentifiedLanguageScore')
                    language_code = status['TranscriptionJob'].get('LanguageCode', 'fr-FR')

                    logger.info(f"✅ Langue détectée: {language_code}")

                    # Nettoyer le job
                    self.transcribe_client.delete_transcription_job(
                        TranscriptionJobName=job_name
                    )

                    return language_code

                elif job_status == 'FAILED':
                    logger.warning(f"⚠️ Échec détection langue, fallback fr-FR")
                    return 'fr-FR'

                time.sleep(2)
                waited += 2

            # Timeout - fallback français
            logger.warning(f"⏱️ Timeout détection langue, fallback fr-FR")
            return 'fr-FR'

        except Exception as e:
            logger.error(f"❌ Erreur détection langue: {e}")
            return 'fr-FR'  # Fallback par défaut

    def transcribe_audio(self, audio_file, session_id: str) -> Dict[str, Any]:
        """Transcrit un fichier audio en texte avec AWS Transcribe"""
        start_time = time.time()

        try:
            # Valider le fichier
            is_valid, error = self.validate_audio_file(audio_file)
            if not is_valid:
                return {
                    'success': False,
                    'error': error,
                    'transcription': '',
                    'language': 'unknown',
                    'confidence': 0.0
                }

            # Générer un nom unique pour le fichier
            timestamp = int(time.time() * 1000)
            extension = audio_file.filename.split('.')[-1]
            s3_key = f"{self.s3_prefix_uploads}{session_id}/{timestamp}.{extension}"

            # Upload vers S3
            logger.info(f"📤 Upload audio vers S3: {s3_key}")
            self.s3_client.upload_fileobj(
                audio_file,
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': f'audio/{extension}'}
            )

            # Détecter la langue automatiquement
            detected_language = self.detect_language(s3_key)
            logger.info(f"🌍 Langue détectée: {detected_language}")

            # Lancer la transcription
            job_name = f"transcribe-{session_id}-{timestamp}"
            audio_uri = f"s3://{self.s3_bucket}/{s3_key}"

            logger.info(f"🎤 Démarrage transcription: {job_name}")

            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': audio_uri},
                MediaFormat=extension,
                LanguageCode=detected_language
            )

            # Attendre la fin de la transcription (max 120s)
            max_wait = 120
            waited = 0

            while waited < max_wait:
                status = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )

                job_status = status['TranscriptionJob']['TranscriptionJobStatus']

                if job_status == 'COMPLETED':
                    # Récupérer le résultat
                    transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']

                    import urllib.request
                    with urllib.request.urlopen(transcript_uri) as response:
                        transcript_data = json.loads(response.read().decode())

                    transcription = transcript_data['results']['transcripts'][0]['transcript']

                    # Calculer la confiance moyenne
                    items = transcript_data['results'].get('items', [])
                    confidences = [float(item['alternatives'][0].get('confidence', 0.0))
                                  for item in items if 'alternatives' in item]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                    # Nettoyer le job
                    self.transcribe_client.delete_transcription_job(
                        TranscriptionJobName=job_name
                    )

                    duration = int((time.time() - start_time) * 1000)

                    logger.info(f"✅ Transcription réussie en {duration}ms")
                    logger.info(f"📝 Texte: {transcription[:100]}...")

                    return {
                        'success': True,
                        'transcription': transcription,
                        'language': detected_language,
                        'confidence': round(avg_confidence, 2),
                        's3_audio_key': s3_key,
                        'transcription_time_ms': duration
                    }

                elif job_status == 'FAILED':
                    failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown')
                    logger.error(f"❌ Transcription échouée: {failure_reason}")

                    return {
                        'success': False,
                        'error': f"Transcription échouée: {failure_reason}",
                        'transcription': '',
                        'language': detected_language,
                        'confidence': 0.0
                    }

                time.sleep(2)
                waited += 2

            # Timeout
            logger.error(f"⏱️ Timeout transcription après {max_wait}s")
            return {
                'success': False,
                'error': 'Timeout transcription (>2min)',
                'transcription': '',
                'language': detected_language,
                'confidence': 0.0
            }

        except Exception as e:
            logger.error(f"❌ Erreur transcription: {e}")
            return {
                'success': False,
                'error': f"Erreur transcription: {str(e)}",
                'transcription': '',
                'language': 'unknown',
                'confidence': 0.0
            }

    def _generate_cache_key(self, text: str, language: str) -> str:
        """Génère une clé de cache pour le texte"""
        content = f"{text.lower().strip()}_{language}"
        return hashlib.md5(content.encode()).hexdigest()

    def _check_cache(self, text: str, language: str) -> Optional[str]:
        """Vérifie si l'audio est en cache"""
        cache_key = self._generate_cache_key(text, language)

        if cache_key in self.audio_cache:
            cached = self.audio_cache[cache_key]

            # Vérifier si le cache n'a pas expiré
            if datetime.now() - cached['timestamp'] < self.cache_duration:
                logger.info(f"💾 Cache HIT pour: {text[:50]}...")
                return cached['url']
            else:
                # Cache expiré, supprimer
                del self.audio_cache[cache_key]

        return None

    def _update_cache(self, text: str, language: str, audio_url: str):
        """Met à jour le cache audio"""
        cache_key = self._generate_cache_key(text, language)
        self.audio_cache[cache_key] = {
            'url': audio_url,
            'timestamp': datetime.now(),
            'language': language
        }
        logger.info(f"💾 Cache mis à jour pour: {text[:50]}...")

    def generate_speech(self, text: str, language: str, session_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """Génère l'audio de la réponse avec AWS Polly (cache intelligent)"""
        start_time = time.time()

        try:
            # Vérifier le cache
            if use_cache:
                cached_url = self._check_cache(text, language)
                if cached_url:
                    return {
                        'success': True,
                        'audio_url': cached_url,
                        'from_cache': True,
                        'voice_model': 'cached',
                        'generation_time_ms': int((time.time() - start_time) * 1000)
                    }

            # Obtenir la configuration de voix pour la langue
            voice_config = self.VOICES_CONFIG.get(language, self.VOICES_CONFIG['fr-FR'])

            # Nettoyer le texte (enlever markdown, limiter longueur)
            clean_text = text.replace('**', '').replace('##', '').replace('*', '')
            clean_text = clean_text[:3000]  # Limite Polly

            # Construire SSML pour une voix plus naturelle
            ssml_text = f"""
            <speak>
                <prosody rate="medium" pitch="medium">
                    {clean_text}
                </prosody>
            </speak>
            """

            # Tenter avec voix Neural d'abord
            try:
                logger.info(f"🎙️ Génération audio avec {voice_config['primary']} ({voice_config['engine']})")

                response = self.polly_client.synthesize_speech(
                    Text=ssml_text,
                    TextType='ssml',
                    OutputFormat='mp3',
                    VoiceId=voice_config['primary'],
                    Engine=voice_config['engine'],
                    SampleRate='22050'
                )

                voice_used = f"{voice_config['primary']}-Neural-{language}"

            except ClientError as e:
                # Fallback vers voix Standard
                logger.warning(f"⚠️ Neural engine indisponible, fallback Standard")

                response = self.polly_client.synthesize_speech(
                    Text=ssml_text,
                    TextType='ssml',
                    OutputFormat='mp3',
                    VoiceId=voice_config['fallback'],
                    Engine=voice_config['fallback_engine'],
                    SampleRate='22050'
                )

                voice_used = f"{voice_config['fallback']}-Standard-{language}"

            # Lire l'audio stream
            audio_stream = response['AudioStream'].read()

            # Générer nom de fichier unique
            timestamp = int(time.time() * 1000)
            text_hash = hashlib.md5(clean_text.encode()).hexdigest()[:8]
            s3_key = f"{self.s3_prefix_responses}{session_id}/{timestamp}_{text_hash}.mp3"

            # Upload vers S3
            logger.info(f"📤 Upload audio réponse vers S3: {s3_key}")

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=audio_stream,
                ContentType='audio/mpeg',
                CacheControl='max-age=86400'  # Cache 24h
            )

            # Générer URL publique (pre-signed pour 24h)
            audio_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': s3_key},
                ExpiresIn=86400  # 24 heures
            )

            # Mettre en cache
            if use_cache:
                self._update_cache(text, language, audio_url)

            duration = int((time.time() - start_time) * 1000)

            logger.info(f"✅ Audio généré en {duration}ms avec {voice_used}")

            return {
                'success': True,
                'audio_url': audio_url,
                's3_key': s3_key,
                'from_cache': False,
                'voice_model': voice_used,
                'audio_duration_seconds': response.get('RequestCharacters', 0) // 15,  # Estimation
                'generation_time_ms': duration
            }

        except Exception as e:
            logger.error(f"❌ Erreur génération audio: {e}")
            return {
                'success': False,
                'error': f"Erreur génération audio: {str(e)}",
                'audio_url': None,
                'from_cache': False
            }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache audio"""
        # Nettoyer les entrées expirées
        now = datetime.now()
        expired_keys = [
            k for k, v in self.audio_cache.items()
            if now - v['timestamp'] >= self.cache_duration
        ]

        for key in expired_keys:
            del self.audio_cache[key]

        return {
            'cache_size': len(self.audio_cache),
            'cache_duration_hours': self.cache_duration.total_seconds() / 3600,
            'expired_removed': len(expired_keys)
        }

# Instance globale
audio_processor = AudioProcessor()

