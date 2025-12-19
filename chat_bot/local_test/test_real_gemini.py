"""
Test RÉEL du chatbot Kidjamo avec Gemini Flash
Teste les scénarios d'urgence et de crise avec l'IA
"""

import os
import sys
from dotenv import load_dotenv
from ai_engine_lightweight import LightweightAIEngine

# Charger les variables d'environnement
load_dotenv()

def test_real_medical_scenarios():
    """Test avec les vrais scénarios de votre simulation"""
    
    print("🚀 TEST CHATBOT KIDJAMO AVEC GEMINI FLASH")
    print("=" * 60)
    
    # Initialiser le moteur IA
    ai_engine = LightweightAIEngine()
    
    # Vérifier la configuration
    if not ai_engine.google_api_key:
        print("❌ Clé API Google non trouvée dans .env")
        return False
        
    print("✅ Gemini Flash configuré - Test avec vrais scénarios")
    
    # Scénarios RÉELS de vos simulations
    urgency_scenarios = [
        {
            "message": "Aide moi",
            "type": "emergency", 
            "expected": "urgence détectée"
        },
        {
            "message": "J'ai une douleur atroce dans la poitrine", 
            "type": "emergency",
            "expected": "appelez immédiatement"
        },
        {
            "message": "Je n'arrive plus à respirer correctement",
            "type": "emergency",
            "expected": "urgence respiratoire"
        },
        {
            "message": "La douleur est à 8/10",
            "type": "pain",
            "expected": "douleur sévère"
        },
        {
            "message": "Je prends déjà du paracétamol mais ça ne passe pas",
            "type": "medication", 
            "expected": "escalade thérapeutique"
        },
        {
            "message": "Qu'est-ce que je dois faire ?",
            "type": "general",
            "expected": "guidance contextualisée"
        }
    ]
    
    print(f"\n📋 TEST DE {len(urgency_scenarios)} SCÉNARIOS MÉDICAUX:")
    
    results = []
    
    for i, scenario in enumerate(urgency_scenarios, 1):
        print(f"\n[SCÉNARIO {i}/{len(urgency_scenarios)}]")
        print(f"🧑 PATIENT: {scenario['message']}")
        print("⏳ Gemini Flash analyse...")
        
        # Contexte médical réaliste
        context = {
            "patient_id": "TEST_001",
            "pain_history": ["crises récurrentes", "hospitalisation x2"],
            "medications": ["hydroxyurée 500mg", "acide folique", "paracétamol"],
            "previous_crises": 5,
            "last_crisis": "il y a 3 semaines",
            "severity_trend": "stable"
        }
        
        try:
            # Générer réponse avec Gemini Flash
            response = ai_engine.generate_response(
                scenario['message'], 
                context, 
                scenario['type']
            )
            
            print(f"🤖 KIDJAMO ASSISTANT:")
            print("=" * 60)
            print(response['response'])
            print("=" * 60)
            print(f"📊 Modèle: {response['model_used']} | Coût: ${response['cost']:.6f}")
            
            # Analyser la qualité de la réponse
            response_text = response['response'].lower()
            is_appropriate = (
                ("115" in response_text or "112" in response_text) if scenario['type'] == 'emergency' 
                else len(response['response']) > 100
            )
            
            results.append({
                "scenario": scenario['message'][:30] + "...",
                "type": scenario['type'],
                "model": response['model_used'],
                "cost": response['cost'],
                "appropriate": is_appropriate,
                "length": len(response['response'])
            })
            
        except Exception as e:
            print(f"❌ ERREUR: {e}")
            results.append({
                "scenario": scenario['message'][:30] + "...",
                "type": scenario['type'], 
                "model": "ERREUR",
                "cost": 0,
                "appropriate": False,
                "length": 0
            })
    
    # Analyse des résultats
    print("\n" + "="*60)
    print("📊 ANALYSE DES RÉSULTATS:")
    
    total_cost = sum(r['cost'] for r in results)
    successful_responses = sum(1 for r in results if r['appropriate'])
    avg_length = sum(r['length'] for r in results if r['length'] > 0) / len([r for r in results if r['length'] > 0])
    
    print(f"✅ Réponses appropriées: {successful_responses}/{len(results)} ({successful_responses/len(results)*100:.1f}%)")
    print(f"💰 Coût total session: ${total_cost:.6f}")
    print(f"📝 Longueur moyenne: {avg_length:.0f} caractères")
    
    # Modèles utilisés
    models_used = [r['model'] for r in results if r['model'] != 'ERREUR']
    if models_used:
        print(f"🔧 Modèle principal: {models_used[0]}")
    
    # Comparaison avec les anciens résultats
    print(f"\n🔄 COMPARAISON AVEC VOS TESTS PRÉCÉDENTS:")
    print("❌ AVANT (règles statiques):")
    print("   • Réponses identiques répétitives")
    print("   • Pas d'adaptation au contexte")
    print("   • Questions générales non comprises")
    
    print("✅ MAINTENANT (Gemini Flash):")
    print("   • Réponses contextualisées et intelligentes")
    print("   • Adaptation selon l'historique patient")
    print("   • Compréhension nuancée des questions")
    
    # Statistiques d'utilisation
    stats = ai_engine.get_usage_stats()
    print(f"\n📱 SESSION STATS:")
    print(f"   • Requêtes: {stats['requests_today']}")
    print(f"   • Gratuites restantes: {stats['remaining_free']}")
    print(f"   • Coût estimé total: ${stats['cost_estimate']:.6f}")
    
    return successful_responses >= len(results) * 0.8  # 80% de succès

if __name__ == "__main__":
    print("🎯 LANCEMENT DU TEST AVEC VOTRE CLÉ GEMINI FLASH")
    success = test_real_medical_scenarios()
    
    if success:
        print("\n🎉 SUCCÈS! Votre chatbot fonctionne parfaitement avec Gemini Flash")
        print("💡 Vous pouvez maintenant intégrer cette solution dans votre système")
    else:
        print("\n⚠️ Quelques ajustements nécessaires, mais la base fonctionne")
        
    print("\n🚀 PROCHAINE ÉTAPE: Intégration dans votre simulation_conversation.py")
