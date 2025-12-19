"""
Fonction Lambda AWS pour la gestion de la reconnaissance vocale
Intègre AWS Transcribe pour Speech-to-Text et AWS Polly pour Text-to-Speech
"""

import json
import boto3
import uuid
import base64
from datetime import datetime
import logging

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
transcribe_client = boto3.client('transcribe')
polly_client = boto3.client('polly')
s3_client = boto3.client('s3')

# Configuration
BUCKET_NAME = 'kidjamo-voice-processing'
TRANSCRIBE_JOB_PREFIX = 'kidjamo-transcribe-'

def lambda_handler(event, context):
    """
    Handler principal pour la gestion vocale
    """
    try:
        # Parser l'événement
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', 'transcribe')

        if action == 'transcribe':
            return handle_transcription(body, context)
        elif action == 'synthesize':
            return handle_text_to_speech(body, context)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Action non supportée: {action}',
                    'supported_actions': ['transcribe', 'synthesize']
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

def handle_transcription(body, context):
    """
    Gère la transcription audio vers texte avec AWS Transcribe
    """
    try:
        audio_data = body.get('audio_data')
        language_code = body.get('language_code', 'fr-FR')

        if not audio_data:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Données audio manquantes'
                })
            }

        # Générer un ID unique pour ce job
        job_id = f"{TRANSCRIBE_JOB_PREFIX}{uuid.uuid4().hex[:8]}"

        # Décoder les données audio (base64)
        audio_bytes = base64.b64decode(audio_data)

        # Upload vers S3
        s3_key = f"voice-input/{job_id}.wav"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=audio_bytes,
            ContentType='audio/wav'
        )

        # Configurer le job de transcription
        media_uri = f"s3://{BUCKET_NAME}/{s3_key}"

        # Lancer le job de transcription
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_id,
            Media={'MediaFileUri': media_uri},
            MediaFormat='wav',
            LanguageCode=language_code,
            Settings={
                'ShowSpeakerLabels': False,
                'MaxSpeakerLabels': 1,
                'VocabularyFilterMethod': 'remove',
                'ShowAlternatives': True,
                'MaxAlternatives': 3
            },
            OutputBucketName=BUCKET_NAME,
            OutputKey=f"transcriptions/{job_id}.json"
        )

        # Attendre la completion du job (pour les petits fichiers)
        waiter = transcribe_client.get_waiter('transcription_job_completed')
        waiter.wait(
            TranscriptionJobName=job_id,
            WaiterConfig={
                'Delay': 2,
                'MaxAttempts': 30
            }
        )

        # Récupérer le résultat
        job_result = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_id
        )

        # Extraire le texte transcrit
        transcript_uri = job_result['TranscriptionJob']['Transcript']['TranscriptFileUri']

        # Télécharger le fichier de transcription
        transcript_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=f"transcriptions/{job_id}.json"
        )

        transcript_data = json.loads(transcript_response['Body'].read())

        # Extraire le texte principal
        transcribed_text = ""
        if 'results' in transcript_data and 'transcripts' in transcript_data['results']:
            transcribed_text = transcript_data['results']['transcripts'][0]['transcript']

        # Nettoyer les ressources temporaires
        cleanup_transcription_resources(job_id, s3_key)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'transcribed_text': transcribed_text,
                'language_detected': language_code,
                'confidence': extract_confidence_score(transcript_data),
                'job_id': job_id,
                'timestamp': datetime.now().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"Erreur dans handle_transcription: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur de transcription',
                'message': str(e)
            })
        }

def handle_text_to_speech(body, context):
    """
    Gère la synthèse vocale avec AWS Polly
    """
    try:
        text = body.get('text', '')
        voice_id = body.get('voice_id', 'Mathieu')  # Voix française par défaut
        output_format = body.get('output_format', 'mp3')

        if not text:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Texte à synthétiser manquant'
                })
            }

        # Adapter le texte pour la drépanocytose (pronunciation améliorée)
        enhanced_text = enhance_medical_pronunciation(text)

        # Synthèse vocale avec Polly
        response = polly_client.synthesize_speech(
            Text=enhanced_text,
            OutputFormat=output_format,
            VoiceId=voice_id,
            Engine='neural',  # Utiliser la voix neurale pour une meilleure qualité
            SampleRate='22050',
            TextType='text'
        )

        # Lire les données audio
        audio_stream = response['AudioStream'].read()

        # Encoder en base64 pour la transmission
        audio_base64 = base64.b64encode(audio_stream).decode('utf-8')

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'audio_data': audio_base64,
                'format': output_format,
                'voice_id': voice_id,
                'duration_estimate': estimate_audio_duration(text),
                'timestamp': datetime.now().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"Erreur dans handle_text_to_speech: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Erreur de synthèse vocale',
                'message': str(e)
            })
        }

def enhance_medical_pronunciation(text):
    """
    Améliore la prononciation des termes médicaux pour la drépanocytose
    """
    # Dictionnaire de replacements pour une meilleure prononciation
    medical_replacements = {
        'drépanocytose': '<phoneme alphabet="ipa" ph="dʁepanositoz">drépanocytose</phoneme>',
        'hydroxyurée': '<phoneme alphabet="ipa" ph="idʁoksiuʁe">hydroxyurée</phoneme>',
        'hémoglobine': '<phoneme alphabet="ipa" ph="emoglobin">hémoglobine</phoneme>',
        'vaso-occlusif': '<phoneme alphabet="ipa" ph="vazooklyzif">vaso-occlusif</phoneme>',
        'falciformation': '<phoneme alphabet="ipa" ph="falsifɔʁmasjɔ̃">falciformation</phoneme>',
        'ictère': '<phoneme alphabet="ipa" ph="iktɛʁ">ictère</phoneme>',
        'SAMU': '<say-as interpret-as="spell-out">SAMU</say-as>',
        'CHU': '<say-as interpret-as="spell-out">CHU</say-as>'
    }

    enhanced_text = text
    for term, replacement in medical_replacements.items():
        enhanced_text = enhanced_text.replace(term, replacement)

    # Ajouter des pauses pour une meilleure compréhension
    enhanced_text = enhanced_text.replace('•', '<break time="0.5s"/>')
    enhanced_text = enhanced_text.replace('**', '<emphasis level="strong">')

    return f'<speak>{enhanced_text}</speak>'

def extract_confidence_score(transcript_data):
    """
    Extrait le score de confiance de la transcription
    """
    try:
        if 'results' in transcript_data and 'items' in transcript_data['results']:
            items = transcript_data['results']['items']
            if items:
                confidences = [float(item.get('alternatives', [{}])[0].get('confidence', 0))
                             for item in items if 'alternatives' in item]
                return sum(confidences) / len(confidences) if confidences else 0.0
        return 0.0
    except:
        return 0.0

def estimate_audio_duration(text):
    """
    Estime la durée audio basée sur le texte
    Approximation: 150 mots par minute
    """
    word_count = len(text.split())
    duration_minutes = word_count / 150
    return round(duration_minutes * 60, 2)  # Retourner en secondes

def cleanup_transcription_resources(job_id, s3_key):
    """
    Nettoie les ressources temporaires après transcription
    """
    try:
        # Supprimer le fichier audio temporaire
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)

        # Supprimer le job de transcription (optionnel)
        # transcribe_client.delete_transcription_job(TranscriptionJobName=job_id)

        logger.info(f"Ressources nettoyées pour le job {job_id}")
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage: {str(e)}")

def get_available_voices():
    """
    Retourne la liste des voix disponibles pour le français
    """
    try:
        response = polly_client.describe_voices(LanguageCode='fr-FR')
        return [
            {
                'id': voice['Id'],
                'name': voice['Name'],
                'gender': voice['Gender'],
                'engine': voice.get('SupportedEngines', [])
            }
            for voice in response['Voices']
        ]
    except Exception as e:
        logger.error(f"Erreur récupération des voix: {str(e)}")
        return []
