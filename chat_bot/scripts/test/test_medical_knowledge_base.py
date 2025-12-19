#!/usr/bin/env python3
"""
Test avancé de recherche médicale Kendra après synchronisation
Valide les capacités de recherche sur la base de connaissances enrichie
"""

import boto3
import json
import time
from datetime import datetime

class AdvancedMedicalSearchTester:
    def __init__(self, index_id="b7472109-44e4-42de-9192-2b6dbe1493cc", region="eu-west-1"):
        self.index_id = index_id
        self.kendra = boto3.client('kendra', region_name=region)
        
    def test_comprehensive_search(self):
        """Tests de recherche complets sur la drépanocytose"""
        print("🔍 TESTS DE RECHERCHE MÉDICALE AVANCÉS")
        print("=" * 50)
        
        # Catégories de tests
        test_categories = {
            "Définitions & Généralités": [
                "qu'est-ce que la drépanocytose",
                "définition anémie falciforme", 
                "maladie génétique hémoglobine",
                "transmission héréditaire drépanocytose"
            ],
            "Symptômes & Manifestations": [
                "symptômes drépanocytose",
                "crise vaso-occlusive douleur",
                "anémie chronique fatigue",
                "complications drépanocytose"
            ],
            "Traitements & Soins": [
                "traitement hydroxyurée",
                "transfusion sanguine drépanocytose",
                "greffe moelle osseuse",
                "gestion crise douleur"
            ],
            "Urgences & Complications": [
                "urgence médicale drépanocytose",
                "syndrome thoracique aigu",
                "accident vasculaire cérébral",
                "séquestration splénique"
            ],
            "Prévention & Surveillance": [
                "dépistage drépanocytose",
                "prévention infections",
                "surveillance médicale",
                "éducation thérapeutique"
            ],
            "Contexte Cameroun/Afrique": [
                "drépanocytose Cameroun",
                "statistiques Afrique",
                "WHO OMS rapport",
                "prévalence drépanocytose"
            ]
        }
        
        overall_results = {
            "total_searches": 0,
            "successful_searches": 0,
            "categories_results": {}
        }
        
        for category, queries in test_categories.items():
            print(f"\n📋 CATÉGORIE: {category}")
            print("-" * 30)
            
            category_results = {
                "queries": len(queries),
                "with_results": 0,
                "total_results": 0
            }
            
            for query in queries:
                try:
                    print(f"🔎 '{query}'")
                    
                    response = self.kendra.query(
                        IndexId=self.index_id,
                        QueryText=query,
                        PageSize=5
                    )
                    
                    results = response.get('ResultItems', [])
                    result_count = len(results)
                    
                    if result_count > 0:
                        category_results["with_results"] += 1
                        category_results["total_results"] += result_count
                        overall_results["successful_searches"] += 1
                        
                        print(f"   ✅ {result_count} résultat(s)")
                        
                        # Afficher le meilleur résultat
                        if results:
                            best_result = results[0]
                            title = best_result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                            confidence = best_result.get('ScoreAttributes', {}).get('ScoreConfidence', 'UNKNOWN')
                            excerpt = best_result.get('DocumentExcerpt', {}).get('Text', '')[:150]
                            
                            print(f"   📄 Meilleur: {title}")
                            print(f"   🎯 Confiance: {confidence}")
                            print(f"   📝 Extrait: {excerpt}...")
                    else:
                        print(f"   ❌ Aucun résultat")
                    
                    overall_results["total_searches"] += 1
                    time.sleep(0.5)  # Éviter le rate limiting
                    
                except Exception as e:
                    print(f"   ❌ Erreur: {str(e)}")
                    overall_results["total_searches"] += 1
            
            overall_results["categories_results"][category] = category_results
        
        # Rapport final
        self._print_summary_report(overall_results)
    
    def test_specific_medical_scenarios(self):
        """Tests de scénarios médicaux spécifiques"""
        print("\n🏥 TESTS DE SCÉNARIOS MÉDICAUX SPÉCIFIQUES")
        print("=" * 45)
        
        scenarios = [
            {
                "scenario": "Patient avec douleur abdominale aiguë",
                "query": "douleur abdominale aiguë drépanocytose urgence",
                "expected_topics": ["crise", "urgence", "hospitalisation"]
            },
            {
                "scenario": "Enfant avec retard de croissance",
                "query": "retard croissance enfant drépanocytose",
                "expected_topics": ["pédiatrique", "croissance", "suivi"]
            },
            {
                "scenario": "Prévention infections chez drépanocytaire",
                "query": "prévention infections vaccination drépanocytose",
                "expected_topics": ["vaccination", "antibiotiques", "prévention"]
            },
            {
                "scenario": "Grossesse et drépanocytose",
                "query": "grossesse femme enceinte drépanocytose",
                "expected_topics": ["grossesse", "maternité", "surveillance"]
            }
        ]
        
        for scenario in scenarios:
            print(f"\n🎭 Scénario: {scenario['scenario']}")
            print(f"🔍 Requête: '{scenario['query']}'")
            
            try:
                response = self.kendra.query(
                    IndexId=self.index_id,
                    QueryText=scenario['query'],
                    PageSize=3
                )
                
                results = response.get('ResultItems', [])
                print(f"   📊 {len(results)} résultat(s) trouvé(s)")
                
                if results:
                    for i, result in enumerate(results[:2]):
                        title = result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                        confidence = result.get('ScoreAttributes', {}).get('ScoreConfidence', 'UNKNOWN')
                        
                        print(f"   [{i+1}] {title} (Confiance: {confidence})")
                        
                        # Vérifier si les sujets attendus sont présents
                        excerpt = result.get('DocumentExcerpt', {}).get('Text', '').lower()
                        found_topics = [topic for topic in scenario['expected_topics'] if topic in excerpt]
                        
                        if found_topics:
                            print(f"       ✅ Sujets pertinents trouvés: {', '.join(found_topics)}")
                        else:
                            print(f"       ⚠️ Sujets attendus non trouvés dans l'extrait")
                else:
                    print("   ❌ Aucune information trouvée pour ce scénario")
                
            except Exception as e:
                print(f"   ❌ Erreur: {str(e)}")
    
    def _print_summary_report(self, results):
        """Affiche le rapport de synthèse"""
        print("\n📊 RAPPORT DE SYNTHÈSE")
        print("=" * 25)
        
        total = results["total_searches"]
        successful = results["successful_searches"]
        success_rate = (successful / total * 100) if total > 0 else 0
        
        print(f"🔍 Total recherches: {total}")
        print(f"✅ Recherches avec résultats: {successful}")
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        
        print(f"\n📋 Détail par catégorie:")
        for category, stats in results["categories_results"].items():
            queries = stats["queries"]
            with_results = stats["with_results"]
            total_results = stats["total_results"]
            category_rate = (with_results / queries * 100) if queries > 0 else 0
            
            print(f"   {category}:")
            print(f"     - {with_results}/{queries} requêtes avec résultats ({category_rate:.0f}%)")
            print(f"     - {total_results} résultats au total")
        
        # Recommandations
        print(f"\n💡 RECOMMANDATIONS:")
        if success_rate >= 80:
            print("   ✅ Excellente couverture de la base de connaissances!")
            print("   ✅ Le chatbot est prêt pour la production")
        elif success_rate >= 60:
            print("   ⚠️ Bonne couverture, mais peut être améliorée")
            print("   📚 Considérez ajouter plus de documents spécialisés")
        else:
            print("   ❌ Couverture insuffisante")
            print("   📚 Ajoutez plus de documents médicaux")
            print("   🔄 Vérifiez que la synchronisation est terminée")

def main():
    """Test principal après synchronisation"""
    print("🚀 VALIDATION DE LA BASE DE CONNAISSANCES MÉDICALE")
    print("=" * 55)
    print("⚠️ Assurez-vous que la synchronisation Kendra est terminée!")
    print()
    
    # Attendre confirmation de l'utilisateur
    input("Appuyez sur Entrée pour commencer les tests...")
    
    tester = AdvancedMedicalSearchTester()
    
    # Tests complets
    tester.test_comprehensive_search()
    
    # Tests de scénarios
    tester.test_specific_medical_scenarios()
    
    print(f"\n🎉 Tests terminés à {datetime.now().strftime('%H:%M:%S')}")
    print("🔧 Votre chatbot médical est maintenant prêt pour l'utilisation!")

if __name__ == "__main__":
    main()
