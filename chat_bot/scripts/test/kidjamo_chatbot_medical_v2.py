#!/usr/bin/env python3
"""
Intégration du chatbot médical temporaire dans l'architecture Kidjamo
Version production-ready avec gestion complète des urgences
"""

import json
import boto3
from typing import Dict, List, Any

class KidjamoChatbotMedical:
    def __init__(self):
        self.base_connaissances = self._charger_base_complete()
        self.urgences_mots_cles = [
            "urgence", "grave", "danger", "hospitalisation", "immédiat",
            "thoracique", "avc", "paralysie", "convulsion", "inconscient",
            "séquestration", "priapisme", "aplasique", "fièvre élevée"
        ]

    def _charger_base_complete(self) -> Dict[str, Any]:
        """Base de connaissances médicale complète et structurée"""
        return {
            "definitions": {
                "drépanocytose": {
                    "titre": "Drépanocytose - Définition",
                    "contenu": "Maladie génétique héréditaire qui affecte l'hémoglobine dans les globules rouges. L'hémoglobine anormale (HbS) provoque la déformation des globules rouges en forme de faucille, causant des obstructions vasculaires et des complications graves.",
                    "mots_cles": ["maladie génétique", "hémoglobine", "globules rouges", "faucille", "héréditaire"]
                },
                "anémie falciforme": {
                    "titre": "Anémie Falciforme",
                    "contenu": "Autre terme pour désigner la drépanocytose. Le nom 'falciforme' fait référence à la forme en faucille que prennent les globules rouges malades.",
                    "mots_cles": ["falciforme", "faucille", "drépanocytose", "globules rouges"]
                },
                "crise vaso-occlusive": {
                    "titre": "Crise Vaso-Occlusive",
                    "contenu": "Episode douloureux aigu causé par l'obstruction des petits vaisseaux sanguins par les globules rouges déformés. Peut affecter tous les organes et nécessite une prise en charge rapide.",
                    "mots_cles": ["douleur", "obstruction", "vaisseaux", "crise", "aigu"]
                }
            },

            "symptomes": {
                "douleurs": {
                    "titre": "Douleurs - Principal Symptôme",
                    "contenu": "Douleurs intenses et soudaines dans les os, articulations, abdomen ou poitrine. Peuvent durer de quelques heures à plusieurs jours. Nécessitent des antalgiques puissants et parfois une hospitalisation.",
                    "urgence": "modérée",
                    "mots_cles": ["douleur", "os", "articulations", "abdomen", "poitrine"]
                },
                "anémie chronique": {
                    "titre": "Anémie Chronique",
                    "contenu": "Fatigue persistante, pâleur, essoufflement dus à la destruction rapide des globules rouges déformés. Peut nécessiter des transfusions sanguines régulières.",
                    "urgence": "faible",
                    "mots_cles": ["fatigue", "pâleur", "essoufflement", "transfusion"]
                },
                "infections fréquentes": {
                    "titre": "Risque Infectieux Élevé",
                    "contenu": "Vulnérabilité accrue aux infections due à la dysfonction de la rate. Vaccination complète et antibioprophylaxie nécessaires. Toute fièvre est une urgence.",
                    "urgence": "élevée",
                    "mots_cles": ["infection", "fièvre", "rate", "vaccination", "antibiotiques"]
                }
            },

            "urgences": {
                "syndrome thoracique aigu": {
                    "titre": "🚨 URGENCE VITALE - Syndrome Thoracique Aigu",
                    "contenu": "Complication potentiellement mortelle : douleur thoracique + fièvre + difficultés respiratoires. HOSPITALISATION IMMÉDIATE en réanimation. Peut évoluer vers détresse respiratoire.",
                    "urgence": "critique",
                    "action": "Appeler le 15 (SAMU) immédiatement",
                    "mots_cles": ["thoracique", "poitrine", "respiration", "fièvre", "toux"]
                },
                "accident vasculaire cérébral": {
                    "titre": "🚨 URGENCE VITALE - AVC",
                    "contenu": "Risque élevé d'AVC chez les drépanocytaires. Signes : paralysie faciale, troubles de la parole, faiblesse d'un côté. URGENCES IMMÉDIATES dans les 4 heures.",
                    "urgence": "critique",
                    "action": "Appeler le 15 (SAMU) immédiatement",
                    "mots_cles": ["avc", "paralysie", "parole", "faiblesse", "visage"]
                },
                "séquestration splénique": {
                    "titre": "🚨 URGENCE PÉDIATRIQUE - Séquestration Splénique",
                    "contenu": "Urgence chez l'enfant : rate brutalement gonflée, douleur abdominale gauche, anémie sévère rapide. Peut être mortelle. Hospitalisation immédiate.",
                    "urgence": "critique",
                    "action": "Urgences pédiatriques immédiatement",
                    "mots_cles": ["rate", "abdomen gauche", "enfant", "gonflement", "anémie sévère"]
                },
                "priapisme": {
                    "titre": "🚨 URGENCE UROLOGIQUE - Priapisme",
                    "contenu": "Érection prolongée (>4h) et douloureuse. Complication urologique nécessitant un traitement dans les 6 heures pour éviter des séquelles permanentes.",
                    "urgence": "critique",
                    "action": "Urgences urologiques dans les 6 heures",
                    "mots_cles": ["érection", "priapisme", "urologiques", "4 heures"]
                }
            },

            "traitements": {
                "hydroxyurée": {
                    "titre": "Hydroxyurée - Traitement Principal",
                    "contenu": "Médicament de référence qui augmente l'hémoglobine fœtale et réduit significativement les crises. Surveillance sanguine régulière nécessaire. Efficace chez 60-80% des patients.",
                    "posologie": "15-35 mg/kg/jour selon réponse",
                    "mots_cles": ["hydroxyurée", "hémoglobine fœtale", "surveillance", "efficace"]
                },
                "transfusions": {
                    "titre": "Transfusions Sanguines",
                    "contenu": "Transfusions régulières pour maintenir un taux d'HbS <30%. Indiquées en cas d'AVC, syndrome thoracique récurrent, ou anémie sévère. Risque de surcharge en fer.",
                    "indication": "HbS >30% ou complications sévères",
                    "mots_cles": ["transfusion", "HbS", "fer", "complications"]
                },
                "greffe moelle osseuse": {
                    "titre": "Greffe de Moelle Osseuse - Traitement Curatif",
                    "contenu": "Seul traitement curatif actuellement disponible. Réservé aux formes sévères avec donneur compatible. Succès de 85-95% mais risques importants.",
                    "indication": "Formes sévères, donneur HLA compatible",
                    "mots_cles": ["greffe", "curatif", "donneur", "HLA", "sévère"]
                }
            },

            "cameroun_contexte": {
                "prévalence": {
                    "titre": "Prévalence au Cameroun",
                    "contenu": "1-2% de la population camerounaise (200,000-400,000 personnes) est atteinte. 10-15% sont porteurs sains. Une des prévalences les plus élevées au monde.",
                    "chiffres": "200,000-400,000 malades, 2-3 millions de porteurs",
                    "mots_cles": ["prévalence", "cameroun", "porteurs", "statistiques"]
                },
                "centres spécialisés": {
                    "titre": "Centres de Soins Spécialisés",
                    "contenu": "Centres principaux : Hôpital Central Yaoundé, Hôpital Laquintinie Douala, Hôpital de District de Biyem-Assi. Prise en charge multidisciplinaire disponible.",
                    "centres": ["Yaoundé", "Douala", "Biyem-Assi", "Bamenda"],
                    "mots_cles": ["centres", "hôpitaux", "yaoundé", "douala", "spécialisés"]
                }
            }
        }

    def detecter_urgence(self, question: str) -> Dict[str, Any]:
        """Détecte si la question concerne une urgence médicale"""
        question_lower = question.lower()

        # Recherche de mots-clés d'urgence
        urgence_detectee = any(mot in question_lower for mot in self.urgences_mots_cles)

        if urgence_detectee:
            # Identifier le type d'urgence spécifique
            for urgence_id, urgence_data in self.base_connaissances["urgences"].items():
                if any(mot in question_lower for mot in urgence_data["mots_cles"]):
                    return {
                        "est_urgence": True,
                        "niveau": urgence_data["urgence"],
                        "type": urgence_id,
                        "titre": urgence_data["titre"],
                        "contenu": urgence_data["contenu"],
                        "action": urgence_data.get("action", "Consulter rapidement un médecin")
                    }

            # Urgence générale détectée
            return {
                "est_urgence": True,
                "niveau": "élevée",
                "type": "générale",
                "titre": "🚨 Situation d'Urgence Détectée",
                "contenu": "Votre question semble concerner une urgence médicale.",
                "action": "En cas d'urgence vitale, appelez le 15 (SAMU) ou rendez-vous aux urgences"
            }

        return {"est_urgence": False}

    def rechercher_reponse_avancee(self, question: str) -> Dict[str, Any]:
        """Recherche avancée avec gestion des urgences"""
        # 1. Vérifier d'abord s'il s'agit d'une urgence
        urgence = self.detecter_urgence(question)

        if urgence["est_urgence"]:
            return {
                "question": question,
                "type_reponse": "urgence",
                "urgence": urgence,
                "resultats": [],
                "suggestions": [
                    "Quels sont les signes d'urgence à surveiller ?",
                    "Où trouver les urgences spécialisées au Cameroun ?",
                    "Comment prévenir les complications graves ?"
                ]
            }

        # 2. Recherche normale dans la base de connaissances
        question_lower = question.lower()
        resultats = []

        # Parcourir toutes les catégories
        for categorie, items in self.base_connaissances.items():
            for item_id, item_data in items.items():
                score = self._calculer_score_pertinence(question_lower, item_data)

                if score > 0:
                    resultats.append({
                        "titre": item_data["titre"],
                        "contenu": item_data["contenu"],
                        "categorie": categorie,
                        "score": score,
                        "item_id": item_id
                    })

        # Trier par score de pertinence
        resultats.sort(key=lambda x: x["score"], reverse=True)

        return {
            "question": question,
            "type_reponse": "normale",
            "urgence": {"est_urgence": False},
            "resultats": resultats[:3],
            "nombre_total": len(resultats),
            "suggestions": self._generer_suggestions_contextuelles(question_lower, resultats)
        }

    def _calculer_score_pertinence(self, question: str, item_data: Dict) -> float:
        """Calcule un score de pertinence pour un item"""
        score = 0

        # Recherche dans les mots-clés (poids fort)
        for mot_cle in item_data.get("mots_cles", []):
            if mot_cle.lower() in question:
                score += 10

        # Recherche dans le titre (poids moyen)
        for mot in question.split():
            if len(mot) > 3 and mot in item_data["titre"].lower():
                score += 5

        # Recherche dans le contenu (poids faible)
        for mot in question.split():
            if len(mot) > 4 and mot in item_data["contenu"].lower():
                score += 1

        return score

    def _generer_suggestions_contextuelles(self, question: str, resultats: List) -> List[str]:
        """Génère des suggestions basées sur le contexte"""
        suggestions = []

        # Suggestions basées sur les résultats trouvés
        if resultats:
            categorie_principale = resultats[0]["categorie"]

            if categorie_principale == "symptomes":
                suggestions.extend([
                    "Comment traiter ces symptômes ?",
                    "Quand consulter en urgence ?",
                    "Comment prévenir l'aggravation ?"
                ])
            elif categorie_principale == "traitements":
                suggestions.extend([
                    "Quels sont les effets secondaires ?",
                    "Comment surveiller l'efficacité ?",
                    "Existe-t-il des alternatives ?"
                ])
            elif categorie_principale == "cameroun_contexte":
                suggestions.extend([
                    "Où se faire soigner au Cameroun ?",
                    "Comment accéder aux traitements ?",
                    "Coût des soins spécialisés ?"
                ])

        # Suggestions générales si pas de résultats spécifiques
        if not suggestions:
            suggestions = [
                "Quels sont les symptômes de la drépanocytose ?",
                "Comment prendre l'hydroxyurée ?",
                "Centres spécialisés au Cameroun",
                "Que faire en cas de crise ?"
            ]

        return suggestions[:3]

    def formater_reponse_complete(self, resultats: Dict[str, Any]) -> str:
        """Formate une réponse complète et professionnelle"""
        if resultats["type_reponse"] == "urgence":
            return self._formater_reponse_urgence(resultats)
        else:
            return self._formater_reponse_normale(resultats)

    def _formater_reponse_urgence(self, resultats: Dict[str, Any]) -> str:
        """Formate une réponse d'urgence"""
        urgence = resultats["urgence"]

        reponse = f"""🚨 {urgence['titre']}

⚠️ **NIVEAU D'URGENCE : {urgence['niveau'].upper()}**

📋 **Description :**
{urgence['contenu']}

🎯 **Action immédiate :**
{urgence['action']}

📞 **Numéros d'urgence Cameroun :**
• SAMU : 15
• Pompiers : 18
• Police : 17

🏥 **Centres spécialisés :**
• Hôpital Central Yaoundé
• Hôpital Laquintinie Douala
• Service d'urgences de votre région
"""

        return reponse

    def _formater_reponse_normale(self, resultats: Dict[str, Any]) -> str:
        """Formate une réponse normale"""
        if not resultats["resultats"]:
            return f"""❓ **Question :** {resultats['question']}

⚠️ Aucune information spécifique trouvée dans ma base de connaissances.

💡 **Suggestions :**
{chr(10).join('• ' + s for s in resultats['suggestions'])}

🏥 **Pour un avis médical personnalisé :**
Consultez votre médecin traitant ou un spécialiste de la drépanocytose."""

        reponse = f"""✅ **Réponse à :** {resultats['question']}

"""

        for i, resultat in enumerate(resultats["resultats"], 1):
            reponse += f"""**{i}. {resultat['titre']}**
{resultat['contenu']}

"""

        if resultats["suggestions"]:
            reponse += f"""💡 **Questions connexes :**
{chr(10).join('• ' + s for s in resultats['suggestions'])}"""

        return reponse

# Interface de test
def tester_chatbot_complet():
    """Test complet du chatbot avec gestion d'urgences"""
    chatbot = KidjamoChatbotMedical()

    questions_test = [
        "J'ai une douleur thoracique et de la fièvre",  # Urgence
        "Qu'est-ce que l'hydroxyurée ?",               # Traitement
        "Symptômes de la drépanocytose",               # Symptômes
        "Mon enfant a la rate gonflée",                # Urgence pédiatrique
        "Centres spécialisés au Cameroun",             # Contexte local
        "Comment prévenir les crises ?"                # Prévention
    ]

    print("🤖 TEST COMPLET DU CHATBOT MÉDICAL KIDJAMO")
    print("=" * 80)

    for question in questions_test:
        print(f"\n❓ Question : {question}")
        print("-" * 60)

        resultats = chatbot.rechercher_reponse_avancee(question)
        reponse = chatbot.formater_reponse_complete(resultats)

        # Afficher un résumé pour le test
        if resultats["type_reponse"] == "urgence":
            print(f"🚨 URGENCE DÉTECTÉE : {resultats['urgence']['niveau']}")
            print(f"Action : {resultats['urgence']['action']}")
        else:
            nb_resultats = len(resultats["resultats"])
            print(f"✅ {nb_resultats} résultat(s) trouvé(s)")
            if nb_resultats > 0:
                print(f"Principal : {resultats['resultats'][0]['titre']}")

if __name__ == "__main__":
    tester_chatbot_complet()
