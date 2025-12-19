"""
Serveur Flask simplifié pour le chatbot Kidjamo Health Assistant
Version qui fonctionne sans dépendances externes
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation de l'application Flask
app = Flask(__name__)
CORS(app)

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
            <p><strong>⚠️ Si la douleur est intense (>7/10) ou s'aggrave rapidement, contactez immédiatement les urgences.</strong></p>
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
            <h4><i class="fas fa-stethoscope"></i> Symptômes principaux :</h4>
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
            <p><strong>🚨 Contactez immédiatement les secours si vous présentez :</strong></p>
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
                <li><span class="emergency-number">15</span> <strong>SAMU</strong> - Urgences médicales</li>
                <li><span class="emergency-number">112</span> <strong>Numéro européen</strong> - Urgences</li>
                <li><strong>Centre de référence drépanocytose</strong> - Contactez votre hôpital de suivi</li>
            </ul>
        </div>
    """
}

@app.route('/chat', methods=['POST'])
def chat():
    """Route principale pour les conversations avec le chatbot"""
    try:
        # Récupérer les données de la requête
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Aucune donnée reçue'}), 400

        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        is_voice = data.get('is_voice', False)

        logger.info(f"💬 Message reçu: '{message}' (Session: {session_id})")

        if not message:
            return jsonify({'success': False, 'error': 'Message vide'}), 400

        # Logique simple de détection de mots-clés
        response = "Je vous écoute. Pouvez-vous me donner plus de détails sur votre situation ?"
        conversation_type = "general"

        message_lower = message.lower()

        # Détection des intentions basée sur les mots-clés
        if any(word in message_lower for word in ['bonjour', 'salut', 'hello', 'bonsoir', 'qui es-tu', 'présentation']):
            response = RESPONSES["bonjour"]
            conversation_type = "greeting"
        elif any(word in message_lower for word in ['mal', 'douleur', 'souffre', 'fait mal', 'j\'ai mal']):
            response = RESPONSES["mal"]
            conversation_type = "pain_management"
        elif any(word in message_lower for word in ['médicament', 'traitement', 'pilule', 'médoc', 'médicaments']):
            response = RESPONSES["médicaments"]
            conversation_type = "medication"
        elif any(word in message_lower for word in ['drépanocytose', 'maladie', 'qu\'est-ce que', 'expliquez', 'info médicale']):
            response = RESPONSES["drépanocytose"]
            conversation_type = "medical_info"
        elif any(word in message_lower for word in ['urgence', 'grave', 'hôpital', 'secours', 'aide immédiatement']):
            response = RESPONSES["urgence"]
            conversation_type = "emergency"
        elif any(word in message_lower for word in ['données vitales', 'bracelet', 'mesures', 'vitales']):
            response = """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-chart-line"></i> Données vitales et bracelet IoT</h3>
                    <p>Le suivi de vos données vitales est essentiel pour la gestion de la drépanocytose.</p>
                    <h4><i class="fas fa-heartbeat"></i> Paramètres surveillés :</h4>
                    <ul class="info-list">
                        <li><strong>Fréquence cardiaque</strong> - Détection des anomalies</li>
                        <li><strong>Saturation en oxygène</strong> - Surveillance continue</li>
                        <li><strong>Température corporelle</strong> - Alerte fièvre</li>
                        <li><strong>Activité physique</strong> - Niveau d'effort</li>
                    </ul>
                    <p>🔗 <strong>Connexion du bracelet en cours de développement...</strong></p>
                </div>
            """
            conversation_type = "vitals"
        elif any(word in message_lower for word in ['comment ça marche', 'aide', 'help']):
            response = """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-question-circle"></i> Comment utiliser Kidjamo Health Assistant</h3>
                    <p>Je suis votre assistant santé intelligent spécialisé dans la drépanocytose. Voici comment m'utiliser :</p>
                    <h4><i class="fas fa-list"></i> Fonctionnalités principales :</h4>
                    <ul class="help-list">
                        <li><strong>Questions sur la douleur</strong> - Dites "j'ai mal" pour une évaluation</li>
                        <li><strong>Informations médicaments</strong> - Demandez "mes médicaments"</li>
                        <li><strong>Éducation santé</strong> - Posez des questions sur la drépanocytose</li>
                        <li><strong>Urgences</strong> - Utilisez le bouton rouge ou dites "urgence"</li>
                        <li><strong>Données vitales</strong> - Consultez vos mesures du bracelet IoT</li>
                    </ul>
                    <h4><i class="fas fa-lightbulb"></i> Conseils d'utilisation :</h4>
                    <ul class="info-list">
                        <li>Soyez précis dans vos questions</li>
                        <li>Utilisez la reconnaissance vocale si nécessaire</li>
                        <li>Cliquez sur les questions suggérées</li>
                        <li>N'hésitez pas à poser des questions de suivi</li>
                    </ul>
                </div>
            """
            conversation_type = "help"

        # Log de la réponse
        logger.info(f"✅ Réponse générée pour type: {conversation_type}")

        return jsonify({
            'success': True,
            'response': response,
            'conversation_type': conversation_type,
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"❌ Erreur dans /chat: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur',
            'details': str(e)
        }), 500

@app.route('/health')
def health():
    """Route de vérification de l'état du serveur"""
    return jsonify({
        'status': 'ok',
        'service': 'Kidjamo Health Assistant',
        'version': '2.0.0-simplified',
        'timestamp': datetime.now().isoformat(),
        'voice_enabled': True
    })

@app.route('/')
def home():
    """Page d'accueil avec redirection vers l'interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Kidjamo Health Assistant</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                text-align: center; 
                padding: 50px;
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
            }
            .container {
                background: rgba(255,255,255,0.1);
                padding: 40px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
                max-width: 600px;
            }
            h1 { color: #fff; margin-bottom: 20px; }
            .status { 
                background: rgba(16, 185, 129, 0.2); 
                padding: 15px; 
                border-radius: 10px; 
                margin: 20px 0;
                border: 1px solid rgba(16, 185, 129, 0.3);
            }
            .info {
                background: rgba(59, 130, 246, 0.2);
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
            a { 
                color: #34d399; 
                text-decoration: none; 
                font-weight: bold;
                background: rgba(52, 211, 153, 0.2);
                padding: 10px 20px;
                border-radius: 5px;
                display: inline-block;
                margin: 10px;
                border: 1px solid rgba(52, 211, 153, 0.3);
            }
            a:hover { 
                background: rgba(52, 211, 153, 0.3);
                transform: translateY(-2px);
                transition: all 0.3s ease;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 Kidjamo Health Assistant</h1>
            <div class="status">
                ✅ Serveur démarré avec succès !<br>
                💬 API chatbot disponible
            </div>
            <div class="info">
                <strong>Pour utiliser l'interface complète :</strong><br>
                Ouvrez votre fichier HTML dans le navigateur<br>
                (kidjamo_chatbot_interface_clean.html)
            </div>
            <a href="/health">🔍 État du serveur</a>
            <br><br>
            <p>Le serveur écoute sur le port 5000 et peut recevoir vos messages !</p>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("🚀 Démarrage du serveur Kidjamo Health Assistant...")
    print("📋 Version: 2.0.0-simplified")
    print("🔧 Mode: Production locale")
    print("🌐 Interface disponible sur: http://localhost:5000")
    print("💬 API chatbot disponible sur: http://localhost:5000/chat")
    print("❤️ Santé du serveur: http://localhost:5000/health")
    print("=" * 60)

    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True
        )
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")
        print("Vérifiez que le port 5000 n'est pas déjà utilisé")
