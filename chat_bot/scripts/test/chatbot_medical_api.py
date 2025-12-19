#!/usr/bin/env python3
"""
API REST pour le chatbot médical Kidjamo
Endpoint de remplacement pour Kendra avec base de connaissances intégrée
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
from datetime import datetime
import sys
import os

# Ajouter le chemin pour importer notre chatbot
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from kidjamo_chatbot_medical_v2 import KidjamoChatbotMedical

# Configuration Flask
app = Flask(__name__)
CORS(app)  # Permettre les requêtes cross-origin

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot_medical_api.log'),
        logging.StreamHandler()
    ]
)

# Instance globale du chatbot
chatbot = KidjamoChatbotMedical()

@app.route('/health', methods=['GET'])
def health_check():
    """Vérification de santé de l'API"""
    return jsonify({
        "status": "healthy",
        "service": "Kidjamo Medical Chatbot API",
        "version": "2.0",
        "timestamp": datetime.utcnow().isoformat(),
        "kendra_replacement": True
    })

@app.route('/query', methods=['POST'])
def process_medical_query():
    """
    Endpoint principal pour traiter les requêtes médicales
    Compatible avec l'interface Kendra existante
    """
    try:
        # Récupérer la requête
        data = request.get_json()

        if not data or 'query' not in data:
            return jsonify({
                "error": "Missing 'query' parameter",
                "status": "error"
            }), 400

        query_text = data['query'].strip()

        if not query_text:
            return jsonify({
                "error": "Empty query",
                "status": "error"
            }), 400

        # Traiter la requête avec notre chatbot
        logging.info(f"Processing query: {query_text}")

        resultats = chatbot.rechercher_reponse_avancee(query_text)
        reponse_formatee = chatbot.formater_reponse_complete(resultats)

        # Format compatible avec l'interface Kendra existante
        response = {
            "status": "success",
            "query": query_text,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "kidjamo_medical_kb",
            "results": {
                "formatted_response": reponse_formatee,
                "raw_results": resultats,
                "total_results": len(resultats.get("resultats", [])),
                "is_emergency": resultats.get("urgence", {}).get("est_urgence", False),
                "emergency_level": resultats.get("urgence", {}).get("niveau", "none"),
                "suggestions": resultats.get("suggestions", [])
            }
        }

        # Log pour monitoring
        logging.info(f"Query processed successfully. Results: {len(resultats.get('resultats', []))}, Emergency: {resultats.get('urgence', {}).get('est_urgence', False)}")

        return jsonify(response)

    except Exception as e:
        logging.error(f"Error processing query: {str(e)}")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "status": "error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/kendra-compatible', methods=['POST'])
def kendra_compatible_query():
    """
    Endpoint 100% compatible avec l'API Kendra existante
    Permet de remplacer Kendra sans changer le code client
    """
    try:
        data = request.get_json()

        # Extraire les paramètres comme Kendra
        query_text = data.get('QueryText', '')
        page_size = data.get('PageSize', 5)

        if not query_text:
            return jsonify({
                "ResultItems": [],
                "TotalNumberOfResults": 0,
                "QueryId": f"kidjamo-{int(datetime.utcnow().timestamp())}"
            })

        # Traiter avec notre chatbot
        resultats = chatbot.rechercher_reponse_avancee(query_text)

        # Convertir au format Kendra
        result_items = []

        for i, resultat in enumerate(resultats.get("resultats", [])[:page_size]):
            result_items.append({
                "Id": f"kidjamo-result-{i+1}",
                "Type": "DOCUMENT" if not resultats.get("urgence", {}).get("est_urgence") else "ANSWER",
                "DocumentTitle": {
                    "Text": resultat["titre"],
                    "Highlights": []
                },
                "DocumentExcerpt": {
                    "Text": resultat["contenu"][:200] + "..." if len(resultat["contenu"]) > 200 else resultat["contenu"],
                    "Highlights": []
                },
                "DocumentId": f"kidjamo-doc-{resultat.get('item_id', i)}",
                "ScoreAttributes": {
                    "ScoreConfidence": "HIGH" if resultat.get("score", 0) > 15 else "MEDIUM"
                }
            })

        # Réponse au format Kendra
        kendra_response = {
            "QueryId": f"kidjamo-{int(datetime.utcnow().timestamp())}",
            "ResultItems": result_items,
            "TotalNumberOfResults": len(resultats.get("resultats", [])),
            "QueryResultTypeFilter": "DOCUMENT"
        }

        logging.info(f"Kendra-compatible query processed: '{query_text}' -> {len(result_items)} results")

        return jsonify(kendra_response)

    except Exception as e:
        logging.error(f"Error in Kendra-compatible endpoint: {str(e)}")
        return jsonify({
            "ResultItems": [],
            "TotalNumberOfResults": 0,
            "QueryId": "error",
            "ErrorMessage": str(e)
        }), 500

@app.route('/emergency-check', methods=['POST'])
def emergency_check():
    """Endpoint spécialisé pour la détection d'urgences"""
    try:
        data = request.get_json()
        query_text = data.get('query', '')

        urgence = chatbot.detecter_urgence(query_text)

        return jsonify({
            "query": query_text,
            "is_emergency": urgence["est_urgence"],
            "emergency_details": urgence if urgence["est_urgence"] else None,
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logging.error(f"Error in emergency check: {str(e)}")
        return jsonify({
            "error": str(e),
            "is_emergency": False
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Statistiques de l'API"""
    return jsonify({
        "service": "Kidjamo Medical Chatbot API",
        "knowledge_base": {
            "categories": len(chatbot.base_connaissances),
            "total_items": sum(len(items) for items in chatbot.base_connaissances.values()),
            "emergency_types": len(chatbot.base_connaissances.get("urgences", {})),
            "treatments": len(chatbot.base_connaissances.get("traitements", {}))
        },
        "capabilities": [
            "Medical Q&A in French",
            "Emergency detection",
            "Cameroon-specific information",
            "Kendra API compatibility",
            "Real-time responses"
        ],
        "uptime": "Available 24/7",
        "last_update": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    print("🚀 DÉMARRAGE API CHATBOT MÉDICAL KIDJAMO")
    print("=" * 60)
    print("🏥 Service: Chatbot médical avec base de connaissances intégrée")
    print("🔄 Remplacement: Compatible API Kendra")
    print("🚨 Urgences: Détection automatique")
    print("🌍 Contexte: Cameroun/Afrique")
    print("=" * 60)

    # Démarrer l'API
    app.run(
        host='0.0.0.0',  # Accessible depuis n'importe quelle IP
        port=5000,       # Port standard
        debug=False,     # Mode production
        threaded=True    # Support multi-thread
    )
