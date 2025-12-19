#!/usr/bin/env python3
"""
Script d'intégration du chatbot médical dans l'architecture Kidjamo existante
Remplace les appels Kendra par notre base de connaissances
"""

from kidjamo_chatbot_medical_v2 import KidjamoChatbotMedical

class KendraReplacement:
    """Classe de remplacement compatible avec l'interface Kendra existante"""
    
    def __init__(self):
        self.chatbot = KidjamoChatbotMedical()
        self.index_id = "kidjamo-medical-kb"  # ID virtuel
    
    def query(self, IndexId=None, QueryText="", PageSize=5, **kwargs):
        """
        Méthode compatible avec l'API Kendra query()
        Remplace directement boto3.client('kendra').query()
        """
        # Traiter avec notre chatbot
        resultats = self.chatbot.rechercher_reponse_avancee(QueryText)
        
        # Convertir au format Kendra
        result_items = []
        
        for i, resultat in enumerate(resultats.get("resultats", [])[:PageSize]):
            result_items.append({
                "Id": f"kidjamo-{i+1}",
                "Type": "DOCUMENT",
                "DocumentTitle": {
                    "Text": resultat["titre"],
                    "Highlights": []
                },
                "DocumentExcerpt": {
                    "Text": resultat["contenu"][:300] + "...",
                    "Highlights": []
                },
                "DocumentId": f"doc-{resultat.get('item_id', i)}",
                "ScoreAttributes": {
                    "ScoreConfidence": "HIGH"
                }
            })
        
        return {
            "ResultItems": result_items,
            "TotalNumberOfResults": len(resultats.get("resultats", [])),
            "QueryId": f"kidjamo-{int(datetime.now().timestamp())}"
        }

# Instructions d'intégration
if __name__ == "__main__":
    print("🔧 INSTRUCTIONS D'INTÉGRATION")
    print("=" * 50)
    print("1. Remplacer dans votre code existant:")
    print("   # ANCIEN CODE:")
    print("   kendra = boto3.client('kendra')")
    print("   response = kendra.query(IndexId=index_id, QueryText=query)")
    print()
    print("   # NOUVEAU CODE:")
    print("   kendra_replacement = KendraReplacement()")
    print("   response = kendra_replacement.query(QueryText=query)")
    print()
    print("2. Le format de réponse est identique à Kendra")
    print("3. Aucun changement dans le reste de votre code")
    print("4. Fonctionne immédiatement sans AWS Kendra")
