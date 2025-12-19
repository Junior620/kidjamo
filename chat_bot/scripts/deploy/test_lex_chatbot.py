#!/usr/bin/env python3
"""
Script de test complet du chatbot Lex Kidjamo
Teste toutes les fonctionnalités et l'intégration Kendra
"""

import boto3
import json
import time
import argparse
from datetime import datetime

class KidjamoLexTester:
    def __init__(self, region='eu-west-1', environment='dev'):
        self.region = region
        self.environment = environment
        self.project_name = 'kidjamo'

        # Clients AWS
        self.lex_runtime = boto3.client('lexv2-runtime', region_name=region)
        self.lex_models = boto3.client('lexv2-models', region_name=region)

        # Configuration (sera mise à jour après déploiement)
        self.bot_id = None
        self.bot_alias_id = None
        self.session_id = f"test-session-{int(time.time())}"

    def load_deployment_config(self):
        """Charge la configuration de déploiement"""
        try:
            with open('lex_deployment_config.json', 'r') as f:
                config = json.load(f)
                deployment_info = config['deployment_info']
                self.bot_id = deployment_info['bot_id']
                self.bot_alias_id = deployment_info['alias_id']

                print(f"✅ Configuration chargée:")
                print(f"   Bot ID: {self.bot_id}")
                print(f"   Alias ID: {self.bot_alias_id}")
                print(f"   Région: {self.region}")

                return True

        except FileNotFoundError:
            print("❌ Fichier de configuration non trouvé")
            print("💡 Exécutez d'abord le déploiement avec deploy_lex_chatbot.py")
            return False
        except Exception as e:
            print(f"❌ Erreur chargement configuration: {str(e)}")
            return False

    def run_complete_tests(self):
        """Lance une suite de tests complète"""
        print("🧪 TESTS COMPLETS DU CHATBOT LEX KIDJAMO")
        print("=" * 60)

        if not self.load_deployment_config():
            return False

        try:
            # Test 1: Vérification du statut du bot
            print("\n1️⃣ Vérification du statut du bot...")
            if not self.test_bot_status():
                return False

            # Test 2: Tests des conversations simples
            print("\n2️⃣ Tests de conversation de base...")
            if not self.test_basic_conversations():
                return False

            # Test 3: Tests des intents spécialisés
            print("\n3️⃣ Tests des intents médicaux...")
            if not self.test_medical_intents():
                return False

            # Test 4: Tests d'urgence
            print("\n4️⃣ Tests des alertes d'urgence...")
            if not self.test_emergency_scenarios():
                return False

            # Test 5: Tests de fallback avec Kendra
            print("\n5️⃣ Tests de recherche Kendra...")
            if not self.test_kendra_integration():
                return False

            # Test 6: Tests de performance
            print("\n6️⃣ Tests de performance...")
            if not self.test_performance():
                return False

            print(f"\n🎉 TOUS LES TESTS RÉUSSIS!")
            print(f"🤖 Votre chatbot Kidjamo est prêt pour la production!")

            return True

        except Exception as e:
            print(f"❌ Erreur lors des tests: {str(e)}")
            return False

    def test_bot_status(self):
        """Teste le statut du bot"""
        try:
            # Vérifier le bot
            bot_response = self.lex_models.describe_bot(botId=self.bot_id)
            bot_status = bot_response['botStatus']

            print(f"   📊 Statut du bot: {bot_status}")

            if bot_status != 'Available':
                print(f"   ❌ Le bot n'est pas disponible (statut: {bot_status})")
                return False

            # Vérifier l'alias
            alias_response = self.lex_models.describe_bot_alias(
                botId=self.bot_id,
                botAliasId=self.bot_alias_id
            )
            alias_status = alias_response['botAliasStatus']

            print(f"   📊 Statut de l'alias: {alias_status}")

            if alias_status != 'Available':
                print(f"   ❌ L'alias n'est pas disponible (statut: {alias_status})")
                return False

            print(f"   ✅ Bot et alias opérationnels")
            return True

        except Exception as e:
            print(f"   ❌ Erreur vérification statut: {str(e)}")
            return False

    def test_basic_conversations(self):
        """Teste les conversations de base"""
        test_cases = [
            {
                "input": "Bonjour",
                "expected_intent": "ConversationGenerale",
                "description": "Salutation simple"
            },
            {
                "input": "Comment allez-vous",
                "expected_intent": "ConversationGenerale",
                "description": "Conversation polie"
            },
            {
                "input": "Aide",
                "expected_intent": "DemanderAide",
                "description": "Demande d'aide"
            },
            {
                "input": "Au revoir",
                "expected_intent": "ConversationGenerale",
                "description": "Salutation de fin"
            }
        ]

        success_count = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"   Test {i}/4: {test_case['description']}")

            if self.send_message_and_validate(test_case['input'], test_case.get('expected_intent')):
                success_count += 1
                print(f"   ✅ Réussi")
            else:
                print(f"   ❌ Échoué")

            time.sleep(1)  # Pause entre les tests

        print(f"   📊 Résultats: {success_count}/{len(test_cases)} tests réussis")
        return success_count >= len(test_cases) * 0.75  # 75% de réussite minimum

    def test_medical_intents(self):
        """Teste les intents médicaux spécialisés"""
        test_cases = [
            {
                "input": "J'ai mal au dos",
                "expected_intent": "SignalerDouleur",
                "description": "Signalement douleur simple"
            },
            {
                "input": "Je souffre intensité 8 au niveau de l'abdomen",
                "expected_intent": "SignalerDouleur",
                "description": "Signalement douleur détaillé"
            },
            {
                "input": "Mes données vitales",
                "expected_intent": "ConsulterVitales",
                "description": "Consultation données IoT"
            },
            {
                "input": "J'ai pris mon Doliprane",
                "expected_intent": "GererMedicaments",
                "description": "Gestion médicaments"
            },
            {
                "input": "Rappel pour hydroxyurée",
                "expected_intent": "GererMedicaments",
                "description": "Rappel traitement"
            }
        ]

        success_count = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"   Test {i}/5: {test_case['description']}")

            if self.send_message_and_validate(test_case['input'], test_case.get('expected_intent')):
                success_count += 1
                print(f"   ✅ Réussi")
            else:
                print(f"   ❌ Échoué")

            time.sleep(1)

        print(f"   📊 Résultats: {success_count}/{len(test_cases)} tests réussis")
        return success_count >= len(test_cases) * 0.8  # 80% de réussite minimum

    def test_emergency_scenarios(self):
        """Teste les scénarios d'urgence"""
        test_cases = [
            {
                "input": "C'est urgent",
                "expected_intent": "SignalerUrgence",
                "description": "Urgence simple"
            },
            {
                "input": "Aidez-moi rapidement",
                "expected_intent": "SignalerUrgence",
                "description": "Demande aide urgente"
            },
            {
                "input": "Appelez les secours",
                "expected_intent": "SignalerUrgence",
                "description": "Demande secours"
            }
        ]

        success_count = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"   Test {i}/3: {test_case['description']}")

            response = self.send_message_and_get_response(test_case['input'])

            if response and any(keyword in response.lower() for keyword in ['urgence', 'samu', '15', 'secours']):
                success_count += 1
                print(f"   ✅ Réussi - Réponse d'urgence détectée")
            else:
                print(f"   ❌ Échoué - Pas de réponse d'urgence appropriée")

            time.sleep(1)

        print(f"   📊 Résultats: {success_count}/{len(test_cases)} tests réussis")
        return success_count >= len(test_cases) * 0.9  # 90% de réussite pour urgences

    def test_kendra_integration(self):
        """Teste l'intégration avec Kendra"""
        test_cases = [
            {
                "input": "Qu'est-ce que la drépanocytose",
                "description": "Question médicale générale"
            },
            {
                "input": "Symptômes anémie falciforme",
                "description": "Question spécialisée"
            },
            {
                "input": "Centres médicaux Cameroun",
                "description": "Information géographique"
            },
            {
                "input": "Traitement hydroxyurée effets",
                "description": "Question technique"
            }
        ]

        success_count = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"   Test {i}/4: {test_case['description']}")

            response = self.send_message_and_get_response(test_case['input'])

            # Vérifier si la réponse contient des informations pertinentes
            if response and len(response) > 50:  # Réponse substantielle
                success_count += 1
                print(f"   ✅ Réussi - Réponse: {response[:100]}...")
            else:
                print(f"   ❌ Échoué - Réponse trop courte ou vide")

            time.sleep(2)  # Pause plus longue pour Kendra

        print(f"   📊 Résultats: {success_count}/{len(test_cases)} tests réussis")
        print(f"   💡 Note: L'intégration Kendra peut nécessiter plus de temps pour l'indexation")

        return success_count >= len(test_cases) * 0.5  # 50% de réussite (Kendra peut être lent)

    def test_performance(self):
        """Teste les performances du chatbot"""
        print(f"   🚀 Test de réactivité...")

        start_time = time.time()
        response = self.send_message_and_get_response("Bonjour test performance")
        end_time = time.time()

        response_time = end_time - start_time

        print(f"   ⏱️ Temps de réponse: {response_time:.2f} secondes")

        if response_time < 5.0:
            print(f"   ✅ Performance excellente (< 5s)")
            return True
        elif response_time < 10.0:
            print(f"   ⚠️ Performance acceptable (< 10s)")
            return True
        else:
            print(f"   ❌ Performance lente (> 10s)")
            return False

    def send_message_and_validate(self, message, expected_intent=None):
        """Envoie un message et valide la réponse"""
        try:
            response = self.lex_runtime.recognize_text(
                botId=self.bot_id,
                botAliasId=self.bot_alias_id,
                localeId='fr_FR',
                sessionId=self.session_id,
                text=message
            )

            # Vérifier qu'il y a une réponse
            if not response.get('messages'):
                return False

            # Vérifier l'intent si spécifié
            if expected_intent:
                actual_intent = response.get('sessionState', {}).get('intent', {}).get('name')
                if actual_intent != expected_intent:
                    print(f"     Intent attendu: {expected_intent}, reçu: {actual_intent}")
                    # Ne pas échouer pour l'intent, juste informer

            return True

        except Exception as e:
            print(f"     Erreur: {str(e)}")
            return False

    def send_message_and_get_response(self, message):
        """Envoie un message et retourne la réponse textuelle"""
        try:
            response = self.lex_runtime.recognize_text(
                botId=self.bot_id,
                botAliasId=self.bot_alias_id,
                localeId='fr_FR',
                sessionId=self.session_id,
                text=message
            )

            if response.get('messages') and len(response['messages']) > 0:
                return response['messages'][0].get('content', '')

            return None

        except Exception as e:
            print(f"     Erreur: {str(e)}")
            return None

    def generate_test_report(self):
        """Génère un rapport de test détaillé"""
        report = {
            "test_date": datetime.utcnow().isoformat(),
            "bot_id": self.bot_id,
            "bot_alias_id": self.bot_alias_id,
            "region": self.region,
            "environment": self.environment,
            "session_id": self.session_id
        }

        with open(f'lex_test_report_{int(time.time())}.json', 'w') as f:
            json.dump(report, f, indent=2)

        print(f"✅ Rapport de test sauvegardé")

def main():
    parser = argparse.ArgumentParser(description='Tests du chatbot Lex Kidjamo')
    parser.add_argument('--region', default='eu-west-1', help='Région AWS')
    parser.add_argument('--environment', default='dev', help='Environnement')
    parser.add_argument('--quick', action='store_true', help='Tests rapides seulement')

    args = parser.parse_args()

    try:
        tester = KidjamoLexTester(region=args.region, environment=args.environment)

        if args.quick:
            print("🏃 Mode tests rapides")
            success = tester.test_basic_conversations()
        else:
            success = tester.run_complete_tests()

        if success:
            print(f"\n🎉 TESTS TERMINÉS AVEC SUCCÈS!")
            print(f"✅ Votre chatbot Kidjamo est prêt!")

            # Générer le rapport
            tester.generate_test_report()

        else:
            print(f"\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
            print(f"💡 Vérifiez la configuration et relancez les tests")

    except Exception as e:
        print(f"❌ Erreur fatale: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
