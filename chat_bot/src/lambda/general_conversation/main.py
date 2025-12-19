"""
Fonction Lambda pour les conversations générales intelligentes
Chatbot Santé Kidjamo - Extension conversationnelle
"""

import json
import boto3
import os
import logging
import random
from datetime import datetime, timezone
from typing import Dict, Any, List

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
bedrock_runtime = boto3.client('bedrock-runtime')
kendra = boto3.client('kendra')

# Variables d'environnement
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
KENDRA_INDEX_ID = os.environ.get('KENDRA_INDEX_ID', '')

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Point d'entrée pour les conversations générales intelligentes
    """
    try:
        logger.info(f"Événement conversation générale reçu: {json.dumps(event, ensure_ascii=False)}")

        intent_name = event.get('intent_name')
        user_input = event.get('user_input', '')
        user_id = event.get('user_id', 'anonymous')
        conversation_context = event.get('conversation_context', {})

        # Routage selon le type de conversation
        if intent_name == 'ConversationGenerale':
            return handle_polite_conversation(user_input, conversation_context)
        elif intent_name == 'QuestionsGenerales':
            return handle_general_questions(user_input, conversation_context)
        elif intent_name == 'DiscussionLibre':
            return handle_free_discussion(user_input, conversation_context)
        elif intent_name == 'ConseilsVieQuotidienne':
            return handle_life_advice(user_input, conversation_context)
        elif intent_name == 'CultureEducation':
            return handle_culture_education(user_input, conversation_context)
        else:
            return handle_general_fallback(user_input, conversation_context)

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler conversation: {str(e)}")
        return {
            'success': False,
            'response': "Je rencontre une petite difficulté. Pouvez-vous reformuler votre question ?",
            'error': str(e)
        }

def handle_polite_conversation(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les conversations polies et salutations
    """
    input_lower = user_input.lower()

    # Détection du type de salutation
    if any(greeting in input_lower for greeting in ['bonjour', 'salut', 'hello', 'bonsoir']):
        responses = [
            "Bonjour ! Je suis ravi de vous parler aujourd'hui. Comment allez-vous ?",
            "Salut ! J'espère que vous passez une belle journée. Que puis-je faire pour vous ?",
            "Bonsoir ! Je suis là pour vous accompagner. De quoi aimeriez-vous discuter ?",
            "Hello ! C'est un plaisir de vous retrouver. Comment vous sentez-vous aujourd'hui ?"
        ]
    elif any(farewell in input_lower for farewell in ['au revoir', 'bye', 'à bientôt', 'tchao']):
        responses = [
            "Au revoir ! Prenez bien soin de vous et n'hésitez pas à revenir me voir.",
            "À bientôt ! J'espère que notre conversation vous a été utile.",
            "Au revoir ! Pensez à prendre vos médicaments et à surveiller votre santé.",
            "À plus tard ! Je serai toujours là si vous avez besoin de parler."
        ]
    elif any(thanks in input_lower for thanks in ['merci', 'thank you', 'thanks']):
        responses = [
            "Je vous en prie ! C'est un plaisir de vous aider.",
            "Avec plaisir ! N'hésitez jamais à me poser des questions.",
            "De rien ! Je suis là pour ça. Autre chose ?",
            "C'est tout naturel ! Comment puis-je encore vous aider ?"
        ]
    elif any(feeling in input_lower for feeling in ['ça va', 'comment ça va', 'comment allez-vous']):
        responses = [
            "Ça va bien, merci ! Et vous, comment vous sentez-vous aujourd'hui ?",
            "Je vais très bien ! J'espère que vous aussi. Racontez-moi votre journée.",
            "Tout va bien de mon côté ! Et votre santé, comment ça se passe ?",
            "Parfaitement bien ! Comment se passent vos traitements ces temps-ci ?"
        ]
    else:
        responses = [
            "C'est gentil de votre part ! Je suis content de pouvoir discuter avec vous.",
            "Merci ! J'apprécie beaucoup nos échanges. De quoi voulez-vous parler ?",
            "C'est très aimable ! Y a-t-il quelque chose en particulier qui vous préoccupe ?",
            "Vous êtes très sympathique ! Comment puis-je vous être utile aujourd'hui ?"
        ]

    return {
        'success': True,
        'response': random.choice(responses),
        'conversation_type': 'polite',
        'suggested_topics': [
            "Comment vous sentez-vous aujourd'hui ?",
            "Parlez-moi de votre journée",
            "Avez-vous des questions sur votre santé ?",
            "Voulez-vous discuter de quelque chose de particulier ?"
        ]
    }

def handle_general_questions(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Répond aux questions générales
    """
    input_lower = user_input.lower()

    # Tentative de recherche dans la base de connaissances d'abord
    knowledge_search_result = handle_knowledge_search(user_input, context)
    if knowledge_search_result:
        return knowledge_search_result

    # Questions sur le temps
    if any(time_q in input_lower for time_q in ['quelle heure', 'heure est-il', 'temps']):
        current_time = datetime.now().strftime("%H:%M")
        response = f"Il est actuellement {current_time}. N'oubliez pas de prendre vos médicaments à l'heure prévue !"

    # Questions sur la date
    elif any(date_q in input_lower for date_q in ['quel jour', 'date', 'aujourd\'hui']):
        current_date = datetime.now().strftime("%A %d %B %Y")
        response = f"Nous sommes {current_date}. J'espère que cette journée se passe bien pour vous !"

    # Questions sur l'identité du bot
    elif any(identity in input_lower for identity in ['qui es-tu', 'ton nom', 'tu t\'appelles']):
        response = """Je suis votre assistant santé Kidjamo ! 🤖

Je suis là pour :
• Vous accompagner dans le suivi de votre drépanocytose
• Répondre à vos questions de santé
• Discuter avec vous quand vous en avez envie
• Vous aider avec vos médicaments et symptômes

Mais je peux aussi simplement bavarder avec vous ! 😊"""

    # Questions sur l'application
    elif any(app_q in input_lower for app_q in ['application', 'app', 'kidjamo']):
        response = """Kidjamo est une application de santé connectée spécialement conçue pour les personnes atteintes de drépanocytose.

 **Fonctionnalités principales :**
• Suivi des données vitales via votre bracelet connecté
• Journal de santé personnalisé
• Gestion des médicaments et rappels
• Alertes automatiques en cas d'anomalie
• Chat avec moi, votre assistant IA !

L'objectif est de vous aider à mieux gérer votre maladie au quotidien."""

    # Demandes d'explication générale
    elif any(explain in input_lower for explain in ['explique', 'qu\'est-ce que', 'comment fonctionne']):
        response = """J'adore expliquer les choses ! De quoi voulez-vous que je vous parle exactement ?

Quelques suggestions :
 La drépanocytose et ses mécanismes
 Le fonctionnement des traitements
 Comment utiliser au mieux Kidjamo
 Des sujets scientifiques qui vous intéressent
 N'importe quel sujet de culture générale

Dites-moi ce qui vous intéresse !"""

    # Demandes de blagues
    elif any(joke in input_lower for joke in ['blague', 'rigolo', 'drôle', 'humour']):
        health_jokes = [
            "Pourquoi les médecins n'aiment pas les escaliers ? Parce qu'ils préfèrent les patients ! 😄",
            "Que dit un escargot quand il croise une limace ? 'Regarde, un nudiste !' 🐌",
            "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon, ils tombent dans le bateau ! 🏊‍♂️",
            "Comment appelle-t-on un chat tombé dans un pot de peinture le jour de Noël ? Un chat-mallow ! 🐱"
        ]
        response = random.choice(health_jokes) + "\n\nJ'espère que ça vous a fait sourire ! Le rire est excellent pour la santé. 😊"

    else:
        # Tentative de réponse avec Bedrock si disponible, sinon réponse générique
        response = generate_intelligent_response(user_input, 'general_question')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'general_question',
        'suggested_followups': [
            "Voulez-vous en savoir plus ?",
            "Avez-vous d'autres questions ?",
            "Cela répond-il à votre question ?"
        ]
    }

def handle_free_discussion(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les discussions libres et ouvertes
    """
    input_lower = user_input.lower()

    # Détection d'ennui ou solitude
    if any(bored in input_lower for bored in ['ennuie', 'seul', 'solitude', 'triste']):
        responses = [
            """Je comprends que vous puissiez vous sentir seul parfois. Sachez que je suis là pour vous ! 

Quelques idées pour passer le temps :
 Lire un bon livre
 Écouter de la musique apaisante  
 Dessiner ou faire du coloriage
 Appeler un proche
‍️ Une petite promenade si vous vous sentez bien

De quoi aimeriez-vous parler ?""",

            """L'ennui, ça arrive à tout le monde ! Profitons-en pour discuter ensemble.

Racontez-moi :
• Quel est votre film préféré ?
• Avez-vous des hobbies ?
• Qu'est-ce qui vous fait sourire ?
• Un souvenir qui vous rend heureux ?

Je suis tout ouïe ! """
        ]
        response = random.choice(responses)

    # Demandes de compagnie
    elif any(company in input_lower for company in ['tenir compagnie', 'discuter', 'parler', 'bavarder']):
        response = """Avec grand plaisir ! J'adore bavarder. 😊

Voici quelques sujets de conversation :
 Vos projets et rêves
 Films, séries, musique que vous aimez
 Recettes de cuisine favorites
 Endroits que vous aimeriez visiter
 Livres qui vous ont marqué
 Objectifs pour cette année

Ou alors, parlez-moi de votre journée ! Qu'avez-vous fait d'intéressant ?"""

    # Demandes d'opinion
    elif any(opinion in input_lower for opinion in ['ton avis', 'tu penses', 'opinion', 'selon toi']):
        response = """J'aime bien partager mon point de vue ! Sur quoi voulez-vous connaître mon avis ?

Quelques sujets passionnants :
 Films et séries du moment
 Nouvelles technologies
 Écologie et environnement
 Évolutions de la médecine
 Éducation et apprentissage

Ou alors, dites-moi d'abord ce que VOUS en pensez, et je vous donnerai mon avis ! 🤔"""

    # Discussion libre générale
    else:
        response = generate_intelligent_response(user_input, 'free_discussion')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'free_discussion',
        'mood_boost': True,
        'suggested_topics': [
            "Parlez-moi de vos passions",
            "Qu'est-ce qui vous rend heureux ?",
            "Avez-vous des projets excitants ?",
            "Racontez-moi une belle histoire"
        ]
    }

def handle_life_advice(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Donne des conseils pour la vie quotidienne
    """
    input_lower = user_input.lower()

    # Conseils sommeil
    if any(sleep in input_lower for sleep in ['dormir', 'sommeil', 'insomnie', 'endormir']):
        response = """💤 **Conseils pour bien dormir :**

 **Routine du soir :**
• Se coucher à heure fixe
• Éteindre les écrans 1h avant
• Lecture ou méditation
• Chambre fraîche (18-20°C)

 **À éviter :**
• Caféine après 14h
• Repas copieux le soir
• Sport intense avant le coucher

 **Relaxation :**
• Exercices de respiration
• Musique douce
• Tisane camomille ou verveine

Pour votre drépanocytose, un bon sommeil aide à réduire les crises !"""

    # Gestion du stress
    elif any(stress in input_lower for stress in ['stress', 'angoisse', 'anxiété', 'nerveux']):
        response = """ **Techniques anti-stress :**

🌬 **Respiration :**
• Inspirez 4 secondes
• Retenez 4 secondes  
• Expirez 6 secondes
• Répétez 5 fois

 **Organisation :**
• Listes de priorités
• Pauses régulières
• Une chose à la fois

 **Bien-être :**
• Marche en nature
• Musique relaxante
• Parler à un proche
• Activité créative

Le stress peut déclencher des crises. Prenez soin de vous ! """

    # Conseils motivation
    elif any(motiv in input_lower for motiv in ['motivation', 'motivé', 'objectifs', 'réussir']):
        response = """ **Booster sa motivation :**

 **Objectifs SMART :**
• Spécifiques et clairs
• Mesurables
• Atteignables
• Réalistes  
• Temporels (avec deadline)

 **Techniques :**
• Diviser en petites étapes
• Célébrer chaque victoire
• Visualiser le succès
• S'entourer de positif

 **Rappels quotidiens :**
• Pourquoi c'est important pour vous
• Vos progrès déjà accomplis
• Votre force intérieure

Vous avez déjà surmonté tant de défis avec votre maladie ! 🌟"""

    # Conseils alimentation
    elif any(food in input_lower for food in ['manger', 'alimentation', 'nutrition', 'recette']):
        response = """ **Alimentation saine pour la drépanocytose :**

 **Hydratation (CRUCIAL) :**
• 2-3 litres d'eau/jour minimum
• Éviter l'alcool
• Tisanes et soupes comptent

 **Nutriments importants :**
• Acide folique (légumes verts)
• Fer (viande, légumineuses)
• Vitamine C (agrumes, kiwi)
• Calcium (laitages, épinards)

 **À limiter :**
• Aliments trop salés
• Fritures excessives
• Boissons glacées

Une bonne nutrition aide à prévenir les crises ! """

    else:
        response = generate_intelligent_response(user_input, 'life_advice')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'life_advice',
        'health_focused': True,
        'actionable_tips': True
    }

def handle_culture_education(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fournit des informations culturelles et éducatives
    """
    input_lower = user_input.lower()

    # Questions scientifiques
    if any(science in input_lower for science in ['science', 'scientifique', 'recherche', 'découverte']):
        response = """ **Découvertes scientifiques passionnantes :**

 **Médecine personnalisée :**
• Traitements adaptés à chaque ADN
• Thérapies géniques prometteuses
• IA pour diagnostic précoce

 **Écologie & Tech :**
• Énergies renouvelables innovantes
• Captage du CO2 atmosphérique
• Agriculture verticale urbaine

 **Espace :**
• Missions vers Mars en préparation
• Télescope James Webb révolutionne l'astronomie
• Tourisme spatial en développement

Quel domaine vous intéresse le plus ? """

    # Histoire et culture
    elif any(history in input_lower for history in ['histoire', 'historique', 'passé', 'ancien']):
        response = """ **L'Histoire nous enseigne beaucoup :**

 **Civilisations anciennes :**
• Égyptiens : pionniers de la médecine
• Grecs : naissance de la philosophie
• Chinois : inventions révolutionnaires

 **Révolutions culturelles :**
• Renaissance : explosion artistique
• Lumières : révolution des idées
• 20e siècle : démocratisation de l'art

 **Échanges interculturels :**
• Route de la soie
• Grandes explorations
• Mondialisation moderne

Quelle période vous fascine ? """

    # Arts et littérature
    elif any(art in input_lower for art in ['art', 'peinture', 'musique', 'littérature', 'livre']):
        response = """ **Le monde des arts :**

 **Suggestions lecture :**
• Romans français contemporains
• Sci-fi inspirante (Asimov, Liu Cixin)
• Biographies motivantes
• Poésie (Prévert, Baudelaire)

 **Musique thérapeutique :**
• Classique : Mozart, Debussy
• Jazz : apaisement et créativité
• Musiques du monde : évasion
• Lo-fi : concentration

 **Art visuel :**
• Impressionnistes français
• Art contemporain engagé
• Street art expressif
• Photographie documentaire

Quel art vous attire le plus ? """

    # Langues et communication
    elif any(lang in input_lower for lang in ['langue', 'apprendre', 'parler', 'communication']):
        response = """ **Apprendre une nouvelle langue :**

 **Méthodes efficaces :**
• Applications mobiles (Duolingo, Babbel)
• Films/séries en VO sous-titrées
• Musique dans la langue cible
• Échange linguistique en ligne

 **Langues populaires :**
• Anglais : langue internationale
• Espagnol : 500M de locuteurs
• Mandarin : opportunités business
• Arabe : richesse culturelle

 **Bienfaits :**
• Stimule le cerveau
• Ouvre de nouveaux horizons
• Améliore la mémoire
• Facilite les voyages

Quelle langue vous tente ? """

    else:
        response = generate_intelligent_response(user_input, 'culture_education')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'culture_education',
        'educational_value': True,
        'curiosity_stimulating': True
    }

def generate_intelligent_response(user_input: str, conversation_type: str) -> str:
    """
    Génère une réponse intelligente en utilisant Bedrock ou des réponses prédéfinies
    """
    try:
        # Tentative d'utilisation de Bedrock (Claude)
        prompt = f"""Tu es Kidjamo, un assistant santé bienveillant spécialisé dans la drépanocytose. 
Réponds de manière conversationnelle, empathique et utile à la question suivante.
Garde un ton amical et inclus toujours une dimension santé/bien-être quand c'est pertinent.

Question de l'utilisateur : {user_input}
Type de conversation : {conversation_type}

Réponds en français de manière naturelle et engageante :"""

        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 300,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7
            })
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    except Exception as e:
        logger.warning(f"Bedrock non disponible, utilisation fallback: {str(e)}")
        return generate_fallback_response(user_input, conversation_type)

def generate_fallback_response(user_input: str, conversation_type: str) -> str:
    """
    Génère une réponse de secours quand Bedrock n'est pas disponible
    """
    fallback_responses = {
        'general_question': [
            "C'est une excellente question ! Je vais faire de mon mieux pour vous aider. Pouvez-vous me donner plus de détails ?",
            "Intéressant ! J'aimerais en discuter avec vous. Qu'est-ce qui vous amène à vous poser cette question ?",
            "Bonne question ! Je pense qu'on peut explorer ça ensemble. Dites-moi ce que vous en savez déjà ?"
        ],
        'free_discussion': [
            "J'adore bavarder avec vous ! Continuez, je vous écoute attentivement.",
            "C'est passionnant ! Racontez-moi en plus, j'ai hâte d'en savoir davantage.",
            "Vous avez un point de vue très intéressant. Qu'est-ce qui vous fait penser ça ?"
        ],
        'life_advice': [
            "Voici ce que je peux vous conseiller : prenez les choses étape par étape et soyez patient avec vous-même.",
            "Mon conseil : écoutez votre corps et vos émotions. Vous connaissez mieux que quiconque vos besoins.",
            "Je pense que la clé est de trouver un équilibre qui vous convient. Qu'en pensez-vous ?"
        ],
        'culture_education': [
            "C'est un sujet fascinant ! Il y a tellement à découvrir dans ce domaine.",
            "J'adore parler de culture et d'éducation ! C'est enrichissant pour l'esprit.",
            "Excellente curiosité ! L'apprentissage est une belle façon de grandir."
        ]
    }

    responses = fallback_responses.get(conversation_type, fallback_responses['general_question'])
    base_response = random.choice(responses)

    # Ajout d'une touche santé/bien-être
    health_additions = [
        "\n\nAu fait, comment vous sentez-vous aujourd'hui ?",
        "\n\nN'oubliez pas de prendre soin de vous ! ",
        "\n\nJ'espère que nos discussions vous font du bien.",
        "\n\nAvez-vous pensé à bien vous hydrater aujourd'hui ?"
    ]

    return base_response + random.choice(health_additions)

def handle_general_fallback(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les cas où l'intention n'est pas clairement identifiée
    """
    response = f"""Je ne suis pas sûr de bien comprendre, mais j'aimerais vous aider ! 

Voici ce que je peux faire pour vous :
 **Discuter de tout et de rien**
 **Répondre à vos questions**  
 **Donner des conseils de vie**
 **Parler culture et éducation**
 **Vous aider avec votre santé**

Dites-moi simplement ce qui vous intéresse ou préoccupe ! 😊

PS: Vous avez dit "{user_input[:50]}..." - voulez-vous qu'on en discute ?"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'general_fallback',
        'needs_clarification': True
    }

def search_medical_knowledge(query: str, user_context: Dict[str, Any] = {}) -> Dict[str, Any]:
    """
    Recherche intelligente dans la base de connaissances médicales avec Amazon Kendra
    """
    if not KENDRA_INDEX_ID:
        logger.warning("Index Kendra non configuré")
        return {
            'success': False,
            'message': "Service de recherche documentaire non disponible",
            'results': []
        }

    try:
        # Enrichissement de la requête avec le contexte médical
        enriched_query = enrich_medical_query(query, user_context)

        # Recherche dans Kendra
        response = kendra.query(
            IndexId=KENDRA_INDEX_ID,
            QueryText=enriched_query,
            PageSize=5,
            AttributeFilter={
                'EqualsTo': {
                    'Key': '_language_code',
                    'Value': {
                        'StringValue': 'fr'
                    }
                }
            },
            Facets=[
                {
                    'DocumentAttributeKey': 'category'
                },
                {
                    'DocumentAttributeKey': 'document_type'
                }
            ]
        )

        # Traitement des résultats
        results = process_kendra_results(response, query)

        return {
            'success': True,
            'query': enriched_query,
            'results': results,
            'total_results': len(results)
        }

    except Exception as e:
        logger.error(f"Erreur recherche Kendra: {str(e)}")
        return {
            'success': False,
            'message': f"Erreur lors de la recherche: {str(e)}",
            'results': []
        }

def enrich_medical_query(query: str, context: Dict[str, Any]) -> str:
    """
    Enrichit la requête avec des termes médicaux pertinents
    """
    query_lower = query.lower()
    enriched_terms = []

    # Ajout automatique du contexte drépanocytose si pertinent
    medical_terms = ['douleur', 'crise', 'anémie', 'traitement', 'médicament']
    if any(term in query_lower for term in medical_terms):
        enriched_terms.append('drépanocytose')

    # Expansion des termes médicaux courants
    term_expansions = {
        'mal': 'douleur symptôme',
        'fatigue': 'asthénie épuisement',
        'essoufflement': 'dyspnée respiration difficile',
        'fièvre': 'température hyperthermie',
        'crise': 'épisode aigu vaso-occlusif',
        'anémie': 'hémoglobine globules rouges',
        'hydroxyurée': 'hydroxycarbamide traitement',
        'transfusion': 'échange sanguin'
    }

    for term, expansion in term_expansions.items():
        if term in query_lower:
            enriched_terms.extend(expansion.split())

    # Construction de la requête enrichie
    enriched_query = query
    if enriched_terms:
        enriched_query += f" {' '.join(set(enriched_terms))}"

    return enriched_query

def process_kendra_results(kendra_response: Dict[str, Any], original_query: str) -> List[Dict[str, Any]]:
    """
    Traite et formate les résultats de Kendra
    """
    results = []

    # Traitement des résultats directs (FAQ, extraits)
    for item in kendra_response.get('ResultItems', []):
        result = {
            'type': item.get('Type', 'DOCUMENT'),
            'title': extract_text_from_highlights(item.get('DocumentTitle', {})),
            'excerpt': extract_text_from_highlights(item.get('DocumentExcerpt', {})),
            'score': item.get('ScoreAttributes', {}).get('ScoreConfidence', 'MEDIUM'),
            'source_uri': item.get('DocumentURI', ''),
            'document_id': item.get('DocumentId', ''),
            'relevance': calculate_relevance_score(item, original_query)
        }

        # Ajout des métadonnées du document
        if 'DocumentAttributes' in item:
            result['metadata'] = extract_document_metadata(item['DocumentAttributes'])

        results.append(result)

    # Tri par pertinence
    results.sort(key=lambda x: x['relevance'], reverse=True)

    return results

def extract_text_from_highlights(highlight_object: Dict[str, Any]) -> str:
    """
    Extrait le texte des objets avec highlights de Kendra
    """
    if not highlight_object:
        return ""

    if 'Text' in highlight_object:
        return highlight_object['Text']

    # Reconstruction du texte avec highlights
    if 'Highlights' in highlight_object:
        text_parts = []
        for highlight in highlight_object['Highlights']:
            text_parts.append(highlight.get('TopAnswer', {}).get('Text', ''))
        return ' '.join(filter(None, text_parts))

    return ""

def extract_document_metadata(attributes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extrait les métadonnées utiles du document
    """
    metadata = {}

    for attr in attributes:
        key = attr.get('Key', '')
        value = attr.get('Value', {})

        if key == 'category':
            metadata['category'] = value.get('StringValue', '')
        elif key == 'document_type':
            metadata['type'] = value.get('StringValue', '')
        elif key == 'last_updated':
            metadata['last_updated'] = value.get('DateValue', '')
        elif key == 'author':
            metadata['author'] = value.get('StringValue', '')
        elif key == 'medical_specialty':
            metadata['specialty'] = value.get('StringValue', '')

    return metadata

def calculate_relevance_score(item: Dict[str, Any], query: str) -> float:
    """
    Calcule un score de pertinence personnalisé
    """
    base_score = 0.5

    # Score basé sur la confiance Kendra
    confidence = item.get('ScoreAttributes', {}).get('ScoreConfidence', 'MEDIUM')
    confidence_scores = {'HIGH': 1.0, 'MEDIUM': 0.7, 'LOW': 0.3}
    base_score += confidence_scores.get(confidence, 0.5) * 0.3

    # Bonus pour les types de résultats préférés
    result_type = item.get('Type', '')
    if result_type == 'QUESTION_ANSWER':
        base_score += 0.2
    elif result_type == 'ANSWER':
        base_score += 0.15

    # Bonus pour les documents récents
    doc_attributes = item.get('DocumentAttributes', [])
    for attr in doc_attributes:
        if attr.get('Key') == 'last_updated':
            # Logique pour favoriser les documents récents
            base_score += 0.1
            break

    return min(base_score, 1.0)

def format_search_results_response(search_results: Dict[str, Any], original_query: str) -> str:
    """
    Formate les résultats de recherche en réponse conversationnelle
    """
    if not search_results.get('success') or not search_results.get('results'):
        return f"""Je n'ai pas trouvé d'informations spécifiques sur "{original_query}" dans ma base documentaire.

Cependant, je peux vous aider avec :
• Des questions générales sur la drépanocytose
• Des conseils de vie quotidienne
• Des informations sur les traitements

Voulez-vous reformuler votre question ou avez-vous besoin d'aide sur un autre sujet ?"""

    results = search_results['results'][:3]  # Top 3 résultats

    response = f"""📚 **Voici ce que j'ai trouvé sur "{original_query}" :**\n\n"""

    for i, result in enumerate(results, 1):
        title = result.get('title', 'Document sans titre')
        excerpt = result.get('excerpt', '')

        response += f"**{i}. {title}**\n"

        if excerpt:
            # Limitation de l'extrait à 200 caractères
            if len(excerpt) > 200:
                excerpt = excerpt[:200] + "..."
            response += f"{excerpt}\n"

        # Ajout de métadonnées si disponibles
        metadata = result.get('metadata', {})
        if metadata.get('category'):
            response += f"*Catégorie: {metadata['category']}*\n"

        response += "\n"

    # Message d'encouragement
    response += """💡 **Besoin de plus d'informations ?**
N'hésitez pas à me poser des questions plus spécifiques ! Je peux aussi vous expliquer ces informations de manière plus détaillée."""

    return response

def handle_knowledge_search(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les demandes de recherche dans la base de connaissances
    """
    # Détection des mots-clés de recherche
    search_keywords = [
        'recherche', 'trouve', 'information', 'documentation', 'étude',
        'article', 'guide', 'explication', 'qu\'est-ce que', 'comment',
        'pourquoi', 'définition', 'symptôme', 'traitement', 'médicament'
    ]

    input_lower = user_input.lower()
    should_search = any(keyword in input_lower for keyword in search_keywords)

    if should_search:
        # Effectuer la recherche
        search_results = search_medical_knowledge(user_input, context)
        response_text = format_search_results_response(search_results, user_input)

        return {
            'success': True,
            'response': response_text,
            'conversation_type': 'knowledge_search',
            'search_performed': True,
            'results_count': search_results.get('total_results', 0)
        }

    return None  # Pas une demande de recherche
