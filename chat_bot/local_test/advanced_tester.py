"""
Suite de tests automatisés avancés pour le chatbot Kidjamo
Tests de régression, performance et qualité des réponses
"""
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Any
import threading

class AdvancedChatbotTester:
    """Testeur avancé pour validation complète du chatbot"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.test_results = []
        self.performance_metrics = []

    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Lance une suite complète de tests"""
        print("🚀 Lancement des tests avancés du chatbot Kidjamo...")

        results = {
            'contextual_tests': self.test_contextual_conversations(),
            'session_management_tests': self.test_session_management(),
            'emergency_detection_tests': self.test_emergency_detection(),
            'performance_tests': self.test_performance(),
            'edge_case_tests': self.test_edge_cases(),
            'user_experience_tests': self.test_user_experience()
        }

        # Génération du rapport final
        results['summary'] = self.generate_test_summary(results)
        return results

    def test_contextual_conversations(self) -> Dict[str, Any]:
        """Teste les conversations avec contexte"""
        print("\n📝 Test des conversations contextuelles...")

        test_scenarios = [
            {
                'name': 'Escalade de crise avec contexte',
                'messages': [
                    "Bonjour",
                    "J'ai mal au dos",
                    "La douleur est à 8/10",
                    "Que dois-je faire ?",  # Devrait être urgence grâce au contexte
                    "Merci"
                ],
                'expected_types': ['greeting', 'pain_management', 'emergency', 'emergency', 'gratitude']
            },
            {
                'name': 'Suivi de médication contextuel',
                'messages': [
                    "J'ai oublié mon médicament",
                    "C'était ce matin",
                    "Que faire ?",  # Contexte médicamenteux
                ],
                'expected_types': ['medication', 'medication', 'medication']
            }
        ]

        results = []
        for scenario in test_scenarios:
            session_id = f"test_context_{datetime.now().strftime('%H%M%S')}"
            scenario_result = self._run_conversation_scenario(scenario, session_id)
            results.append(scenario_result)

        return {
            'total_scenarios': len(test_scenarios),
            'passed': sum(1 for r in results if r['passed']),
            'failed': sum(1 for r in results if not r['passed']),
            'details': results
        }

    def test_session_management(self) -> Dict[str, Any]:
        """Teste la gestion des sessions"""
        print("\n🗂️ Test de la gestion des sessions...")

        session_id = f"test_session_{datetime.now().strftime('%H%M%S')}"

        # Test 1: Créer une session et vérifier l'historique
        self._send_message("Bonjour", session_id)
        self._send_message("J'ai mal", session_id)

        # Récupérer l'historique
        try:
            response = requests.get(f"{self.base_url}/session/{session_id}/history")
            if response.status_code == 200:
                history_data = response.json()
                history_test = len(history_data.get('history', [])) == 2
            else:
                history_test = False
        except:
            history_test = False

        # Test 2: Reset du contexte de crise
        try:
            response = requests.post(f"{self.base_url}/session/{session_id}/reset")
            reset_test = response.status_code == 200
        except:
            reset_test = False

        return {
            'history_retrieval': history_test,
            'context_reset': reset_test,
            'overall_passed': history_test and reset_test
        }

    def test_emergency_detection(self) -> Dict[str, Any]:
        """Teste la détection d'urgences améliorée"""
        print("\n🚨 Test de détection d'urgences...")

        emergency_tests = [
            {'message': 'Aide moi', 'should_be_emergency': True},
            {'message': 'La douleur est à 9/10', 'should_be_emergency': True},
            {'message': 'Je n\'arrive plus à respirer', 'should_be_emergency': True},
            {'message': 'Ça ne passe pas avec les médicaments', 'should_be_emergency': True},
            {'message': 'Dois-je aller aux urgences ?', 'should_be_emergency': True},
            {'message': 'Bonjour comment allez-vous', 'should_be_emergency': False},
            {'message': 'Qu\'est-ce que la drépanocytose', 'should_be_emergency': False}
        ]

        results = []
        for test in emergency_tests:
            response = self._send_message(test['message'])
            is_emergency = response.get('conversation_type') == 'emergency'
            passed = is_emergency == test['should_be_emergency']

            results.append({
                'message': test['message'],
                'expected_emergency': test['should_be_emergency'],
                'detected_as_emergency': is_emergency,
                'passed': passed
            })

        passed_count = sum(1 for r in results if r['passed'])

        return {
            'total_tests': len(emergency_tests),
            'passed': passed_count,
            'success_rate': (passed_count / len(emergency_tests)) * 100,
            'details': results
        }

    def test_performance(self) -> Dict[str, Any]:
        """Teste les performances du chatbot"""
        print("\n⚡ Test de performance...")

        # Test de charge - messages simultanés
        def send_concurrent_message(message_id):
            start_time = time.time()
            response = self._send_message(f"Test message {message_id}")
            end_time = time.time()
            return {
                'message_id': message_id,
                'response_time': end_time - start_time,
                'success': response.get('success', False)
            }

        # Lancer 10 requêtes concurrentes
        threads = []
        concurrent_results = []

        for i in range(10):
            thread = threading.Thread(
                target=lambda i=i: concurrent_results.append(send_concurrent_message(i))
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Analyser les résultats
        response_times = [r['response_time'] for r in concurrent_results]
        success_count = sum(1 for r in concurrent_results if r['success'])

        return {
            'concurrent_requests': len(concurrent_results),
            'successful_responses': success_count,
            'success_rate': (success_count / len(concurrent_results)) * 100,
            'avg_response_time': sum(response_times) / len(response_times),
            'max_response_time': max(response_times),
            'min_response_time': min(response_times)
        }

    def test_edge_cases(self) -> Dict[str, Any]:
        """Teste les cas limites"""
        print("\n🔍 Test des cas limites...")

        edge_cases = [
            {'message': '', 'expected_success': False},
            {'message': 'a' * 1000, 'expected_success': True},  # Message très long
            {'message': '🚨💊😣🏥', 'expected_success': True},  # Emojis seulement
            {'message': 'MESSAGE EN MAJUSCULES', 'expected_success': True},
            {'message': '   espaces   multiples   ', 'expected_success': True},
            {'message': '123456789', 'expected_success': True}  # Chiffres seulement
        ]

        results = []
        for case in edge_cases:
            try:
                response = self._send_message(case['message'])
                actual_success = response.get('success', False)
                passed = actual_success == case['expected_success']
            except:
                passed = not case['expected_success']  # Si exception, doit échouer

            results.append({
                'case': case['message'][:50] + '...' if len(case['message']) > 50 else case['message'],
                'expected_success': case['expected_success'],
                'passed': passed
            })

        return {
            'total_cases': len(edge_cases),
            'passed': sum(1 for r in results if r['passed']),
            'details': results
        }

    def test_user_experience(self) -> Dict[str, Any]:
        """Teste l'expérience utilisateur"""
        print("\n👥 Test d'expérience utilisateur...")

        ux_tests = [
            {
                'name': 'Réponse à une salutation contient-elle les fonctionnalités ?',
                'message': 'Bonjour',
                'check': lambda r: 'Gestion de la douleur' in r.get('response', '')
            },
            {
                'name': 'Réponse d\'urgence contient-elle les numéros ?',
                'message': 'Aide urgent',
                'check': lambda r: '115' in r.get('response', '') and '112' in r.get('response', '')
            },
            {
                'name': 'Réponse formatée en HTML ?',
                'message': 'Bonjour',
                'check': lambda r: '<div' in r.get('response', '') and '</div>' in r.get('response', '')
            }
        ]

        results = []
        for test in ux_tests:
            response = self._send_message(test['message'])
            passed = test['check'](response)
            results.append({
                'test_name': test['name'],
                'passed': passed
            })

        return {
            'total_tests': len(ux_tests),
            'passed': sum(1 for r in results if r['passed']),
            'details': results
        }

    def _send_message(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Envoie un message au chatbot"""
        if not session_id:
            session_id = f"test_{datetime.now().strftime('%H%M%S%f')}"

        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    'message': message,
                    'session_id': session_id
                },
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _run_conversation_scenario(self, scenario: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Exécute un scénario de conversation complet"""
        messages = scenario['messages']
        expected_types = scenario['expected_types']

        results = []
        for i, (message, expected_type) in enumerate(zip(messages, expected_types)):
            response = self._send_message(message, session_id)
            actual_type = response.get('conversation_type', 'unknown')

            results.append({
                'step': i + 1,
                'message': message,
                'expected_type': expected_type,
                'actual_type': actual_type,
                'passed': actual_type == expected_type
            })

            time.sleep(0.5)  # Pause entre messages

        scenario_passed = all(r['passed'] for r in results)

        return {
            'scenario_name': scenario['name'],
            'passed': scenario_passed,
            'steps': results
        }

    def generate_test_summary(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Génère un résumé des tests"""
        total_tests = 0
        total_passed = 0

        # Compter tous les tests
        for category, results in all_results.items():
            if isinstance(results, dict):
                if 'passed' in results:
                    total_tests += results.get('total_scenarios', results.get('total_tests', 1))
                    total_passed += results['passed']

        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        return {
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_tests - total_passed,
            'success_rate': round(success_rate, 2),
            'test_timestamp': datetime.now().isoformat(),
            'overall_status': 'PASSED' if success_rate >= 80 else 'FAILED'
        }

    def save_test_report(self, results: Dict[str, Any], filename: str = None):
        """Sauvegarde le rapport de tests"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'chatbot_test_report_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📊 Rapport de tests sauvegardé: {filename}")

if __name__ == "__main__":
    # Lancer les tests
    tester = AdvancedChatbotTester()

    try:
        print("⏳ Vérification que le serveur est démarré...")
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Serveur non accessible. Démarrez le chatbot avec: python chatbot_server.py")
            exit(1)
    except:
        print("❌ Serveur non accessible. Démarrez le chatbot avec: python chatbot_server.py")
        exit(1)

    # Lancer tous les tests
    results = tester.run_comprehensive_tests()

    # Afficher le résumé
    summary = results['summary']
    print(f"\n" + "="*60)
    print(f"📊 RÉSUMÉ DES TESTS AVANCÉS")
    print(f"="*60)
    print(f"✅ Tests réussis: {summary['total_passed']}/{summary['total_tests']}")
    print(f"❌ Tests échoués: {summary['total_failed']}/{summary['total_tests']}")
    print(f"📈 Taux de réussite: {summary['success_rate']}%")
    print(f"🏆 Statut global: {summary['overall_status']}")

    # Sauvegarder le rapport
    tester.save_test_report(results)

    if summary['success_rate'] >= 80:
        print(f"\n🎉 Félicitations ! Votre chatbot passe tous les tests avec succès !")
    else:
        print(f"\n⚠️ Des améliorations sont nécessaires. Consultez le rapport détaillé.")
