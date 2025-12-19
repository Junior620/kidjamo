#!/usr/bin/env python3
"""
Chatbot médical temporaire avec base de connaissances intégrée
Solution immédiate en attendant la résolution du problème Kendra
"""

import json
import re
from typing import Dict, List, Any

class ChatbotMedicalTemporaire:
    def __init__(self):
        # Base de connaissances médicale intégrée
        self.base_connaissances = {
            "definitions": {
                "drépanocytose": "Maladie génétique héréditaire qui affecte l'hémoglobine dans les globules rouges, causant leur déformation en forme de faucille.",
                "anémie falciforme": "Autre nom de la drépanocytose, appelée ainsi à cause de la forme en faucille des globules rouges malades.",
                "hémoglobine S": "Forme anormale d'hémoglobine responsable de la drépanocytose, résultant d'une mutation génétique.",
                "crise vaso-occlusive": "Episode douloureux causé par l'obstruction des vaisseaux sanguins par les globules rouges déformés."
            },

            "symptomes": {
                "douleur": "Douleurs intenses et soudaines, principalement dans les os, les articulations, l'abdomen ou la poitrine.",
                "anémie": "Fatigue chronique, pâleur, essoufflement dus au manque de globules rouges sains.",
                "infections": "Risque élevé d'infections dues à la rate endommagée.",
                "retard croissance": "Retard de croissance et de développement chez les enfants.",
                "ictère": "Jaunissement de la peau et des yeux dû à la destruction des globules rouges."
            },

            "traitements": {
                "hydroxyurée": "Médicament principal qui augmente la production d'hémoglobine fœtale et réduit les crises.",
                "transfusion": "Transfusions sanguines régulières pour remplacer les globules rouges malades.",
                "greffe": "Greffe de moelle osseuse, seul traitement curatif mais risqué.",
                "antidouleurs": "Médicaments contre la douleur : paracétamol, anti-inflammatoires, opioïdes si nécessaire.",
                "antibiotiques": "Prévention des infections par antibiotiques prophylactiques."
            },

            "urgences": {
                "syndrome thoracique": "Urgence vitale : douleur thoracique, fièvre, difficultés respiratoires. Hospitalisation immédiate.",
                "AVC": "Accident vasculaire cérébral : paralysie, troubles de la parole. Urgences immédiatement.",
                "séquestration splénique": "Rate gonflée, douleur abdominale gauche, anémie sévère. Urgence pédiatrique.",
                "priapisme": "Érection prolongée et douloureuse. Urgence urologique.",
                "crise aplasique": "Arrêt de production des globules rouges. Anémie sévère rapide."
            },

            "prevention": {
                "dépistage": "Dépistage néonatal systématique pour diagnostic précoce.",
                "vaccination": "Vaccinations complètes : pneumocoque, méningocoque, grippe, hépatite B.",
                "pénicilline": "Pénicilline prophylactique chez l'enfant jusqu'à 5 ans.",
                "hydratation": "Boire beaucoup d'eau pour prévenir les crises.",
                "éviter": "Éviter le froid, l'altitude, la déshydratation, le stress intense."
            },

            "cameroun": {
                "prévalence": "1-2% de la population camerounaise est atteinte de drépanocytose.",
                "porteurs": "10-15% de la population sont porteurs sains du trait drépanocytaire.",
                "dépistage": "Dépistage gratuit disponible dans les hôpitaux publics.",
                "centres": "Centres spécialisés à Yaoundé et Douala.",
                "associations": "Association camerounaise de lutte contre la drépanocytose (ACLCD)."
            }
        }

        # Mots-clés pour la recherche
        self.mots_cles = {
            "définition": ["qu'est-ce", "définition", "c'est quoi", "définir", "expliquer"],
            "symptômes": ["symptômes", "signes", "manifestations", "comment savoir"],
            "traitement": ["traitement", "soigner", "médicament", "guérir", "soulager"],
            "urgence": ["urgence", "grave", "danger", "hospitalisation", "immédiat"],
            "prévention": ["prévenir", "éviter", "protection", "dépistage", "vaccination"],
            "cameroun": ["cameroun", "afrique", "statistiques", "prévalence", "centres"]
        }

    def rechercher_reponse(self, question: str) -> Dict[str, Any]:
        """Recherche une réponse dans la base de connaissances"""
        question_lower = question.lower()

        # Identifier la catégorie de la question
        categorie = self._identifier_categorie(question_lower)

        # Rechercher des termes spécifiques
        resultats = []

        if categorie:
            section = self.base_connaissances.get(categorie, {})

            for cle, valeur in section.items():
                if any(terme in question_lower for terme in cle.split()):
                    resultats.append({
                        "titre": cle.title(),
                        "contenu": valeur,
                        "categorie": categorie,
                        "pertinence": "élevée"
                    })

        # Recherche élargie si pas de résultats
        if not resultats:
            for cat_nom, cat_data in self.base_connaissances.items():
                for cle, valeur in cat_data.items():
                    if any(mot in question_lower for mot in cle.split()) or \
                       any(mot in valeur.lower() for mot in question_lower.split() if len(mot) > 3):
                        resultats.append({
                            "titre": cle.title(),
                            "contenu": valeur,
                            "categorie": cat_nom,
                            "pertinence": "moyenne"
                        })

        return {
            "question": question,
            "resultats": resultats[:3],  # Top 3 résultats
            "nombre_resultats": len(resultats),
            "suggestions": self._generer_suggestions(question_lower)
        }

    def _identifier_categorie(self, question: str) -> str:
        """Identifie la catégorie de la question"""
        for categorie, mots in self.mots_cles.items():
            if any(mot in question for mot in mots):
                return categorie.replace("ô", "o")  # Normaliser

        # Recherche par termes médicaux spécifiques
        if any(terme in question for terme in ["drépanocytose", "falciforme", "anémie"]):
            if any(terme in question for terme in ["douleur", "symptôme", "signe"]):
                return "symptomes"
            elif any(terme in question for terme in ["traitement", "médicament"]):
                return "traitements"
            elif any(terme in question for terme in ["urgence", "grave"]):
                return "urgences"
            else:
                return "definitions"

        return ""

    def _generer_suggestions(self, question: str) -> List[str]:
        """Génère des suggestions de questions connexes"""
        suggestions = [
            "Quels sont les symptômes de la drépanocytose ?",
            "Comment traiter une crise de drépanocytose ?",
            "Quand consulter en urgence ?",
            "Comment prévenir les crises ?",
            "Statistiques de la drépanocytose au Cameroun"
        ]

        # Personnaliser selon la question
        if "traitement" in question:
            suggestions.insert(0, "Qu'est-ce que l'hydroxyurée ?")
        elif "urgence" in question:
            suggestions.insert(0, "Qu'est-ce que le syndrome thoracique aigu ?")

        return suggestions[:3]

    def formater_reponse(self, resultats: Dict[str, Any]) -> str:
        """Formate la réponse pour l'affichage"""
        if not resultats["resultats"]:
            return self._reponse_par_defaut(resultats["question"])

        reponse = f"🔍 **Réponse à votre question :** {resultats['question']}\n\n"

        for i, resultat in enumerate(resultats["resultats"], 1):
            reponse += f"**{i}. {resultat['titre']}**\n"
            reponse += f"{resultat['contenu']}\n\n"

        if resultats["suggestions"]:
            reponse += "💡 **Questions connexes :**\n"
            for suggestion in resultats["suggestions"]:
                reponse += f"• {suggestion}\n"

        return reponse

    def _reponse_par_defaut(self, question: str) -> str:
        """Réponse par défaut si aucun résultat trouvé"""
        return f"""❓ **Question :** {question}

⚠️ Je n'ai pas trouvé d'information spécifique pour cette question dans ma base de connaissances actuelle.

💡 **Suggestions :**
• Quels sont les symptômes de la drépanocytose ?
• Comment traiter une crise de drépanocytose ?
• Que faire en cas d'urgence ?
• Statistiques au Cameroun

🏥 **En cas d'urgence :** Contactez immédiatement un médecin ou les urgences."""

def tester_chatbot():
    """Teste le chatbot avec des questions types"""
    chatbot = ChatbotMedicalTemporaire()

    questions_test = [
        "Qu'est-ce que la drépanocytose ?",
        "Quels sont les symptômes ?",
        "Comment traiter la douleur ?",
        "Que faire en cas d'urgence ?",
        "Statistiques au Cameroun",
        "Comment prévenir les crises ?"
    ]

    print("🤖 TEST DU CHATBOT MÉDICAL TEMPORAIRE")
    print("=" * 60)

    for question in questions_test:
        print(f"\n❓ {question}")
        print("-" * 40)

        resultats = chatbot.rechercher_reponse(question)
        reponse = chatbot.formater_reponse(resultats)

        # Afficher seulement le premier résultat pour le test
        if resultats["resultats"]:
            premier = resultats["resultats"][0]
            print(f"✅ {premier['titre']}: {premier['contenu'][:100]}...")
        else:
            print("❌ Aucun résultat trouvé")

def main():
    """Interface principale du chatbot"""
    chatbot = ChatbotMedicalTemporaire()

    print("🏥 CHATBOT MÉDICAL KIDJAMO - VERSION TEMPORAIRE")
    print("=" * 60)
    print("💡 Posez vos questions sur la drépanocytose")
    print("⌨️  Tapez 'quit' pour quitter")
    print("🧪 Tapez 'test' pour voir des exemples")
    print()

    while True:
        try:
            question = input("❓ Votre question : ").strip()

            if question.lower() in ['quit', 'exit', 'sortir']:
                print("👋 Au revoir !")
                break

            if question.lower() == 'test':
                tester_chatbot()
                continue

            if not question:
                print("⚠️  Veuillez poser une question.")
                continue

            # Rechercher et afficher la réponse
            resultats = chatbot.rechercher_reponse(question)
            reponse = chatbot.formater_reponse(resultats)

            print("\n" + "="*60)
            print(reponse)
            print("="*60 + "\n")

        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break
        except Exception as e:
            print(f"❌ Erreur : {str(e)}")

if __name__ == "__main__":
    # Décommenter pour l'interface interactive
    # main()

    # Test automatique
    tester_chatbot()
