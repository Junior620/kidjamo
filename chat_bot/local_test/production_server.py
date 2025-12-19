"""
Serveur Flask Production - Kidjamo Health Assistant
Version sécurisée avec Gemini Flash pour déploiement professionnel
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
import redis
import json

# Charger configuration production
load_dotenv('.env.production')

# Import du moteur production
from production_gemini_engine import ProductionGeminiFlashEngine

# Configuration logging production
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kidjamo_production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionChatbotServer:
    """Serveur chatbot production avec sécurité renforcée"""

    def __init__(self):
        # Initialisation Flask
        self.app = Flask(__name__)

        # Configuration sécurité
        self.app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-prod')
        self.app.config['DEBUG'] = os.getenv('DEBUG', 'false').lower() == 'true'

        # CORS sécurisé
        allowed_origins = os.getenv('CORS_ORIGINS', '*').split(',')
        CORS(self.app, origins=allowed_origins)

        # Rate limiting
        try:
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            self.limiter = Limiter(
                app=self.app,
                key_func=get_remote_address,
                storage_uri=os.getenv('REDIS_URL', 'redis://localhost:6379')
            )
        except:
            logger.warning("Redis non disponible - rate limiting en mémoire")
            self.limiter = Limiter(
                app=self.app,
                key_func=get_remote_address,
                storage_uri="memory://"
            )

        # Initialisation moteur IA production
        try:
            self.gemini_engine = ProductionGeminiFlashEngine()
            logger.info("Moteur Gemini Flash production initialisé")
        except Exception as e:
            logger.error(f"Erreur initialisation Gemini: {e}")
            raise

        # Configuration des routes
        self._setup_routes()

        logger.info("Serveur production Kidjamo initialisé avec sécurité")

    def _setup_routes(self):
        """Configuration des routes sécurisées"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check pour monitoring"""
            try:
                metrics = self.gemini_engine.get_production_metrics()
                return jsonify({
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'version': '2.0.0-production',
                    'service': 'kidjamo-chatbot',
                    'ai_metrics': metrics
                }), 200
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e)
                }), 500

        @self.app.route('/metrics', methods=['GET'])
        def get_metrics():
            """Métriques détaillées pour monitoring"""
            try:
                metrics = self.gemini_engine.get_production_metrics()
                return jsonify(metrics), 200
            except Exception as e:
                logger.error(f"Erreur métriques: {e}")
                return jsonify({'error': 'Metrics unavailable'}), 500

        @self.app.route('/chat', methods=['POST'])
        @self.limiter.limit("100 per minute")  # Rate limiting par IP
        def chat_endpoint():
            """Endpoint chat principal avec sécurité renforcée"""
            try:
                # Validation des données d'entrée
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Content-Type application/json requis'
                    }), 400

                data = request.get_json()
                user_message = data.get('message', '').strip()
                session_id = data.get('session_id', f'prod_{datetime.now().strftime("%Y%m%d_%H%M%S")}')

                # Validation message
                if not user_message:
                    return jsonify({
                        'success': False,
                        'error': 'Message vide',
                        'session_id': session_id
                    }), 400

                max_length = int(os.getenv('MAX_MESSAGE_LENGTH', 2000))
                if len(user_message) > max_length:
                    return jsonify({
                        'success': False,
                        'error': f'Message trop long (max {max_length} caractères)',
                        'session_id': session_id
                    }), 400

                # Logging sécurisé (pas de données sensibles)
                logger.info(f"Message reçu - Session: {session_id[:8]}..., Longueur: {len(user_message)}")

                # Contexte enrichi pour production
                context = {
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'user_ip': get_remote_address(),
                    'patient_info': data.get('patient_info', {}),
                    'urgency_level': self._assess_urgency(user_message)
                }

                # Traitement avec IA
                response_data = self.gemini_engine.process_message_with_ai(user_message, context)

                # Enrichissement réponse
                response_data.update({
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'success': True,
                    'environment': 'production'
                })

                # Logging du succès
                logger.info(f"Réponse générée - Session: {session_id[:8]}..., "
                          f"Type: {response_data.get('conversation_type')}, "
                          f"Source: {response_data.get('source')}")

                return jsonify(response_data), 200

            except Exception as e:
                logger.error(f"Erreur critique chat endpoint: {e}")

                # Réponse d'urgence en cas d'erreur système
                emergency_response = {
                    'success': False,
                    'response': """
                    <div class="response-section emergency-alert">
                        <h3><i class="fas fa-exclamation-triangle"></i> Service temporairement indisponible</h3>
                        <p><strong>Pour une urgence médicale drépanocytaire :</strong></p>
                        <ul class="urgent-list">
                            <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                            <li><strong>CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                            <li><strong>Hôpital Central Yaoundé</strong> - Service urgences</li>
                        </ul>
                        <p>⚠️ Ce service sera rétabli dans les plus brefs délais</p>
                    </div>
                    """,
                    'conversation_type': 'system_error',
                    'session_id': data.get('session_id', 'unknown'),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'emergency_fallback'
                }

                return jsonify(emergency_response), 500

        @self.app.route('/', methods=['GET'])
        def index():
            """Page d'accueil production"""
            return render_template_string("""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Kidjamo Health Assistant - Production</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', sans-serif; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        margin: 0; padding: 40px; min-height: 100vh;
                        display: flex; align-items: center; justify-content: center;
                    }
                    .container { 
                        max-width: 800px; background: white; border-radius: 20px;
                        padding: 60px; text-align: center; box-shadow: 0 25px 50px rgba(0,0,0,0.15);
                    }
                    .logo { font-size: 4rem; color: #667eea; margin-bottom: 20px; }
                    h1 { color: #333; font-size: 2.5rem; margin-bottom: 15px; }
                    .subtitle { color: #666; font-size: 1.3rem; margin-bottom: 40px; }
                    .status { 
                        background: #e8f5e8; border: 2px solid #4caf50; border-radius: 12px;
                        padding: 20px; margin-bottom: 40px; font-weight: 600; color: #2e7d32;
                    }
                    .features { 
                        display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 30px; margin: 40px 0;
                    }
                    .feature { 
                        background: #f8f9fa; padding: 25px; border-radius: 12px;
                        border-left: 4px solid #667eea;
                    }
                    .feature h3 { color: #667eea; margin-bottom: 10px; }
                    .api-info { 
                        background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px;
                        padding: 20px; margin-top: 30px; text-align: left;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">🏥</div>
                    <h1>Kidjamo Health Assistant</h1>
                    <p class="subtitle">Assistant médical IA spécialisé drépanocytose - Version Production</p>
                    
                    <div class="status">
                        ✅ Service opérationnel - IA Gemini Flash intégrée
                    </div>
                    
                    <div class="features">
                        <div class="feature">
                            <h3>🚨 Gestion Urgences</h3>
                            <p>Détection automatique des situations critiques avec protocole d'urgence camerounais</p>
                        </div>
                        <div class="feature">
                            <h3>🤖 IA Médicale</h3>
                            <p>Réponses contextualisées par Gemini Flash spécialisé drépanocytose</p>
                        </div>
                        <div class="feature">
                            <h3>🔒 Sécurité</h3>
                            <p>Chiffrement, rate limiting, monitoring temps réel</p>
                        </div>
                        <div class="feature">
                            <h3>🇨🇲 Contexte Local</h3>
                            <p>Adapté au système de santé camerounais</p>
                        </div>
                    </div>
                    
                    <div class="api-info">
                        <h3>🔗 API Endpoints</h3>
                        <p><strong>POST /chat</strong> - Conversation médicale</p>
                        <p><strong>GET /health</strong> - Status système</p>
                        <p><strong>GET /metrics</strong> - Métriques détaillées</p>
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
                'retry_after': getattr(e, 'retry_after', 60)
            }), 429

        @self.app.errorhandler(500)
        def internal_error(e):
            """Gestion des erreurs internes"""
            logger.error(f"Erreur interne: {e}")
            return jsonify({
                'success': False,
                'error': 'Erreur interne du serveur',
                'timestamp': datetime.now().isoformat()
            }), 500

    def _assess_urgency(self, message: str) -> str:
        """Évalue le niveau d'urgence du message"""
        message_lower = message.lower()

        critical_keywords = ["poitrine", "respir", "8/10", "9/10", "10/10", "insupportable"]
        high_keywords = ["mal", "douleur", "aide", "urgent"]

        if any(kw in message_lower for kw in critical_keywords):
            return "critical"
        elif any(kw in message_lower for kw in high_keywords):
            return "high"
        else:
            return "normal"

    def run(self):
        """Démarre le serveur production"""
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 5000))

        logger.info(f"Démarrage serveur production sur {host}:{port}")

        # Configuration production
        self.app.run(
            host=host,
            port=port,
            debug=False,  # JAMAIS True en production
            threaded=True,
            use_reloader=False
        )

# Point d'entrée
if __name__ == '__main__':
    try:
        server = ProductionChatbotServer()
        server.run()
    except Exception as e:
        logger.critical(f"Impossible de démarrer le serveur: {e}")
        exit(1)
