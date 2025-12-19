"""
Fonction Lambda AWS pour la reconnaissance vocale et la synthèse vocale
Complète le chatbot Kidjamo avec les capacités audio
"""

import json
import boto3
import logging
from typing import Dict, Any

# Configuration des services AWS
polly_client = boto3.client('polly')
transcribe_client = boto3.client('transcribe')
s3_client = boto3.client('s3')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Point d'entrée principal pour la fonction Lambda vocale
    """
    try:
        # Déterminer le type d'opération vocale
        operation = event.get('operation', 'tts')  # 'tts' ou 'stt'

        if operation == 'tts':
            # Text-to-Speech (Synthèse vocale)
            return handle_text_to_speech(event)
        elif operation == 'stt':
            # Speech-to-Text (Reconnaissance vocale)
            return handle_speech_to_text(event)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Opération non supportée',
                    'supported_operations': ['tts', 'stt']
                })
            }

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur interne du serveur',
                'message': str(e)
            })
        }

def handle_text_to_speech(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit le texte en audio avec Amazon Polly
    """
    try:
        text = event.get('text', '')
        if not text:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Texte requis pour la synthèse vocale'})
            }

        # Nettoyer le texte des emojis et markdown pour Polly
        clean_text = clean_text_for_speech(text)

        # Paramètres pour Polly
        polly_params = {
            'Text': clean_text,
            'OutputFormat': 'mp3',
            'VoiceId': 'Celine',  # Voix française féminine
            'LanguageCode': 'fr-FR',
            'TextType': 'text'
        }

        # Appel à Polly
        response = polly_client.synthesize_speech(**polly_params)

        # Sauvegarder l'audio dans S3
        bucket_name = 'kidjamo-audio-cache'
        audio_key = f"tts/{context.aws_request_id}.mp3"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=audio_key,
            Body=response['AudioStream'].read(),
            ContentType='audio/mpeg'
        )

        # URL d'accès à l'audio
        audio_url = f"https://{bucket_name}.s3.amazonaws.com/{audio_key}"

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'audio_url': audio_url,
                'text_processed': clean_text,
                'voice_used': 'Celine'
            })
        }

    except Exception as e:
        logger.error(f"Erreur TTS: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur lors de la synthèse vocale',
                'message': str(e)
            })
        }

def handle_speech_to_text(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit l'audio en texte avec Amazon Transcribe
    """
    try:
        audio_url = event.get('audio_url', '')
        if not audio_url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'URL audio requise pour la transcription'})
            }

        # Nom unique pour le job de transcription
        job_name = f"kidjamo-transcribe-{context.aws_request_id}"

        # Paramètres pour Transcribe
        transcribe_params = {
            'TranscriptionJobName': job_name,
            'LanguageCode': 'fr-FR',
            'MediaFormat': 'mp3',  # ou 'wav', 'flac'
            'Media': {
                'MediaFileUri': audio_url
            },
            'OutputBucketName': 'kidjamo-transcriptions'
        }

        # Démarrer la transcription
        transcribe_client.start_transcription_job(**transcribe_params)

        # Attendre la completion (pour les petits fichiers)
        import time
        max_wait = 30  # secondes
        wait_time = 0

        while wait_time < max_wait:
            job_status = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )

            status = job_status['TranscriptionJob']['TranscriptionJobStatus']

            if status == 'COMPLETED':
                # Récupérer le résultat
                transcript_uri = job_status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                transcript = get_transcript_from_s3(transcript_uri)

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': True,
                        'transcript': transcript,
                        'job_name': job_name
                    })
                }
            elif status == 'FAILED':
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Échec de la transcription',
                        'job_name': job_name
                    })
                }

            time.sleep(1)
            wait_time += 1

        # Si timeout, retourner le nom du job pour vérification ultérieure
        return {
            'statusCode': 202,
            'body': json.dumps({
                'message': 'Transcription en cours',
                'job_name': job_name,
                'check_url': f"/check-transcription/{job_name}"
            })
        }

    except Exception as e:
        logger.error(f"Erreur STT: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur lors de la transcription',
                'message': str(e)
            })
        }

def clean_text_for_speech(text: str) -> str:
    """
    Nettoie le texte pour la synthèse vocale
    """
    import re

    # Supprimer les emojis
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)

    clean = emoji_pattern.sub('', text)

    # Remplacer les balises markdown
    clean = re.sub(r'\*\*(.*?)\*\*', r'\1', clean)  # **gras**
    clean = re.sub(r'\*(.*?)\*', r'\1', clean)      # *italique*
    clean = re.sub(r'#{1,6}\s', '', clean)          # titres
    clean = re.sub(r'•\s', '', clean)               # puces

    # Remplacer les abréviations médicales pour une meilleure prononciation
    replacements = {
        'SAMU': 'Samu',
        'CHU': 'C H U',
        'IoT': 'Internet des objets',
        '15': 'quinze',
        '112': 'cent douze',
        'mg': 'milligrammes',
        'ml': 'millilitres',
        'h': 'heures'
    }

    for abbrev, full in replacements.items():
        clean = clean.replace(abbrev, full)

    # Nettoyer les caractères spéciaux
    clean = re.sub(r'\n+', '. ', clean)
    clean = re.sub(r'\s+', ' ', clean)

    return clean.strip()

def get_transcript_from_s3(transcript_uri: str) -> str:
    """
    Récupère le transcript depuis S3
    """
    try:
        import requests
        response = requests.get(transcript_uri)
        transcript_data = response.json()

        # Extraire le texte du transcript
        transcript = ""
        for result in transcript_data['results']['transcripts']:
            transcript += result['transcript'] + " "

        return transcript.strip()
    except Exception as e:
        logger.error(f"Erreur récupération transcript: {str(e)}")
        return ""

def check_transcription_status(job_name: str) -> Dict[str, Any]:
    """
    Vérifie le statut d'un job de transcription
    Fonction utilitaire pour les appels asynchrones
    """
    try:
        job_status = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )

        status = job_status['TranscriptionJob']['TranscriptionJobStatus']

        if status == 'COMPLETED':
            transcript_uri = job_status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            transcript = get_transcript_from_s3(transcript_uri)

            return {
                'status': 'completed',
                'transcript': transcript
            }
        elif status == 'FAILED':
            return {
                'status': 'failed',
                'error': 'Transcription échouée'
            }
        else:
            return {
                'status': 'in_progress'
            }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

# Fonction Lambda séparée pour vérifier le statut des transcriptions
def lambda_check_transcription(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Vérifie le statut d'une transcription en cours
    """
    try:
        job_name = event.get('pathParameters', {}).get('job_name', '')
        if not job_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Nom du job requis'})
            }

        result = check_transcription_status(job_name)

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur lors de la vérification',
                'message': str(e)
            })
        }
