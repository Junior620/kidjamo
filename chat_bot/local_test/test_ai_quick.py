"""
Test rapide de l'IA générative intégrée
"""
from hybrid_logic import process_message_with_ai
import json

# Test d'une conversation typique qui posait problème
messages = [
    'Aide moi',
    'J ai une douleur atroce dans la poitrine',
    'Que faire ?'
]

print("🧪 TEST DE L'IA GÉNÉRATIVE INTÉGRÉE")
print("=" * 50)

for i, msg in enumerate(messages, 1):
    print(f'\n=== TEST {i}: {msg} ===')
    response = process_message_with_ai(msg, {'session_id': 'test_session'})
    print(f'Source IA: {response.get("source", "unknown")}')
    print(f'Type: {response.get("conversation_type", "unknown")}')
    print(f'Réponse: {response.get("response", "Erreur")[:300]}...')
    print("-" * 40)

print("\n✅ Test terminé !")
