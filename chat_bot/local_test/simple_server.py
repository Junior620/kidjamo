"""
Serveur Flask simplifié pour le chatbot Kidjamo
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import random

app = Flask(__name__)
CORS(app)

# Réponses simulées pour le chatbot
RESPONSES = {
    "bonjour": """
        <div class="response-section medical-info">
            <h3><i class="fas fa-user-md"></i> Bonjour ! Je suis votre assistant santé Kidjamo</h3>
            <p>Je suis spécialisé dans l'accompagnement des patients atteints de drépanocytose. Je peux vous aider avec :</p>
            <ul class="help-list">
                <li><strong>Gestion de la douleur</strong> - Évaluation et conseils personnalisés</li>
                <li><strong>Suivi des médicaments</strong> - Rappels et interactions</li>
                <li><strong>Données vitales</strong> - Analyse de vos mesures IoT</li>
                <li><strong>Urgences médicales</strong> - Protocoles et contacts d'urgence</li>
                <li><strong>Éducation thérapeutique</strong> - Informations sur votre maladie</li>
            </ul>
            <p>Comment puis-je vous aider aujourd'hui ?</p>
        </div>
    """,
    "mal": """
        <div class="response-section pain-management">
            <h3><i class="fas fa-exclamation-triangle"></i> Évaluation de la douleur</h3>
            <p>Je comprends que vous ressentez de la douleur. C'est important de bien l'évaluer pour vous aider efficacement.</p>
            <h4><i class="fas fa-clipboard-check"></i> Évaluation rapide :</h4>
            <ul class="urgent-list">
                <li><strong>Localisation</strong> - Où ressentez-vous la douleur exactement ?</li>
                <li><strong>Intensité</strong> - Sur une échelle de 1 à 10, comment évaluez-vous la douleur ?</li>
                <li><strong>Durée</strong> - Depuis combien de temps dure cette douleur ?</li>
                <li><strong>Caractère</strong> - Est-ce une douleur aiguë, sourde, pulsatile ?</li>
            </ul>
            <h4><i class="fas fa-pills"></i> Actions immédiates :</h4>
            <ul class="help-list">
                <li><strong>Hydratation</strong> - Buvez beaucoup d'eau</li>
                <li><strong>Repos</strong> - Mettez-vous au calme</li>
                <li><strong>Médicaments</strong> - Prenez vos antalgiques si prescrits</li>
                <li><strong>Chaleur</strong> - Appliquez une source de chaleur douce si possible</li>
            </ul>
            <p><strong>⚠️ Si la douleur est intense (>7/10) ou s'aggrave rapidement, contactez immédiatement les urgences.</strong></p>
        </div>
    """,
    "médicaments": """
        <div class="response-section medication-section">
            <h3><i class="fas fa-pills"></i> Gestion des médicaments</h3>
            <p>La gestion rigoureuse des médicaments est cruciale dans le traitement de la drépanocytose.</p>
            <h4><i class="fas fa-list-check"></i> Médicaments principaux :</h4>
            <ul class="info-list">
                <li><strong>Hydroxyurée</strong> - Traitement de fond pour réduire les crises</li>
                <li><strong>Antalgiques</strong> - Paracétamol, anti-inflammatoires pour la douleur</li>
                <li><strong>Acide folique</strong> - Supplément vitaminique essentiel</li>
                <li><strong>Antibiotiques préventifs</strong> - Protection contre les infections</li>
            </ul>
            <h4><i class="fas fa-clock"></i> Conseils de prise :</h4>
            <ul class="help-list">
                <li><strong>Régularité</strong> - Prenez vos médicaments aux heures fixes</li>
                <li><strong>Hydratation</strong> - Avec un grand verre d'eau</li>
                <li><strong>Suivi</strong> - Notez les prises dans un carnet</li>
                <li><strong>Interactions</strong> - Vérifiez avec votre médecin avant tout nouveau médicament</li>
            </ul>
        </div>
    """,
    "drépanocytose": """
        <div class="response-section medical-info">
            <h3><i class="fas fa-dna"></i> Qu'est-ce que la drépanocytose ?</h3>
            <p>La drépanocytose est une maladie génétique qui affecte l'hémoglobine, la protéine des globules rouges qui transporte l'oxygène.</p>
            <h4><i class="fas fa-microscope"></i> Mécanisme :</h4>
            <ul class="info-list">
                <li><strong>Hémoglobine anormale</strong> - Les globules rouges prennent une forme de faucille</li>
                <li><strong>Obstruction vasculaire</strong> - Blocage de la circulation sanguine</li>
                <li><strong>Hémolyse</strong> - Destruction prématurée des globules rouges</li>
                <li><strong>Anémie chronique</strong> - Manque d'oxygène dans les tissus</li>
            </ul>
            <h4><i class="fas fa-symptoms"></i> Symptômes principaux :</h4>
            <ul class="urgent-list">
                <li><strong>Crises douloureuses</strong> - Episodes de douleur intense</li>
                <li><strong>Fatigue</strong> - Due à l'anémie chronique</li>
                <li><strong>Infections fréquentes</strong> - Système immunitaire affaibli</li>
                <li><strong>Retard de croissance</strong> - Chez les enfants</li>
            </ul>
        </div>
    """,
    "urgence": """
        <div class="emergency-alert">
            <h3><i class="fas fa-ambulance"></i> URGENCE MÉDICALE</h3>
            <p><strong>🚨 Contactez immédiatement les secours si vous présentez :</strong></p>
            <ul class="urgent-list">
                <li><strong>Douleur thoracique intense</strong> - Possible syndrome thoracique aigu</li>
                <li><strong>Difficultés respiratoires</strong> - Essoufflement, respiration rapide</li>
                <li><strong>Fièvre élevée (>38.5°C)</strong> - Risque d'infection grave</li>
                <li><strong>Douleur abdominale sévère</strong> - Possible séquestration splénique</li>
                <li><strong>Priapisme</strong> - Érection douloureuse prolongée</li>
                <li><strong>AVC</strong> - Troubles de la parole, paralysie, confusion</li>
            </ul>
            <h4><i class="fas fa-phone"></i> Numéros d'urgence :</h4>
            <ul class="help-list">
                <li><span class="emergency-number">15</span> <strong>SAMU</strong> - Urgences médicales</li>
                <li><span class="emergency-number">112</span> <strong>Numéro européen</strong> - Urgences</li>
                <li><strong>Centre de référence drépanocytose</strong> - Contactez votre hôpital de suivi</li>
            </ul>
        </div>
    """
}

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '').lower()

        # Logique simple de détection de mots-clés
        response = "Je vous écoute. Pouvez-vous me donner plus de détails ?"
        conversation_type = "general"

        if any(word in message for word in ['bonjour', 'salut', 'hello', 'bonsoir']):
            response = RESPONSES["bonjour"]
            conversation_type = "greeting"
        elif any(word in message for word in ['mal', 'douleur', 'souffre', 'fait mal']):
            response = RESPONSES["mal"]
            conversation_type = "pain_management"
        elif any(word in message for word in ['médicament', 'traitement', 'pilule', 'médoc']):
            response = RESPONSES["médicaments"]
            conversation_type = "medication"
        elif any(word in message for word in ['drépanocytose', 'maladie', 'qu\'est-ce que']):
            response = RESPONSES["drépanocytose"]
            conversation_type = "medical_info"
        elif any(word in message for word in ['urgence', 'grave', 'hôpital', 'secours']):
            response = RESPONSES["urgence"]
            conversation_type = "emergency"

        return jsonify({
            'success': True,
            'response': response,
            'conversation_type': conversation_type,
            'timestamp': str(datetime.now())
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'Kidjamo Chatbot'})

if __name__ == '__main__':
    print("🚀 Démarrage du serveur Kidjamo Health Assistant...")
    print("🌐 Interface web disponible sur: http://localhost:5000")
    print("💬 API chatbot disponible sur: http://localhost:5000/chat")
    app.run(host='0.0.0.0', port=5000, debug=True)
