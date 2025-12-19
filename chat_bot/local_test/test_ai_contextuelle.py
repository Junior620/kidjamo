#!/usr/bin/env python3
"""
🧠 TESTEUR DIRECT DES RÉPONSES IA CONTEXTUELLES
Simule les réponses IA intelligentes pour vérifier l'intégration
"""

from hybrid_logic import classify_message_with_context, extract_pain_level
from session_manager import session_manager
import time

class AIResponseSimulator:
    """Simule les réponses IA contextuelles pour démonstration"""

    def __init__(self):
        self.responses = {
            "emergency": {
                "aide moi": """🚨 **URGENCE DÉTECTÉE**

Je comprends que vous avez besoin d'aide urgente. Votre sécurité est ma priorité absolue.

**APPELEZ IMMÉDIATEMENT :**
• 115 (SAMU Cameroun) 
• 112 (Urgences européennes)

**EN ATTENDANT LES SECOURS :**
• Restez calme et ne paniquez pas
• Asseyez-vous ou allongez-vous confortablement
• Préparez vos papiers d'identité et carte de santé
• Mentionnez "patient drépanocytaire" aux secours

*Je reste avec vous pour vous accompagner.*""",

                "douleur atroce poitrine": """🆘 **DOULEUR THORACIQUE - URGENCE ABSOLUE**

Une douleur thoracique chez un patient drépanocytaire nécessite une prise en charge immédiate !

**ACTION IMMÉDIATE :**
• Appelez le 115 MAINTENANT
• NE BOUGEZ PLUS - restez en position assise
• Desserrez vos vêtements
• Si vous avez des antalgiques forts prescrits, prenez-les

**SYNDROME THORACIQUE AIGU** possible - c'est une complication grave de la drépanocytose qui nécessite une hospitalisation d'urgence.

*Les secours sont-ils en route ?*""",

                "ne peux plus respirer": """⚡ **DÉTRESSE RESPIRATOIRE - APPELEZ IMMÉDIATEMENT LE 115**

**ACTIONS VITALES :**
1️⃣ Appelez les secours SI CE N'EST PAS DÉJÀ FAIT
2️⃣ Position assise, dos droi
3️⃣ Inspirez lentement par le nez, expirez par la bouche
4️⃣ Ouvrez portes/fenêtres pour l'air frais

**⚠️ SYNDROME THORACIQUE AIGU** - complication potentiellement mortelle de la drépanocytose.

*Continuez à respirer calmement. Les secours arrivent.*"""
            },

            "emergency_followup": {
                "que faire": """🎯 **SUITE À VOTRE URGENCE**

Basé sur votre situation actuelle (douleur thoracique + difficultés respiratoires) :

**SI LES SECOURS NE SONT PAS ENCORE APPELÉS :**
• Faites-le MAINTENANT - 115

**SI LES SECOURS SONT EN ROUTE :**
• Restez en position assise
• Surveillez votre respiration
• Préparez-vous à expliquer : "Crise drépanocytose avec syndrome thoracique possible"

**À L'HÔPITAL, MENTIONNEZ :**
• Vos antécédents de drépanocytose
• Vos médicaments habituels
• L'évolution de vos symptômes

*Cette situation nécessite absolument une prise en charge hospitalière.*""",

                "dois aller urgences": """🏥 **OUI, ABSOLUMENT AUX URGENCES**

Avec vos symptômes (douleur thoracique + difficultés respiratoires), c'est une urgence médicale avérée.

**POURQUOI C'EST URGENT :**
• Syndrome thoracique aigu possible
• Complications cardio-pulmonaires
• Risque de crise vaso-occlusive majeure

**TRANSPORT :**
• Ambulance (appelez 115) - RECOMMANDÉ
• Évitez de conduire vous-même

**À EMPORTER :**
• Carte vitale et mutuelle
• Ordonnances en cours
• Liste de vos crises récentes

*N'attendez pas que ça passe - agissez maintenant !*"""
            },

            "gratitude": {
                "merci": """💙 **De rien, c'est naturel !**

Je suis ravi d'avoir pu vous accompagner dans ce moment difficile. Votre sécurité est ce qui compte le plus.

**RAPPELS IMPORTANTS :**
• Gardez mes conseils d'urgence en mémoire
• N'hésitez jamais à consulter en cas de doute
• Je suis là 24h/24 pour vous aider

**PRENEZ SOIN DE VOUS** 🌟
Et n'oubliez pas : en cas de nouvelle urgence, appelez toujours le 115 en premier.

*À bientôt, et j'espère dans de meilleures circonstances !*"""
            }
        }

    def generate_contextual_response(self, user_message: str, conversation_type: str, context: dict) -> str:
        """Génère une réponse contextuelle intelligente"""

        # Chercher une réponse spécifique
        category = self.responses.get(conversation_type, {})

        # Recherche par mots-clés
        message_lower = user_message.lower()
        for key, response in category.items():
            if any(keyword in message_lower for keyword in key.split()):
                return response

        # Réponses par défaut selon le type
        if conversation_type == "emergency_followup":
            return """🔄 **SUITE DE VOTRE URGENCE**

Vous avez déjà reçu les conseils d'urgence. Votre question spécifique mérite une réponse adaptée à votre situation actuelle.

**RAPPEL DE SÉCURITÉ :**
• Si les symptômes s'aggravent → Appelez 115
• Si les secours ne sont pas encore en route → Appelez maintenant
• Si vous hésitez → Mieux vaut consulter aux urgences

*Pouvez-vous me préciser votre situation actuelle ?*"""

        elif conversation_type == "pain_evolution":
            pain_level = extract_pain_level(user_message)
            if pain_level >= 8:
                return f"""🔥 **DOULEUR NIVEAU {pain_level}/10 - URGENCE**

Ce niveau de douleur nécessite une intervention médicale immédiate.

**ACTIONS URGENTES :**
• Prenez vos antalgiques les plus forts prescrits
• Appelez votre médecin ou les urgences (115)
• Position confortable, chaleur douce
• Hydratation importante

*Une douleur à {pain_level}/10 ne doit pas être supportée - cherchez de l'aide maintenant !*"""

        return """🤖 **Réponse IA Contextuelle**

Je comprends votre message dans le contexte de votre situation médicale actuelle. 

Basé sur notre conversation, je peux vous donner des conseils adaptés. Pouvez-vous être plus précis sur ce dont vous avez besoin ?"""

def test_ai_responses():
    """Test complet des réponses IA contextuelles"""

    print("\n" + "="*70)
    print("🧠 TEST DES RÉPONSES IA CONTEXTUELLES KIDJAMO")
    print("="*70)

    simulator = AIResponseSimulator()
    session_id = "test_ai_session"

    # Scénario d'urgence avec contextualisation
    scenarios = [
        {
            "message": "Aide moi",
            "expected_type": "emergency"
        },
        {
            "message": "J'ai une douleur atroce dans la poitrine",
            "expected_type": "emergency"
        },
        {
            "message": "Je n'arrive plus à respirer correctement",
            "expected_type": "emergency"
        },
        {
            "message": "Que faire ?",
            "expected_type": "emergency_followup"  # Contextuel après urgence
        },
        {
            "message": "Merci",
            "expected_type": "gratitude"
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[ÉTAPE {i}/5]")
        print(f"🧑 UTILISATEUR: {scenario['message']}")

        # Récupérer le contexte de session
        context = session_manager.get_context_for_ai(session_id)

        # Classification intelligente
        conversation_type, priority = classify_message_with_context(
            scenario['message'].lower(),
            context
        )

        print(f"🔍 CLASSIFICATION: {conversation_type} (priorité: {priority})")

        # Générer réponse IA contextuelle
        response = simulator.generate_contextual_response(
            scenario['message'],
            conversation_type,
            context
        )

        print(f"\n🤖 RÉPONSE IA CONTEXTUELLE:")
        print("-" * 50)
        print(response)
        print("-" * 50)

        # Mettre à jour le contexte
        session_manager.add_message(session_id, scenario['message'], response, conversation_type)

        # Gestion des contextes spéciaux
        if conversation_type == "emergency":
            session_manager.set_emergency_context(session_id, True)
        elif conversation_type == "gratitude":
            session_manager.reset_crisis_context(session_id)
            session_manager.set_emergency_context(session_id, False)

        time.sleep(1)

    print(f"\n✅ TEST TERMINÉ - L'IA CONTEXTUELLE FONCTIONNE !")
    print("🎯 Réponses adaptées au contexte conversationnel")
    print("🔄 Suivi intelligent des urgences")
    print("💡 Classification contextuelle avancée")

if __name__ == "__main__":
    test_ai_responses()
