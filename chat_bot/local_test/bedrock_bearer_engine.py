"""
Bedrock AI Engine adapté pour Bearer Token Authentication
Version optimisée pour votre clé API Bedrock spécifique
"""

import requests
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

class BedrockBearerTokenEngine:
    """Moteur Bedrock avec authentification Bearer Token"""

    def __init__(self):
        # Configuration avec votre token Bearer
        self.bearer_token = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
        self.api_endpoint = os.getenv('BEDROCK_API_ENDPOINT', 'https://bedrock-runtime.us-east-1.amazonaws.com')

        if not self.bearer_token:
            raise ValueError("AWS_BEARER_TOKEN_BEDROCK non trouvé dans les variables d'environnement")

        # Configuration des modèles Bedrock disponibles
        self.available_models = {
            "claude-3-haiku": {
                "id": "anthropic.claude-3-haiku-20240307-v1:0",
                "max_tokens": 4096,
                "cost_per_1k_input": 0.00025,
                "cost_per_1k_output": 0.00125,
                "recommended": True,
                "use_case": "Urgences médicales - Rapide et précis"
            },
            "claude-3-sonnet": {
                "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "max_tokens": 4096,
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "recommended": False,
                "use_case": "Analyses complexes - Qualité supérieure"
            },
            "claude-v2": {
                "id": "anthropic.claude-v2",
                "max_tokens": 8192,
                "cost_per_1k_input": 0.008,
                "cost_per_1k_output": 0.024,
                "recommended": False,
                "use_case": "Conversations longues"
            },
            "titan-text": {
                "id": "amazon.titan-text-express-v1",
                "max_tokens": 8192,
                "cost_per_1k_input": 0.0008,
                "cost_per_1k_output": 0.0016,
                "recommended": True,
                "use_case": "Questions générales économiques"
            }
        }

        # Modèle par défaut optimisé pour médical
        self.primary_model = os.getenv('BEDROCK_PRIMARY_MODEL', 'claude-3-haiku')
        self.fallback_model = os.getenv('BEDROCK_FALLBACK_MODEL', 'titan-text')

        # Configuration performance
        self.request_timeout = int(os.getenv('BEDROCK_TIMEOUT', 30))
        self.max_retries = int(os.getenv('BEDROCK_MAX_RETRIES', 3))
        self.conversation_contexts = {}

        # Cache et métriques
        self.response_cache = {}
        self.cache_ttl = int(os.getenv('BEDROCK_CACHE_TTL', 1800))
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cost_estimate': 0.0,
            'models_used': {}
        }

        logger.info(f"BedrockBearerTokenEngine initialisé avec modèle principal: {self.primary_model}")
        logger.info(f"Endpoint: {self.api_endpoint}")

    def process_message_with_ai(self, user_message: str, context: Dict) -> Dict:
        """Traite le message avec Bedrock via Bearer Token"""

        session_id = context.get('session_id', 'default')
        self.metrics['total_requests'] += 1

        try:
            # Vérification du cache
            cache_key = self._get_cache_key(user_message, session_id)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                logger.info(f"Réponse servie depuis le cache pour session {session_id}")
                return cached_response

            # Sélection du modèle selon l'urgence
            model_name = self._select_model_for_urgency(user_message, context)
            model_config = self.available_models[model_name]

            # Construire le prompt médical spécialisé
            system_prompt = self._build_medical_prompt(user_message, session_id, context)

            # Générer la réponse avec Bedrock
            response = self._generate_with_bedrock_api(
                model_config["id"],
                system_prompt,
                user_message,
                model_config
            )

            if response:
                # Construire la réponse finale
                final_response = {
                    "response": self._format_response_as_html(response["content"], user_message),
                    "conversation_type": self._detect_conversation_type(user_message),
                    "source": "bedrock-bearer-token",
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
                return self._fallback_response(user_message, "bedrock_api_error")

        except Exception as e:
            logger.error(f"Erreur critique Bedrock Bearer Token: {e}")
            self.metrics['failed_requests'] += 1
            return self._fallback_response(user_message, "system_error")

    def _select_model_for_urgency(self, user_message: str, context: Dict) -> str:
        """Sélectionne le modèle optimal selon l'urgence médicale"""

        urgency_level = context.get('urgency_level', 'normal')
        message_lower = user_message.lower()

        # Mots-clés d'urgence critique
        critical_keywords = ["poitrine", "respir", "8/10", "9/10", "10/10", "insupportable", "mourir"]

        # Pour les urgences médicales critiques → Claude Haiku (rapidité + précision)
        if urgency_level == 'critical' or any(word in message_lower for word in critical_keywords):
            return "claude-3-haiku"

        # Pour les questions sur médicaments → Claude Haiku (sécurité médicale)
        elif any(word in message_lower for word in ["médicament", "siklos", "traitement", "dose"]):
            return "claude-3-haiku"

        # Pour les questions générales → Titan (économique)
        else:
            return "titan-text"

    def _generate_with_bedrock_api(self, model_id: str, system_prompt: str, user_message: str, model_config: Dict) -> Optional[Dict]:
        """Génère une réponse via l'API Bedrock avec Bearer Token"""

        try:
            # URL de l'endpoint Bedrock
            url = f"{self.api_endpoint}/model/{model_id}/invoke"

            # Headers avec Bearer Token
            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Kidjamo-HealthBot-Bedrock/1.0"
            }

            # Construire le payload selon le type de modèle
            if "claude" in model_id:
                payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": min(model_config["max_tokens"], 800),
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
            elif "titan" in model_id:
                full_prompt = f"{system_prompt}\n\nQuestion: {user_message}\nRéponse médicale:"
                payload = {
                    "inputText": full_prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": min(model_config["max_tokens"], 700),
                        "temperature": 0.3,
                        "topP": 0.8
                    }
                }
            else:
                raise ValueError(f"Type de modèle non supporté: {model_id}")

            # Appel API avec retry
            response = self._make_api_call_with_retry(url, headers, payload)

            if response and response.status_code == 200:
                response_data = response.json()

                # Parser la réponse selon le type de modèle
                parsed_response = self._parse_model_response(model_id, response_data)

                # Calculer le coût estimé
                cost = self._calculate_cost(model_config, parsed_response.get("tokens", {}))

                return {
                    "content": parsed_response["content"],
                    "cost": cost,
                    "tokens": parsed_response.get("tokens", {})
                }
            else:
                error_msg = f"Erreur API Bedrock: {response.status_code if response else 'Timeout'}"
                logger.error(error_msg)
                return None

        except Exception as e:
            logger.error(f"Erreur génération Bedrock: {e}")
            return None

    def _make_api_call_with_retry(self, url: str, headers: Dict, payload: Dict) -> Optional[requests.Response]:
        """Effectue l'appel API Bedrock avec retry automatique"""

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout
                )

                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout API Bedrock - Tentative {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur réseau Bedrock - Tentative {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def _parse_model_response(self, model_id: str, response: Dict) -> Dict:
        """Parse la réponse selon le type de modèle avec gestion robuste des formats"""

        try:
            logger.info(f"Debug - Réponse brute Bedrock: {json.dumps(response, indent=2)[:500]}...")

            # Essayer différents formats de réponse Claude
            if "claude" in model_id:
                content = None
                tokens = {"input": 0, "output": 0}

                # Format 1: Standard Bedrock Claude
                if "content" in response and isinstance(response["content"], list):
                    content = response["content"][0]["text"]
                    if "usage" in response:
                        tokens = {
                            "input": response["usage"].get("input_tokens", 0),
                            "output": response["usage"].get("output_tokens", 0)
                        }

                # Format 2: Direct text response
                elif "completion" in response:
                    content = response["completion"]

                # Format 3: Message format
                elif "message" in response:
                    content = response["message"]

                # Format 4: Text field direct
                elif "text" in response:
                    content = response["text"]

                # Format 5: Réponse dans un wrapper
                elif "response" in response:
                    content = response["response"]

                # 🔧 NOUVEAU: Format avec liste ['Output', 'Version']
                elif isinstance(response, list) and len(response) >= 2:
                    # Si on reçoit ['Output', 'Version'], prendre le premier élément
                    content = str(response[0])
                    logger.info(f"Format liste détecté: {response}")

                # 🔧 NOUVEAU: Format avec clés spécifiques
                elif "Output" in response:
                    content = response["Output"]
                elif "output" in response:
                    content = response["output"]

                if not content:
                    # Dernière tentative: chercher n'importe quel champ text
                    for key, value in response.items():
                        if isinstance(value, str) and len(value) > 10:
                            content = value
                            break

                if not content:
                    # 🔧 NOUVEAU: Si format complètement inattendu, générer réponse de fallback
                    logger.warning(f"Format Bedrock inattendu: {response}")
                    content = "Bonjour ! Je suis votre assistant Kidjamo spécialisé dans la drépanocytose. Comment puis-je vous aider aujourd'hui ?"

            # Essayer différents formats de réponse Titan
            elif "titan" in model_id:
                content = None
                tokens = {"input": 0, "output": 0}

                # Format 1: Standard Titan
                if "results" in response and isinstance(response["results"], list):
                    content = response["results"][0]["outputText"]
                    tokens = {
                        "input": response.get("inputTextTokenCount", 0),
                        "output": response["results"][0].get("tokenCount", 0)
                    }

                # Format 2: Direct outputText
                elif "outputText" in response:
                    content = response["outputText"]

                # 🔧 NOUVEAU: Format Titan avec liste ['Output', 'Version']
                elif isinstance(response, list) and len(response) >= 2:
                    content = str(response[0])
                    logger.info(f"Format Titan liste détecté: {response}")

                # 🔧 NOUVEAU: Format avec clés spécifiques Titan
                elif "Output" in response:
                    content = response["Output"]
                elif "output" in response:
                    content = response["output"]

                if not content:
                    # 🔧 NOUVEAU: Fallback pour Titan aussi
                    logger.warning(f"Format Titan inattendu: {response}")
                    content = "Bonjour ! Je suis votre assistant Kidjamo. Pour toute question sur la drépanocytose, je suis là pour vous aider !"

            else:
                content = f"Modèle {model_id} non supporté"

            # 🔧 VALIDATION FINALE du contenu
            if not content or len(content.strip()) < 5:
                content = "Bonjour ! Je suis Kidjamo Assistant, votre compagnon santé spécialisé dans la drépanocytose. Comment puis-je vous accompagner aujourd'hui ?"

            return {
                "content": content.strip() if content else "Réponse vide de Bedrock",
                "tokens": tokens
            }

        except Exception as e:
            logger.error(f"Erreur parsing réponse {model_id}: {e}")
            logger.error(f"Réponse problématique: {response}")
            # 🔧 FALLBACK ROBUSTE en cas d'erreur critique
            return {
                "content": "Bonjour ! Je suis votre assistant Kidjamo spécialisé dans l'accompagnement des patients atteints de drépanocytose. Comment puis-je vous aider aujourd'hui ? En cas d'urgence médicale, contactez le 1510 ou rendez-vous au CHU Yaoundé.",
                "tokens": {"input": 0, "output": 0}
            }

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

        patient_info = context.get('patient_info', {})
        age = patient_info.get('age', 'Non spécifié')

        base_prompt = f"""Tu es Kidjamo Assistant, un assistant médical IA spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun.

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

INSTRUCTIONS DE RÉPONSE:
- Sois empathique et rassurant mais prudent médicalement
- Structure avec des émojis (🚨 🩺 💊) pour clarifier
- Si urgence: priorise ABSOLUMENT la sécurité du patient
- Donne des conseils pratiques et précis adaptés au Cameroun
- Termine par une question de suivi si approprié"""

        # Ajouter contexte conversation récente
        if session_id in self.conversation_contexts:
            recent = self.conversation_contexts[session_id][-2:]
            if recent:
                base_prompt += "\n\nCONTEXTE CONVERSATION RÉCENTE:\n"
                for ctx in recent:
                    base_prompt += f"Patient: {ctx['user']}\nAssistant: {ctx['bot'][:100]}...\n"

        return base_prompt

    def _detect_conversation_type(self, message: str) -> str:
        """Détecte le type de conversation"""
        message_lower = message.lower()

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
            "service": "bedrock-bearer-token",
            "endpoint": self.api_endpoint,
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
            "selection_strategy": "Automatique selon urgence médicale"
        }
