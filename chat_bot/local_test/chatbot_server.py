"""
Serveur Flask pour le chatbot Kidjamo Health Assistant
Version locale avec IA Gemini Flash intégrée (0GB vs 12GB Ollama)
"""

from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
import json
import logging
import os
import requests
import time
import random
from datetime import datetime
from typing import Dict, Any

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiFlashEngine:
    """Moteur Gemini Flash intégré au serveur Flask avec résilience améliorée"""

    def __init__(self):
        # Votre clé API Gemini Flash
        self.api_key = "AIzaSyCM7YXGLREXa1w7r9RwqOHWn4Ywd2ZLHRE"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        self.conversation_contexts = {}  # Stockage par session
        self.max_retries = 3
        self.base_delay = 2

    def process_message_with_ai(self, user_message: str, context: Dict) -> Dict:
        """Traite le message avec Gemini Flash - version améliorée avec retry"""

        session_id = context.get('session_id', 'default')

        # Tentative avec retry intelligent
        for attempt in range(self.max_retries):
            try:
                # Construire le prompt médical spécialisé
                system_prompt = self._build_medical_prompt(user_message, session_id)

                payload = {
                    "contents": [{
                        "parts": [{"text": system_prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 600,
                        "topP": 0.8
                    }
                }

                # Timeout progressif (5s, 10s, 15s)
                timeout = 5 + (attempt * 5)
                response = requests.post(self.url, json=payload, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    ai_response = data["candidates"][0]["content"]["parts"][0]["text"]

                    # Sauvegarder le contexte de conversation
                    if session_id not in self.conversation_contexts:
                        self.conversation_contexts[session_id] = []

                    self.conversation_contexts[session_id].append({
                        "user": user_message,
                        "bot": ai_response,
                        "timestamp": datetime.now().isoformat()
                    })

                    # Limiter l'historique à 10 échanges
                    if len(self.conversation_contexts[session_id]) > 10:
                        self.conversation_contexts[session_id] = self.conversation_contexts[session_id][-10:]

                    # Convertir en HTML pour l'interface web
                    html_response = self._format_response_as_html(ai_response, user_message)

                    return {
                        "response": html_response,
                        "conversation_type": self._detect_conversation_type(user_message),
                        "source": f"gemini-flash-attempt-{attempt+1}",
                        "model_used": "gemini-1.5-flash",
                        "raw_response": ai_response,
                        "success": True
                    }

                elif response.status_code == 503:
                    logger.warning(f"Gemini surchargé (503), tentative {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        # Backoff exponentiel avec jitter
                        delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"⏳ Attente {delay:.1f}s avant nouvelle tentative...")
                        time.sleep(delay)
                        continue

                elif response.status_code == 429:
                    logger.warning(f"Rate limit atteint (429), tentative {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (3 ** attempt)
                        logger.info(f"⏳ Rate limit - Attente {delay}s...")
                        time.sleep(delay)
                        continue

                else:
                    logger.error(f"Erreur API Gemini: {response.status_code} - {response.text}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.base_delay)
                        continue

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout Gemini (tentative {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay)
                    continue
            except Exception as e:
                logger.error(f"Erreur Gemini Flash (tentative {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay)
                    continue

        # Si toutes les tentatives échouent, utiliser le fallback intelligent
        logger.error("🚨 Gemini Flash indisponible - Basculement vers fallback intelligent")
        return self._intelligent_fallback_response(user_message, session_id)

    def _intelligent_fallback_response(self, user_message: str, session_id: str) -> Dict:
        """Fallback intelligent basé sur l'analyse du message utilisateur"""

        message_lower = user_message.lower()

        # Analyse des mots-clés pour une réponse contextualisée
        if any(word in message_lower for word in ["mal", "douleur", "souffre", "crise", "intense"]):
            html_response = """
            <div class="response-section pain-management">
                <h3><i class="fas fa-exclamation-triangle"></i> Gestion de la douleur</h3>
                <p><strong>⚠️ L'IA est temporairement indisponible, mais voici les conseils essentiels :</strong></p>
                
                <h4><i class="fas fa-thermometer-half"></i> Évaluation rapide :</h4>
                <ul class="urgent-list">
                    <li><strong>Intensité :</strong> Évaluez votre douleur de 1 à 10</li>
                    <li><strong>Si >7/10 :</strong> Contactez immédiatement les urgences</li>
                    <li><strong>Localisation :</strong> Notez où vous avez mal</li>
                </ul>
                
                <h4><i class="fas fa-first-aid"></i> Actions immédiates :</h4>
                <ul class="help-list">
                    <li>💧 <strong>Hydratation :</strong> Buvez beaucoup d'eau</li>
                    <li>🛌 <strong>Repos :</strong> Allongez-vous au calme</li>
                    <li>💊 <strong>Médicaments :</strong> Prenez vos antalgiques prescrits</li>
                    <li>🔥 <strong>Chaleur :</strong> Bouillotte ou bain chaud</li>
                </ul>
                
                <div class="emergency-contact">
                    <p><strong>☎️ URGENCES CAMEROUN :</strong></p>
                    <p>📞 <strong>1510</strong> - Numéro d'urgence national</p>
                    <p>🏥 CHU Yaoundé - Service urgences</p>
                </div>
            </div>
            """
            conversation_type = "pain_management_offline"

        elif any(word in message_lower for word in ["médicament", "traitement", "siklos", "hydroxyurée", "pilule"]):
            html_response = """
            <div class="response-section medication-section">
                <h3><i class="fas fa-pills"></i> Rappels médicaments</h3>
                <p><strong>💊 L'IA est temporairement indisponible. Voici les rappels essentiels :</strong></p>
                
                <h4><i class="fas fa-list-check"></i> Médicaments principaux drépanocytose :</h4>
                <ul class="info-list">
                    <li><strong>Hydroxyurée (Siklos) :</strong> Traitement de fond quotidien</li>
                    <li><strong>Acide folique :</strong> 5mg par jour</li>
                    <li><strong>Paracétamol :</strong> Maximum 3g/jour</li>
                    <li><strong>Antibiotiques préventifs :</strong> Si prescrits</li>
                </ul>
                
                <h4><i class="fas fa-clock"></i> Conseils de prise :</h4>
                <ul class="help-list">
                    <li>⏰ <strong>Horaires fixes :</strong> Même heure chaque jour</li>
                    <li>💧 <strong>Avec de l'eau :</strong> Grand verre</li>
                    <li>📝 <strong>Carnet :</strong> Notez les prises</li>
                    <li>⚠️ <strong>Jamais d'aspirine</strong> en cas de drépanocytose</li>
                </ul>
            </div>
            """
            conversation_type = "medication_offline"

        elif any(word in message_lower for word in ["urgent", "aide", "respir", "poitrine", "grave"]):
            html_response = """
            <div class="emergency-alert">
                <h3><i class="fas fa-ambulance"></i> PROTOCOLE D'URGENCE</h3>
                <p><strong>🚨 URGENCE DÉTECTÉE - L'IA est indisponible mais voici le protocole :</strong></p>
                
                <h4><i class="fas fa-phone-alt"></i> APPELEZ IMMÉDIATEMENT :</h4>
                <ul class="urgent-list">
                    <li><span class="emergency-number">1510</span> <strong>Urgences nationales Cameroun</strong></li>
                    <li><strong>CHU Yaoundé :</strong> Service d'urgences</li>
                    <li><strong>Hôpital Général Douala :</strong> Urgences médicales</li>
                </ul>
                
                <h4><i class="fas fa-exclamation-triangle"></i> Signes d'alarme drépanocytose :</h4>
                <ul class="urgent-list">
                    <li><strong>Douleur thoracique</strong> → Syndrome thoracique aigu</li>
                    <li><strong>Difficultés respiratoires</strong> → Urgence vitale</li>
                    <li><strong>Fièvre >38.5°C</strong> → Risque infectieux</li>
                    <li><strong>Douleur abdominale intense</strong> → Séquestration</li>
                </ul>
                
                <p><strong>⚠️ Mentionnez "PATIENT DRÉPANOCYTAIRE" aux secours</strong></p>
            </div>
            """
            conversation_type = "emergency_offline"

        elif any(word in message_lower for word in ["drépanocytose", "maladie", "qu'est-ce", "définition"]):
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-dna"></i> Drépanocytose - Informations essentielles</h3>
                <p><strong>📚 L'IA est temporairement indisponible. Voici les informations de base :</strong></p>
                
                <h4><i class="fas fa-microscope"></i> Qu'est-ce que la drépanocytose ?</h4>
                <ul class="info-list">
                    <li><strong>Maladie génétique :</strong> Affecte l'hémoglobine</li>
                    <li><strong>Globules rouges :</strong> Forme de faucille</li>
                    <li><strong>Circulation :</strong> Obstructions vasculaires</li>
                    <li><strong>Héréditaire :</strong> Transmise par les parents</li>
                </ul>
                
                <h4><i class="fas fa-symptoms"></i> Symptômes principaux :</h4>
                <ul class="help-list">
                    <li>🩸 <strong>Anémie chronique :</strong> Fatigue constante</li>
                    <li>⚡ <strong>Crises douloureuses :</strong> Episodes aigus</li>
                    <li>🦠 <strong>Infections fréquentes :</strong> Immunité réduite</li>
                    <li>📈 <strong>Complications organiques :</strong> Cœur, poumons, reins</li>
                </ul>
            </div>
            """
            conversation_type = "education_offline"

        else:
            # Réponse générale de bienvenue
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-robot"></i> Assistant Kidjamo - Mode Dégradé</h3>
                <p><strong>🔧 L'IA Gemini est temporairement surchargée. Mode fallback activé.</strong></p>
                
                <h4><i class="fas fa-life-ring"></i> Je peux vous aider avec :</h4>
                <ul class="help-list">
                    <li>🩺 <strong>"J'ai mal"</strong> - Gestion de la douleur</li>
                    <li>💊 <strong>"Médicaments"</strong> - Rappels traitements</li>
                    <li>🚨 <strong>"Urgent"</strong> - Protocoles d'urgence</li>
                    <li>📚 <strong>"Drépanocytose"</strong> - Informations médicales</li>
                </ul>
                
                <div class="status-info">
                    <p><i class="fas fa-clock"></i> <strong>Statut :</strong> Fallback intelligent activé</p>
                    <p><i class="fas fa-sync-alt"></i> <strong>IA :</strong> Reconnexion automatique en cours</p>
                </div>
                
                <p>💬 <strong>Posez votre question, je ferai de mon mieux pour vous aider !</strong></p>
            </div>
            """
            conversation_type = "general_offline"

        return {
            "response": html_response,
            "conversation_type": conversation_type,
            "source": "fallback-intelligent-enhanced",
            "model_used": "pattern-matching-fallback",
            "success": True,
            "gemini_status": "overloaded_503"
        }

    def _build_medical_prompt(self, user_message: str, session_id: str) -> str:
        """Construit un prompt médical contextualisé"""

        # Récupérer l'historique récent
        recent_context = ""
        if session_id in self.conversation_contexts:
            recent = self.conversation_contexts[session_id][-2:]  # 2 derniers échanges
            if recent:
                recent_context = "\n\nCONTEXTE CONVERSATION RÉCENTE:\n"
                for ctx in recent:
                    recent_context += f"Patient: {ctx['user']}\nAssistant: {ctx['bot'][:100]}...\n"

        base_prompt = f"""Tu es Kidjamo Assistant, un assistant médical spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun.

PERSONNALITÉ:
- Empathique, rassurant mais prudent médicalement
- Ton chaleureux et professionnel
- Langage simple et accessible
- Utilise des émojis pour structurer

RÈGLES MÉDICALES CRITIQUES:
- Tu ne remplaces JAMAIS un médecin
- URGENCE si: douleur >7/10, difficultés respiratoires, fièvre >38.5°C
- En urgence: recommande TOUJOURS d'appeler les secours camerounais
- Tu restes dans le domaine drépanocytose

NUMÉROS D'URGENCE CAMEROUN:
- 1510 (Numéro d'urgence national camerounais)
- Hôpital Central de Yaoundé - Service d'urgences
- Hôpital Général de Douala - Urgences médicales
- Centre Hospitalier Universitaire (CHU) - Service hématologie

CENTRES SPÉCIALISÉS CAMEROUN:
- CHU de Yaoundé - Centre de référence drépanocytose
- Hôpital Laquintinie Douala - Service hématologie
- Centre Pasteur Cameroun - Suivi drépanocytose

DOMAINES D'EXPERTISE:
🩺 Gestion douleur et crises drépanocytose
💊 Médicaments (Hydroxyurée, antalgiques)
🚨 Protocoles d'urgence médicale camerounaise
📚 Éducation thérapeutique
🤗 Soutien psychologique{recent_context}

QUESTION ACTUELLE: {user_message}

Réponds de manière empathique et médicalement appropriée. Si c'est une urgence (comme "j'ai mal à la poitrine"), priorise ABSOLUMENT la sécurité et recommande d'appeler les services d'urgence camerounais:"""

        return base_prompt

    def _detect_conversation_type(self, message: str) -> str:
        """Détecte le type de conversation"""
        message_lower = message.lower()

        urgency_keywords = ["mal", "poitrine", "respir", "aide", "urgent", "grave", "intense"]
        pain_keywords = ["douleur", "mal", "/10", "souffre", "crise"]
        medication_keywords = ["médicament", "siklos", "traitement", "pilule"]

        if any(keyword in message_lower for keyword in urgency_keywords):
            return "emergency"
        elif any(keyword in message_lower for keyword in pain_keywords):
            return "pain_management"
        elif any(keyword in message_lower for keyword in medication_keywords):
            return "medication"
        else:
            return "general"

    def _format_response_as_html(self, ai_response: str, user_message: str) -> str:
        """Formate la réponse IA en HTML pour l'interface web"""

        # Détecter si c'est une urgence pour appliquer le style approprié
        is_emergency = any(word in user_message.lower() for word in ["mal", "poitrine", "respir", "aide", "urgent"])

        if is_emergency:
            css_class = "response-section emergency-alert"
            icon = "fas fa-exclamation-triangle"
        else:
            css_class = "response-section medical-info"
            icon = "fas fa-user-md"

        # Convertir le markdown basique en HTML
        formatted_response = ai_response.replace('\n\n', '</p><p>')
        formatted_response = formatted_response.replace('**', '<strong>').replace('**', '</strong>')
        formatted_response = formatted_response.replace('- ', '<li>').replace('\n', '</li>')

        html_response = f"""
        <div class="{css_class}">
            <h3><i class="{icon}"></i> Kidjamo Assistant</h3>
            <p>{formatted_response}</p>
        </div>
        """

        return html_response

    def _fallback_response(self, user_message: str) -> Dict:
        """Réponse de secours si Gemini Flash échoue"""

        message_lower = user_message.lower()

        if any(word in message_lower for word in ["mal", "poitrine", "respir", "aide", "urgent"]):
            html_response = """
            <div class="response-section emergency-alert">
                <h3><i class="fas fa-ambulance"></i> URGENCE DÉTECTÉE</h3>
                <p><strong>Si vous ressentez une douleur thoracique ou des difficultés respiratoires :</strong></p>
                <ul class="urgent-list">
                    <li><strong>APPELEZ IMMÉDIATEMENT les secours camerounais</strong></li>
                    <li><span class="emergency-number">1510</span> Numéro d'urgence national Cameroun</li>
                    <li><strong>Hôpital Central Yaoundé</strong> - Service d'urgences</li>
                    <li><strong>Hôpital Général Douala</strong> - Urgences médicales</li>
                </ul>
                <p>⚠️ <strong>Mentionnez "patient drépanocytaire" aux secours</strong></p>
                <p>En attendant : restez calme, position confortable, préparez vos documents médicaux</p>
            </div>
            """
        else:
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-user-md"></i> Assistant Kidjamo</h3>
                <p>Je suis spécialisé dans l'accompagnement drépanocytose au Cameroun :</p>
                <ul class="help-list">
                    <li>🩺 Gestion douleur - "J'ai mal"</li>
                    <li>💊 Médicaments - "Rappel traitement"</li>
                    <li>🚨 Urgences - "Aide urgent"</li>
                    <li>📚 Questions - "Qu'est-ce que..."</li>
                </ul>
                <p>Comment puis-je vous aider ?</p>
            </div>
            """

        return {
            "response": html_response,
            "conversation_type": "fallback",
            "source": "fallback-intelligent",
            "success": True
        }

# Initialiser le moteur Gemini Flash
gemini_engine = GeminiFlashEngine()

def process_message_with_ai(user_message: str, context: Dict) -> Dict:
    """Fonction de compatibilité - remplace l'ancien hybrid_logic"""
    return gemini_engine.process_message_with_ai(user_message, context)

# Initialisation de l'application Flask
app = Flask(__name__)
CORS(app, origins=["*"])

# Configuration globale
CONFIG = {
    'version': '2.0.0',
    'service_name': 'Kidjamo Health Assistant',
    'mode': 'local_development',
    'voice_enabled': True,
    'debug': True
}

@app.route('/')
def index():
    """Interface web du chatbot Kidjamo"""
    try:
        # Chemin vers le fichier HTML de l'interface
        html_file_path = os.path.join(os.path.dirname(__file__), '..', 'web_interface', 'interface_fixed.html')

        if os.path.exists(html_file_path):
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content
        else:
            # Interface de fallback si le fichier HTML n'est pas trouvé
            return render_template_string(FALLBACK_HTML)
    except Exception as e:
        logger.error(f"Erreur lors du chargement de l'interface: {e}")
        return render_template_string(FALLBACK_HTML)

# Interface HTML de secours
FALLBACK_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kidjamo Health Assistant</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 600px;
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            text-align: center;
        }
        .header {
            margin-bottom: 30px;
        }
        .logo {
            font-size: 3rem;
            color: #667eea;
            margin-bottom: 15px;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2rem;
        }
        .subtitle {
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 30px;
        }
        .status {
            background: #e8f5e8;
            border: 1px solid #4caf50;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 30px;
        }
        .status-text {
            color: #2e7d32;
            font-weight: 600;
        }
        .instructions {
            background: #f5f5f5;
            border-radius: 8px;
            padding: 20px;
            text-align: left;
        }
        .instructions h3 {
            color: #333;
            margin-top: 0;
        }
        .instructions ol {
            color: #555;
            line-height: 1.6;
        }
        .links {
            margin-top: 20px;
            display: flex;
            gap: 15px;
            justify-content: center;
        }
        .link-btn {
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
            transition: background 0.3s;
        }
        .link-btn:hover {
            background: #5a67d8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">
                <i class="fas fa-user-md"></i>
            </div>
            <h1>Kidjamo Health Assistant</h1>
            <p class="subtitle">Assistant santé intelligent spécialisé dans la drépanocytose</p>
        </div>
        
        <div class="status">
            <div class="status-text">
                <i class="fas fa-check-circle"></i>
                Serveur démarré avec succès !
            </div>
        </div>
        
        <div class="instructions">
            <h3>Pour utiliser l'interface principale :</h3>
            <ol>
                <li>Le fichier HTML principal est maintenant servi automatiquement</li>
                <li>Rechargez cette page pour voir l'interface complète</li>
                <li>Ou accédez directement à l'API via /chat</li>
            </ol>
        </div>
        
        <div class="links">
            <a href="/" class="link-btn">
                <i class="fas fa-home"></i> Interface
            </a>
            <a href="/health" class="link-btn">
                <i class="fas fa-heart"></i> Santé
            </a>
        </div>
    </div>
</body>
</html>
"""

# Réponses simulées pour le chatbot
RESPONSES = {
    "bonjour": """
        <div class="response-section medical-info">
            <h3><i class="fas fa-user-md"></i> Bonjour ! Je suis votre assistant santé Kidjamo</h3>
            <p>Je suis spécialisé dans l'accompagnement des patients atteints de drépanocytose. Je peux vous aider avec :</p>
            <ul class="help-list">
                <li><strong>Gestion de la douleur</strong> - Évaluation et conseils personnalisés</li>
                <li><strong>Suivi des médicaments</strong> - Rappels et interactions</li>
                <li><strong>Données vitales</strong> - Analyse de vos mesures IoT</li>
                <li><strong>Urgences médicales</strong> - Protocoles et contacts d'urgence</li>
                <li><strong>Éducation thérapeutique</strong> - Informations sur votre maladie</li>
            </ul>
            <p>Comment puis-je vous aider aujourd'hui ?</p>
        </div>
    """,
    "mal": """
        <div class="response-section pain-management">
            <h3><i class="fas fa-exclamation-triangle"></i> Évaluation de la douleur</h3>
            <p>Je comprends que vous ressentez de la douleur. C'est important de bien l'évaluer pour vous aider efficacement.</p>
            <h4><i class="fas fa-clipboard-check"></i> Évaluation rapide :</h4>
            <ul class="urgent-list">
                <li><strong>Localisation</strong> - Où ressentez-vous la douleur exactement ?</li>
                <li><strong>Intensité</strong> - Sur une échelle de 1 à 10, comment évaluez-vous la douleur ?</li>
                <li><strong>Durée</strong> - Depuis combien de temps dure cette douleur ?</li>
                <li><strong>Caractère</strong> - Est-ce une douleur aiguë, sourde, pulsatile ?</li>
            </ul>
            <h4><i class="fas fa-pills"></i> Actions immédiates :</h4>
            <ul class="help-list">
                <li><strong>Hydratation</strong> - Buvez beaucoup d'eau</li>
                <li><strong>Repos</strong> - Mettez-vous au calme</li>
                <li><strong>Médicaments</strong> - Prenez vos antalgiques si prescrits</li>
                <li><strong>Chaleur</strong> - Appliquez une source de chaleur douce si possible</li>
            </ul>
            <p><strong> Si la douleur est intense (>7/10) ou s'aggrave rapidement, contactez immédiatement les urgences.</strong></p>
        </div>
    """,
    "médicaments": """
        <div class="response-section medication-section">
            <h3><i class="fas fa-pills"></i> Gestion des médicaments</h3>
            <p>La gestion rigoureuse des médicaments est cruciale dans le traitement de la drépanocytose.</p>
            <h4><i class="fas fa-list-check"></i> Médicaments principaux :</h4>
            <ul class="info-list">
                <li><strong>Hydroxyurée</strong> - Traitement de fond pour réduire les crises</li>
                <li><strong>Antalgiques</strong> - Paracétamol, anti-inflammatoires pour la douleur</li>
                <li><strong>Acide folique</strong> - Supplément vitaminique essentiel</li>
                <li><strong>Antibiotiques préventifs</strong> - Protection contre les infections</li>
            </ul>
            <h4><i class="fas fa-clock"></i> Conseils de prise :</h4>
            <ul class="help-list">
                <li><strong>Régularité</strong> - Prenez vos médicaments aux heures fixes</li>
                <li><strong>Hydratation</strong> - Avec un grand verre d'eau</li>
                <li><strong>Suivi</strong> - Notez les prises dans un carnet</li>
                <li><strong>Interactions</strong> - Vérifiez avec votre médecin avant tout nouveau médicament</li>
            </ul>
        </div>
    """,
    "drépanocytose": """
        <div class="response-section medical-info">
            <h3><i class="fas fa-dna"></i> Qu'est-ce que la drépanocytose ?</h3>
            <p>La drépanocytose est une maladie génétique qui affecte l'hémoglobine, la protéine des globules rouges qui transporte l'oxygène.</p>
            <h4><i class="fas fa-microscope"></i> Mécanisme :</h4>
            <ul class="info-list">
                <li><strong>Hémoglobine anormale</strong> - Les globules rouges prennent une forme de faucille</li>
                <li><strong>Obstruction vasculaire</strong> - Blocage de la circulation sanguine</li>
                <li><strong>Hémolyse</strong> - Destruction prématurée des globules rouges</li>
                <li><strong>Anémie chronique</strong> - Manque d'oxygène dans les tissus</li>
            </ul>
            <h4><i class="fas fa-symptoms"></i> Symptômes principaux :</h4>
            <ul class="urgent-list">
                <li><strong>Crises douloureuses</strong> - Episodes de douleur intense</li>
                <li><strong>Fatigue</strong> - Due à l'anémie chronique</li>
                <li><strong>Infections fréquentes</strong> - Système immunitaire affaibli</li>
                <li><strong>Retard de croissance</strong> - Chez les enfants</li>
            </ul>
        </div>
    """,
    "urgence": """
        <div class="emergency-alert">
            <h3><i class="fas fa-ambulance"></i> URGENCE MÉDICALE</h3>
            <p><strong> Contactez immédiatement les secours si vous présentez :</strong></p>
            <ul class="urgent-list">
                <li><strong>Douleur thoracique intense</strong> - Possible syndrome thoracique aigu</li>
                <li><strong>Difficultés respiratoires</strong> - Essoufflement, respiration rapide</li>
                <li><strong>Fièvre élevée (>38.5°C)</strong> - Risque d'infection grave</li>
                <li><strong>Douleur abdominale sévère</strong> - Possible séquestration splénique</li>
                <li><strong>Priapisme</strong> - Érection douloureuse prolongée</li>
                <li><strong>AVC</strong> - Troubles de la parole, paralysie, confusion</li>
            </ul>
            <h4><i class="fas fa-phone"></i> Numéros d'urgence :</h4>
            <ul class="help-list">
                <li><span class="emergency-number">115</span> <strong>KIDJAMO</strong> - Urgences médicales</li>
                <li><span class="emergency-number">112</span> <strong>Numéro européen</strong> - Urgences</li>
                <li><strong>Centre de référence drépanocytose</strong> - Contactez votre hôpital de suivi</li>
            </ul>
        </div>
    """
}

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal pour le chat avec IA générative intégrée"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        is_voice = data.get('is_voice', False)

        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Message vide',
                'session_id': session_id
            }), 400

        logger.info(f"💬 Message reçu (Session {session_id}): {user_message}")

        # Traitement avec IA générative
        response_data = process_message_with_ai(user_message, {'session_id': session_id})

        # Enrichir la réponse avec des métadonnées
        response_data.update({
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'is_voice_response': is_voice,
            'success': True
        })

        logger.info(f"🤖 Réponse générée par {response_data.get('source', 'unknown')} "
                   f"(Type: {response_data.get('conversation_type', 'general')})")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"❌ Erreur dans l'endpoint chat: {e}")
        return jsonify({
            'success': False,
            'response': "Je rencontre des difficultés techniques. Si c'est urgent, contactez le 115.",
            'error': str(e),
            'session_id': session_id,
            'source': 'error_fallback'
        }), 500

@app.route('/session/<session_id>/history', methods=['GET'])
def get_session_history(session_id: str):
    """Récupère l'historique d'une session"""
    try:
        from session_manager import session_manager
        session = session_manager.get_session(session_id)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'history': session['conversation_history'][-10:],  # Derniers 10 messages
            'context': session['context']
        })
    except Exception as e:
        logger.error(f"Erreur récupération historique: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/session/<session_id>/reset', methods=['POST'])
def reset_session_context(session_id: str):
    """Remet à zéro le contexte de crise d'une session"""
    try:
        from session_manager import session_manager
        session_manager.reset_crisis_context(session_id)

        return jsonify({
            'success': True,
            'message': 'Contexte de session réinitialisé'
        })
    except Exception as e:
        logger.error(f"Erreur reset session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Vérification de l'état du système avec info IA"""
    from ai_engine import ai_engine

    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': CONFIG['version'],
        'ai_status': {
            'ollama_available': ai_engine.ollama_available,
            'local_model': ai_engine.local_model,
            'fallback_enabled': ai_engine.fallback_enabled,
            'openai_configured': bool(ai_engine.openai_api_key),
            'claude_configured': bool(ai_engine.claude_api_key)
        }
    }

    return jsonify(health_status)

@app.route('/voice', methods=['POST'])
def voice_endpoint():
    """Endpoint pour le traitement vocal (futur)"""
    return jsonify({
        'success': False,
        'message': 'Fonctionnalité vocale en développement',
        'response': """<div class="response-section medical-info">
            <h3><i class="fas fa-microphone"></i> Fonction vocale</h3>
            <p>La reconnaissance vocale est actuellement en développement.</p>
            <p>Pour l'instant, vous pouvez utiliser l'interface texte pour poser vos questions.</p>
        </div>""",
        'conversation_type': 'info'
    })

if __name__ == '__main__':
    logger.info(f"Démarrage du serveur {CONFIG['service_name']} v{CONFIG['version']}")
    logger.info(f"Mode: {CONFIG['mode']}")
    logger.info("Interface disponible sur http://localhost:5000")

    app.run(
        debug=CONFIG['debug'],
        host='0.0.0.0',
        port=5000,
        use_reloader=False  # Évite les problèmes avec les imports
    )
