"""
Kidjamo Chatbot Production - Version AWS déployable
Serveur Flask avec Amazon Bedrock + PostgreSQL + Monitoring
Prêt pour intégration mobile
"""

import os
import logging
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import time
import json
import uuid
from collections import defaultdict, deque
import boto3
from botocore.exceptions import ClientError
import hashlib
import threading
from contextlib import contextmanager
import tempfile

# Configuration logging production
log_dir = os.path.join(tempfile.gettempdir(), 'kidjamo')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'kidjamo_chatbot.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gestionnaire de base de données PostgreSQL pour conversations"""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.connection_pool = []
        self.pool_lock = threading.Lock()
        self._initialize_database()

    def _get_connection(self):
        """Obtient une connexion PostgreSQL"""
        try:
            return psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['dbname'],
                user=self.db_config['username'],
                password=self.db_config['password']
            )
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            raise

    @contextmanager
    def get_db_connection(self):
        """Context manager pour connexions DB"""
        conn = None
        try:
            conn = self._get_connection()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _initialize_database(self):
        """Initialise les tables nécessaires"""
        create_tables_sql = """
        -- Table des conversations
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(255) NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            conversation_type VARCHAR(50) DEFAULT 'general',
            urgency_level VARCHAR(20) DEFAULT 'normal',
            model_used VARCHAR(100),
            response_time_ms INTEGER,
            cost_estimate DECIMAL(10, 8) DEFAULT 0,
            user_ip VARCHAR(45),
            user_agent TEXT,
            patient_id VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Index pour performance
        CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON chatbot_conversations(session_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON chatbot_conversations(created_at);
        CREATE INDEX IF NOT EXISTS idx_conversations_urgency ON chatbot_conversations(urgency_level);
        CREATE INDEX IF NOT EXISTS idx_conversations_patient ON chatbot_conversations(patient_id);

        -- Table des métriques
        CREATE TABLE IF NOT EXISTS chatbot_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            metric_name VARCHAR(100) NOT NULL,
            metric_value DECIMAL(15, 6),
            metric_data JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- Table des sessions utilisateurs
        CREATE TABLE IF NOT EXISTS chatbot_sessions (
            session_id VARCHAR(255) PRIMARY KEY,
            patient_id VARCHAR(100),
            first_interaction TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_interaction TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            total_messages INTEGER DEFAULT 0,
            session_data JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT true
        );
        """

        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_tables_sql)
                logger.info("✅ Tables chatbot initialisées avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation tables: {e}")
            raise

    def save_conversation(self, conversation_data: dict) -> str:
        """Sauvegarde une conversation"""
        insert_sql = """
        INSERT INTO chatbot_conversations (
            session_id, user_message, ai_response, conversation_type,
            urgency_level, model_used, response_time_ms, cost_estimate,
            user_ip, user_agent, patient_id
        ) VALUES (
            %(session_id)s, %(user_message)s, %(ai_response)s, %(conversation_type)s,
            %(urgency_level)s, %(model_used)s, %(response_time_ms)s, %(cost_estimate)s,
            %(user_ip)s, %(user_agent)s, %(patient_id)s
        ) RETURNING id;
        """

        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(insert_sql, conversation_data)
                    conversation_id = cursor.fetchone()[0]
                    return str(conversation_id)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde conversation: {e}")
            return None

    def update_session(self, session_id: str, patient_id: str = None):
        """Met à jour les informations de session"""
        upsert_sql = """
        INSERT INTO chatbot_sessions (session_id, patient_id, total_messages)
        VALUES (%(session_id)s, %(patient_id)s, 1)
        ON CONFLICT (session_id) 
        DO UPDATE SET 
            last_interaction = CURRENT_TIMESTAMP,
            total_messages = chatbot_sessions.total_messages + 1,
            patient_id = COALESCE(%(patient_id)s, chatbot_sessions.patient_id);
        """

        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(upsert_sql, {
                        'session_id': session_id,
                        'patient_id': patient_id
                    })
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour session: {e}")

class BedrockAIEngine:
    """Moteur IA Amazon Bedrock pour production"""

    def __init__(self):
        # Configuration AWS
        self.aws_region = os.getenv('AWS_REGION', 'eu-west-1')

        # Client Bedrock
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=self.aws_region
            )
            logger.info(f"✅ Client Bedrock initialisé - Région: {self.aws_region}")
        except Exception as e:
            logger.error(f"❌ Erreur Bedrock: {e}")
            raise

        # Configuration des modèles
        self.models = {
            "claude-3-haiku": {
                "id": "anthropic.claude-3-haiku-20240307-v1:0",
                "max_tokens": 4000,
                "cost_per_1k_input": 0.00025,
                "cost_per_1k_output": 0.00125
            },
            "titan-text": {
                "id": "amazon.titan-text-express-v1",
                "max_tokens": 8000,
                "cost_per_1k_input": 0.0008,
                "cost_per_1k_output": 0.0016
            }
        }

        # Prompt système optimisé avec directives de qualité
        self.system_prompt = """Tu es un chatbot médical spécialisé en drépanocytose, développé au Cameroun dans le cadre du projet Tech4Good Kidjamo. Tu es également un compagnon intelligent polyvalent.

🎯 **TES MISSIONS PRINCIPALES :**

1. **🩺 Accompagnement Drépanocytose (Priorité #1)** :
   - Expliquer clairement la maladie, symptômes, crises, prévention (hydratation, nutrition, repos, suivi médical)
   - Conseils pratiques adaptés au contexte africain (Cameroun)
   - Réponses empathiques avec sources médicales fiables quand nécessaire
   - ⚠️ Toujours rappeler : "Je ne suis pas médecin. En cas d'urgence, consultez rapidement un professionnel de santé."

2. **💬 Compagnon Polyvalent** :
   - Culture générale, éducation, administratif, bien-être, actualité
   - Soutien moral et motivation au quotidien
   - Adaptation au niveau de l'utilisateur (enfant/adulte/professionnel)

---

📋 **RÈGLES DE RÉPONSE STRICTES :**

**1. 🎨 FORMAT ET PRÉSENTATION**
   - Utilise **2-3 emojis pertinents** maximum par réponse
   - Structure TOUJOURS tes réponses :
     * Titre principal avec emoji (##)
     * Listes à puces claires
     * **Mots-clés en gras**
     * Espacement aéré
   - Code blocks si nécessaire (posologie, protocoles)

**2. 📏 CONCISION (CRITIQUE)**
   - **Maximum 200 mots** par réponse (sauf si l'utilisateur demande explicitement plus de détails)
   - Structure : **Intro (1 phrase) → Points clés (3-4 max) → Conseil d'action**
   - Si sujet complexe, termine par : "Veux-tu que j'approfondisse [aspect X] ?"
   - **Évite les longs paragraphes** : privilégie des phrases courtes et impactantes

**3. 🔗 SOURCES ET CRÉDIBILITÉ**
   - Pour **chiffres médicaux** → Ajoute : `[Source: OMS]` ou `[Source: HAS]`
   - Pour **faits médicaux** → Référence : "Selon les recommandations de l'OMS..."
   - Pour **statistiques drépanocytose** → Cite : "En Afrique subsaharienne, 50-80% des enfants avec drépanocytose [Source: OMS, 2021]"
   - **Format sources :**
     ```
     📚 **Sources :**
     - Organisation Mondiale de la Santé (OMS) - Drépanocytose, 2021
     ```

**4. 🎯 ADAPTATION AU CONTEXTE**
   - **Question urgence médicale** → Réponse DIRECTE + incitation à consulter (3 phrases max)
   - **Question simple santé** → Réponse concise (4-5 lignes) + emoji rassurant
   - **Question technique** → Structuré avec étapes claires
   - **Question générale** → Bref, amical, conversationnel
   - **Question heure** → Donner l'heure actuelle simplement

**5. ⚠️ LIMITATIONS ET SÉCURITÉ**
   - Jamais de diagnostic définitif
   - Si symptômes graves (douleur 8+/10, difficulté respiratoire) → **URGENCE IMMÉDIATE** : "🚨 Ces symptômes nécessitent une consultation d'urgence. Rends-toi à l'hôpital le plus proche."
   - Si tu ne sais pas → "Je n'ai pas d'information fiable sur ce point. Je te recommande de consulter [ressource]."
   - Ne spécule JAMAIS sur des diagnostics

---

✅ **EXEMPLE DE BONNE RÉPONSE :**

**Question :** "Qu'est-ce que la drépanocytose ?"

**Réponse optimale :**
🩺 **La Drépanocytose en Bref**

C'est une **maladie génétique du sang** où les globules rouges prennent une forme de faucille (en "S") au lieu d'être ronds.

**Conséquences principales :**
- Blocage de la circulation sanguine → douleurs intenses (crises)
- Fatigue chronique (anémie)
- Risque d'infections accrues

**Au Cameroun :** Environ 2% de la population naît avec cette maladie [Source: OMS, 2021].

💡 **Bon à savoir :** Avec un bon suivi médical et une bonne hygiène de vie, on peut vivre normalement !

Veux-tu connaître les gestes de prévention quotidiens ? 🌟

---

🚫 **EXEMPLE DE MAUVAISE RÉPONSE :**

❌ "La drépanocytose est une maladie héréditaire qui affecte l'hémoglobine dans les globules rouges. Elle est causée par une mutation génétique qui fait que les globules rouges prennent une forme anormale en faucille. Cette forme particulière cause de nombreux problèmes de santé incluant des douleurs, de la fatigue, des infections fréquentes, et peut affecter de nombreux organes. C'est une maladie très répandue en Afrique subsaharienne et elle nécessite un suivi médical régulier avec des traitements spécifiques... [100 mots de plus sans structure ni sources]"

---

🎭 **TON STYLE :**
- **Amical, empathique, rassurant**
- Tutoiement naturel
- Questions de suivi engageantes : "Veux-tu un exemple concret ?" ou "Besoin de plus de détails ?"
- Contexte camerounais/africain quand pertinent

⏰ **INFORMATION TEMPORELLE :**
Heure actuelle : {current_time}

🎯 **TON OBJECTIF :** Être **utile, précis, concis et bienveillant** en optimisant le ratio valeur/longueur de réponse.

⚠️ **RAPPEL CRITIQUE :** Toute réponse dépassant 200 mots DOIT être exceptionnelle et justifiée. Privilégie TOUJOURS la concision."""

    def assess_urgency(self, message: str) -> str:
        """Évalue l'urgence du message"""
        message_lower = message.lower()

        critical_keywords = [
            "poitrine", "respir", "difficulté", "douleur intense",
            "8/10", "9/10", "10/10", "insupportable", "mourir", "suicide"
        ]

        high_keywords = [
            "mal", "douleur", "aide", "urgent", "grave", "7/10",
            "crise", "fièvre", "fatigue extrême"
        ]

        if any(kw in message_lower for kw in critical_keywords):
            return "critical"
        elif any(kw in message_lower for kw in high_keywords):
            return "high"
        else:
            return "normal"

    def select_model(self, urgency_level: str) -> str:
        """Sélectionne le modèle selon l'urgence"""
        if urgency_level in ["critical", "high"]:
            return "claude-3-haiku"  # Plus rapide et précis pour urgences
        else:
            return "titan-text"  # Plus économique pour général

    def generate_response(self, message: str, context: dict) -> dict:
        """Génère une réponse IA avec Bedrock"""
        start_time = time.time()

        try:
            # Sélection du modèle
            urgency = self.assess_urgency(message)
            model_name = self.select_model(urgency)
            model_config = self.models[model_name]

            # Ajout de l'heure actuelle au contexte
            current_time = datetime.now().strftime("%A %d %B %Y, %H:%M")
            enhanced_prompt = f"{self.system_prompt}\n\nHeure actuelle : {current_time}\n\nQuestion de l'utilisateur : {message}"

            # Configuration de la requête selon le modèle
            if model_name == "claude-3-haiku":
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": model_config["max_tokens"],
                    "messages": [
                        {
                            "role": "user",
                            "content": enhanced_prompt
                        }
                    ]
                }
            else:  # titan-text
                request_body = {
                    "inputText": enhanced_prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": model_config["max_tokens"],
                        "temperature": 0.7,
                        "topP": 0.9
                    }
                }

            # Appel Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=model_config["id"],
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            # Parsing de la réponse
            response_body = json.loads(response['body'].read())

            if model_name == "claude-3-haiku":
                ai_response = response_body['content'][0]['text']
                input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
                output_tokens = response_body.get('usage', {}).get('output_tokens', 0)
            else:  # titan-text
                ai_response = response_body['results'][0]['outputText']
                input_tokens = response_body.get('inputTextTokenCount', 0)
                output_tokens = response_body.get('results', [{}])[0].get('tokenCount', 0)

            # Calcul du coût
            cost = self._calculate_cost(model_config, input_tokens, output_tokens)

            response_time = int((time.time() - start_time) * 1000)

            return {
                'success': True,
                'response': ai_response,
                'model_used': model_name,
                'urgency_level': urgency,
                'response_time_ms': response_time,
                'cost_estimate': cost,
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens
                }
            }

        except Exception as e:
            logger.error(f"❌ Erreur génération réponse: {e}")
            return {
                'success': False,
                'response': self._get_emergency_response(),
                'model_used': 'fallback',
                'urgency_level': 'critical',
                'response_time_ms': int((time.time() - start_time) * 1000),
                'cost_estimate': 0,
                'error': str(e)
            }

    def _calculate_cost(self, model_config: dict, input_tokens: int, output_tokens: int) -> float:
        """Calcule le coût de la requête"""
        input_cost = (input_tokens / 1000) * model_config['cost_per_1k_input']
        output_cost = (output_tokens / 1000) * model_config['cost_per_1k_output']
        return round(input_cost + output_cost, 8)

    def _get_emergency_response(self) -> str:
        """Réponse d'urgence en cas d'erreur"""
        return """🚨 **Service IA temporairement indisponible**

**Pour une urgence médicale drépanocytaire :**
• **1510** - Urgence nationale Cameroun
• **CHU Yaoundé** - Centre de référence drépanocytose
• **Hôpital Central Yaoundé** - Service urgences
• **Hôpital Laquintinie Douala** - Hématologie

⚠️ En cas de crise douloureuse sévère, consultez immédiatement un médecin.

L'assistant IA sera rétabli rapidement."""

class KidjamoChatbotProduction:
    """Serveur Chatbot Kidjamo pour production AWS"""

    def __init__(self):
        # Configuration Flask
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'kidjamo-prod-secret-2024')

        # CORS
        CORS(self.app, origins=["*"])

        # Base de données
        db_config = {
            'host': os.getenv('DB_HOST', 'kidjamo-dev-postgres-fixed.crgg26e8owiz.eu-west-1.rds.amazonaws.com'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'dbname': os.getenv('DB_NAME', 'kidjamo'),
            'username': os.getenv('DB_USERNAME', 'kidjamo_admin'),
            'password': os.getenv('DB_PASSWORD', 'JBRPp5t!uLqDKJRY')
        }

        try:
            self.db = DatabaseManager(db_config)
            logger.info("✅ Base de données PostgreSQL connectée")
        except Exception as e:
            logger.error(f"❌ Erreur DB: {e}")
            raise

        # Moteur IA
        try:
            self.ai_engine = BedrockAIEngine()
            logger.info("✅ Moteur Bedrock initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur IA: {e}")
            raise

        # Rate limiting simple
        self.rate_limiter = defaultdict(deque)

        # Configuration des routes
        self._setup_routes()

        logger.info("🚀 Serveur Kidjamo Chatbot Production prêt")

    def _check_rate_limit(self, ip: str, limit: int = 60) -> bool:
        """Vérifie les limites de taux"""
        now = time.time()
        window = 60  # 1 minute

        # Nettoyer les anciennes requêtes
        while self.rate_limiter[ip] and self.rate_limiter[ip][0] < now - window:
            self.rate_limiter[ip].popleft()

        # Vérifier la limite
        if len(self.rate_limiter[ip]) >= limit:
            return False

        # Ajouter la nouvelle requête
        self.rate_limiter[ip].append(now)
        return True

    def _setup_routes(self):
        """Configuration des routes API"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check pour ALB/monitoring"""
            try:
                # Test de connexion DB
                with self.db.get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")

                return jsonify({
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'version': '1.0.0-production',
                    'service': 'kidjamo-chatbot',
                    'database': 'connected',
                    'ai_engine': 'bedrock-ready'
                }), 200

            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e)
                }), 500

        @self.app.route('/api/v1/chat', methods=['POST'])
        def chat_endpoint():
            """Endpoint principal pour le chat - API mobile"""

            # Rate limiting
            client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
            if not self._check_rate_limit(client_ip):
                return jsonify({
                    'success': False,
                    'error': 'Trop de requêtes - Limite 60/minute',
                    'retry_after': 60
                }), 429

            try:
                # Validation
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Content-Type application/json requis'
                    }), 400

                data = request.get_json()
                user_message = data.get('message', '').strip()
                session_id = data.get('session_id', str(uuid.uuid4()))
                patient_id = data.get('patient_id')

                if not user_message:
                    return jsonify({
                        'success': False,
                        'error': 'Message vide'
                    }), 400

                if len(user_message) > 2000:
                    return jsonify({
                        'success': False,
                        'error': 'Message trop long (max 2000 caractères)'
                    }), 400

                # Contexte
                context = {
                    'session_id': session_id,
                    'patient_id': patient_id,
                    'user_ip': client_ip,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'timestamp': datetime.now().isoformat()
                }

                # Génération de la réponse IA
                ai_result = self.ai_engine.generate_response(user_message, context)

                # Préparation des données de sauvegarde
                conversation_data = {
                    'session_id': session_id,
                    'user_message': user_message,
                    'ai_response': ai_result['response'],
                    'conversation_type': 'medical_support',
                    'urgency_level': ai_result.get('urgency_level', 'normal'),
                    'model_used': ai_result.get('model_used', 'unknown'),
                    'response_time_ms': ai_result.get('response_time_ms', 0),
                    'cost_estimate': ai_result.get('cost_estimate', 0),
                    'user_ip': client_ip,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'patient_id': patient_id
                }

                # Sauvegarde asynchrone
                try:
                    conversation_id = self.db.save_conversation(conversation_data)
                    self.db.update_session(session_id, patient_id)
                except Exception as e:
                    logger.error(f"❌ Erreur sauvegarde: {e}")

                # Réponse finale
                response_data = {
                    'success': ai_result['success'],
                    'response': ai_result['response'],
                    'session_id': session_id,
                    'conversation_id': conversation_id if 'conversation_id' in locals() else None,
                    'timestamp': datetime.now().isoformat(),
                    'metadata': {
                        'model_used': ai_result.get('model_used'),
                        'urgency_level': ai_result.get('urgency_level'),
                        'response_time_ms': ai_result.get('response_time_ms'),
                        'cost_estimate': ai_result.get('cost_estimate')
                    }
                }

                return jsonify(response_data), 200

            except Exception as e:
                logger.error(f"❌ Erreur chat endpoint: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Erreur interne du serveur',
                    'response': self.ai_engine._get_emergency_response()
                }), 500

        @self.app.route('/api/v1/conversations/<session_id>', methods=['GET'])
        def get_conversation_history(session_id):
            """Récupère l'historique d'une conversation"""
            try:
                limit = request.args.get('limit', 50, type=int)

                sql = """
                SELECT user_message, ai_response, urgency_level, 
                       created_at, conversation_type
                FROM chatbot_conversations 
                WHERE session_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
                """

                with self.db.get_db_connection() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute(sql, (session_id, limit))
                        conversations = cursor.fetchall()

                return jsonify({
                    'success': True,
                    'session_id': session_id,
                    'conversations': [dict(conv) for conv in conversations]
                }), 200

            except Exception as e:
                logger.error(f"❌ Erreur historique: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Erreur récupération historique'
                }), 500

        @self.app.route('/api/v1/metrics', methods=['GET'])
        def get_metrics():
            """Métriques pour monitoring"""
            try:
                sql = """
                SELECT 
                    COUNT(*) as total_conversations,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    AVG(response_time_ms) as avg_response_time,
                    SUM(cost_estimate) as total_cost,
                    urgency_level,
                    COUNT(*) as count_by_urgency
                FROM chatbot_conversations 
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                GROUP BY urgency_level
                """

                with self.db.get_db_connection() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute(sql)
                        metrics = cursor.fetchall()

                return jsonify({
                    'success': True,
                    'period': '24h',
                    'metrics': [dict(m) for m in metrics]
                }), 200

            except Exception as e:
                logger.error(f"❌ Erreur métriques: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Erreur récupération métriques'
                }), 500

        @self.app.route('/', methods=['GET'])
        def index():
            """Page d'accueil - Documentation API"""
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Kidjamo Chatbot API - Production</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                    .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
                    .method { background: #007bff; color: white; padding: 3px 8px; border-radius: 3px; }
                    .success { color: #28a745; }
                    .info { background: #e7f3ff; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0; }
                </style>
            </head>
            <body>
                <h1>🏥 Kidjamo Chatbot API - Production</h1>
                <div class="success">✅ Service opérationnel et prêt pour intégration mobile</div>
                
                <div class="info">
                    <h3>📱 Pour l'équipe mobile :</h3>
                    <p><strong>Endpoint principal :</strong> <code>POST /api/v1/chat</code></p>
                    <p><strong>Format JSON :</strong> <code>{"message": "votre message", "session_id": "uuid", "patient_id": "optional"}</code></p>
                    <p><strong>Rate limit :</strong> 60 requêtes/minute par IP</p>
                </div>
                
                <h2>🔗 Endpoints API</h2>
                
                <div class="endpoint">
                    <span class="method">POST</span> <strong>/api/v1/chat</strong>
                    <p>Conversation principale avec l'IA médicale</p>
                    <p><strong>Body :</strong> <code>{"message": "string", "session_id": "string", "patient_id": "string"}</code></p>
                </div>
                
                <div class="endpoint">
                    <span class="method">GET</span> <strong>/api/v1/conversations/{session_id}</strong>
                    <p>Historique des conversations d'une session</p>
                </div>
                
                <div class="endpoint">
                    <span class="method">GET</span> <strong>/health</strong>
                    <p>Health check pour monitoring AWS</p>
                </div>
                
                <div class="endpoint">
                    <span class="method">GET</span> <strong>/api/v1/metrics</strong>
                    <p>Métriques d'utilisation (24h)</p>
                </div>
                
                <h2>📊 Fonctionnalités</h2>
                <ul>
                    <li>🤖 IA Amazon Bedrock (Claude 3 + Titan)</li>
                    <li>🗄️ Sauvegarde PostgreSQL automatique</li>
                    <li>🚨 Détection d'urgence médicale</li>
                    <li>📈 Monitoring et métriques</li>
                    <li>🔒 Rate limiting et sécurité</li>
                    <li>⚡ Optimisé pour mobile</li>
                </ul>
                
                <div class="info">
                    <h3>🚀 Déploiement AWS :</h3>
                    <p>EC2 + RDS PostgreSQL + Bedrock + ALB</p>
                    <p>Auto-scaling et haute disponibilité</p>
                </div>
            </body>
            </html>
            """)

    def run(self, host='0.0.0.0', port=5000):
        """Lance le serveur"""
        print(f"""
🚀 KIDJAMO CHATBOT PRODUCTION DÉMARRÉ
====================================
🌐 URL: http://{host}:{port}
📱 API Mobile: /api/v1/chat
🗄️ Base: PostgreSQL connectée
🤖 IA: Amazon Bedrock prêt
📊 Monitoring: /health et /metrics
====================================
        """)

        self.app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True
        )

if __name__ == '__main__':
    # Chargement des variables d'environnement
    load_dotenv()

    try:
        chatbot = KidjamoChatbotProduction()
        chatbot.run()
    except Exception as e:
        logger.critical(f"❌ Erreur critique au démarrage: {e}")
        exit(1)
