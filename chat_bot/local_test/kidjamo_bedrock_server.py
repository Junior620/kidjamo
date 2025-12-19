"""
Serveur Kidjamo avec votre token Bedrock Bearer configuré
Prêt à remplacer Gemini Flash avec votre clé API Bedrock
"""

import os
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any

# Charger votre configuration Bedrock
load_dotenv('.env.bedrock')

# Import du moteur Bedrock avec votre token
from bedrock_bearer_engine import BedrockBearerTokenEngine

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kidjamo_bedrock_bearer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KidjamoBedrockServer:
    """Serveur Kidjamo avec votre token Bearer Bedrock configuré"""

    def __init__(self):
        # Initialisation Flask
        self.app = Flask(__name__)

        # Configuration
        self.app.config['SECRET_KEY'] = 'kidjamo-bedrock-bearer-key'
        self.app.config['DEBUG'] = False

        # CORS pour votre application
        CORS(self.app, origins=["*"])

        # Rate limiting
        self.limiter = Limiter(
            app=self.app,
            key_func=get_remote_address,
            default_limits=["60 per minute", "1000 per hour"]
        )

        # Initialisation moteur Bedrock avec votre token
        try:
            self.bedrock_engine = BedrockBearerTokenEngine()
            logger.info("✅ Moteur Bedrock Bearer Token initialisé avec votre clé API")
            logger.info(f"Token configuré: {self.bedrock_engine.bearer_token[:20]}...")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Bedrock: {e}")
            raise

        # Configuration des routes
        self._setup_routes()

        logger.info("🚀 Serveur Kidjamo Bedrock prêt à remplacer Gemini Flash")

    def _setup_routes(self):
        """Configuration des routes avec votre token Bedrock"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check avec métriques Bedrock Bearer Token"""
            try:
                metrics = self.bedrock_engine.get_bedrock_metrics()
                return jsonify({
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'version': '2.0.0-bedrock-bearer',
                    'service': 'kidjamo-bedrock-chatbot',
                    'authentication': 'bearer-token',
                    'bedrock_metrics': metrics
                }), 200
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e)
                }), 500

        @self.app.route('/chat', methods=['POST'])
        @self.limiter.limit("60 per minute")
        def chat_endpoint():
            """Endpoint chat principal - REMPLACEMENT DIRECT de Gemini Flash"""
            try:
                # Validation identique à votre serveur actuel
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Content-Type application/json requis'
                    }), 400

                data = request.get_json()
                user_message = data.get('message', '').strip()
                session_id = data.get('session_id', f'bedrock_{datetime.now().strftime("%Y%m%d_%H%M%S")}')

                if not user_message:
                    return jsonify({
                        'success': False,
                        'error': 'Message vide',
                        'session_id': session_id
                    }), 400

                if len(user_message) > 2000:
                    return jsonify({
                        'success': False,
                        'error': 'Message trop long (max 2000 caractères)',
                        'session_id': session_id
                    }), 400

                # Logging sécurisé
                logger.info(f"💬 Message Bedrock - Session: {session_id[:8]}..., Longueur: {len(user_message)}")

                # Contexte enrichi avec détection d'urgence
                context = {
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'user_ip': get_remote_address(),
                    'patient_info': data.get('patient_info', {}),
                    'urgency_level': self._assess_urgency(user_message),
                    'is_voice': data.get('is_voice', False)
                }

                # 🔄 REMPLACEMENT DIRECT : Bedrock au lieu de Gemini Flash
                response_data = self.bedrock_engine.process_message_with_ai(user_message, context)

                # Enrichissement réponse (format identique à votre serveur actuel)
                response_data.update({
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'success': True,
                    'environment': 'bedrock-production',
                    'is_voice_response': context['is_voice']
                })

                # Logging succès avec coûts Bedrock
                logger.info(f"🤖 Réponse Bedrock générée - Session: {session_id[:8]}..., "
                          f"Modèle: {response_data.get('model_used')}, "
                          f"Type: {response_data.get('conversation_type')}, "
                          f"Coût: ${response_data.get('cost_estimate', 0):.6f}")

                return jsonify(response_data), 200

            except Exception as e:
                logger.error(f"❌ Erreur critique chat Bedrock: {e}")

                # Réponse d'urgence médicale (même format que votre serveur actuel)
                emergency_response = {
                    'success': False,
                    'response': """
                    <div class="response-section emergency-alert">
                        <h3><i class="fas fa-exclamation-triangle"></i> Service IA temporairement indisponible</h3>
                        <p><strong>Pour une urgence médicale drépanocytaire :</strong></p>
                        <ul class="urgent-list">
                            <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                            <li><strong>CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                            <li><strong>Hôpital Central Yaoundé</strong> - Service urgences</li>
                        </ul>
                        <p>⚠️ L'assistance IA Bedrock sera rétablie rapidement</p>
                    </div>
                    """,
                    'conversation_type': 'system_error',
                    'session_id': data.get('session_id', 'unknown'),
                    'source': 'bedrock_emergency_fallback',
                    'timestamp': datetime.now().isoformat()
                }

                return jsonify(emergency_response), 500

        @self.app.route('/', methods=['GET'])
        def index():
            """Page d'accueil montrant votre configuration Bedrock"""
            return render_template_string("""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Kidjamo Assistant - Powered by Amazon Bedrock Bearer Token</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', sans-serif; 
                        background: linear-gradient(135deg, #232F3E 0%, #FF9900 50%, #232F3E 100%);
                        margin: 0; padding: 40px; min-height: 100vh;
                        display: flex; align-items: center; justify-content: center;
                    }
                    .container { 
                        max-width: 900px; background: white; border-radius: 25px;
                        padding: 60px; text-align: center; 
                        box-shadow: 0 30px 60px rgba(255,153,0,0.3);
                        border: 3px solid #FF9900;
                    }
                    .logo { font-size: 4.5rem; margin-bottom: 20px; }
                    .bedrock-badge { 
                        background: linear-gradient(135deg, #FF9900, #232F3E); 
                        color: white; padding: 12px 24px; 
                        border-radius: 25px; font-size: 1rem; font-weight: 700;
                        display: inline-block; margin-bottom: 20px;
                        box-shadow: 0 4px 15px rgba(255,153,0,0.3);
                    }
                    h1 { color: #333; font-size: 2.8rem; margin-bottom: 15px; }
                    .subtitle { color: #666; font-size: 1.4rem; margin-bottom: 40px; }
                    .status { 
                        background: linear-gradient(135deg, #e8f5e8, #c8e6c9); 
                        border: 3px solid #4caf50; border-radius: 20px;
                        padding: 25px; margin-bottom: 40px; font-weight: 700; color: #1b5e20;
                    }
                    .replacement-info {
                        background: linear-gradient(135deg, #fff3e0, #ffcc02); 
                        border: 3px solid #ff9800; border-radius: 20px;
                        padding: 25px; margin: 30px 0; font-weight: 600; color: #e65100;
                    }
                    .features { 
                        display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 30px; margin: 40px 0;
                    }
                    .feature { 
                        background: linear-gradient(135deg, #f8f9fa, #e9ecef); 
                        padding: 30px; border-radius: 20px;
                        border-left: 6px solid #FF9900; 
                        transition: transform 0.3s, box-shadow 0.3s;
                    }
                    .feature:hover { 
                        transform: translateY(-8px); 
                        box-shadow: 0 15px 35px rgba(255,153,0,0.2);
                    }
                    .feature h3 { color: #FF9900; margin-bottom: 15px; font-size: 1.3rem; }
                    .token-info { 
                        background: linear-gradient(135deg, #e3f2fd, #bbdefb); 
                        border: 3px solid #2196f3; border-radius: 20px;
                        padding: 25px; margin: 30px 0; text-align: left;
                    }
                    .api-info {
                        background: linear-gradient(135deg, #f3e5f5, #e1bee7);
                        border: 3px solid #9c27b0; border-radius: 20px;
                        padding: 25px; margin: 30px 0; text-align: left;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="bedrock-badge">🚀 Amazon Bedrock Bearer Token Ready</div>
                    <div class="logo">🏥🤖</div>
                    <h1>Kidjamo Health Assistant</h1>
                    <p class="subtitle">Assistant médical IA avec Amazon Bedrock - Votre token configuré !</p>
                    
                    <div class="status">
                        ✅ Service Amazon Bedrock opérationnel avec votre Bearer Token
                    </div>
                    
                    <div class="replacement-info">
                        🔄 <strong>REMPLACEMENT RÉUSSI !</strong><br>
                        Gemini Flash → Amazon Bedrock Bearer Token<br>
                        Même interface, performance supérieure, scaling illimité
                    </div>
                    
                    <div class="features">
                        <div class="feature">
                            <h3>🚨 Urgences Optimisées</h3>
                            <p>Sélection automatique Claude 3 Haiku pour les urgences médicales critiques</p>
                        </div>
                        <div class="feature">
                            <h3>🧠 Multi-Modèles IA</h3>
                            <p>Claude 3 Haiku (urgences) + Titan Text (économique) selon le contexte</p>
                        </div>
                        <div class="feature">
                            <h3>💰 Coût Maîtrisé</h3>
                            <p>Cache intelligent + sélection automatique pour optimiser les coûts</p>
                        </div>
                        <div class="feature">
                            <h3>🔒 Bearer Token Auth</h3>
                            <p>Authentification sécurisée avec votre token Bedrock configuré</p>
                        </div>
                        <div class="feature">
                            <h3>🇨🇲 Contexte Cameroun</h3>
                            <p>Protocoles d'urgence camerounais : 1510, CHU Yaoundé, Hôpital Central</p>
                        </div>
                        <div class="feature">
                            <h3>📊 Monitoring Avancé</h3>
                            <p>Métriques temps réel, coûts par modèle, performance tracking</p>
                        </div>
                    </div>
                    
                    <div class="token-info">
                        <h3>🔑 Configuration Bearer Token</h3>
                        <p><strong>✅ Token configuré :</strong> ABSKQmVkcm9ja0F...U0= (actif)</p>
                        <p><strong>✅ Endpoint :</strong> https://bedrock-runtime.us-east-1.amazonaws.com</p>
                        <p><strong>✅ Modèle principal :</strong> Claude 3 Haiku (urgences médicales)</p>
                        <p><strong>✅ Modèle économique :</strong> Amazon Titan Text (questions générales)</p>
                    </div>
                    
                    <div class="api-info">
                        <h3>🔗 API Endpoints (Identique à Gemini Flash)</h3>
                        <p><strong>POST /chat</strong> - Conversation médicale (même format qu'avant)</p>
                        <p><strong>GET /health</strong> - Status + métriques Bedrock</p>
                        <p><strong>GET /metrics</strong> - Coûts détaillés par modèle</p>
                        <p><strong>GET /models</strong> - Modèles Bedrock disponibles</p>
                        
                        <br>
                        <p><strong>💡 Migration transparente :</strong> Changez juste l'URL de votre chatbot !</p>
                    </div>
                </div>
            </body>
            </html>
            """)

        @self.app.route('/models', methods=['GET'])
        def get_models():
            """Liste des modèles Bedrock avec votre token"""
            try:
                models_info = self.bedrock_engine.get_available_models()
                return jsonify(models_info), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/metrics', methods=['GET'])
        def get_metrics():
            """Métriques détaillées Bedrock"""
            try:
                metrics = self.bedrock_engine.get_bedrock_metrics()
                return jsonify(metrics), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.errorhandler(429)
        def ratelimit_handler(e):
            return jsonify({
                'success': False,
                'error': 'Trop de requêtes - Veuillez patienter',
                'service': 'bedrock-bearer'
            }), 429

    def _assess_urgency(self, message: str) -> str:
        """Évalue l'urgence pour sélection automatique du modèle"""
        message_lower = message.lower()

        critical_keywords = ["poitrine", "respir", "8/10", "9/10", "10/10", "insupportable", "mourir"]
        high_keywords = ["mal", "douleur", "aide", "urgent", "grave", "7/10"]

        if any(kw in message_lower for kw in critical_keywords):
            return "critical"
        elif any(kw in message_lower for kw in high_keywords):
            return "high"
        else:
            return "normal"

    def run(self):
        """Démarre le serveur Bedrock Bearer Token"""
        host = '0.0.0.0'
        port = 5000

        logger.info("🚀 DÉMARRAGE SERVEUR KIDJAMO BEDROCK")
        logger.info(f"   URL: http://{host}:{port}")
        logger.info(f"   Token Bearer: {self.bedrock_engine.bearer_token[:20]}...")
        logger.info(f"   Modèle principal: {self.bedrock_engine.primary_model}")
        logger.info("   Prêt à remplacer Gemini Flash !")

        self.app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )

if __name__ == '__main__':
    try:
        server = KidjamoBedrockServer()
        server.run()
    except Exception as e:
        logger.critical(f"❌ Impossible de démarrer le serveur Bedrock: {e}")
        print(f"""
❌ ERREUR DE DÉMARRAGE BEDROCK BEARER TOKEN

Vérifiez:
1. Token Bearer dans .env.bedrock
2. Endpoint Bedrock accessible
3. Permissions sur votre token
4. Configuration réseau

Token configuré: {os.getenv('AWS_BEARER_TOKEN_BEDROCK', 'NON TROUVÉ')[:20]}...

Erreur: {e}
        """)
        exit(1)
