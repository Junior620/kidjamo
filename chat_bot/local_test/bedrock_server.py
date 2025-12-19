"""
Serveur Kidjamo avec Amazon Bedrock - Alternative professionnelle à Gemini Flash
Support multi-modèles Claude, Llama, Titan avec sélection automatique
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

# Charger configuration Bedrock
load_dotenv('.env.bedrock')

# Import du moteur Bedrock
from bedrock_ai_engine import BedrockAIEngine

# Configuration logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kidjamo_bedrock.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BedrockChatbotServer:
    """Serveur chatbot avec Amazon Bedrock"""

    def __init__(self):
        # Initialisation Flask
        self.app = Flask(__name__)

        # Configuration sécurité
        self.app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'bedrock-kidjamo-key')
        self.app.config['DEBUG'] = os.getenv('DEBUG', 'false').lower() == 'true'

        # CORS
        CORS(self.app, origins=["*"])

        # Rate limiting
        self.limiter = Limiter(
            app=self.app,
            key_func=get_remote_address,
            default_limits=["60 per minute", "1000 per hour"]
        )

        # Initialisation moteur Bedrock
        try:
            self.bedrock_engine = BedrockAIEngine()
            logger.info("Moteur Amazon Bedrock initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur initialisation Bedrock: {e}")
            raise

        # Configuration des routes
        self._setup_routes()

        logger.info("Serveur Bedrock Kidjamo initialisé")

    def _setup_routes(self):
        """Configuration des routes"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check avec métriques Bedrock"""
            try:
                metrics = self.bedrock_engine.get_bedrock_metrics()
                return jsonify({
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'version': '2.0.0-bedrock',
                    'service': 'kidjamo-bedrock-chatbot',
                    'aws_region': os.getenv('AWS_REGION'),
                    'bedrock_metrics': metrics
                }), 200
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e)
                }), 500

        @self.app.route('/models', methods=['GET'])
        def get_available_models():
            """Liste des modèles Bedrock disponibles"""
            try:
                models_info = self.bedrock_engine.get_available_models()
                return jsonify(models_info), 200
            except Exception as e:
                logger.error(f"Erreur récupération modèles: {e}")
                return jsonify({'error': 'Models info unavailable'}), 500

        @self.app.route('/metrics', methods=['GET'])
        def get_detailed_metrics():
            """Métriques détaillées Bedrock"""
            try:
                metrics = self.bedrock_engine.get_bedrock_metrics()
                return jsonify(metrics), 200
            except Exception as e:
                logger.error(f"Erreur métriques: {e}")
                return jsonify({'error': 'Metrics unavailable'}), 500

        @self.app.route('/chat', methods=['POST'])
        @self.limiter.limit("60 per minute")
        def chat_endpoint():
            """Endpoint chat principal avec Bedrock"""
            try:
                # Validation des données
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

                # Limitation longueur message
                if len(user_message) > 2000:
                    return jsonify({
                        'success': False,
                        'error': 'Message trop long (max 2000 caractères)',
                        'session_id': session_id
                    }), 400

                # Logging sécurisé
                logger.info(f"Message Bedrock - Session: {session_id[:8]}..., Longueur: {len(user_message)}")

                # Contexte enrichi
                context = {
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'user_ip': get_remote_address(),
                    'patient_info': data.get('patient_info', {}),
                    'urgency_level': self._assess_urgency(user_message),
                    'preferred_model': data.get('preferred_model'),  # Permet au client de spécifier un modèle
                }

                # Traitement avec Bedrock
                response_data = self.bedrock_engine.process_message_with_ai(user_message, context)

                # Enrichissement réponse
                response_data.update({
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'success': True,
                    'environment': 'bedrock-production',
                    'aws_region': os.getenv('AWS_REGION')
                })

                # Logging succès avec métriques
                logger.info(f"Réponse Bedrock générée - Session: {session_id[:8]}..., "
                          f"Modèle: {response_data.get('model_used')}, "
                          f"Coût: ${response_data.get('cost_estimate', 0):.6f}")

                return jsonify(response_data), 200

            except Exception as e:
                logger.error(f"Erreur critique chat Bedrock: {e}")

                # Réponse d'urgence
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
                        <p>⚠️ L'assistance IA sera rétablie rapidement</p>
                    </div>
                    """,
                    'conversation_type': 'system_error',
                    'session_id': data.get('session_id', 'unknown'),
                    'source': 'bedrock_emergency_fallback'
                }

                return jsonify(emergency_response), 500

        @self.app.route('/', methods=['GET'])
        def index():
            """Page d'accueil Bedrock"""
            return render_template_string("""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Kidjamo Assistant - Powered by Amazon Bedrock</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', sans-serif; 
                        background: linear-gradient(135deg, #FF9500 0%, #FF6B35 50%, #F7931E 100%);
                        margin: 0; padding: 40px; min-height: 100vh;
                        display: flex; align-items: center; justify-content: center;
                    }
                    .container { 
                        max-width: 900px; background: white; border-radius: 25px;
                        padding: 60px; text-align: center; 
                        box-shadow: 0 30px 60px rgba(255,149,0,0.2);
                        border: 3px solid #FF9500;
                    }
                    .logo { font-size: 4.5rem; margin-bottom: 20px; }
                    .aws-badge { 
                        background: #FF9500; color: white; padding: 8px 16px; 
                        border-radius: 20px; font-size: 0.9rem; font-weight: 600;
                        display: inline-block; margin-bottom: 20px;
                    }
                    h1 { color: #333; font-size: 2.8rem; margin-bottom: 15px; }
                    .subtitle { color: #666; font-size: 1.4rem; margin-bottom: 40px; }
                    .status { 
                        background: #e8f5e8; border: 2px solid #4caf50; border-radius: 15px;
                        padding: 25px; margin-bottom: 40px; font-weight: 600; color: #2e7d32;
                    }
                    .features { 
                        display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                        gap: 30px; margin: 40px 0;
                    }
                    .feature { 
                        background: #f8f9fa; padding: 30px; border-radius: 15px;
                        border-left: 5px solid #FF9500; transition: transform 0.3s;
                    }
                    .feature:hover { transform: translateY(-5px); }
                    .feature h3 { color: #FF9500; margin-bottom: 15px; font-size: 1.2rem; }
                    .models-info { 
                        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); 
                        border: 2px solid #FF9500; border-radius: 15px;
                        padding: 25px; margin: 30px 0; text-align: left;
                    }
                    .model-item { 
                        background: white; padding: 15px; margin: 10px 0; 
                        border-radius: 8px; border-left: 4px solid #FF9500;
                    }
                    .cost-badge { 
                        background: #4caf50; color: white; padding: 4px 8px; 
                        border-radius: 12px; font-size: 0.8rem;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="aws-badge">⚡ Powered by Amazon Bedrock</div>
                    <div class="logo">🏥🤖</div>
                    <h1>Kidjamo Health Assistant</h1>
                    <p class="subtitle">Assistant médical IA multi-modèles spécialisé drépanocytose</p>
                    
                    <div class="status">
                        ✅ Service Amazon Bedrock opérationnel - Multi-modèles IA disponibles
                    </div>
                    
                    <div class="features">
                        <div class="feature">
                            <h3>🚨 Urgences Intelligentes</h3>
                            <p>Sélection automatique du modèle optimal selon la criticité médicale</p>
                        </div>
                        <div class="feature">
                            <h3>🧠 Multi-Modèles IA</h3>
                            <p>Claude 3 Haiku, Llama 3, Titan - Sélection automatique optimisée</p>
                        </div>
                        <div class="feature">
                            <h3>💰 Coût Optimisé</h3>
                            <p>Gestion intelligente des coûts avec cache et sélection de modèles</p>
                        </div>
                        <div class="feature">
                            <h3>🔒 Enterprise Grade</h3>
                            <p>Sécurité AWS, SLA garantis, conformité médicale</p>
                        </div>
                        <div class="feature">
                            <h3>🇨🇲 Contexte Cameroun</h3>
                            <p>Adapté au système de santé camerounais avec protocoles locaux</p>
                        </div>
                        <div class="feature">
                            <h3>📊 Monitoring Avancé</h3>
                            <p>Métriques temps réel, alertes coûts, performance tracking</p>
                        </div>
                    </div>
                    
                    <div class="models-info">
                        <h3>🤖 Modèles IA Disponibles</h3>
                        
                        <div class="model-item">
                            <strong>Claude 3 Haiku</strong> <span class="cost-badge">$0.25/1M tokens</span>
                            <br><small>Recommandé pour urgences - Rapide et précis</small>
                        </div>
                        
                        <div class="model-item">
                            <strong>Llama 3 8B</strong> <span class="cost-badge">$0.30/1M tokens</span>
                            <br><small>Open source - Questions générales économiques</small>
                        </div>
                        
                        <div class="model-item">
                            <strong>Amazon Titan</strong> <span class="cost-badge">$0.80/1M tokens</span>
                            <br><small>Natif AWS - Intégration optimisée</small>
                        </div>
                        
                        <p><strong>💡 Sélection automatique</strong> selon l'urgence et la complexité de la question</p>
                    </div>
                    
                    <div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 12px; padding: 20px; margin-top: 30px; text-align: left;">
                        <h3 style="color: #856404;">🔗 API Endpoints</h3>
                        <p><strong>POST /chat</strong> - Conversation médicale intelligente</p>
                        <p><strong>GET /health</strong> - Status système + métriques Bedrock</p>
                        <p><strong>GET /models</strong> - Modèles disponibles et configuration</p>
                        <p><strong>GET /metrics</strong> - Métriques détaillées et coûts</p>
                    </div>
                </div>
            </body>
            </html>
            """)

        @self.app.errorhandler(429)
        def ratelimit_handler(e):
            """Gestion des limites de taux"""
            return jsonify({
                'success': False,
                'error': 'Trop de requêtes - Veuillez patienter',
                'retry_after': getattr(e, 'retry_after', 60),
                'service': 'bedrock'
            }), 429

        @self.app.errorhandler(500)
        def internal_error(e):
            """Gestion des erreurs internes"""
            logger.error(f"Erreur interne Bedrock: {e}")
            return jsonify({
                'success': False,
                'error': 'Erreur interne du serveur Bedrock',
                'timestamp': datetime.now().isoformat()
            }), 500

    def _assess_urgency(self, message: str) -> str:
        """Évalue le niveau d'urgence pour sélection de modèle"""
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
        """Démarre le serveur Bedrock"""
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 5000))

        logger.info(f"Démarrage serveur Bedrock sur {host}:{port}")
        logger.info(f"Région AWS: {os.getenv('AWS_REGION')}")
        logger.info(f"Modèles: {self.bedrock_engine.primary_model} (primary), {self.bedrock_engine.fallback_model} (fallback)")

        self.app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )

if __name__ == '__main__':
    try:
        server = BedrockChatbotServer()
        server.run()
    except Exception as e:
        logger.critical(f"Impossible de démarrer le serveur Bedrock: {e}")
        print(f"""
❌ ERREUR DE DÉMARRAGE BEDROCK

Vérifiez:
1. Variables AWS dans .env.bedrock
2. Permissions IAM Bedrock
3. Région AWS supportée
4. Modèles activés dans votre compte

Erreur: {e}
        """)
        exit(1)
