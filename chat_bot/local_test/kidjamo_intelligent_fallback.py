"""
Serveur Kidjamo avec Fallback Intelligent - En attendant l'activation Bedrock
Chatbot médical intelligent sans IA externe, spécialisé drépanocytose
"""

import os
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime
from typing import Dict, Any
import json
import re

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KidjamoIntelligentFallback:
    """Chatbot médical intelligent sans IA externe - Spécialisé drépanocytose"""

    def __init__(self):
        # Base de connaissances médicales drépanocytose
        self.medical_knowledge = {
            "urgences": {
                "keywords": ["mal", "douleur", "poitrine", "respir", "8/10", "9/10", "10/10", "insupportable", "mourir", "aide", "urgent"],
                "response": """
                <div class="response-section emergency-alert">
                    <h3><i class="fas fa-ambulance"></i> 🚨 URGENCE MÉDICALE DÉTECTÉE</h3>
                    <p><strong>Protocole d'urgence drépanocytose activé</strong></p>
                    
                    <div class="urgent-actions">
                        <h4>🚨 ACTIONS IMMÉDIATES :</h4>
                        <ul class="urgent-list">
                            <li><strong>APPELEZ MAINTENANT :</strong></li>
                            <li><span class="emergency-number">📞 1510</span> Urgence nationale Cameroun</li>
                            <li><strong>🏥 CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                            <li><strong>🏥 Hôpital Central Yaoundé</strong> - Service urgences</li>
                            <li><strong>🏥 Hôpital Laquintinie Douala</strong> - Urgences spécialisées</li>
                        </ul>
                        
                        <h4>⚠️ MENTIONNEZ ABSOLUMENT :</h4>
                        <p><strong>"Patient drépanocytaire"</strong> pour prise en charge adaptée</p>
                        
                        <h4>🩺 EN ATTENDANT LES SECOURS :</h4>
                        <ul>
                            <li>Position confortable, éviter les mouvements brusques</li>
                            <li>Hydratation si conscient (eau tiède)</li>
                            <li>Préparer documents médicaux et traitement habituel</li>
                            <li>Noter l'heure de début des symptômes</li>
                        </ul>
                    </div>
                </div>
                """
            },
            
            "crise_douleur": {
                "keywords": ["crise", "douleur", "/10", "souffre", "insupportable", "mal"],
                "response": """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-heartbeat"></i> 🩺 GESTION CRISE DOULOUREUSE</h3>
                    
                    <div class="medical-protocol">
                        <h4>📊 ÉVALUATION DOULEUR :</h4>
                        <ul>
                            <li><strong>Échelle 1-3/10 :</strong> Crise légère - Antalgiques niveau 1</li>
                            <li><strong>Échelle 4-6/10 :</strong> Crise modérée - Consultation rapide</li>
                            <li><strong>Échelle 7-10/10 :</strong> 🚨 URGENCE - Hôpital immédiatement</li>
                        </ul>
                        
                        <h4>💊 PROTOCOLE ANTALGIQUE CAMEROUN :</h4>
                        <ul>
                            <li><strong>Niveau 1 :</strong> Paracétamol 1g x 4/jour</li>
                            <li><strong>Niveau 2 :</strong> + Ibuprofène 400mg x 3/jour</li>
                            <li><strong>Niveau 3 :</strong> 🏥 Morphiniques en milieu hospitalier</li>
                        </ul>
                        
                        <h4>🌡️ MESURES D'ACCOMPAGNEMENT :</h4>
                        <ul>
                            <li>Hydratation abondante (2-3L/jour)</li>
                            <li>Repos au calme, température ambiante</li>
                            <li>Éviter le froid et les efforts intenses</li>
                            <li>Application de chaleur douce sur zones douloureuses</li>
                        </ul>
                        
                        <p><strong>⚠️ Si douleur > 6/10 ou persistante > 2h : Consultation d'urgence</strong></p>
                    </div>
                </div>
                """
            },
            
            "medicaments": {
                "keywords": ["médicament", "siklos", "traitement", "pilule", "dose", "oubli", "hydroxyurée"],
                "response": """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-pills"></i> 💊 TRAITEMENT DRÉPANOCYTOSE</h3>
                    
                    <div class="medication-guide">
                        <h4>🔸 SIKLOS (Hydroxyurée) - Traitement de fond :</h4>
                        <ul>
                            <li><strong>Posologie habituelle :</strong> 15-25 mg/kg/jour</li>
                            <li><strong>Prise :</strong> 1 fois/jour, de préférence le matin</li>
                            <li><strong>Surveillance :</strong> NFS mensuelle obligatoire</li>
                            <li><strong>Oubli :</strong> Si < 12h, prendre immédiatement. Si > 12h, attendre le lendemain</li>
                        </ul>
                        
                        <h4>🔸 ANTALGIQUES D'URGENCE :</h4>
                        <ul>
                            <li><strong>Paracétamol :</strong> 1g x 4/jour (max 4g/jour)</li>
                            <li><strong>Ibuprofène :</strong> 400mg x 3/jour (avec repas)</li>
                            <li><strong>Tramadol :</strong> Sur prescription, 50-100mg x 4/jour</li>
                        </ul>
                        
                        <h4>🔸 SUPPLÉMENTATION :</h4>
                        <ul>
                            <li><strong>Acide folique :</strong> 5mg/jour en continu</li>
                            <li><strong>Fer :</strong> Seulement si carence prouvée</li>
                            <li><strong>Vitamines B :</strong> Selon prescription médicale</li>
                        </ul>
                        
                        <h4>⚠️ INTERACTIONS À ÉVITER :</h4>
                        <ul>
                            <li>Aspirine (risque hémorragique)</li>
                            <li>Alcool (majore la toxicité)</li>
                            <li>Médicaments néphrotoxiques</li>
                        </ul>
                        
                        <p><strong>📞 Suivi médical : CHU Yaoundé - Hématologie : +237 222 23 40 29</strong></p>
                    </div>
                </div>
                """
            },
            
            "prevention": {
                "keywords": ["prévention", "éviter", "conseil", "hygiène", "vie"],
                "response": """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-shield-alt"></i> 🛡️ PRÉVENTION CRISES DRÉPANOCYTOSE</h3>
                    
                    <div class="prevention-guide">
                        <h4>💧 HYDRATATION (Priorité absolue) :</h4>
                        <ul>
                            <li><strong>Minimum 2,5-3L/jour</strong> en climat camerounais</li>
                            <li>Eau à température ambiante (éviter trop froide)</li>
                            <li>Augmenter en cas de fièvre, chaleur, effort</li>
                            <li>Jus de fruits dilués acceptés</li>
                        </ul>
                        
                        <h4>🌡️ GESTION CLIMAT CAMEROUN :</h4>
                        <ul>
                            <li>Éviter exposition solaire 11h-16h</li>
                            <li>Ventilation/climatisation modérée (éviter chocs thermiques)</li>
                            <li>Vêtements légers, couvrants, clairs</li>
                            <li>Protection tête et nuque obligatoire</li>
                        </ul>
                        
                        <h4>🏃‍♂️ ACTIVITÉ PHYSIQUE ADAPTÉE :</h4>
                        <ul>
                            <li>Exercice modéré encouragé (marche, natation douce)</li>
                            <li>Éviter sports intensifs, contact, altitude</li>
                            <li>Hydratation avant/pendant/après effort</li>
                            <li>Arrêt immédiat si essoufflement anormal</li>
                        </ul>
                        
                        <h4>🦠 PRÉVENTION INFECTIONS :</h4>
                        <ul>
                            <li>Vaccination à jour (pneumocoque, méningocoque, grippe)</li>
                            <li>Hygiène rigoureuse (lavage mains)</li>
                            <li>Éviter foules pendant épidémies</li>
                            <li>Antibiothérapie préventive si prescrite</li>
                        </ul>
                        
                        <h4>🚫 À ÉVITER ABSOLUMENT :</h4>
                        <ul>
                            <li>Déshydratation (alcool, diurétiques)</li>
                            <li>Froid intense (climatisation excessive)</li>
                            <li>Altitude > 1500m sans précautions</li>
                            <li>Stress intense, manque de sommeil</li>
                        </ul>
                    </div>
                </div>
                """
            },
            
            "vaccinations": {
                "keywords": ["vaccin", "vaccination", "pneumocoque", "méningocoque"],
                "response": """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-syringe"></i> 💉 VACCINATIONS DRÉPANOCYTOSE</h3>
                    
                    <div class="vaccination-protocol">
                        <h4>🔸 VACCINATIONS OBLIGATOIRES :</h4>
                        <ul>
                            <li><strong>Pneumocoque (Prevenar 13) :</strong> Protection infections pulmonaires</li>
                            <li><strong>Méningocoque ACWY :</strong> Prévention méningites</li>
                            <li><strong>Haemophilus influenzae :</strong> Protection ORL</li>
                            <li><strong>Grippe saisonnière :</strong> Annuelle, octobre-novembre</li>
                        </ul>
                        
                        <h4>🔸 VACCINATIONS RECOMMANDÉES :</h4>
                        <ul>
                            <li><strong>Hépatite B :</strong> Protection hépatique</li>
                            <li><strong>COVID-19 :</strong> Priorité patient à risque</li>
                            <li><strong>Fièvre jaune :</strong> Obligatoire au Cameroun</li>
                        </ul>
                        
                        <h4>🏥 CENTRES VACCINATION CAMEROUN :</h4>
                        <ul>
                            <li><strong>CHU Yaoundé :</strong> Service Médecine Interne</li>
                            <li><strong>Hôpital Central Yaoundé :</strong> Consultations externes</li>
                            <li><strong>Centre Pasteur Cameroun :</strong> Vaccinations spécialisées</li>
                            <li><strong>Centres de santé intégrés :</strong> Vaccins de routine</li>
                        </ul>
                        
                        <p><strong>📞 Info vaccinations : Centre Pasteur +237 222 23 15 55</strong></p>
                    </div>
                </div>
                """
            }
        }
        
        # Réponses générales
        self.general_responses = {
            "salutation": {
                "keywords": ["bonjour", "salut", "bonsoir", "hello", "coucou"],
                "response": """
                <div class="response-section medical-info">
                    <h3><i class="fas fa-user-md"></i> 👋 Bonjour ! Je suis Kidjamo Assistant</h3>
                    <p>Assistant médical spécialisé dans l'accompagnement des patients atteints de <strong>drépanocytose au Cameroun</strong>.</p>
                    
                    <div class="services-overview">
                        <h4>🩺 MES SERVICES :</h4>
                        <ul>
                            <li><strong>🚨 Urgences médicales</strong> - Protocoles d'urgence spécialisés</li>
                            <li><strong>💊 Gestion médicaments</strong> - Siklos, antalgiques, posologies</li>
                            <li><strong>🛡️ Prévention crises</strong> - Conseils adaptés au climat camerounais</li>
                            <li><strong>🏥 Orientation soins</strong> - Centres spécialisés Yaoundé/Douala</li>
                        </ul>
                        
                        <h4>🇨🇲 CENTRES RÉFÉRENCE CAMEROUN :</h4>
                        <ul>
                            <li><strong>CHU Yaoundé</strong> - Hématologie spécialisée</li>
                            <li><strong>Hôpital Central Yaoundé</strong> - Urgences 24h/24</li>
                            <li><strong>Hôpital Laquintinie Douala</strong> - Suivi drépanocytose</li>
                        </ul>
                    </div>
                    
                    <p><strong>Comment puis-je vous accompagner aujourd'hui ?</strong></p>
                    <p><em>💡 Exemples : "J'ai une crise douloureuse", "Conseils prévention", "Oubli médicament"</em></p>
                </div>
                """
            },
            
            "date_temps": {
                "keywords": ["jour", "date", "heure", "temps", "quand"],
                "response": f"""
                <div class="response-section medical-info">
                    <h3><i class="fas fa-calendar"></i> 📅 Informations Temporelles</h3>
                    <p>Nous sommes le <strong>{datetime.now().strftime('%A %d %B %Y')}</strong></p>
                    <p>Il est actuellement <strong>{datetime.now().strftime('%H:%M')}</strong> (heure Cameroun)</p>
                    
                    <div class="medical-reminder">
                        <h4>⏰ RAPPELS MÉDICAUX QUOTIDIENS :</h4>
                        <ul>
                            <li><strong>Matin (8h) :</strong> Prise Siklos + Hydratation (500ml)</li>
                            <li><strong>Midi (12h) :</strong> Contrôle hydratation</li>
                            <li><strong>Soir (18h) :</strong> Bilan journée, température</li>
                            <li><strong>Nuit (22h) :</strong> Préparation repos, hydratation</li>
                        </ul>
                        
                        <p><strong>💧 Objectif hydratation journalière : 2,5-3L minimum</strong></p>
                    </div>
                </div>
                """
            }
        }

    def process_message(self, user_message: str, context: Dict) -> Dict:
        """Analyse le message et génère une réponse médicale intelligente"""
        
        message_lower = user_message.lower().strip()
        
        # 1. Vérification urgences (priorité absolue)
        for keyword in self.medical_knowledge["urgences"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.medical_knowledge["urgences"]["response"],
                    "conversation_type": "emergency",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "critical",
                    "success": True
                }
        
        # 2. Gestion crises douloureuses
        for keyword in self.medical_knowledge["crise_douleur"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.medical_knowledge["crise_douleur"]["response"],
                    "conversation_type": "pain_management",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "high",
                    "success": True
                }
        
        # 3. Questions médicaments
        for keyword in self.medical_knowledge["medicaments"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.medical_knowledge["medicaments"]["response"],
                    "conversation_type": "medication",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "normal",
                    "success": True
                }
        
        # 4. Prévention et conseils
        for keyword in self.medical_knowledge["prevention"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.medical_knowledge["prevention"]["response"],
                    "conversation_type": "prevention",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "normal",
                    "success": True
                }
        
        # 5. Vaccinations
        for keyword in self.medical_knowledge["vaccinations"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.medical_knowledge["vaccinations"]["response"],
                    "conversation_type": "vaccination",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "normal",
                    "success": True
                }
        
        # 6. Salutations
        for keyword in self.general_responses["salutation"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.general_responses["salutation"]["response"],
                    "conversation_type": "greeting",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "normal",
                    "success": True
                }
        
        # 7. Questions date/temps
        for keyword in self.general_responses["date_temps"]["keywords"]:
            if keyword in message_lower:
                return {
                    "response": self.general_responses["date_temps"]["response"],
                    "conversation_type": "datetime",
                    "source": "kidjamo-intelligent-fallback",
                    "urgency_level": "normal",
                    "success": True
                }
        
        # 8. Réponse par défaut avec orientation
        return {
            "response": """
            <div class="response-section medical-info">
                <h3><i class="fas fa-user-md"></i> 🤔 Pouvez-vous préciser votre question ?</h3>
                <p>Je suis spécialisé dans l'accompagnement des patients atteints de <strong>drépanocytose au Cameroun</strong>.</p>
                
                <div class="help-suggestions">
                    <h4>💡 EXEMPLES DE QUESTIONS :</h4>
                    <ul>
                        <li><strong>"J'ai mal à la poitrine"</strong> → Protocole d'urgence</li>
                        <li><strong>"Crise douloureuse 7/10"</strong> → Gestion antalgique</li>
                        <li><strong>"Oubli Siklos"</strong> → Conseils médicamenteux</li>
                        <li><strong>"Conseils prévention"</strong> → Hygiène de vie</li>
                        <li><strong>"Vaccinations"</strong> → Protocole vaccinal</li>
                    </ul>
                    
                    <h4>🚨 EN CAS D'URGENCE IMMÉDIATE :</h4>
                    <ul class="urgent-list">
                        <li><span class="emergency-number">📞 1510</span> Urgence nationale Cameroun</li>
                        <li><strong>🏥 CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                    </ul>
                </div>
                
                <p><strong>Reformulez votre question pour une assistance médicale personnalisée.</strong></p>
            </div>
            """,
            "conversation_type": "clarification",
            "source": "kidjamo-intelligent-fallback",
            "urgency_level": "normal",
            "success": True
        }

# Serveur Flask avec chatbot intelligent
app = Flask(__name__)
CORS(app, origins=["*"])
chatbot = KidjamoIntelligentFallback()

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Endpoint chat avec IA médicale intelligente"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'fallback_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Message vide',
                'session_id': session_id
            }), 400
        
        # Contexte enrichi
        context = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'user_ip': request.environ.get('REMOTE_ADDR', 'unknown')
        }
        
        # Traitement intelligent
        response_data = chatbot.process_message(user_message, context)
        
        # Enrichissement réponse
        response_data.update({
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'environment': 'kidjamo-intelligent-fallback',
            'cost_estimate': 0.0,  # Gratuit !
            'model_used': 'kidjamo-medical-kb',
            'raw_response': 'Réponse générée par base de connaissances médicales'
        })
        
        logger.info(f"🤖 Réponse intelligente générée - Session: {session_id[:8]}..., Type: {response_data.get('conversation_type')}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ Erreur chat intelligent: {e}")
        return jsonify({
            'success': False,
            'response': """
            <div class="response-section emergency-alert">
                <h3><i class="fas fa-exclamation-triangle"></i> Service temporairement indisponible</h3>
                <p><strong>Pour une urgence médicale drépanocytaire :</strong></p>
                <ul class="urgent-list">
                    <li><span class="emergency-number">1510</span> Urgence nationale Cameroun</li>
                    <li><strong>CHU Yaoundé</strong> - Centre référence drépanocytose</li>
                </ul>
            </div>
            """,
            'conversation_type': 'system_error',
            'session_id': data.get('session_id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check chatbot intelligent"""
    return jsonify({
        'status': 'healthy',
        'service': 'kidjamo-intelligent-fallback',
        'version': '1.0.0-medical-kb',
        'specialization': 'Drépanocytose Cameroun',
        'cost': 'Gratuit',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Page d'accueil chatbot intelligent"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Kidjamo Assistant - IA Médicale Intelligente ACTIVE !</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #4CAF50, #2196F3); margin: 0; padding: 40px; }
            .container { max-width: 800px; background: white; border-radius: 20px; padding: 40px; text-align: center; margin: 0 auto; }
            .logo { font-size: 4rem; margin-bottom: 20px; }
            .badge { background: linear-gradient(135deg, #4CAF50, #2196F3); color: white; padding: 10px 20px; border-radius: 20px; font-weight: bold; }
            h1 { color: #333; margin: 20px 0 10px; }
            .status { background: #e8f5e8; border: 2px solid #4CAF50; border-radius: 15px; padding: 20px; margin: 20px 0; }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }
            .feature { background: #f8f9fa; padding: 20px; border-radius: 15px; border-left: 5px solid #4CAF50; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="badge">🤖 IA MÉDICALE INTELLIGENTE ACTIVE</div>
            <div class="logo">🏥💚🧠</div>
            <h1>Kidjamo Assistant</h1>
            <p style="font-size: 1.2rem; color: #666;">IA Médicale Intelligente - Spécialisée Drépanocytose Cameroun</p>
            
            <div class="status">
                <h3>✅ SERVICE OPÉRATIONNEL</h3>
                <p>✅ Base de connaissances médicales active<br>
                ✅ Protocoles d'urgence Cameroun intégrés<br>
                ✅ Réponses intelligentes sans coût externe</p>
            </div>
            
            <div class="features">
                <div class="feature">
                    <h4>🚨 Urgences Médicales</h4>
                    <p>Détection automatique + protocoles CHU Yaoundé</p>
                </div>
                <div class="feature">
                    <h4>💊 Gestion Siklos</h4>
                    <p>Posologies, oublis, surveillance adaptée</p>
                </div>
                <div class="feature">
                    <h4>🛡️ Prévention</h4>
                    <p>Conseils climat camerounais spécialisés</p>
                </div>
                <div class="feature">
                    <h4>🏥 Orientation Soins</h4>
                    <p>Centres spécialisés Yaoundé/Douala</p>
                </div>
            </div>
            
            <h3>🧪 Testez maintenant :</h3>
            <p><strong>Exemples :</strong> "Bonjour", "J'ai mal", "Conseil prévention", "Oubli Siklos"</p>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 KIDJAMO ASSISTANT - IA MÉDICALE INTELLIGENTE")
    print("="*60)
    print("   🌐 URL: http://localhost:5000")
    print("   🧠 Base de connaissances médicales active")
    print("   🇨🇲 Spécialisé drépanocytose Cameroun")
    print("   💰 Coût: GRATUIT (pas d'IA externe)")
    print("   🚀 PRÊT À FONCTIONNER IMMÉDIATEMENT !")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
