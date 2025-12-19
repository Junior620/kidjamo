"""
Adaptation des VRAIES fonctions Lambda pour le mode local
Utilise la logique originale sans les dépendances AWS
"""

import json
import os
import logging
import random
from datetime import datetime, timezone
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)

# =================================================================
# ADAPTATION DE general_conversation/main.py POUR LE MODE LOCAL
# =================================================================

def lambda_handler_general_conversation(event: Dict[str, Any], context=None) -> Dict[str, Any]:
    """
    Version locale du lambda_handler de general_conversation
    """
    try:
        logger.info(f"Événement conversation générale reçu: {json.dumps(event, ensure_ascii=False)}")

        intent_name = event.get('intent_name')
        user_input = event.get('user_input', '')
        user_id = event.get('user_id', 'anonymous')
        conversation_context = event.get('conversation_context', {})

        # Routage selon le type de conversation (VRAIE LOGIQUE LAMBDA)
        if intent_name == 'ConversationGenerale':
            return handle_polite_conversation_real(user_input, conversation_context)
        elif intent_name == 'QuestionsGenerales':
            return handle_general_questions_real(user_input, conversation_context)
        elif intent_name == 'DiscussionLibre':
            return handle_free_discussion_real(user_input, conversation_context)
        elif intent_name == 'ConseilsVieQuotidienne':
            return handle_life_advice_real(user_input, conversation_context)
        elif intent_name == 'CultureEducation':
            return handle_culture_education_real(user_input, conversation_context)
        else:
            return handle_general_fallback_real(user_input, conversation_context)

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler conversation: {str(e)}")
        return {
            'success': False,
            'response': "Je rencontre une petite difficulté. Pouvez-vous reformuler votre question ?",
            'error': str(e)
        }

def handle_polite_conversation_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_polite_conversation des Lambda
    """
    input_lower = user_input.lower()

    # Détection du type de salutation (VRAIE LOGIQUE)
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
    elif any(feeling in input_lower for feeling in ['ça va', 'ca va', 'comment ça va', 'comment ca va', 'comment allez-vous', 'comment tu vas', 'comment vous allez', 'tu vas bien', 'vous allez bien', 'ça va ?', 'ca va ?']):
        responses = [
            "Ça va très bien, merci beaucoup ! Et vous, comment vous sentez-vous aujourd'hui ?",
            "Je vais parfaitement bien ! J'espère que vous aussi. Racontez-moi votre journée.",
            "Tout va bien de mon côté ! Et votre santé, comment ça se passe ?",
            "Excellente forme ! Comment se passent vos traitements ces temps-ci ?",
            "Je me sens en pleine forme pour vous aider ! Et vous, comment allez-vous ?",
            "Super bien ! Prêt à discuter avec vous. Comment vous portez-vous ?"
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

def handle_general_questions_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_general_questions des Lambda
    """
    input_lower = user_input.lower()

    # Questions sur le temps (VRAIE LOGIQUE)
    if any(time_q in input_lower for time_q in ['quelle heure', 'heure est-il', 'temps']):
        current_time = datetime.now().strftime("%H:%M")
        response = f"Il est actuellement {current_time}. N'oubliez pas de prendre vos médicaments à l'heure prévue !"

    # Questions sur la date (VRAIE LOGIQUE)
    elif any(date_q in input_lower for date_q in ['quel jour', 'date', 'aujourd\'hui']):
        current_date = datetime.now().strftime("%A %d %B %Y")
        response = f"Nous sommes {current_date}. J'espère que cette journée se passe bien pour vous !"

    # Questions sur l'identité du bot (VRAIE LOGIQUE)
    elif any(identity in input_lower for identity in ['qui es-tu', 'qui êtes-vous', 'ton nom', 'tu t\'appelles', 'tu es qui']):
        response = """Je suis votre assistant santé Kidjamo ! 🤖

🎯 **Mon rôle :**
• Vous accompagner dans le suivi de votre drépanocytose
• Répondre à vos questions de santé
• Discuter avec vous quand vous en avez envie
• Vous aider avec vos médicaments et symptômes
• Être là pour vous 24h/24 et 7j/7

💬 **Ce que j'aime faire :**
• Bavarder de tout et de rien
• Donner des conseils bienveillants
• Expliquer des sujets complexes simplement
• Vous encourager et vous soutenir

Je suis vraiment heureux de pouvoir vous aider ! 😊"""

    # Questions sur l'application (VRAIE LOGIQUE)
    elif any(app_q in input_lower for app_q in ['application', 'app', 'kidjamo']):
        response = """🏥 **Kidjamo** est une application de santé connectée spécialement conçue pour les personnes atteintes de drépanocytose.

✨ **Fonctionnalités principales :**
•  Suivi des données vitales via votre bracelet connecté
•  Journal de santé personnalisé et intelligent
•  Gestion des médicaments avec rappels automatiques
•  Alertes automatiques en cas d'anomalie détectée
•  Chat avec moi, votre assistant IA personnel !
•  Analyses et tendances de votre état de santé

 **Notre mission :**
Vous aider à mieux gérer votre drépanocytose au quotidien grâce à la technologie, tout en gardant une approche humaine et bienveillante."""

    # Demandes d'explication générale (VRAIE LOGIQUE)
    elif any(explain in input_lower for explain in ['explique', 'qu\'est-ce que', 'comment fonctionne']):
        response = """J'adore expliquer les choses ! 📚 De quoi voulez-vous que je vous parle exactement ?

💡 **Quelques suggestions :**
•  La drépanocytose et ses mécanismes
•  Le fonctionnement des traitements
•  Comment utiliser au mieux Kidjamo
•  Des sujets scientifiques qui vous intéressent
•  N'importe quel sujet de culture générale
•  Art, littérature, musique...

Dites-moi ce qui vous intéresse et je vous expliquerai avec plaisir ! 😊"""

    # Demandes de blagues (VRAIE LOGIQUE)
    elif any(joke in input_lower for joke in ['blague', 'rigolo', 'drôle', 'humour']):
        health_jokes = [
            "Pourquoi les médecins n'aiment pas les escaliers ? Parce qu'ils préfèrent les patients ! 😄",
            "Que dit un escargot quand il croise une limace ? 'Regarde, un nudiste !' 🐌",
            "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon, ils tombent dans le bateau ! 🏊‍♂️",
            "Comment appelle-t-on un chat tombé dans un pot de peinture le jour de Noël ? Un chat-mallow ! 🐱",
            "Qu'est-ce qui est jaune et qui attend ? Jonathan ! 🍌"
        ]
        response = random.choice(health_jokes) + "\n\n😊 J'espère que ça vous a fait sourire ! Le rire est excellent pour la santé et peut même aider à réduire le stress."

    # Questions sur la drépanocytose (VRAIE LOGIQUE)
    elif any(sickle in input_lower for sickle in ['drépanocytose', 'drepanocytose', 'anémie falciforme']):
        response = """🩸 **La drépanocytose - Information essentielle :**

🔬 **Qu'est-ce que c'est ?**
La drépanocytose est une maladie génétique qui affecte l'hémoglobine dans les globules rouges. Au lieu d'être ronds et flexibles, les globules rouges prennent une forme de faucille (croissant) et deviennent rigides.

⚡ **Principales manifestations :**
• Crises douloureuses vaso-occlusives
• Anémie chronique et fatigue
• Risque d'infections accrues
• Complications possibles aux organes

🎯 **Prise en charge moderne :**
• Hydroxyurée (traitement de fond)
• Gestion préventive des crises
• Vaccination renforcée
• Suivi médical régulier
• Hydratation constante (très important !)

💪 **Vivre avec la drépanocytose :**
Grâce aux avancées médicales et à un suivi adapté, il est possible de mener une vie épanouie ! L'essentiel est un bon suivi médical et l'écoute de son corps.

Avez-vous des questions spécifiques sur votre suivi ?"""

    else:
        # Réponse générique intelligente (adaptation de la logique Bedrock)
        response = generate_local_intelligent_response(user_input, 'general_question')

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

def handle_free_discussion_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_free_discussion des Lambda
    """
    input_lower = user_input.lower()

    # Détection d'ennui ou solitude (VRAIE LOGIQUE)
    if any(bored in input_lower for bored in ['ennuie', 'seul', 'solitude', 'triste', 'm\'ennuie']):
        responses = [
            """💙 Je comprends que vous puissiez vous sentir seul parfois. Sachez que je suis là pour vous ! 

🌟 **Quelques idées pour passer le temps :**
• 📚 Lire un bon livre (ça occupe l'esprit)
• 🎵 Écouter de la musique apaisante  
• 🎨 Dessiner ou faire du coloriage (très relaxant)
• 📞 Appeler un proche qui vous fait du bien
• 🚶‍♀️ Une petite promenade si vous vous sentez bien
• 🧘‍♀️ Méditation ou exercices de respiration

💬 De quoi aimeriez-vous parler ? Je suis là pour bavarder ! 😊""",

            """😔 L'ennui, ça arrive à tout le monde ! Profitons-en pour discuter ensemble.

🤔 **Racontez-moi :**
• Quel est votre film ou série préféré ?
• Avez-vous des hobbies ou passions ?
• Qu'est-ce qui vous fait vraiment sourire ?
• Un souvenir heureux qui vous réchauffe le cœur ?
• Des projets ou rêves qui vous motivent ?

Je suis tout ouïe et j'adore apprendre à connaître les gens ! 😊"""
        ]
        response = random.choice(responses)

    # Demandes de compagnie (VRAIE LOGIQUE)
    elif any(company in input_lower for company in ['tenir compagnie', 'discuter', 'parler', 'bavarder', 'discute avec moi']):
        response = """😊 Avec grand plaisir ! J'adore bavarder et faire connaissance.

💬 **Voici quelques sujets de conversation sympa :**
• 🎯 Vos projets et rêves pour l'avenir
• 🎬 Films, séries, musique que vous aimez
• 🍽️ Recettes de cuisine favorites (j'adore ça !)
• 🌍 Endroits que vous aimeriez visiter
• 📖 Livres qui vous ont marqué
• 🏆 Objectifs pour cette année
• 🎨 Activités créatives qui vous plaisent

🗣️ **Ou alors, parlez-moi de votre journée !** 
Qu'avez-vous fait d'intéressant ? Comment vous sentez-vous ? 

Je suis vraiment curieux de vous connaître ! ✨"""

    # Demandes d'opinion (VRAIE LOGIQUE)
    elif any(opinion in input_lower for opinion in ['ton avis', 'tu penses', 'opinion', 'selon toi', 'que penses-tu']):
        response = """🤔 J'aime bien partager mon point de vue ! Sur quoi voulez-vous connaître mon avis ?

💭 **Quelques sujets passionnants :**
• 🎬 Films et séries du moment
• 💻 Nouvelles technologies et IA
• 🌱 Écologie et environnement
• 🏥 Évolutions de la médecine
• 📚 Éducation et apprentissage
• 🎵 Musique et tendances culturelles

🗨️ **Ou alors, dites-moi d'abord ce que VOUS en pensez !** 
J'adore échanger les points de vue et comprendre différentes perspectives. 

De quoi voulez-vous débattre ? 😊"""

    # Discussion libre générale (VRAIE LOGIQUE)
    else:
        response = generate_local_intelligent_response(user_input, 'free_discussion')

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

def handle_life_advice_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_life_advice des Lambda
    """
    input_lower = user_input.lower()

    # Conseils sommeil (VRAIE LOGIQUE)
    if any(sleep in input_lower for sleep in ['dormir', 'sommeil', 'insomnie', 'endormir']):
        response = """💤 **Conseils pour bien dormir avec la drépanocytose :**

🌙 **Routine du soir optimale :**
• Se coucher à heure fixe (régularité = clé !)
• Éteindre les écrans 1h avant le coucher
• Lecture paisible ou méditation douce
• Chambre fraîche (18-20°C) et bien ventilée
• Literie confortable et position adaptée

❌ **À éviter absolument :**
• Caféine après 14h (café, thé, sodas)
• Repas copieux le soir (digestion difficile)
• Sport intense 3h avant le coucher
• Stress et préoccupations au lit

🧘‍♀️ **Techniques de relaxation :**
• Exercices de respiration profonde (4-7-8)
• Musique douce ou sons de la nature
• Tisane camomille, verveine ou tilleul
• Étirements légers

💊 **Important pour votre drépanocytose :**
Un bon sommeil aide à réduire les crises et renforce votre système immunitaire ! 🛡️"""

    # Gestion du stress (VRAIE LOGIQUE)
    elif any(stress in input_lower for stress in ['stress', 'angoisse', 'anxiété', 'nerveux', 'stressé']):
        response = """🧠 **Techniques anti-stress spécialement efficaces :**

🌬️ **Respiration thérapeutique :**
• Inspirez lentement 4 secondes
• Retenez votre souffle 4 secondes  
• Expirez doucement 6 secondes
• Répétez 5-10 fois (effet immédiat !)

📋 **Organisation mentale :**
• Listes de priorités claires
• Pauses régulières (technique Pomodoro)
• Une seule chose à la fois (focus)
• Dire NON quand c'est nécessaire

🌿 **Bien-être naturel :**
• Marche en nature (même 10 min)
• Musique relaxante ou méditation
• Parler à un proche de confiance
• Activité créative libératrice

⚠️ **Important drépanocytose :**
Le stress peut déclencher des crises ! Ces techniques sont votre bouclier protecteur. 🛡️"""

    # Conseils motivation (VRAIE LOGIQUE)
    elif any(motiv in input_lower for motiv in ['motivation', 'motivé', 'objectifs', 'réussir']):
        response = """🚀 **Booster sa motivation durablement :**

🎯 **Méthode SMART pour vos objectifs :**
• **S**pécifiques et clairs (pas de flou)
• **M**esurables (quantifiables)
• **A**tteignables (réalistes)
• **R**elevants (importantes pour vous)
• **T**emporels (avec deadline précise)

💪 **Techniques de motivation :**
• Diviser en petites étapes (effet domino)
• Célébrer chaque victoire (même petite !)
• Visualiser le succès final
• S'entourer de personnes positives
• Journal de progression

🌟 **Rappels quotidiens puissants :**
• POURQUOI c'est important pour vous
• Vos progrès déjà accomplis
• Votre force intérieure démontrée

💎 **Message spécial :**
Vous gérez déjà une maladie complexe avec courage. Cette force vous aidera pour TOUS vos autres défis ! 🦾"""

    # Conseils alimentation (VRAIE LOGIQUE)
    elif any(food in input_lower for food in ['manger', 'alimentation', 'nutrition', 'recette']):
        response = """🍽️ **Alimentation optimale pour la drépanocytose :**

💧 **HYDRATATION (CRUCIAL) :**
• 2,5-3 litres d'eau/jour MINIMUM
• Éviter l'alcool (déshydrate)
• Tisanes, soupes, fruits juteux comptent
• Toujours avoir une bouteille à portée

🥗 **Nutriments essentiels :**
• **Acide folique** : épinards, brocolis, légumes verts
• **Fer** : viande rouge, lentilles, quinoa
• **Vitamine C** : agrumes, kiwi, poivrons (aide absorption fer)
• **Calcium** : produits laitiers, amandes, épinards
• **Zinc** : fruits de mer, graines de tournesol

❌ **À limiter pour votre santé :**
• Aliments très salés (déshydratation)
• Fritures excessives (inflammation)
• Boissons glacées (peuvent déclencher crises)
• Alcool (interfère avec traitements)

🎯 **Résultat :** Une nutrition adaptée prévient les crises et booste votre énergie ! ⚡"""

    else:
        # Réponse générique de conseil de vie
        response = generate_local_intelligent_response(user_input, 'life_advice')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'life_advice',
        'health_focused': True,
        'actionable_tips': True
    }

def handle_culture_education_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_culture_education des Lambda
    """
    input_lower = user_input.lower()

    # Questions scientifiques (VRAIE LOGIQUE)
    if any(science in input_lower for science in ['science', 'scientifique', 'recherche', 'découverte']):
        response = """🔬 **Découvertes scientifiques fascinantes d'aujourd'hui :**

🧬 **Médecine personnalisée :**
• Traitements adaptés à chaque ADN unique
• Thérapies géniques CRISPR prometteuses
• IA pour diagnostic précoce ultra-précis
• Nano-médecine ciblée

🌱 **Écologie & Technologies vertes :**
• Énergies renouvelables révolutionnaires
• Captage du CO2 atmosphérique à grande échelle
• Agriculture verticale urbaine high-tech
• Biocarburants de nouvelle génération

🚀 **Exploration spatiale :**
• Missions vers Mars en préparation active
• Télescope James Webb révolutionne l'astronomie
• Tourisme spatial en développement rapide
• Recherche de vie extraterrestre

💡 **Intelligence artificielle :**
• IA conversationnelle (comme moi ! 😊)
• Voitures autonomes
• Diagnostic médical assisté

Quel domaine vous passionne le plus ? 🤔"""

    # Histoire et culture (VRAIE LOGIQUE)
    elif any(history in input_lower for history in ['histoire', 'historique', 'passé', 'ancien']):
        response = """📚 **L'Histoire nous enseigne tant de choses :**

🏛️ **Civilisations anciennes fascinantes :**
• **Égyptiens** : pionniers de la médecine moderne
• **Grecs** : naissance de la philosophie et démocratie
• **Chinois** : inventions révolutionnaires (boussole, poudre...)
• **Mayas** : mathématiques et astronomie avancées

🎨 **Révolutions culturelles majeures :**
• **Renaissance** : explosion artistique et scientifique
• **Siècle des Lumières** : révolution des idées
• **20e siècle** : démocratisation de l'art et culture

🌍 **Échanges interculturels :**
• Route de la soie (commerce et idées)
• Grandes explorations (découverte du monde)
• Mondialisation moderne (internet, voyages)

💭 **Leçons intemporelles :**
Les peuples qui s'adaptent et s'ouvrent aux autres prospèrent !

Quelle période vous fascine le plus ? ⏰"""

    # Arts et littérature (VRAIE LOGIQUE)
    elif any(art in input_lower for art in ['art', 'peinture', 'musique', 'littérature', 'livre']):
        response = """🎨 **Le merveilleux monde des arts :**

📖 **Suggestions lecture enrichissantes :**
• **Romans français** : Amélie Nothomb, Marc Levy
• **Sci-fi inspirante** : Isaac Asimov, Liu Cixin
• **Biographies motivantes** : Nelson Mandela, Maya Angelou
• **Poésie** : Jacques Prévert, Baudelaire

🎵 **Musique thérapeutique :**
• **Classique** : Mozart (effet cognitif), Debussy (apaisement)
• **Jazz** : Miles Davis, John Coltrane (créativité)
• **Musiques du monde** : Reggae, Afrobeat (évasion)
• **Lo-fi/Ambient** : concentration et détente

🖼️ **Art visuel inspirant :**
• **Impressionnistes** : Monet, Renoir (lumière et couleur)
• **Art contemporain** : Banksy, Kehinde Wiley (messages)
• **Street art** : expression libre et accessible
• **Photographie** : Vivian Maier, Henri Cartier-Bresson

🎭 L'art soigne l'âme et stimule la créativité ! Quel art vous attire ? ✨"""

    # Langues et communication (VRAIE LOGIQUE)
    elif any(lang in input_lower for lang in ['langue', 'apprendre', 'parler', 'communication']):
        response = """🗣️ **Apprendre une nouvelle langue - Guide complet :**

📱 **Méthodes modernes efficaces :**
• **Apps mobiles** : Duolingo, Babbel, Busuu
• **Immersion** : Films/séries en VO sous-titrées
• **Musique** : chansons dans la langue cible
• **Échange** : HelloTalk, Tandem (natifs en ligne)

🌍 **Langues populaires et opportunités :**
• **Anglais** : langue internationale business/tech
• **Espagnol** : 500M locuteurs, culture riche
• **Mandarin** : opportunités économiques Asie
• **Arabe** : richesse culturelle millénaire

🧠 **Bienfaits scientifiquement prouvés :**
• Stimule le cerveau (prévient Alzheimer)
• Ouvre nouveaux horizons culturels
• Améliore mémoire et concentration
• Facilite voyages et rencontres

💡 **Astuce motivation :** 15 min/jour = progrès visibles en 3 mois !

Quelle langue vous tente le plus ? 🌟"""

    else:
        # Réponse générique culturelle/éducative
        response = generate_local_intelligent_response(user_input, 'culture_education')

    return {
        'success': True,
        'response': response,
        'conversation_type': 'culture_education',
        'educational_value': True,
        'curiosity_stimulating': True
    }

def handle_general_fallback_real(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de handle_general_fallback des Lambda
    """
    # Détection de mots-clés pour orientation
    input_lower = user_input.lower()

    suggestions = []

    if any(health in input_lower for health in ['mal', 'douleur', 'fatigue', 'symptôme']):
        suggestions.append("🩺 Signaler une douleur ? (\"J'ai mal...\")")

    if any(med in input_lower for med in ['médicament', 'traitement', 'pilule']):
        suggestions.append("💊 Parler de médicaments ? (\"Mes médicaments...\")")

    if any(data in input_lower for data in ['données', 'vitales', 'mesure']):
        suggestions.append("📊 Voir vos données ? (\"Mes vitales...\")")

    if any(quest in input_lower for quest in ['question', 'qu\'est-ce', 'pourquoi', 'comment']):
        suggestions.append("📚 Poser une question médicale ? (\"Qu'est-ce que...\")")

    if any(chat in input_lower for chat in ['parler', 'discuter', 'bavarder']):
        suggestions.append("💬 Simplement discuter ? (\"Bonjour\", \"Comment ça va...\")")

    # Si pas de suggestions spécifiques, suggestions générales
    if not suggestions:
        suggestions = [
            "🩺 Signaler une douleur ? (\"J'ai mal...\")",
            "💊 Parler de médicaments ? (\"Mes médicaments...\")",
            "📊 Voir vos données ? (\"Mes vitales...\")",
            "📚 Poser une question médicale ? (\"Qu'est-ce que...\")",
            "💬 Simplement discuter ? (\"Bonjour\", \"Comment ça va...\")"
        ]

    response = f"""🤔 Je n'ai pas bien saisi votre demande, mais j'aimerais vraiment vous aider !

**Vous avez dit :** "{user_input}"

💡 **Peut-être vouliez-vous :**
{chr(10).join(f"• {s}" for s in suggestions)}

🎯 **Pour de meilleurs résultats :**
• Utilisez des phrases simples et directes
• Mentionnez les mots-clés importants
• N'hésitez pas à reformuler différemment

🆘 **Aide rapide :**
Tapez "aide" pour le guide complet d'utilisation.

Comment puis-je vous aider aujourd'hui ? 😊"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'general_fallback',
        'needs_clarification': True
    }

def generate_local_intelligent_response(user_input: str, conversation_type: str) -> str:
    """
    Génère une réponse intelligente locale (adaptation de Bedrock)
    """
    # Réponses contextiques basées sur l'analyse du texte
    input_lower = user_input.lower()

    # Analyse du sentiment et du contexte
    context_responses = {
        'positive': [
            "C'est formidable ! J'adore votre enthousiasme. Racontez-moi en plus !",
            "Que c'est positif ! Votre énergie est communicative. Continuez !",
            "Excellent ! J'aime beaucoup votre approche. Développez votre idée !"
        ],
        'curious': [
            "Excellente question ! Voyons cela ensemble. Qu'est-ce qui vous amène à vous interroger là-dessus ?",
            "Très intéressant ! J'aimerais explorer ce sujet avec vous. Que savez-vous déjà ?",
            "Bonne curiosité ! C'est en questionnant qu'on apprend. Dites-moi votre point de vue !"
        ],
        'neutral': [
            "Je vous écoute attentivement. Pouvez-vous me donner plus de détails ?",
            "Intéressant ! J'aimerais mieux comprendre votre perspective. Continuez !",
            "Je vois. Aidez-moi à mieux saisir ce que vous voulez dire."
        ]
    }

    # Détection du sentiment
    if any(pos in input_lower for pos in ['super', 'génial', 'formidable', 'excellent', 'parfait', 'content', 'heureux']):
        sentiment = 'positive'
    elif any(quest in input_lower for quest in ['pourquoi', 'comment', 'qu\'est-ce', '?']):
        sentiment = 'curious'
    else:
        sentiment = 'neutral'

    base_response = random.choice(context_responses[sentiment])

    # Ajout contextuel selon le type de conversation
    health_additions = {
        'general_question': [
            "\n\nAu fait, comment vous portez-vous aujourd'hui ?",
            "\n\nN'oubliez pas de prendre soin de vous ! 💚",
            "\n\nJ'espère que nos échanges vous sont utiles."
        ],
        'free_discussion': [
            "\n\nJ'adore nos conversations ! 😊",
            "\n\nVous avez toujours des sujets passionnants.",
            "\n\nContinuez, vous m'intéressez beaucoup !"
        ],
        'life_advice': [
            "\n\nPrenez votre temps, chaque petit pas compte.",
            "\n\nVous êtes sur la bonne voie ! 🌟",
            "\n\nFaites-vous confiance, vous avez les ressources."
        ],
        'culture_education': [
            "\n\nL'apprentissage est un beau voyage ! 📚",
            "\n\nVotre curiosité est inspirante.",
            "\n\nContinuons à explorer ensemble !"
        ]
    }

    addition = random.choice(health_additions.get(conversation_type, health_additions['general_question']))

    return base_response + addition

# =================================================================
# ADAPTATION DE lex_fulfillment/main.py POUR LE MODE LOCAL
# =================================================================

def lambda_handler_lex_fulfillment(event: Dict[str, Any], context=None) -> Dict[str, Any]:
    """
    Version locale du lambda_handler de lex_fulfillment
    """
    try:
        logger.info(f"Événement Lex reçu: {json.dumps(event, ensure_ascii=False)}")

        intent_name = event.get('intent_name')
        user_input = event.get('user_input', '')
        slots = event.get('slots', {})
        user_id = event.get('user_id', 'anonymous')

        # Routage selon l'intention (VRAIE LOGIQUE LEX)
        if intent_name == 'SignalerDouleur':
            return handle_pain_report_real(user_input, slots)
        elif intent_name == 'GestionMedicaments':
            return handle_medication_management_real(user_input, slots)
        elif intent_name == 'Urgence':
            return handle_emergency_real(user_input, slots)
        elif intent_name == 'ConsulterDonneesVitales':
            return handle_vitals_query_real(user_input, slots)
        elif intent_name == 'DemandeAide':
            return handle_help_request_real(user_input, slots)
        else:
            return handle_lex_fallback_real(user_input, slots)

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler lex: {str(e)}")
        return {
            'success': False,
            'response': "Je rencontre un problème technique. Pouvez-vous reformuler ?",
            'error': str(e)
        }

def handle_pain_report_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de signalement de douleur des Lambda
    """
    # Extraction des informations de douleur
    intensite = slots.get('IntensiteDouleur', {}).get('value', {}).get('interpretedValue')
    localisation = slots.get('LocalisationDouleur', {}).get('value', {}).get('interpretedValue')
    duree = slots.get('DureeDouleur', {}).get('value', {}).get('interpretedValue')

    # Analyse de l'intensité
    if intensite:
        intensite_num = int(intensite)
        if intensite_num >= 8:
            urgence_level = "ÉLEVÉ"
            conseil_urgence = "🚨 **Cette douleur semble intense. Considérez contacter votre médecin rapidement.**"
        elif intensite_num >= 6:
            urgence_level = "MODÉRÉ"
            conseil_urgence = "⚠️ **Douleur significative. Surveillez l'évolution et n'hésitez pas à consulter.**"
        else:
            urgence_level = "FAIBLE"
            conseil_urgence = "💚 **Douleur légère à modérée. Voici des conseils pour vous soulager.**"
    else:
        urgence_level = "NON DÉFINI"
        conseil_urgence = "🔍 **Évaluons ensemble votre douleur.**"

    # Conseils selon la localisation
    conseils_localisation = {
        'dos': [
            "🛏️ Position allongée avec coussin sous les genoux",
            "🔥 Bouillotte chaude sur la zone douloureuse",
            "💊 Anti-douleur habituel si prescrit",
            "🚶‍♀️ Éviter les mouvements brusques"
        ],
        'abdomen': [
            "🤲 Position fœtale sur le côté",
            "🔥 Chaleur douce sur le ventre",
            "💧 Hydratation importante (eau tiède)",
            "😮‍💨 Respiration profonde et lente"
        ],
        'membres': [
            "🦵 Surélévation du membre si possible",
            "🧊 Alternance chaud/froid si toléré",
            "💆‍♀️ Massage très doux",
            "🛌 Repos du membre affecté"
        ]
    }

    conseils = conseils_localisation.get(localisation, [
        "🔥 Application de chaleur douce",
        "💧 Hydratation abondante",
        "💊 Antalgiques selon prescription",
        "🛌 Repos en position confortable"
    ])

    response = f"""🩺 **Signalement de douleur enregistré**

📊 **Évaluation :**
• **Intensité :** {intensite or 'À préciser'}/10
• **Localisation :** {localisation or 'À préciser'}
• **Durée :** {duree or 'À préciser'}
• **Niveau d'urgence :** {urgence_level}

{conseil_urgence}

💡 **Conseils immédiats :**
{chr(10).join(f"• {conseil}" for conseil in conseils)}

⚕️ **Surveillance importante :**
• Notez l'évolution dans les prochaines heures
• Si aggravation : contactez votre médecin
• Si très intense (8-10/10) : urgences si nécessaire

💬 **Besoin de parler ?** Je suis là pour vous accompagner."""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'pain_report',
        'urgency_level': urgence_level,
        'pain_intensity': intensite,
        'pain_location': localisation,
        'medical_advice': True
    }

def handle_medication_management_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de gestion des médicaments des Lambda
    """
    medicament = slots.get('NomMedicament', {}).get('value', {}).get('interpretedValue')
    action = slots.get('ActionMedicament', {}).get('value', {}).get('interpretedValue')

    # Médicaments courants pour la drépanocytose
    medicaments_info = {
        'hydroxyuree': {
            'nom': 'Hydroxyurée (Hydrea)',
            'fonction': 'Traitement de fond - Réduit les crises',
            'conseils': [
                "💊 Prendre à heure fixe chaque jour",
                "🍽️ Peut être pris avec ou sans nourriture",
                "💧 Boire beaucoup d'eau",
                "🩸 Surveillance régulière (prise de sang)",
                "☀️ Protection solaire renforcée"
            ]
        },
        'acide_folique': {
            'nom': 'Acide folique (Spéciafoldine)',
            'fonction': 'Complément - Aide la production de globules rouges',
            'conseils': [
                "🌅 Prendre le matin de préférence",
                "🥗 Complète une alimentation riche en légumes verts",
                "⏰ Important de ne pas oublier",
                "💚 Généralement très bien toléré"
            ]
        }
    }

    if action == 'rappel':
        response = f"""⏰ **Rappel médicaments configuré**

💊 **Votre traitement drépanocytose :**

🔹 **Hydroxyurée** : Traitement principal
• Heure recommandée : Même heure chaque jour
• Avec beaucoup d'eau
• Ne pas oublier !

🔹 **Acide folique** : Complément essentiel  
• Le matin de préférence
• Aide vos globules rouges

🔹 **Antalgiques** : En cas de douleur
• Selon prescription médicale
• Paracétamol en première intention

🔔 **Rappels automatiques :**
Configurez des alarmes sur votre téléphone pour ne jamais oublier !

💡 **Astuce :** Préparez vos piluliers le dimanche pour toute la semaine."""

    elif action == 'information':
        if medicament and medicament.lower() in medicaments_info:
            info = medicaments_info[medicament.lower()]
            response = f"""💊 **Information sur {info['nom']} :**

🎯 **Fonction :** {info['fonction']}

📋 **Conseils d'utilisation :**
{chr(10).join(f"• {conseil}" for conseil in info['conseils'])}

⚠️ **Important :** 
• Respectez scrupuleusement les doses
• Prévenez votre médecin en cas d'effets indésirables
• Ne jamais arrêter sans avis médical

❓ **Questions ?** N'hésitez pas à me demander plus d'informations !"""
        else:
            response = """💊 **Gestion des médicaments - Drépanocytose**

🔹 **Traitements principaux :**
• **Hydroxyurée** : Réduction des crises
• **Acide folique** : Support globules rouges
• **Antalgiques** : Gestion douleur

🔹 **Conseils généraux :**
• Régularité absolue dans les prises
• Hydratation importante
• Surveillance médicale régulière
• Pilulier hebdomadaire recommandé

📞 **En cas de doute :** Contactez votre médecin ou pharmacien

Quel médicament vous intéresse spécifiquement ?"""

    else:
        response = """💊 **Gestion des médicaments**

🎯 **Je peux vous aider avec :**
• 🔔 Rappels de prise
• 📚 Informations sur vos traitements
• 💡 Conseils d'observance
• ⚠️ Signaler des effets indésirables

💬 **Exemples de demandes :**
• "Rappel pour mes médicaments"
• "Information sur l'hydroxyurée"
• "Conseils pour ne pas oublier"

Comment puis-je vous aider avec vos médicaments ? 😊"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'medication_management',
        'medication_focus': True,
        'adherence_support': True
    }

def handle_emergency_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE d'urgence des Lambda
    """
    response = """🚨 **PROCÉDURE D'URGENCE ACTIVÉE**

⚠️ **Cette fonction est réservée aux vraies urgences médicales !**

📞 **NUMÉROS D'URGENCE FRANCE :**
• **15** (SAMU) - Urgences médicales
• **112** - Numéro d'urgence européen  
• **15** - Service d'aide médicale urgente

🏥 **CENTRES D'URGENCE SPÉCIALISÉS :**
• **CHU de votre région** - Service hématologie
• **Centres de référence drépanocytose**

📋 **INFORMATIONS IMPORTANTES À COMMUNIQUER :**
• **Votre identité** - Nom, prénom, âge
• **Maladie** - "Patient drépanocytaire"  
• **Symptômes actuels** - Description précise
• **Localisation** - Votre adresse exacte
• **Traitements en cours** - Liste de vos médicaments

🚨 **SIGNES D'URGENCE ABSOLUE :**
• Douleur intense (8-10/10) non soulagée
• Difficultés respiratoires importantes
• Fièvre élevée (>38.5°C)
• Signes neurologiques (confusion, troubles vision)
• Douleur thoracique intense

⚠️ **Si ce n'était pas une vraie urgence :** Tapez "nouvelle conversation" pour reprendre l'utilisation normale."""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'emergency',
        'urgent': True,
        'medical_emergency': True
    }

def handle_vitals_query_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de consultation des données vitales des Lambda
    """
    # Simulation de données vitales (en prod, viendrait du bracelet IoT)
    import random

    # Génération de données réalistes pour démonstration
    current_time = datetime.now()

    # Données simulées mais réalistes pour un patient drépanocytaire
    vital_data = {
        'heart_rate': random.randint(70, 90),
        'spo2': random.randint(95, 99),
        'temperature': round(36.5 + random.uniform(-0.5, 1.0), 1),
        'activity_level': random.choice(['Faible', 'Modérée', 'Active']),
        'hydration_status': random.choice(['Bonne', 'À surveiller', 'Insuffisante']),
        'last_update': current_time.strftime("%H:%M")
    }

    # Évaluation automatique
    alerts = []
    if vital_data['spo2'] < 95:
        alerts.append("⚠️ Saturation en oxygène faible - Consultez rapidement")
    if vital_data['temperature'] > 38.0:
        alerts.append("🌡️ Température élevée - Surveillance recommandée")
    if vital_data['heart_rate'] > 100:
        alerts.append("💓 Fréquence cardiaque élevée - Repos conseillé")

    alert_section = ""
    if alerts:
        alert_section = f"\n🚨 **ALERTES :**\n{chr(10).join(f'• {alert}' for alert in alerts)}\n"

    response = f"""📊 **Vos données vitales actuelles**

🔄 **Dernière synchronisation :** {vital_data['last_update']}

📈 **Mesures en temps réel :**
• **Fréquence cardiaque :** {vital_data['heart_rate']} bpm
• **Saturation O2 :** {vital_data['spo2']}%  
• **Température :** {vital_data['temperature']}°C
• **Niveau d'activité :** {vital_data['activity_level']}
• **État d'hydratation :** {vital_data['hydration_status']}

{alert_section}💡 **Recommandations personnalisées :**
• Continuez à bien vous hydrater (2-3L/jour)
• Maintenez une activité physique adaptée
• Surveillez votre température régulièrement
• Reposez-vous si nécessaire

📱 **Bracelet connecté :** Synchronisation automatique active

❓ **Questions sur vos données ?** Je peux vous expliquer chaque mesure !"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'vitals_query',
        'health_monitoring': True,
        'vital_signs': vital_data
    }

def handle_help_request_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de demande d'aide des Lambda
    """
    response = """🆘 **Guide d'utilisation Kidjamo Assistant**

🎯 **Mes principales fonctions :**

🩺 **Santé & Drépanocytose :**
• "J'ai mal au dos intensité 7" → Signaler douleur
• "Mes données vitales" → Consultation bracelet IoT
• "Information hydroxyurée" → Aide médicaments
• "Qu'est-ce que la drépanocytose ?" → Questions médicales

💬 **Conversation & Support :**
• "Bonjour comment ça va ?" → Discussion générale
• "Je m'ennuie" → Compagnie et divertissement  
• "Conseils pour dormir" → Aide vie quotidienne
• "Raconte-moi une blague" → Détente

🚨 **Urgences :**
• "Urgence" → Procédure d'urgence médicale
• "Aide urgente" → Numéros et conseils

📚 **Éducation & Culture :**
• "Parle-moi de science" → Découvertes récentes
• "Histoire de France" → Culture générale
• "Apprendre l'anglais" → Conseils langues

💡 **Conseils d'utilisation :**
• Phrases simples et directes
• Mots-clés précis (douleur, médicament, etc.)
• N'hésitez pas à reformuler
• Je comprends le langage naturel !

🤖 **À propos de moi :**
Je suis votre assistant santé IA, spécialisé dans la drépanocytose mais capable de discuter de tout ! Disponible 24h/24 pour vous accompagner. 😊

❓ **Besoin d'aide spécifique ?** Dites-moi simplement ce que vous cherchez !"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'help_request',
        'helpful': True,
        'guide_provided': True
    }

def handle_lex_fallback_real(user_input: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    VRAIE LOGIQUE de fallback Lex des Lambda
    """
    response = f"""🤔 **Je n'ai pas bien compris votre demande**

**Vous avez dit :** "{user_input}"

💡 **Peut-être vouliez-vous :**
• 🩺 **Signaler une douleur ?** → "J'ai mal..." 
• 💊 **Parler de médicaments ?** → "Mes médicaments..."
• 📊 **Voir vos données ?** → "Mes vitales..."
• 📚 **Poser une question médicale ?** → "Qu'est-ce que..."
• 💬 **Simplement discuter ?** → "Bonjour", "Comment ça va..."

🎯 **Pour de meilleurs résultats :**
• Utilisez des phrases simples et directes
• Mentionnez les mots-clés importants  
• N'hésitez pas à reformuler différemment

🆘 **Aide rapide :**
Tapez "aide" pour le guide complet d'utilisation.

Comment puis-je vous aider aujourd'hui ? 😊"""

    return {
        'success': True,
        'response': response,
        'conversation_type': 'lex_fallback',
        'needs_clarification': True
    }
