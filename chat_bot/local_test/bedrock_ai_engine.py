"""
Amazon Bedrock Engine - Alternative professionnelle à Gemini Flash
Support multi-modèles avec Claude, Llama, et Titan
"""

import boto3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

class BedrockAIEngine:
    """Moteur IA Amazon Bedrock pour production médicale"""

    def __init__(self):
        # Configuration AWS
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')

        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("Clés AWS non trouvées dans les variables d'environnement")

        # Initialisation client Bedrock
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            logger.info(f"Client Bedrock initialisé dans la région {self.aws_region}")
        except Exception as e:
            logger.error(f"Erreur initialisation Bedrock: {e}")
            raise

        # Configuration des modèles disponibles
        self.available_models = {
            "claude-3-haiku": {
                "id": "anthropic.claude-3-haiku-20240307-v1:0",
                "max_tokens": 4096,
                "cost_per_1k_input": 0.00025,  # $0.25/1M tokens
                "cost_per_1k_output": 0.00125,  # $1.25/1M tokens
                "recommended": True,
                "use_case": "Rapide et économique"
            },
            "claude-3-sonnet": {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "max_tokens": 4096,
                "cost_per_1k_input": 0.003,    # $3/1M tokens
                "cost_per_1k_output": 0.015,   # $15/1M tokens
                "recommended": False,
                "use_case": "Qualité supérieure"
            },
            "llama-3-8b": {
                "id": "meta.llama3-8b-instruct-v1:0",
                "max_tokens": 2048,
                "cost_per_1k_input": 0.0003,   # $0.3/1M tokens
                "cost_per_1k_output": 0.0006,  # $0.6/1M tokens
                "recommended": True,
                "use_case": "Open source, économique"
            },
            "titan-text": {
                "id": "amazon.titan-text-express-v1",
                "max_tokens": 8192,
                "cost_per_1k_input": 0.0008,   # $0.8/1M tokens
                "cost_per_1k_output": 0.0016,  # $1.6/1M tokens
                "recommended": False,
                "use_case": "Amazon natif"
            }
        }

        # Modèle par défaut (recommandé pour médical)
        self.primary_model = "claude-3-haiku"
        self.fallback_model = "llama-3-8b"

        # Configuration production
        self.request_timeout = 30
        self.max_retries = 3
        self.conversation_contexts = {}

        # Cache et métriques
        self.response_cache = {}
        self.cache_ttl = 1800  # 30 minutes
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cost_estimate': 0.0,
            'models_used': {}
        }

        logger.info(f"BedrockAIEngine initialisé avec modèle principal: {self.primary_model}")

    def process_message_with_ai(self, user_message: str, context: Dict) -> Dict:
        """Traite le message avec Amazon Bedrock"""

        session_id = context.get('session_id', 'default')
        self.metrics['total_requests'] += 1

        try:
            # NOUVEAU: Vérifier d'abord si c'est une question simple (heure, salutation, etc.)
            simple_response = self._handle_simple_questions(user_message, session_id)
            if simple_response:
                logger.info(f"Question simple détectée pour session {session_id}")
                return simple_response

            # Vérification du cache
            cache_key = self._get_cache_key(user_message, session_id)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                logger.info(f"Réponse servie depuis le cache pour session {session_id}")
                return cached_response

            # Sélection du modèle selon l'urgence
            model_name = self._select_model_for_context(user_message, context)
            model_config = self.available_models[model_name]

            # Construire le prompt médical spécialisé
            system_prompt = self._build_medical_prompt(user_message, session_id, context)

            # Générer la réponse avec le modèle sélectionné
            response = self._generate_with_bedrock(
                model_name,
                model_config["id"],
                system_prompt,
                user_message
            )

            if response:
                # Construire la réponse finale
                final_response = {
                    "response": self._format_response_as_html(response["content"], user_message),
                    "conversation_type": self._detect_conversation_type(user_message),
                    "source": "amazon-bedrock",
                    "model_used": model_name,
                    "model_id": model_config["id"],
                    "raw_response": response["content"],
                    "success": True,
                    "cached": False,
                    "cost_estimate": response["cost"],
                    "tokens_used": response.get("tokens", {})
                }

                # Stocker en cache
                self._store_in_cache(cache_key, final_response)

                # Sauvegarder le contexte
                self._save_conversation_context(session_id, user_message, response["content"])

                # Mettre à jour les métriques
                self.metrics['successful_requests'] += 1
                self.metrics['cost_estimate'] += response["cost"]
                self.metrics['models_used'][model_name] = self.metrics['models_used'].get(model_name, 0) + 1

                logger.info(f"Réponse Bedrock générée avec {model_name} pour session {session_id}")
                return final_response
            else:
                return self._fallback_response(user_message, "bedrock_error")

        except Exception as e:
            logger.error(f"Erreur critique Bedrock: {e}")
            self.metrics['failed_requests'] += 1
            return self._fallback_response(user_message, "system_error")

    def _select_model_for_context(self, user_message: str, context: Dict) -> str:
        """Sélectionne le modèle optimal selon le contexte"""

        urgency_level = context.get('urgency_level', 'normal')
        message_lower = user_message.lower()

        # Pour les urgences médicales critiques -> Claude Haiku (rapide et fiable)
        if urgency_level == 'critical' or any(word in message_lower for word in ["poitrine", "respir", "8/10", "9/10", "10/10"]):
            return "claude-3-haiku"

        # Pour les questions complexes -> Claude Haiku (meilleure compréhension)
        elif len(user_message) > 200 or "comment" in message_lower:
            return "claude-3-haiku"

        # Pour les questions simples -> Llama (économique)
        else:
            return "llama-3-8b"

    def _generate_with_bedrock(self, model_name: str, model_id: str, system_prompt: str, user_message: str) -> Optional[Dict]:
        """Génère une réponse avec un modèle Bedrock spécifique"""

        try:
            model_config = self.available_models[model_name]

            # Construire le payload selon le type de modèle
            if "claude" in model_id:
                payload = self._build_claude_payload(system_prompt, user_message, model_config)
            elif "llama" in model_id:
                payload = self._build_llama_payload(system_prompt, user_message, model_config)
            elif "titan" in model_id:
                payload = self._build_titan_payload(system_prompt, user_message, model_config)
            else:
                raise ValueError(f"Type de modèle non supporté: {model_id}")

            # Appel API Bedrock avec retry
            response = self._make_bedrock_call_with_retry(model_id, payload)

            if response:
                # Parser la réponse selon le type de modèle
                parsed_response = self._parse_model_response(model_id, response)

                # Calculer le coût estimé
                cost = self._calculate_cost(model_config, parsed_response.get("tokens", {}))

                return {
                    "content": parsed_response["content"],
                    "cost": cost,
                    "tokens": parsed_response.get("tokens", {})
                }

        except Exception as e:
            logger.error(f"Erreur génération {model_name}: {e}")
            return None

    def _build_claude_payload(self, system_prompt: str, user_message: str, config: Dict) -> Dict:
        """Construit le payload pour Claude"""
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": min(config["max_tokens"], 800),
            "temperature": 0.3,
            "top_p": 0.8,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        }

    def _build_llama_payload(self, system_prompt: str, user_message: str, config: Dict) -> Dict:
        """Construit le payload pour Llama"""
        full_prompt = f"{system_prompt}\n\nHuman: {user_message}\n\nAssistant:"

        return {
            "prompt": full_prompt,
            "max_gen_len": min(config["max_tokens"], 600),
            "temperature": 0.3,
            "top_p": 0.8
        }

    def _build_titan_payload(self, system_prompt: str, user_message: str, config: Dict) -> Dict:
        """Construit le payload pour Titan"""
        full_prompt = f"{system_prompt}\n\nQuestion: {user_message}\nRéponse:"

        return {
            "inputText": full_prompt,
            "textGenerationConfig": {
                "maxTokenCount": min(config["max_tokens"], 700),
                "temperature": 0.3,
                "topP": 0.8
            }
        }

    def _make_bedrock_call_with_retry(self, model_id: str, payload: Dict) -> Optional[Dict]:
        """Effectue l'appel Bedrock avec retry automatique"""

        for attempt in range(self.max_retries):
            try:
                response = self.bedrock_client.invoke_model(
                    modelId=model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(payload)
                )

                response_body = json.loads(response['body'].read())
                return response_body

            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ThrottlingException':
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"Throttling Bedrock - Attente {wait_time}s (tentative {attempt + 1})")
                    time.sleep(wait_time)
                elif error_code == 'ValidationException':
                    logger.error(f"Erreur validation Bedrock: {e}")
                    break
                else:
                    logger.error(f"Erreur Bedrock {error_code}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Erreur réseau Bedrock - Tentative {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def _parse_model_response(self, model_id: str, response: Dict) -> Dict:
        """Parse la réponse selon le type de modèle"""

        try:
            if "claude" in model_id:
                content = response["content"][0]["text"]
                tokens = {
                    "input": response.get("usage", {}).get("input_tokens", 0),
                    "output": response.get("usage", {}).get("output_tokens", 0)
                }
            elif "llama" in model_id:
                content = response["generation"]
                tokens = {
                    "input": response.get("prompt_token_count", 0),
                    "output": response.get("generation_token_count", 0)
                }
            elif "titan" in model_id:
                content = response["results"][0]["outputText"]
                tokens = {
                    "input": response.get("inputTextTokenCount", 0),
                    "output": response.get("results", [{}])[0].get("tokenCount", 0)
                }
            else:
                raise ValueError(f"Parser non disponible pour {model_id}")

            return {
                "content": content.strip(),
                "tokens": tokens
            }

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Erreur parsing réponse {model_id}: {e}")
            return {"content": "Erreur de traitement de la réponse", "tokens": {}}

    def _calculate_cost(self, model_config: Dict, tokens: Dict) -> float:
        """Calcule le coût estimé de la requête"""
        try:
            input_tokens = tokens.get("input", 0)
            output_tokens = tokens.get("output", 0)

            input_cost = (input_tokens / 1000) * model_config["cost_per_1k_input"]
            output_cost = (output_tokens / 1000) * model_config["cost_per_1k_output"]

            return round(input_cost + output_cost, 6)
        except:
            return 0.0

    def _build_medical_prompt(self, user_message: str, session_id: str, context: Dict) -> str:
        """Construit un prompt médical contextualisé pour Bedrock"""

        # Informations patient si disponibles
        patient_info = context.get('patient_info', {})
        age = patient_info.get('age', 'Non spécifié')

        base_prompt = f"""Tu es Kidjamo Assistant, un assistant médical AI spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun.

CONTEXTE PATIENT:
- Âge: {age}
- Session: {session_id}
- Niveau d'urgence: {context.get('urgency_level', 'normal')}

PROTOCOLE MÉDICAL STRICT:
- Tu ne remplaces JAMAIS un médecin qualifié
- URGENCE VITALE si: douleur >7/10, difficultés respiratoires, fièvre >38.5°C
- En urgence: directive IMMÉDIATE vers services d'urgence camerounais
- Domaine STRICT: drépanocytose uniquement
- Réponds en français simple et accessible

SERVICES D'URGENCE CAMEROUN:
- 1510 (Urgence nationale Cameroun)
- Hôpital Central Yaoundé - Urgences
- Hôpital Général Douala - Service d'urgence  
- CHU Yaoundé - Centre référence drépanocytose

CENTRES SPÉCIALISÉS:
- CHU Yaoundé - Hématologie spécialisée
- Hôpital Laquintinie Douala - Suivi drépanocytose
- Centre Pasteur Cameroun - Expertise drépanocytose

MÉDICAMENTS DRÉPANOCYTOSE:
- Hydroxyurée (Siklos) - Traitement de fond
- Antalgiques (paracétamol, anti-inflammatoires)
- Acide folique - Supplément vital
- Antibiotiques préventifs

INSTRUCTIONS DE RÉPONSE:
- Sois empathique et rassurant
- Structure avec des émojis (🚨 🩺 💊)
- Si urgence: priorise ABSOLUMENT la sécurité
- Donne des conseils pratiques et précis
- Termine par une question de suivi si approprié"""

        # Ajouter contexte conversation récente
        if session_id in self.conversation_contexts:
            recent = self.conversation_contexts[session_id][-2:]  # 2 derniers échanges
            if recent:
                base_prompt += "\n\nCONTEXTE CONVERSATION RÉCENTE:\n"
                for ctx in recent:
                    base_prompt += f"Patient: {ctx['user']}\nAssistant: {ctx['bot'][:100]}...\n"

        return base_prompt

    def _detect_conversation_type(self, message: str) -> str:
        """Détecte le type de conversation avec analyse avancée"""
        message_lower = message.lower()

        # Mots-clés d'urgence critique
        critical_keywords = ["mal", "poitrine", "respir", "aide", "urgent", "grave", "intense", "8/10", "9/10", "10/10"]
        pain_keywords = ["douleur", "mal", "/10", "souffre", "crise", "insupportable"]
        medication_keywords = ["médicament", "siklos", "traitement", "pilule", "dose", "oubli"]

        if any(keyword in message_lower for keyword in critical_keywords):
            return "emergency"
        elif any(keyword in message_lower for keyword in pain_keywords):
            return "pain_management"
        elif any(keyword in message_lower for keyword in medication_keywords):
            return "medication"
        else:
            return "general"

    def _format_response_as_html(self, ai_response: str, user_message: str) -> str:
        """Formate la réponse IA en HTML sécurisé"""

        # Détection d'urgence
        is_emergency = any(word in user_message.lower() for word in ["mal", "poitrine", "respir", "aide", "urgent"])

        if is_emergency:
            css_class = "response-section emergency-alert"
            icon = "fas fa-exclamation-triangle"
        else:
            css_class = "response-section medical-info"
            icon = "fas fa-user-md"

        # Nettoyage sécurisé du contenu
        import html
        safe_response = html.escape(ai_response)

        # Conversion markdown basique
        safe_response = safe_response.replace('\n\n', '</p><p>')
        safe_response = safe_response.replace('**', '<strong>').replace('**', '</strong>')

        html_response = f"""
        <div class="{css_class}">
            <h3><i class="{icon}"></i> Kidjamo Assistant</h3>
            <p>{safe_response}</p>
            <div class="bedrock-footer">
                <small>Réponse générée par Amazon Bedrock - Ne remplace pas un avis médical</small>
            </div>
        </div>
        """

        return html_response

    def _get_cache_key(self, user_message: str, session_id: str) -> str:
        """Génère une clé de cache"""
        return f"{session_id}:{hash(user_message.lower().strip())}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Récupère une réponse du cache si disponible"""
        if cache_key in self.response_cache:
            cached_data = self.response_cache[cache_key]
            if datetime.now().timestamp() - cached_data['timestamp'] < self.cache_ttl:
                self.metrics['cache_hits'] += 1
                return cached_data['response']
        return None

    def _store_in_cache(self, cache_key: str, response: Dict):
        """Stocke une réponse dans le cache"""
        self.response_cache[cache_key] = {
            'response': response,
            'timestamp': datetime.now().timestamp()
        }

    def _save_conversation_context(self, session_id: str, user_message: str, ai_response: str):
        """Sauvegarde le contexte de conversation"""
        if session_id not in self.conversation_contexts:
            self.conversation_contexts[session_id] = []

        self.conversation_contexts[session_id].append({
            "user": user_message,
            "bot": ai_response,
            "timestamp": datetime.now().isoformat()
        })

        # Limiter à 10 échanges par session
        if len(self.conversation_contexts[session_id]) > 10:
            self.conversation_contexts[session_id] = self.conversation_contexts[session_id][-10:]

    def _fallback_response(self, user_message: str, error_type: str) -> Dict:
        """Réponses de secours si Bedrock échoue"""

        message_lower = user_message.lower()

        if any(word in message_lower for word in ["mal", "poitrine", "respir", "aide", "urgent"]):
            html_response = """
            <div class="response-section emergency-alert">
                <h3><i class="fas fa-ambulance"></i> PROTOCOLE D'URGENCE ACTIVÉ</h3>
                <p><strong>Douleur thoracique ou difficultés respiratoires détectées</strong></p>
                <ul class="urgent-list">
                    <li><strong>APPELEZ IMMÉDIATEMENT:</strong></li>
                    <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                    <li><strong>CHU Yaoundé</strong> - Centre spécialisé drépanocytose</li>
                    <li><strong>Hôpital Central Yaoundé</strong> - Service urgences</li>
                </ul>
                <p>⚠️ <strong>Mentionnez "patient drépanocytaire"</strong></p>
                <p>Actions immédiates: restez calme, position confortable, documents médicaux prêts</p>
            </div>
            """
        else:
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-user-md"></i> Assistant Kidjamo</h3>
                <p>Service médical spécialisé drépanocytose Cameroun:</p>
                <ul class="help-list">
                    <li>🩺 Gestion crises douloureuses</li>
                    <li>💊 Suivi médicamenteux (Siklos, antalgiques)</li>
                    <li>🚨 Protocoles urgence drépanocytose</li>
                    <li>📚 Éducation thérapeutique</li>
                </ul>
                <p>Reformulez votre question pour une assistance personnalisée</p>
            </div>
            """

        return {
            "response": html_response,
            "conversation_type": "fallback",
            "source": f"bedrock-fallback-{error_type}",
            "success": True,
            "cached": False
        }

    def get_bedrock_metrics(self) -> Dict[str, Any]:
        """Métriques détaillées pour monitoring Bedrock"""

        # Calcul des coûts par modèle
        cost_breakdown = {}
        for model_name, usage_count in self.metrics['models_used'].items():
            model_config = self.available_models[model_name]
            estimated_cost = usage_count * 0.002  # Estimation moyenne par requête
            cost_breakdown[model_name] = {
                "requests": usage_count,
                "estimated_cost": estimated_cost,
                "cost_per_request": estimated_cost / max(usage_count, 1)
            }

        return {
            "status": "operational",
            "service": "amazon-bedrock",
            "region": self.aws_region,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "performance": {
                "total_requests": self.metrics['total_requests'],
                "successful_requests": self.metrics['successful_requests'],
                "failed_requests": self.metrics['failed_requests'],
                "success_rate": (self.metrics['successful_requests'] / max(self.metrics['total_requests'], 1)) * 100,
                "cache_hit_rate": (self.metrics['cache_hits'] / max(self.metrics['total_requests'], 1)) * 100
            },
            "costs": {
                "total_estimated": self.metrics['cost_estimate'],
                "average_per_request": self.metrics['cost_estimate'] / max(self.metrics['total_requests'], 1),
                "breakdown_by_model": cost_breakdown
            },
            "models_usage": self.metrics['models_used'],
            "cache_size": len(self.response_cache),
            "active_sessions": len(self.conversation_contexts)
        }

    def get_available_models(self) -> Dict[str, Any]:
        """Retourne la liste des modèles disponibles avec leurs caractéristiques"""
        return {
            "models": self.available_models,
            "current_primary": self.primary_model,
            "current_fallback": self.fallback_model,
            "selection_strategy": "Automatique selon urgence et complexité"
        }

    def _handle_simple_questions(self, user_message: str, session_id: str) -> Optional[Dict]:
        """Gère les questions simples comme l'heure, la date, ou les salutations"""

        message_lower = user_message.lower().strip()

        # Détection spécifique des demandes d'heure
        time_patterns = [
            "il est quelle heure",
            "quelle heure il est",
            "quelle heure",
            "l'heure",
            "heure actuelle",
            "heure qu'il est",
            "temps actuel",
            "horaire"
        ]

        # Vérifier si c'est une demande d'heure
        if any(pattern in message_lower for pattern in time_patterns):
            current_time = datetime.now().strftime("%H:%M")
            current_date = datetime.now().strftime("%d/%m/%Y")

            html_response = f"""
            <div class="response-section info-section">
                <h3><i class="fas fa-clock"></i> Heure actuelle</h3>
                <p><strong>Il est actuellement {current_time}</strong></p>
                <p>Date: {current_date}</p>
                <p>Si vous avez besoin d'aide médicale concernant votre traitement contre la drépanocytose, n'hésitez pas à me poser vos questions!</p>
            </div>
            """

            return {
                "response": html_response,
                "conversation_type": "time_request",
                "source": "time-handler",
                "success": True,
                "cached": False,
                "model_used": "simple-handler",
                "cost_estimate": 0.0
            }

        # Détection des salutations
        greeting_patterns = ["bonjour", "salut", "hello", "bonsoir", "bonne nuit", "hey"]
        if any(pattern in message_lower for pattern in greeting_patterns):
            current_hour = datetime.now().hour
            if current_hour < 12:
                greeting = "Bonjour"
            elif current_hour < 18:
                greeting = "Bon après-midi"
            else:
                greeting = "Bonsoir"

            html_response = f"""
            <div class="response-section medical-info">
                <h3><i class="fas fa-hand-wave"></i> Kidjamo Assistant</h3>
                <p>{greeting}! Je suis votre assistant médical spécialisé dans la drépanocytose.</p>
                <p>Comment puis-je vous aider aujourd'hui ?</p>
                <ul class="help-list">
                    <li>🩺 Questions sur vos symptômes</li>
                    <li>💊 Gestion de vos médicaments</li>
                    <li>🚨 Conseils en cas de crise</li>
                    <li>📚 Informations sur la drépanocytose</li>
                </ul>
            </div>
            """

            return {
                "response": html_response,
                "conversation_type": "greeting",
                "source": "greeting-handler",
                "success": True,
                "cached": False,
                "model_used": "simple-handler",
                "cost_estimate": 0.0
            }

        # Détection des remerciements
        thanks_patterns = ["merci", "thank", "remercie"]
        if any(pattern in message_lower for pattern in thanks_patterns):
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-heart"></i> Kidjamo Assistant</h3>
                <p>De rien! Je suis là pour vous accompagner dans votre prise en charge.</p>
                <p>N'hésitez pas si vous avez d'autres questions sur votre santé ou votre traitement.</p>
            </div>
            """

            return {
                "response": html_response,
                "conversation_type": "thanks",
                "source": "thanks-handler",
                "success": True,
                "cached": False,
                "model_used": "simple-handler",
                "cost_estimate": 0.0
            }

        # Détection des demandes d'aide générale
        help_patterns = ["aide", "help", "qui es-tu", "qui es tu", "que peux-tu faire", "comment ça marche"]
        if any(pattern in message_lower for pattern in help_patterns):
            html_response = """
            <div class="response-section medical-info">
                <h3><i class="fas fa-robot"></i> À propos de Kidjamo Assistant</h3>
                <p>Je suis votre assistant médical intelligent spécialisé dans la drépanocytose au Cameroun.</p>
                
                <h4><i class="fas fa-stethoscope"></i> Mes capacités</h4>
                <ul class="help-list">
                    <li><strong>Gestion des crises:</strong> Conseils personnalisés pour gérer la douleur</li>
                    <li><strong>Suivi médicamenteux:</strong> Rappels et conseils sur vos traitements</li>
                    <li><strong>Urgences médicales:</strong> Orientation vers les services d'urgence</li>
                    <li><strong>Éducation thérapeutique:</strong> Informations fiables sur la drépanocytose</li>
                </ul>
                
                <h4><i class="fas fa-exclamation-triangle"></i> Important</h4>
                <p>⚠️ Je ne remplace jamais un médecin qualifié. En cas d'urgence, contactez le 1510 ou rendez-vous au CHU de Yaoundé.</p>
            </div>
            """

            return {
                "response": html_response,
                "conversation_type": "help",
                "source": "help-handler",
                "success": True,
                "cached": False,
                "model_used": "simple-handler",
                "cost_estimate": 0.0
            }

        # Aucune question simple détectée
        return None
