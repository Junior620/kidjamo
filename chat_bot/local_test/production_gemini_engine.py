"""
Gemini Flash Engine - VERSION PRODUCTION
Sécurisé et optimisé pour un déploiement professionnel
"""

import os
import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from functools import wraps
import json

logger = logging.getLogger(__name__)

class ProductionGeminiFlashEngine:
    """Moteur Gemini Flash sécurisé pour production"""

    def __init__(self):
        # Configuration sécurisée via variables d'environnement
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY non trouvée dans les variables d'environnement")

        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

        # Configuration production
        self.max_requests_per_minute = 15  # Limite gratuite
        self.max_requests_per_day = 1500   # Limite gratuite
        self.request_timeout = 30          # Timeout plus long pour production

        # Système de rate limiting
        self.request_history = []
        self.daily_request_count = 0
        self.last_reset_date = datetime.now().date()

        # Cache des réponses pour optimiser
        self.response_cache = {}
        self.cache_ttl = 3600  # 1 heure

        # Métriques pour monitoring
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'rate_limited': 0
        }

        logger.info("ProductionGeminiFlashEngine initialisé avec sécurité renforcée")

    def _check_rate_limits(self) -> bool:
        """Vérifie les limites de taux"""
        now = datetime.now()

        # Reset quotidien
        if now.date() > self.last_reset_date:
            self.daily_request_count = 0
            self.last_reset_date = now.date()
            logger.info("Compteur quotidien réinitialisé")

        # Vérifier limite quotidienne
        if self.daily_request_count >= self.max_requests_per_day:
            logger.warning(f"Limite quotidienne atteinte: {self.daily_request_count}")
            return False

        # Nettoyer l'historique (garde seulement la dernière minute)
        minute_ago = now - timedelta(minutes=1)
        self.request_history = [req_time for req_time in self.request_history if req_time > minute_ago]

        # Vérifier limite par minute
        if len(self.request_history) >= self.max_requests_per_minute:
            logger.warning(f"Limite par minute atteinte: {len(self.request_history)}")
            return False

        return True

    def _get_cache_key(self, user_message: str, session_id: str) -> str:
        """Génère une clé de cache pour éviter les appels répétitifs"""
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

    def process_message_with_ai(self, user_message: str, context: Dict) -> Dict:
        """Traite le message avec Gemini Flash - Version Production"""

        session_id = context.get('session_id', 'default')
        self.metrics['total_requests'] += 1

        try:
            # Vérification du cache
            cache_key = self._get_cache_key(user_message, session_id)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                logger.info(f"Réponse servie depuis le cache pour session {session_id}")
                return cached_response

            # Vérification des limites de taux
            if not self._check_rate_limits():
                self.metrics['rate_limited'] += 1
                logger.error("Limite de taux Gemini Flash dépassée")
                return self._fallback_response(user_message, "rate_limited")

            # Construire le prompt médical spécialisé
            system_prompt = self._build_medical_prompt(user_message, session_id, context)

            payload = {
                "contents": [{
                    "parts": [{"text": system_prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 600,
                    "topP": 0.8,
                    "topK": 40
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_MEDICAL",
                        "threshold": "BLOCK_ONLY_HIGH"
                    }
                ]
            }

            # Enregistrer la requête dans l'historique
            self.request_history.append(datetime.now())
            self.daily_request_count += 1

            # Appel API avec retry automatique
            response = self._make_api_call_with_retry(payload)

            if response and response.status_code == 200:
                data = response.json()
                ai_response = data["candidates"][0]["content"]["parts"][0]["text"]

                # Construire la réponse finale
                final_response = {
                    "response": self._format_response_as_html(ai_response, user_message),
                    "conversation_type": self._detect_conversation_type(user_message),
                    "source": "gemini-flash-production",
                    "model_used": "gemini-1.5-flash",
                    "raw_response": ai_response,
                    "success": True,
                    "cached": False,
                    "request_count": self.daily_request_count
                }

                # Stocker en cache
                self._store_in_cache(cache_key, final_response)

                self.metrics['successful_requests'] += 1
                logger.info(f"Réponse IA générée avec succès pour session {session_id}")
                return final_response

            else:
                error_msg = f"Erreur API Gemini: {response.status_code if response else 'Timeout'}"
                logger.error(error_msg)
                self.metrics['failed_requests'] += 1
                return self._fallback_response(user_message, "api_error")

        except Exception as e:
            logger.error(f"Erreur critique Gemini Flash: {e}")
            self.metrics['failed_requests'] += 1
            return self._fallback_response(user_message, "system_error")

    def _make_api_call_with_retry(self, payload: Dict, max_retries: int = 3) -> Optional[requests.Response]:
        """Effectue l'appel API avec retry automatique"""

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=self.request_timeout,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'Kidjamo-HealthBot/1.0'
                    }
                )
                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout API Gemini - Tentative {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponentiel

            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur réseau Gemini - Tentative {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def _build_medical_prompt(self, user_message: str, session_id: str, context: Dict) -> str:
        """Construit un prompt médical contextualisé pour production"""

        # Informations patient si disponibles
        patient_info = context.get('patient_info', {})
        age = patient_info.get('age', 'Non spécifié')
        severity_history = patient_info.get('severity_history', [])

        base_prompt = f"""Tu es Kidjamo Assistant, un assistant médical certifié spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun.

CONTEXTE PATIENT:
- Âge: {age}
- Historique: {', '.join(severity_history) if severity_history else 'Nouvelle consultation'}

PROTOCOLE MÉDICAL STRICT:
- Tu ne remplaces JAMAIS un médecin qualifié
- URGENCE VITALE si: douleur >7/10, difficultés respiratoires, fièvre >38.5°C
- En urgence: directive IMMÉDIATE vers services d'urgence camerounais
- Domaine STRICT: drépanocytose uniquement

SERVICES D'URGENCE CAMEROUN:
- 1510 (Urgence nationale Cameroun)
- Hôpital Central Yaoundé - Urgences
- Hôpital Général Douala - Service d'urgence
- CHU Yaoundé - Centre référence drépanocytose

CENTRES SPÉCIALISÉS:
- CHU Yaoundé - Hématologie spécialisée
- Hôpital Laquintinie Douala - Suivi drépanocytose
- Centre Pasteur Cameroun - Expertise drépanocytose

QUESTION PATIENT: {user_message}

RÉPONSE ATTENDUE: Analyse médicale empathique, protocole d'urgence si nécessaire, guidance vers soins appropriés."""

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
        """Formate la réponse IA en HTML sécurisé pour production"""

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
            <div class="production-footer">
                <small>Réponse générée par IA - Ne remplace pas un avis médical</small>
            </div>
        </div>
        """

        return html_response

    def _fallback_response(self, user_message: str, error_type: str) -> Dict:
        """Réponses de secours robustes pour production"""

        message_lower = user_message.lower()

        if error_type == "rate_limited":
            html_response = """
            <div class="response-section warning-alert">
                <h3><i class="fas fa-clock"></i> Service temporairement surchargé</h3>
                <p><strong>Notre service IA connaît actuellement un pic d'utilisation.</strong></p>
                <p>Pour une urgence médicale drépanocytaire :</p>
                <ul class="urgent-list">
                    <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                    <li><strong>CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                </ul>
                <p>Veuillez réessayer dans quelques minutes pour les questions non-urgentes.</p>
            </div>
            """
        elif any(word in message_lower for word in ["mal", "poitrine", "respir", "aide", "urgent"]):
            html_response = """
            <div class="response-section emergency-alert">
                <h3><i class="fas fa-ambulance"></i> PROTOCOLE D'URGENCE ACTIVÉ</h3>
                <p><strong>Douleur thoracique ou difficultés respiratoires détectées</strong></p>
                <ul class="urgent-list">
                    <li><strong>APPELEZ IMMÉDIATEMENT:</strong></li>
                    <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                    <li><strong>Hôpital Central Yaoundé</strong> - Service urgences</li>
                    <li><strong>CHU Yaoundé</strong> - Centre spécialisé drépanocytose</li>
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
            "source": f"fallback-{error_type}",
            "success": True,
            "cached": False
        }

    def get_production_metrics(self) -> Dict[str, Any]:
        """Métriques détaillées pour monitoring production"""
        return {
            "status": "operational",
            "api_health": "connected" if self.api_key else "disconnected",
            "daily_usage": {
                "requests_made": self.daily_request_count,
                "requests_remaining": self.max_requests_per_day - self.daily_request_count,
                "usage_percentage": (self.daily_request_count / self.max_requests_per_day) * 100
            },
            "performance": {
                "cache_hit_rate": (self.metrics['cache_hits'] / max(self.metrics['total_requests'], 1)) * 100,
                "success_rate": (self.metrics['successful_requests'] / max(self.metrics['total_requests'], 1)) * 100,
                "rate_limit_incidents": self.metrics['rate_limited']
            },
            "metrics": self.metrics,
            "last_reset": self.last_reset_date.isoformat(),
            "cache_size": len(self.response_cache)
        }
