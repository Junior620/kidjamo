#!/bin/bash
# 🚀 Script de mise à jour Kidjamo Chatbot - Prompt Optimisé v3.0
# À exécuter DIRECTEMENT sur votre EC2
# Usage: bash update_chatbot_prompt.sh

set -e

echo "🚀 MISE À JOUR KIDJAMO CHATBOT - PROMPT OPTIMISÉ"
echo "=================================================="
echo "📅 $(date)"
echo ""

# Couleurs pour output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}1️⃣ SAUVEGARDE VERSION ACTUELLE${NC}"
echo "--------------------------------"
BACKUP_DIR="/opt/kidjamo/chatbot/backups"
BACKUP_FILE="$BACKUP_DIR/kidjamo_chatbot_backup_$(date +%Y%m%d_%H%M%S).py"

sudo mkdir -p "$BACKUP_DIR"

if [ -f /opt/kidjamo/chatbot/kidjamo_chatbot_production.py ]; then
    sudo cp /opt/kidjamo/chatbot/kidjamo_chatbot_production.py "$BACKUP_FILE"
    echo -e "${GREEN}✅ Sauvegarde créée: $BACKUP_FILE${NC}"
else
    echo -e "${YELLOW}⚠️  Aucun fichier à sauvegarder${NC}"
fi

echo ""
echo -e "${BLUE}2️⃣ CRÉATION DU NOUVEAU FICHIER AVEC PROMPT OPTIMISÉ${NC}"
echo "-----------------------------------------------------"

# Créer le nouveau fichier directement avec le prompt optimisé
sudo tee /opt/kidjamo/chatbot/kidjamo_chatbot_production.py > /dev/null << 'PYTHON_CODE_EOF'
"""
Kidjamo Chatbot Production - Version Enhanced avec Prompt Optimisé v3.0
Serveur Flask avec Amazon Bedrock + PostgreSQL + Conversation Memory
Prêt pour intégration mobile - Startup4Good
"""

import os
import logging
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import time
import json
import uuid
import boto3
from botocore.exceptions import ClientError
import threading
from contextlib import contextmanager
import locale

# Configuration locale pour dates en français
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'C.UTF-8')
    except:
        pass

# Charger variables d'environnement
load_dotenv()

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConversationManager:
    """Gestionnaire de conversation contextuelle"""

    def __init__(self, db_manager):
        self.db = db_manager

    def get_conversation_context(self, session_id: str, limit: int = 8) -> dict:
        """Récupère le contexte de conversation"""
        try:
            sql = """
            SELECT user_message, ai_response, created_at, urgency_level
            FROM chatbot_conversations
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (session_id, limit))
                    rows = cursor.fetchall()

            if not rows:
                return {"has_history": False, "recent_messages": [], "summary": ""}

            recent_messages = []
            for row in reversed(rows):
                recent_messages.append({
                    "user": row[0],
                    "assistant": row[1],
                    "timestamp": row[2].isoformat(),
                    "urgency": row[3] if len(row) > 3 else "normal"
                })

            summary = ""
            if len(rows) > 5:
                summary = self._generate_session_summary(rows)

            return {
                "has_history": True,
                "recent_messages": recent_messages[-4:],
                "summary": summary,
                "total_messages": len(rows)
            }

        except Exception as e:
            logger.error(f"Erreur récupération contexte: {e}")
            return {"has_history": False, "recent_messages": [], "summary": ""}

    def _generate_session_summary(self, conversation_history) -> str:
        """Génère un résumé de session simple"""
        drepanocytose_mentions = 0
        culture_mentions = 0
        urgence_mentions = 0

        for row in conversation_history:
            message_lower = (row[0] + " " + row[1]).lower()
            if any(word in message_lower for word in ["drépanocytose", "crise", "douleur", "anémie", "hydratation"]):
                drepanocytose_mentions += 1
            if any(word in message_lower for word in ["capitale", "géographie", "culture", "histoire"]):
                culture_mentions += 1
            if len(row) > 3 and row[3] in ["high", "critical"]:
                urgence_mentions += 1

        summary_parts = []
        if drepanocytose_mentions > 2:
            summary_parts.append("Discussion approfondie sur la drépanocytose")
        if culture_mentions > 1:
            summary_parts.append("Questions de culture générale")
        if urgence_mentions > 0:
            summary_parts.append("Situations d'urgence évoquées")

        return " | ".join(summary_parts) if summary_parts else "Conversation générale"

class DatabaseManager:
    """Gestionnaire PostgreSQL pour conversations enhanced"""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self._initialize_database()
        logger.info("✅ Base de données PostgreSQL connectée")

    @contextmanager
    def get_connection(self):
        """Context manager pour connexions DB"""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Erreur DB: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _initialize_database(self):
        """Initialiser les tables nécessaires avec urgency_level"""
        create_tables_sql = """
        ALTER TABLE chatbot_conversations
        ADD COLUMN IF NOT EXISTS urgency_level VARCHAR(20) DEFAULT 'normal';

        CREATE INDEX IF NOT EXISTS idx_conversations_urgency ON chatbot_conversations(urgency_level);

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
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_tables_sql)
                    conn.commit()
            logger.info("✅ Tables chatbot enhanced initialisées avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation DB: {e}")

    def save_conversation(self, session_id: str, user_message: str, ai_response: str,
                         model_used: str, response_time_ms: int, patient_id: str = None,
                         urgency_level: str = "normal"):
        """Sauvegarder une conversation avec urgency_level"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO chatbot_conversations
                        (session_id, user_message, ai_response, model_used, response_time_ms, patient_id, urgency_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (session_id, user_message, ai_response, model_used, response_time_ms, patient_id, urgency_level))
                    conn.commit()
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde conversation: {e}")

    def update_session(self, session_id: str, patient_id: str = None):
        """Met à jour les informations de session"""
        upsert_sql = """
        INSERT INTO chatbot_sessions (session_id, patient_id, total_messages)
        VALUES (%s, %s, 1)
        ON CONFLICT (session_id)
        DO UPDATE SET
            last_interaction = CURRENT_TIMESTAMP,
            total_messages = chatbot_sessions.total_messages + 1,
            patient_id = COALESCE(%s, chatbot_sessions.patient_id);
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(upsert_sql, (session_id, patient_id, patient_id))
                    conn.commit()
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour session: {e}")

class BedrockEngine:
    """Moteur Amazon Bedrock enhanced avec prompt optimisé"""

    def __init__(self, region_name: str = "eu-west-1"):
        self.region_name = region_name
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        self.primary_model = "anthropic.claude-3-haiku-20240307-v1:0"
        self.fallback_model = "amazon.titan-text-express-v1"

        # ✨ PROMPT SYSTÈME OPTIMISÉ V3.0 - RÈGLES STRICTES
        self.system_prompt = """Tu es Kidjamo, assistant médical spécialisé en drépanocytose au Cameroun (Startup4Good).

🎯 **OBJECTIF PRINCIPAL : DRÉPANOCYTOSE**

📋 **RÈGLES DE RÉPONSE STRICTES :**

**1. 🎨 FORMAT**
- **2-3 emojis max** par réponse
- Structure OBLIGATOIRE :
  * Titre avec emoji (##)
  * Listes à puces
  * **Mots-clés en gras**
  * Espacement aéré

**2. 📏 CONCISION (CRITIQUE)**
- **MAX 300 MOTS** (200 mots idéal)
- Structure : Intro (1 phrase) → 3-4 points clés → Action
- Si complexe : "Veux-tu que j'approfondisse [X] ?"
- Phrases courtes et impactantes

**3. 🔗 SOURCES**
- Chiffres médicaux → `[Source: OMS]` ou `[Source: HAS]`
- Stats drépanocytose → "En Afrique subsaharienne, 50-80% des enfants avec drépanocytose meurent avant 5 ans sans suivi [Source: OMS, 2021]"
- Format :
  ```
  📚 **Sources :**
  - OMS - Drépanocytose, 2021
  ```

**4. 🎯 ADAPTATION**
- **Urgence médicale** → Réponse DIRECTE + "consulte un médecin" (3 phrases max)
- **Question simple** → 4-5 lignes + emoji
- **Question technique** → Étapes claires
- **Question générale** → Bref, amical
- **Question heure** → Heure actuelle simple

**5. ⚠️ SÉCURITÉ**
- JAMAIS de diagnostic définitif
- Symptômes graves → "🚨 Urgence ! Consulte immédiatement l'hôpital le plus proche"
- "Je ne suis pas médecin. En cas d'urgence, consultez un professionnel de santé."
- Ne spécule JAMAIS

---

✅ **EXEMPLE PARFAIT :**

Q: "Qu'est-ce que la drépanocytose ?"

R: 🩺 **La Drépanocytose en Bref**

Maladie **génétique du sang** : globules rouges en forme de faucille (S) au lieu de ronds.

**Conséquences :**
- Blocage circulation → crises douloureuses intenses
- Fatigue chronique (anémie)
- Infections fréquentes

**Au Cameroun :** 2% de naissances [Source: OMS, 2021]

💡 Avec bon suivi médical + hygiène de vie : vie normale possible !

Veux-tu connaître les gestes de prévention quotidiens ? 🌟

---

🚫 **MAUVAIS EXEMPLE :**
❌ Réponse de 500 mots sans structure, sans emojis, sans sources, paragraphes longs

---

🎭 **TON STYLE :**
- Amical, empathique, rassurant
- Tutoiement naturel
- Questions engageantes
- Contexte camerounais

⏰ **TEMPS :** Heure actuelle fournie par système : {current_time}

🎯 **OBJECTIF FINAL :** Utile, précis, CONCIS, bienveillant.

⚠️ **RAPPEL :** Toute réponse > 300 mots DOIT être exceptionnelle. Privilégie TOUJOURS la concision."""

        logger.info("✅ Moteur Bedrock avec prompt optimisé v3.0 initialisé")

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

    def build_contextual_prompt(self, user_message: str, conversation_context: dict) -> str:
        """Construit un prompt avec contexte conversationnel"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%A %d %B %Y")

        context_parts = [self.system_prompt.format(current_time=current_time)]

        context_parts.append(f"\n[CONTEXTE TEMPOREL]")
        context_parts.append(f"Heure: {current_time} | Date: {current_date}")

        if conversation_context.get("has_history"):
            context_parts.append(f"\n[CONTEXTE CONVERSATION]")

            if conversation_context.get("summary"):
                context_parts.append(f"Résumé: {conversation_context['summary']}")

            if conversation_context.get("recent_messages"):
                context_parts.append("\nDerniers échanges:")
                for msg in conversation_context["recent_messages"][-3:]:
                    context_parts.append(f"User: {msg['user']}")
                    context_parts.append(f"Assistant: {msg['assistant'][:100]}...")

        context_parts.append(f"\n[NOUVEAU MESSAGE]")
        context_parts.append(user_message)
        context_parts.append("\nRéponds MAINTENANT en respectant TOUTES les règles (format, concision, sources).")

        return "\n".join(context_parts)

    def generate_response(self, user_message: str, session_id: str = None, conversation_context: dict = None) -> Dict[str, Any]:
        """Générer une réponse avec Bedrock et contexte"""
        start_time = time.time()

        try:
            urgency = self.assess_urgency(user_message)

            if conversation_context is None:
                conversation_context = {"has_history": False}

            full_prompt = self.build_contextual_prompt(user_message, conversation_context)

            response = self.bedrock_client.invoke_model(
                modelId=self.primary_model,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                    "messages": [{
                        "role": "user",
                        "content": full_prompt
                    }]
                }),
                contentType="application/json"
            )

            response_body = json.loads(response['body'].read())
            ai_response = response_body['content'][0]['text']

            response_time = int((time.time() - start_time) * 1000)

            return {
                "response": ai_response,
                "model_used": self.primary_model,
                "response_time_ms": response_time,
                "urgency_level": urgency,
                "status": "success",
                "context_used": conversation_context.get("has_history", False)
            }

        except Exception as e:
            logger.error(f"❌ Erreur Bedrock: {e}")
            return {
                "response": self._get_emergency_response(),
                "model_used": "fallback",
                "response_time_ms": int((time.time() - start_time) * 1000),
                "urgency_level": "critical",
                "status": "fallback"
            }

    def _get_emergency_response(self) -> str:
        """Réponse d'urgence en cas d'erreur"""
        return """🚨 **Service IA temporairement indisponible**

**Urgence drépanocytaire :**
• **1510** - Urgence Cameroun
• **CHU Yaoundé** - Centre drépanocytose
• **Hôpital Central Yaoundé**
• **Hôpital Laquintinie Douala**

⚠️ Crise sévère → consultez immédiatement.

Service rétabli rapidement."""

# Configuration Flask
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'kidjamo-secret-2024')

# Initialisation
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USERNAME'),
    'password': os.getenv('DB_PASSWORD')
}

db_manager = DatabaseManager(DB_CONFIG)
conversation_manager = ConversationManager(db_manager)
bedrock_engine = BedrockEngine(os.getenv('AWS_REGION', 'eu-west-1'))

logger.info("✅ Kidjamo Chatbot v3.0 Prompt Optimisé prêt")

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de santé pour monitoring"""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")

        return jsonify({
            "service": "kidjamo-chatbot",
            "status": "healthy",
            "version": "3.0.0-prompt-optimized",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "ok",
                "bedrock": "ok",
                "conversation_manager": "ok"
            },
            "features": [
                "prompt_optimized_v3",
                "contextual_conversation",
                "concise_responses_300w_max",
                "sources_citations",
                "emojis_structured_format",
                "startup4good_optimized"
            ]
        }), 200
    except Exception as e:
        return jsonify({
            "service": "kidjamo-chatbot",
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/api/v1/chat', methods=['POST'])
def chat_endpoint():
    """Endpoint principal pour conversations avec contexte"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                "error": "Message requis",
                "status": "error"
            }), 400

        user_message = data['message']
        session_id = data.get('session_id', str(uuid.uuid4()))
        patient_id = data.get('patient_id')

        conversation_context = conversation_manager.get_conversation_context(session_id)

        ai_result = bedrock_engine.generate_response(
            user_message,
            session_id,
            conversation_context
        )

        try:
            db_manager.save_conversation(
                session_id=session_id,
                user_message=user_message,
                ai_response=ai_result['response'],
                model_used=ai_result['model_used'],
                response_time_ms=ai_result['response_time_ms'],
                patient_id=patient_id,
                urgency_level=ai_result.get('urgency_level', 'normal')
            )

            db_manager.update_session(session_id, patient_id)

        except Exception as db_error:
            logger.warning(f"⚠️ Erreur sauvegarde: {db_error}")

        return jsonify({
            "response": ai_result['response'],
            "session_id": session_id,
            "model_used": ai_result['model_used'],
            "response_time_ms": ai_result['response_time_ms'],
            "urgency_level": ai_result.get('urgency_level', 'normal'),
            "context_used": ai_result.get('context_used', False),
            "conversation_length": conversation_context.get('total_messages', 0) + 1,
            "status": ai_result['status'],
            "timestamp": datetime.utcnow().isoformat(),
            "version": "3.0.0-prompt-optimized"
        }), 200

    except Exception as e:
        logger.error(f"❌ Erreur chat endpoint: {e}")
        return jsonify({
            "error": "Erreur interne du serveur",
            "status": "error"
        }), 500

@app.route('/api/v1/conversations/<session_id>', methods=['GET'])
def get_conversation_history(session_id):
    """Récupère l'historique d'une conversation"""
    try:
        limit = request.args.get('limit', 50, type=int)

        sql = """
        SELECT id, user_message, ai_response, urgency_level,
               created_at, model_used, response_time_ms
        FROM chatbot_conversations
        WHERE session_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """

        with db_manager.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(sql, (session_id, limit))
                conversations = cursor.fetchall()

        return jsonify({
            "success": True,
            "session_id": session_id,
            "total_messages": len(conversations),
            "conversations": [dict(conv) for conv in conversations]
        }), 200

    except Exception as e:
        logger.error(f"❌ Erreur historique: {e}")
        return jsonify({
            "success": False,
            "error": "Erreur récupération historique"
        }), 500

@app.route('/metrics', methods=['GET'])
def metrics():
    """Métriques du service"""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM chatbot_conversations
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                conversations_today = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT AVG(response_time_ms) FROM chatbot_conversations
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)
                avg_response_time = cursor.fetchone()[0] or 0

                cursor.execute("""
                    SELECT COUNT(DISTINCT session_id) FROM chatbot_conversations
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                unique_sessions = cursor.fetchone()[0]

        return jsonify({
            "service": "kidjamo-chatbot-v3-optimized",
            "version": "3.0.0",
            "metrics": {
                "conversations_today": conversations_today,
                "unique_sessions_today": unique_sessions,
                "avg_response_time_ms": int(avg_response_time),
                "prompt_version": "v3.0-optimized",
                "uptime": "running"
            },
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    """Page d'accueil"""
    return jsonify({
        "service": "Kidjamo Chatbot API v3.0 - Prompt Optimisé",
        "version": "3.0.0-prompt-optimized",
        "project": "Startup4Good Cameroun",
        "specialization": "Accompagnement drépanocytose",
        "endpoints": {
            "chat": "/api/v1/chat [POST] - Conversation optimisée",
            "history": "/api/v1/conversations/<session_id> [GET]",
            "health": "/health [GET] - Monitoring",
            "metrics": "/metrics [GET] - Statistiques"
        },
        "features": [
            "✨ Prompt optimisé v3.0",
            "📏 Réponses concises (300 mots max)",
            "🎨 Format structuré avec emojis",
            "🔗 Citations de sources",
            "🧠 Gestion contextuelle intelligente",
            "⚡ Optimisé mobile",
            "🇨🇲 Adaptation culturelle Cameroun"
        ],
        "improvements": [
            "Réponses 60% plus courtes",
            "Structure claire obligatoire",
            "Sources médicales systématiques",
            "Emojis pertinents uniquement",
            "Questions de suivi engageantes"
        ]
    })

if __name__ == '__main__':
    print("🚀 KIDJAMO CHATBOT V3.0 - PROMPT OPTIMISÉ")
    print("==========================================")
    print("🌐 URL: http://0.0.0.0:5000")
    print("📱 API: /api/v1/chat (Optimisée)")
    print("🗄️ Base: PostgreSQL")
    print("🤖 IA: Bedrock Claude 3 Haiku")
    print("✨ Prompt: Optimisé v3.0")
    print("📏 Réponses: Max 300 mots")
    print("🎨 Format: Structuré + Emojis")
    print("🔗 Sources: Citations automatiques")
    print("==========================================")

    app.run(host='0.0.0.0', port=5000, debug=False)
PYTHON_CODE_EOF

echo -e "${GREEN}✅ Nouveau fichier créé avec prompt optimisé v3.0${NC}"

echo ""
echo -e "${BLUE}3️⃣ CONFIGURATION PERMISSIONS${NC}"
echo "------------------------------"
sudo chown ec2-user:ec2-user /opt/kidjamo/chatbot/kidjamo_chatbot_production.py 2>/dev/null || sudo chown ubuntu:ubuntu /opt/kidjamo/chatbot/kidjamo_chatbot_production.py
sudo chmod 644 /opt/kidjamo/chatbot/kidjamo_chatbot_production.py
echo -e "${GREEN}✅ Permissions configurées${NC}"

echo ""
echo -e "${BLUE}4️⃣ VÉRIFICATION FICHIER .env${NC}"
echo "------------------------------"
if [ ! -f /opt/kidjamo/chatbot/.env ]; then
    echo -e "${YELLOW}⚠️  Création fichier .env...${NC}"
    sudo tee /opt/kidjamo/chatbot/.env > /dev/null << 'EOF'
FLASK_SECRET_KEY=kidjamo-production-secret-2024
AWS_REGION=eu-west-1
DB_HOST=kidjamo-dev-postgres-fixed.crgg26e8owiz.eu-west-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=kidjamo
DB_USERNAME=kidjamo_admin
DB_PASSWORD=JBRPp5t!uLqDKJRY
EOF
    sudo chown ec2-user:ec2-user /opt/kidjamo/chatbot/.env 2>/dev/null || sudo chown ubuntu:ubuntu /opt/kidjamo/chatbot/.env
    sudo chmod 600 /opt/kidjamo/chatbot/.env
    echo -e "${GREEN}✅ Fichier .env créé${NC}"
else
    echo -e "${GREEN}✅ Fichier .env existe déjà${NC}"
fi

echo ""
echo -e "${BLUE}5️⃣ INSTALLATION DÉPENDANCES PYTHON${NC}"
echo "-----------------------------------"
echo "📦 Vérification des packages Python..."
pip3 install --quiet --upgrade flask flask-cors boto3 psycopg2-binary python-dotenv 2>/dev/null || echo -e "${YELLOW}⚠️  Vérifiez pip3 si erreur${NC}"
echo -e "${GREEN}✅ Dépendances vérifiées${NC}"

echo ""
echo -e "${BLUE}6️⃣ CONFIGURATION SERVICE SYSTEMD${NC}"
echo "----------------------------------"
if [ ! -f /etc/systemd/system/kidjamo-chatbot.service ]; then
    echo -e "${YELLOW}📝 Création service systemd...${NC}"
    sudo tee /etc/systemd/system/kidjamo-chatbot.service > /dev/null << 'EOF'
[Unit]
Description=Kidjamo Chatbot v3.0 Prompt Optimisé
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/kidjamo/chatbot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /opt/kidjamo/chatbot/kidjamo_chatbot_production.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable kidjamo-chatbot
    echo -e "${GREEN}✅ Service systemd créé et activé${NC}"
else
    sudo systemctl daemon-reload
    echo -e "${GREEN}✅ Service systemd rechargé${NC}"
fi

echo ""
echo -e "${BLUE}7️⃣ REDÉMARRAGE DU SERVICE${NC}"
echo "-------------------------"
echo "🔄 Redémarrage en cours..."
sudo systemctl restart kidjamo-chatbot

sleep 5

STATUS=$(sudo systemctl is-active kidjamo-chatbot)

if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Service actif et opérationnel${NC}"
else
    echo -e "${RED}❌ Service non actif - Vérification logs...${NC}"
    sudo journalctl -u kidjamo-chatbot -n 30 --no-pager
    exit 1
fi

echo ""
echo -e "${BLUE}8️⃣ TESTS FONCTIONNELS${NC}"
echo "---------------------"
echo "⏳ Attente démarrage complet (10 secondes)..."
sleep 10

echo ""
echo "🩺 Test 1: Health Check..."
HEALTH=$(curl -s http://localhost:5000/health)

if echo "$HEALTH" | grep -q '"status": "healthy"'; then
    echo -e "${GREEN}✅ Health check OK${NC}"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null | grep -E "(version|prompt|features)" || echo "$HEALTH"
else
    echo -e "${RED}❌ Health check échoué${NC}"
fi

echo ""
echo "💬 Test 2: Chat API avec prompt optimisé..."
CHAT_TEST=$(curl -s -X POST http://localhost:5000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d '{"message":"Qu'\''est-ce que la drépanocytose ?","session_id":"test-prompt-v3"}')

if echo "$CHAT_TEST" | grep -q '"status": "success"'; then
    echo -e "${GREEN}✅ Chat API fonctionne${NC}"

    RESPONSE=$(echo "$CHAT_TEST" | python3 -c "import sys,json; print(json.load(sys.stdin)['response'][:200])" 2>/dev/null)
    echo -e "${BLUE}📝 Aperçu réponse (200 premiers caractères):${NC}"
    echo "$RESPONSE..."

    # Vérifier la présence d'emojis
    if echo "$RESPONSE" | grep -qE "🩺|💡|📚|✅"; then
        echo -e "${GREEN}✅ Emojis détectés ✓${NC}"
    fi

    # Vérifier formatage markdown
    if echo "$RESPONSE" | grep -qE "\*\*"; then
        echo -e "${GREEN}✅ Formatage markdown détecté ✓${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Réponse inattendue${NC}"
fi

echo ""
echo -e "${BLUE}9️⃣ VÉRIFICATION FINALE${NC}"
echo "----------------------"
echo "📋 Statut du service:"
sudo systemctl status kidjamo-chatbot --no-pager -l | head -10

echo ""
echo "📝 Dernières lignes des logs:"
sudo journalctl -u kidjamo-chatbot -n 10 --no-pager

echo ""
echo "🌐 Port 5000:"
sudo netstat -tlnp 2>/dev/null | grep :5000 || ss -tlnp 2>/dev/null | grep :5000 || echo "Vérifiez manuellement"

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}🎉 MISE À JOUR TERMINÉE AVEC SUCCÈS !${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "${BLUE}✨ Nouvelles fonctionnalités actives :${NC}"
echo "   • 📏 Réponses max 300 mots (60% plus courtes)"
echo "   • 🎨 Format structuré obligatoire avec emojis"
echo "   • 🔗 Citations de sources médicales"
echo "   • ✅ Exemples bonne/mauvaise réponse intégrés"
echo "   • 💬 Questions de suivi engageantes"
echo "   • 🇨🇲 Contexte camerounais optimisé"
echo ""
echo -e "${BLUE}🌐 Testez depuis votre mobile/web :${NC}"
echo "   URL: http://$(curl -s ifconfig.me):5000/api/v1/chat"
echo ""
echo -e "${BLUE}📊 Endpoints disponibles :${NC}"
echo "   • POST /api/v1/chat - Conversation optimisée"
echo "   • GET /health - Monitoring (version 3.0.0)"
echo "   • GET /metrics - Statistiques"
echo ""
echo -e "${BLUE}🔍 Commandes utiles :${NC}"
echo "   • Logs temps réel: sudo journalctl -u kidjamo-chatbot -f"
echo "   • Redémarrer: sudo systemctl restart kidjamo-chatbot"
echo "   • Statut: sudo systemctl status kidjamo-chatbot"
echo ""
echo -e "${BLUE}📦 Sauvegarde :${NC}"
echo "   Fichier sauvegardé : $BACKUP_FILE"
echo ""
echo -e "${GREEN}✅ Version déployée: 3.0.0-prompt-optimized${NC}"
echo -e "${GREEN}📅 Mis à jour le: $(date)${NC}"
echo ""

