"""
Test de débogage pour comprendre pourquoi les salutations ne fonctionnent pas
"""

def test_detection():
    test_messages = [
        "comment tu vas",
        "ça va",
        "ca va",
        "comment ça va",
        "comment allez-vous",
        "bonjour"
    ]

    for message in test_messages:
        input_lower = message.lower()
        print(f"\nTest: '{message}' -> '{input_lower}'")

        # Test des conditions
        if any(greeting in input_lower for greeting in ['bonjour', 'salut', 'hello', 'bonsoir']):
            print("  ✅ Détecté comme: SALUTATION")
        elif any(farewell in input_lower for farewell in ['au revoir', 'bye', 'à bientôt', 'tchao']):
            print("  ✅ Détecté comme: AU REVOIR")
        elif any(thanks in input_lower for thanks in ['merci', 'thank you', 'thanks']):
            print("  ✅ Détecté comme: REMERCIEMENT")
        elif any(feeling in input_lower for feeling in ['ça va', 'ca va', 'comment ça va', 'comment ca va', 'comment allez-vous', 'comment tu vas', 'comment vous allez', 'tu vas bien', 'vous allez bien', 'ça va ?', 'ca va ?']):
            print("  ✅ Détecté comme: QUESTION BIEN-ÊTRE")
        else:
            print("  ❌ Tombe dans: ELSE (générique)")

        # Test de chaque condition individuellement
        print(f"    - Salutation: {any(greeting in input_lower for greeting in ['bonjour', 'salut', 'hello', 'bonsoir'])}")
        print(f"    - Bien-être: {any(feeling in input_lower for feeling in ['ça va', 'ca va', 'comment ça va', 'comment ca va', 'comment allez-vous', 'comment tu vas', 'comment vous allez', 'tu vas bien', 'vous allez bien', 'ça va ?', 'ca va ?'])}")

if __name__ == "__main__":
    test_detection()
