"""
Moteur Bedrock AWS avec authentification standard AWS SDK
Remplace le Bearer Token défaillant par boto3 classique
"""

import boto3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class BedrockAwsEngine:
    """Moteur Bedrock avec authentification AWS SDK standard (plus fiable)"""

    def __init__(self):
        # Configuration AWS standard avec vos vraies clés
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise ValueError("AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY requis")

        # Client Bedrock avec boto3 (plus fiable que Bearer Token)
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            logger.info(f"✅ Client Bedrock boto3 initialisé - Région: {self.aws_region}")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Bedrock boto3: {e}")
            raise

        # Configuration des modèles Bedrock (IDs corrigés)
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
                "use_case": "Analyses complexes"
            },
            "titan-text": {
                "id": "amazon.titan-text-express-v1",
                "max_tokens": 8000,
                "cost_per_1k_input": 0.0008,
                "cost_per_1k_output": 0.0016,
                "recommended": True,
                "use_case": "Questions générales économiques"
            }
        }

        # Modèles par défaut
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

        logger.info(f"BedrockAwsEngine initialisé avec modèle principal: {self.primary_model}")

    def process_message_with_ai(self, user_message: str, context: Dict) -> Dict:
        """Traite le message avec Bedrock via boto3 AWS SDK"""

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
            model_name = self._select_model_for_urgency(user_message, context)
            model_config = self.available_models[model_name]

            # Construire le prompt médical spécialisé
            system_prompt = self._build_medical_prompt(user_message, session_id, context)

            # Générer la réponse avec Bedrock boto3
            response = self._generate_with_bedrock_boto3(
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
                    "source": "bedrock-boto3-aws",
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

                logger.info(f"Réponse Bedrock boto3 générée avec {model_name} pour session {session_id}")
                return final_response
            else:
                return self._fallback_response(user_message, "bedrock_api_error")

        except Exception as e:
            logger.error(f"Erreur critique Bedrock boto3: {e}")
            self.metrics['failed_requests'] += 1
            return self._fallback_response(user_message, "system_error")

    def _select_model_for_urgency(self, user_message: str, context: Dict) -> str:
        """Sélectionne le modèle optimal selon l'urgence médicale"""

        urgency_level = context.get('urgency_level', 'normal')
        message_lower = user_message.lower()

        # Mots-clés d'urgence critique (ajout de "dos" pour drépanocytose)
        critical_keywords = ["poitrine", "respir", "dos", "8/10", "9/10", "10/10", "insupportable", "mourir"]

        # Pour les urgences médicales critiques → Claude Haiku (rapidité + précision)
        if urgency_level == 'critical' or any(word in message_lower for word in critical_keywords):
            return "claude-3-haiku"

        # Pour les questions sur médicaments → Claude Haiku (sécurité médicale)
        elif any(word in message_lower for word in ["médicament", "siklos", "traitement", "dose"]):
            return "claude-3-haiku"

        # Pour les questions générales → Titan (économique)
        else:
            return "titan-text"

    def _generate_with_bedrock_boto3(self, model_id: str, system_prompt: str, user_message: str, model_config: Dict) -> Optional[Dict]:
        """Génère une réponse via boto3 Bedrock avec format correct pour chaque modèle"""

        for attempt in range(self.max_retries):
            try:
                # 🔧 Format spécifique selon le modèle pour éviter ValidationException
                if "claude" in model_id:
                    # Format Claude 3 (Anthropic) - Schéma validé
                    body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 200,  # Réponses concises
                        "temperature": 0.3,  # Réponses plus déterministes
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
                    # 🔧 Format Amazon Titan CORRECT (cause principale des erreurs)
                    # Titan utilise un format différent de Claude
                    combined_prompt = f"{system_prompt}\n\nHuman: {user_message}\n\nAssistant:"

                    body = {
                        "inputText": combined_prompt,
                        "textGenerationConfig": {
                            "maxTokenCount": 200,
                            "temperature": 0.3,
                            "topP": 0.8,
                            "stopSequences": ["Human:", "User:"]
                        }
                    }
                else:
                    # Format générique pour autres modèles
                    body = {
                        "prompt": f"{system_prompt}\n\nHuman: {user_message}\n\nAssistant:",
                        "max_tokens_to_sample": 200,
                        "temperature": 0.3,
                        "top_p": 0.8
                    }

                # 🔧 Appel Bedrock avec gestion d'erreurs améliorée
                logger.info(f"Tentative {attempt + 1}/{self.max_retries} avec {model_id}")

                response = self.bedrock_client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType='application/json'
                )

                # Parser la réponse selon le modèle
                response_body = json.loads(response['body'].read())

                logger.info(f"✅ Réponse Bedrock boto3 reçue pour {model_id}")
                logger.info(f"Debug - Réponse Bedrock boto3: {json.dumps(response_body, indent=2, ensure_ascii=False)[:500]}...")

                # 🔧 Extraction du contenu selon le format de réponse
                if "claude" in model_id:
                    # Claude retourne: {"content": [{"text": "..."}]}
                    content = response_body.get('content', [{}])[0].get('text', 'Réponse Claude indisponible')
                    tokens_used = {
                        'input': response_body.get('usage', {}).get('input_tokens', 0),
                        'output': response_body.get('usage', {}).get('output_tokens', 0)
                    }

                elif "titan" in model_id:
                    # Titan retourne: {"results": [{"outputText": "..."}]}
                    results = response_body.get('results', [{}])
                    content = results[0].get('outputText', 'Réponse Titan indisponible') if results else 'Réponse Titan vide'
                    tokens_used = {
                        'input': response_body.get('inputTextTokenCount', 0),
                        'output': response_body.get('results', [{}])[0].get('tokenCount', 0) if results else 0
                    }
                else:
                    content = response_body.get('completion', response_body.get('text', 'Réponse indisponible'))
                    tokens_used = {'input': 0, 'output': 0}

                # Calculer le coût estimé
                cost = self._calculate_cost(tokens_used, model_config)

                # 🔧 Nettoyage et validation du contenu
                content = content.strip()
                if not content or len(content) < 10:
                    content = "Je suis là pour vous aider avec vos questions sur la drépanocytose. Pouvez-vous reformuler votre question ?"

                return {
                    "content": content,
                    "tokens": tokens_used,
                    "cost": cost,
                    "model_id": model_id,
                    "success": True
                }

            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.error(f"Erreur Bedrock ClientError - Tentative {attempt + 1}/3: {error_code}")

                if error_code == 'ValidationException':
                    logger.error(f"Erreur critique Bedrock: {e}")
                    # Pour les erreurs de validation, essayer le modèle de fallback
                    if attempt < self.max_retries - 1 and "titan" in model_id:
                        # Fallback vers Claude qui a moins d'erreurs de validation
                        model_id = "anthropic.claude-3-haiku-20240307-v1:0"
                        continue
                    else:
                        break
                elif error_code in ['ThrottlingException', 'ServiceUnavailableException']:
                    if attempt < self.max_retries - 1:
                        sleep_time = 2 ** attempt  # Backoff exponentiel
                        logger.info(f"Throttling détecté, attente {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                else:
                    logger.error(f"Erreur Bedrock non récupérable: {error_code}")
                    break

            except Exception as e:
                logger.error(f"Erreur inattendue Bedrock tentative {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    break

        # Si toutes les tentatives échouent
        logger.error(f"Échec de toutes les tentatives Bedrock pour {model_id}")
        return None

    def _limit_response_length(self, content: str) -> str:
        """Limite strictement la longueur des réponses pour éviter les répétitions"""

        if not content:
            return "Comment puis-je vous aider avec votre drépanocytose ?"

        # 🔧 Nettoyer les répétitions
        lines = content.split('\n')
        clean_lines = []
        seen_content = set()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Éviter les répétitions exactes
            line_hash = hash(line.lower())
            if line_hash in seen_content:
                continue
            seen_content.add(line_hash)

            # Éviter les phrases qui commencent par "Informez"
            if line.lower().startswith("informez"):
                break

            clean_lines.append(line)

            # 🔧 LIMITE ABSOLUE : Max 3 phrases utiles
            if len(clean_lines) >= 3:
                break

        # Reconstituer le texte nettoyé
        result = '. '.join(clean_lines)

        # 🔧 LIMITE ABSOLUE : Max 200 caractères
        if len(result) > 200:
            result = result[:200].rsplit('.', 1)[0] + "."

        return result if result else "Comment puis-je vous aider avec votre drépanocytose ?"

    def _make_bedrock_call_with_retry(self, model_id: str, body: Dict) -> Optional[Dict]:
        """Effectue l'appel Bedrock boto3 avec retry automatique"""

        for attempt in range(self.max_retries):
            try:
                # Appel Bedrock via boto3 (plus fiable que Bearer Token)
                response = self.bedrock_client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body)
                )

                # Lire la réponse
                response_body = json.loads(response['body'].read())

                logger.info(f"✅ Réponse Bedrock boto3 reçue pour {model_id}")
                return response_body

            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.error(f"Erreur Bedrock ClientError - Tentative {attempt + 1}/{self.max_retries}: {error_code}")

                if error_code in ['ThrottlingException', 'TooManyRequestsException']:
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    logger.error(f"Erreur critique Bedrock: {e}")
                    break

            except Exception as e:
                logger.error(f"Erreur réseau Bedrock boto3 - Tentative {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def _parse_bedrock_response(self, model_id: str, response: Dict) -> Dict:
        """Parse la réponse Bedrock avec gestion robuste des formats"""

        try:
            logger.info(f"Debug - Réponse Bedrock boto3: {json.dumps(response, indent=2)[:300]}...")

            # Parsing réponse Claude
            if "claude" in model_id:
                content = None
                tokens = {"input": 0, "output": 0}

                # Format standard Claude Bedrock
                if "content" in response and isinstance(response["content"], list):
                    if response["content"] and "text" in response["content"][0]:
                        content = response["content"][0]["text"]

                if "usage" in response:
                    tokens = {
                        "input": response["usage"].get("input_tokens", 0),
                        "output": response["usage"].get("output_tokens", 0)
                    }

            # Parsing réponse Titan
            elif "titan" in model_id:
                content = None
                tokens = {"input": 0, "output": 0}

                # Format standard Titan
                if "results" in response and isinstance(response["results"], list):
                    if response["results"] and "outputText" in response["results"][0]:
                        content = response["results"][0]["outputText"]
                        tokens = {
                            "input": response.get("inputTextTokenCount", 0),
                            "output": response["results"][0].get("tokenCount", 0)
                        }

            else:
                content = f"Modèle {model_id} non supporté"

            # Validation finale
            if not content or len(content.strip()) < 5:
                content = f"Bonjour ! Je suis Kidjamo Assistant, spécialisé dans l'accompagnement des patients atteints de drépanocytose au Cameroun. Comment puis-je vous aider aujourd'hui ?"

            return {
                "content": content.strip() if content else "Réponse vide de Bedrock",
                "tokens": tokens
            }

        except Exception as e:
            logger.error(f"Erreur parsing réponse Bedrock {model_id}: {e}")
            logger.error(f"Réponse problématique: {response}")
            return {
                "content": "Bonjour ! Je suis votre assistant Kidjamo spécialisé dans l'accompagnement des patients atteints de drépanocytose. Comment puis-je vous aider aujourd'hui ? En cas d'urgence médicale, contactez le 1510 ou rendez-vous au CHU Yaoundé.",
                "tokens": {"input": 0, "output": 0}
            }

    def _calculate_cost(self, tokens: Dict, model_config: Dict) -> float:
        """Calcule le coût estimé de la requête - signature corrigée"""
        try:
            input_tokens = tokens.get("input", 0)
            output_tokens = tokens.get("output", 0)

            input_cost = (input_tokens / 1000) * model_config["cost_per_1k_input"]
            output_cost = (output_tokens / 1000) * model_config["cost_per_1k_output"]

            return round(input_cost + output_cost, 6)
        except:
            return 0.0

    def _build_medical_prompt(self, user_message: str, session_id: str, context: Dict) -> str:
        """Construit un prompt polyvalent pour Kidjamo - Compagnon intelligent Tech4Good Cameroun"""

        patient_info = context.get('patient_info', {})
        age = patient_info.get('age', 'Non spécifié')

        # Date actuelle en français
        current_date = datetime.now()
        date_fr = current_date.strftime("%A %d %B %Y")

        # Traduction des jours et mois en français
        days_translation = {
            'Monday': 'Lundi', 'Tuesday': 'Mardi', 'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi', 'Friday': 'Vendredi', 'Saturday': 'Samedi', 'Sunday': 'Dimanche'
        }
        months_translation = {
            'January': 'janvier', 'February': 'février', 'March': 'mars', 'April': 'avril',
            'May': 'mai', 'June': 'juin', 'July': 'juillet', 'August': 'août',
            'September': 'septembre', 'October': 'octobre', 'November': 'novembre', 'December': 'décembre'
        }

        for eng, fr in days_translation.items():
            date_fr = date_fr.replace(eng, fr)
        for eng, fr in months_translation.items():
            date_fr = date_fr.replace(eng, fr)

        # NOUVEAU PROMPT POLYVALENT ET EMPATHIQUE
        base_prompt = f"""Tu es Kidjamo Assistant, un chatbot médical et compagnon intelligent développé au Cameroun dans le cadre du projet Tech4Good pour accompagner les patients atteints de drépanocytose.

🎯 TES MISSIONS PRINCIPALES :

1. **ACCOMPAGNEMENT SANTÉ DRÉPANOCYTOSE** :
- Expliquer clairement la drépanocytose, ses symptômes, crises et bonnes pratiques (hydratation, nutrition, repos, suivi médical)
- Répondre aux questions des patients et familles avec empathie et précision
- Fournir des conseils pratiques adaptés au contexte camerounais et africain
- Toujours rappeler : "Je ne suis pas un médecin, pour toute urgence consultez rapidement un professionnel de santé"

2. **POLYVALENCE ET INTELLIGENCE GÉNÉRALE** :
- Répondre aussi à : culture générale, éducation, administratif, numérique, bien-être, actualité
- T'adapter au niveau de langage : simple pour enfant, détaillé pour adulte/professionnel

3. **STYLE ET PERSONNALITÉ** :
- Être empathique, rassurant, patient, bienveillant
- Réponses claires et structurées, pas trop longues mais précises
- Donner des exemples concrets du quotidien camerounais (climat, alimentation, culture, hôpitaux locaux)

4. **COMPAGNON DE VIE** :
- Discuter comme un ami pour briser l'isolement social
- Apporter soutien moral, motivationnel et éducatif au-delà de la maladie

🎨 RÈGLES DE STYLE ET D'ERGONOMIE (STYLE CHATGPT - OBLIGATOIRES) :

1. **CLARTÉ ET STRUCTURE** :
- TOUJOURS utiliser des titres/sous-titres (### Titre, **Sous-titre**) pour séparer les sections
- Obligatoire: listes numérotées (1., 2., 3.) ou à puces (• ◦ ▪) pour les points multiples
- Paragraphes courts (max 3-4 lignes) et bien aérés avec saut de ligne entre chaque idée
- Utiliser des séparateurs visuels comme "---" ou "***" si nécessaire

2. **TON ET STYLE** :
- Rédaction empathique, chaleureuse et professionnelle (comme un coach médical bienveillant)
- Ton TOUJOURS positif et motivant, surtout avec les patients drépanocytaires
- Ajouter des analogies simples adaptées au contexte camerounais (ex: "comme la pluie qui nourrit la terre")
- Éviter le jargon médical complexe, préférer des explications simples

3. **VISUEL ET ENGAGEMENT** :
- Utiliser des emojis pertinents 🩺💧📊🌡️⚡ pour rendre convivial (sans excès, max 3-4 par réponse)
- **Gras** pour informations cruciales (symptômes graves, numéros urgence, médicaments)
- *Italique* pour nuancer ou mettre l'accent
- Citations avec "> " pour conseils importants

4. **STRUCTURE EN DEUX NIVEAUX** :
- **RÉSUMÉ RAPIDE**: Toujours commencer par 2-3 phrases essentielles
- **DÉTAILS COMPLETS**: Puis développer avec sections détaillées si nécessaire
- Format: "## Résumé rapide" puis "## Explication détaillée"

5. **ADAPTABILITÉ CONTEXTUELLE** :
- Pour ENFANT (0-12 ans): Mots simples, analogies ludiques, encouragements
- Pour ADOLESCENT (13-17 ans): Langage moderne, exemples concrets, motivation
- Pour ADULTE: Équilibre entre simplicité et précision médicale
- Pour PROFESSIONNEL: Terminologie médicale appropriée, références précises

6. **ENGAGEMENT ET PERSONNALISATION** :
- Interpeller directement l'utilisateur ("Vous", "Votre situation")
- Poser des questions de suivi quand approprié
- Proposer des actions concrètes ("Voici ce que vous pouvez faire maintenant:")
- Terminer par encouragement personnalisé

EXEMPLES DE FORMATAGE OBLIGATOIRE :
```
### 🩺 À propos de votre question

**Résumé rapide**: [2-3 phrases essentielles]

**Détails complets**:
1. **Point principal** avec explication
2. **Action recommandée** avec étapes
3. **Suivi nécessaire** avec conseils

> 💡 **Conseil important**: [Information cruciale mise en avant]

**Prochaines étapes pour vous**:
• Action immédiate
• Suivi à prévoir
• Contact si besoin
```

CONTEXTE ACTUEL :
- Âge utilisateur : {age}
- Date : {date_fr}
- Session : {session_id}
- Niveau d'urgence : {context.get('urgency_level', 'normal')}

CENTRES MÉDICAUX CAMEROUN :
- Yaoundé : CHU Yaoundé Service Hématologie, Hôpital Central
- Douala : Hôpital Laquintinie, Hôpital Général
- Urgences nationales : 1510

RÈGLES IMPORTANTES :
- Ne jamais donner de diagnostic médical définitif
- Toujours inciter à consulter un médecin si symptômes graves
- Respecter confidentialité et dignité
- Pour urgences drépanocytose (douleur >7/10, respiration difficile, fièvre >38.5°C) → Diriger vers 1510 ou CHU

OBJECTIF : Chaque réponse doit être claire, ergonomique, structurée, agréable à lire et engageante, comme un coach/ami intelligent mais aussi expert. Réponds de manière empathique et adaptée à la question, que ce soit médical ou général. Sois un vrai compagnon intelligent !"""

        return base_prompt

    def _detect_conversation_type(self, message: str) -> str:
        """Détecte le type de conversation"""
        message_lower = message.lower()

        critical_keywords = ["mal", "poitrine", "respir", "dos", "aide", "urgent", "grave", "intense", "8/10", "9/10", "10/10"]
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
        """Formate la réponse IA en HTML sécurisé avec style amélioré"""

        # Détection d'urgence (ajout de "dos")
        is_emergency = any(word in user_message.lower() for word in ["mal", "poitrine", "respir", "dos", "aide", "urgent"])

        if is_emergency:
            css_class = "response-section emergency-alert"
            icon = "fas fa-exclamation-triangle"
        else:
            css_class = "response-section medical-info"
            icon = "fas fa-user-md"

        # Nettoyage sécurisé du contenu
        import html
        safe_response = html.escape(ai_response)

        # 🎨 AMÉLIORATION DU STYLE - Formatage intelligent
        formatted_response = self._enhance_text_formatting(safe_response)

        html_response = f"""
        <div class="{css_class}">
            <h3><i class="{icon}"></i> Kidjamo Assistant</h3>
            <div class="response-content">
                {formatted_response}
            </div>
        </div>
        """

        return html_response

    def _enhance_text_formatting(self, text: str) -> str:
        """Améliore le formatage du texte avec style professionnel"""

        if not text or len(text.strip()) < 5:
            return "<p>Comment puis-je vous aider avec votre drépanocytose ?</p>"

        # Détecter si c'est une liste de conseils
        if any(indicator in text.lower() for indicator in ["éviter", "conseils", "prévention", "-", "•"]):
            return self._format_as_styled_list(text)

        # Détecter si c'est une urgence
        elif any(word in text.lower() for word in ["1510", "chu", "urgence", "appelez"]):
            return self._format_as_emergency(text)

        # Formatage standard avec style
        else:
            return self._format_as_standard(text)

    def _format_as_styled_list(self, text: str) -> str:
        """Formate le texte comme une liste stylée de conseils"""

        # Séparer en phrases/éléments
        items = []
        sentences = text.replace('-', '').replace('•', '').split('.')

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:  # Éviter les fragments trop courts
                # Ajouter icônes selon le contenu
                if "éviter" in sentence.lower():
                    items.append(f"🚫 {sentence}")
                elif "boire" in sentence.lower() or "hydrat" in sentence.lower():
                    items.append(f"💧 {sentence}")
                elif "médicament" in sentence.lower() or "siklos" in sentence.lower():
                    items.append(f"💊 {sentence}")
                elif "médecin" in sentence.lower() or "suivi" in sentence.lower():
                    items.append(f"🩺 {sentence}")
                else:
                    items.append(f"✅ {sentence}")

        if items:
            list_html = "<div class='advice-list'><h4>💡 Conseils drépanocytose :</h4><ul class='styled-list'>"
            for item in items[:4]:  # Max 4 conseils
                list_html += f"<li>{item}</li>"
            list_html += "</ul></div>"
            return list_html

        return f"<p>{text}</p>"

    def _format_as_emergency(self, text: str) -> str:
        """Formate le texte comme une alerte d'urgence"""

        return f"""
        <div class="emergency-content">
            <p class="emergency-text">🚨 <strong>{text}</strong></p>
            <div class="emergency-contacts">
                <p><strong>📞 URGENCES CAMEROUN :</strong></p>
                <ul class="contact-list">
                    <li><span class="phone-number">1510</span> Urgence nationale</li>
                    <li><strong>CHU Yaoundé</strong> - Hématologie</li>
                    <li><strong>Hôpital Laquintinie Douala</strong></li>
                </ul>
            </div>
        </div>
        """

    def _format_as_standard(self, text: str) -> str:
        """Formatage standard avec style professionnel"""

        # Remplacer les mots-clés importants par du texte stylé
        styled_text = text

        # Numéros de téléphone
        styled_text = styled_text.replace("1510", "<span class='phone-number'>📞 1510</span>")

        # Hôpitaux
        styled_text = styled_text.replace("CHU Yaoundé", "<strong>🏥 CHU Yaoundé</strong>")
        styled_text = styled_text.replace("Hôpital Laquintinie", "<strong>🏥 Hôpital Laquintinie</strong>")

        # Médicaments
        styled_text = styled_text.replace("Siklos", "<span class='medication'>💊 Siklos</span>")
        styled_text = styled_text.replace("siklos", "<span class='medication'>💊 Siklos</span>")

        # Niveaux de douleur
        for level in ["7/10", "8/10", "9/10", "10/10"]:
            if level in styled_text:
                styled_text = styled_text.replace(level, f"<span class='pain-level'>🔥 {level}</span>")

        return f"<p class='medical-response'>{styled_text}</p>"

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

        if any(word in message_lower for word in ["mal", "poitrine", "respir", "aide", "urgent", "dos"]):
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
            "source": f"bedrock-boto3-fallback-{error_type}",
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
            "service": "bedrock-boto3-aws-sdk",
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
            "selection_strategy": "Automatique selon urgence médicale"
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

            logger.info(f"Réponse à la demande d'heure pour session {session_id}")
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

            logger.info(f"Réponse à la salutation pour session {session_id}")
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

            logger.info(f"Réponse aux remerciements pour session {session_id}")
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

            logger.info(f"Réponse à la demande d'aide pour session {session_id}")
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
