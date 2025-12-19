"""
🧪 TEST MANUEL DU PIPELINE KIDJAMO
===================================
Lance manuellement une exécution du pipeline Step Functions pour tester
"""

import boto3
import json
import time
from datetime import datetime

# Configuration
REGION = 'eu-west-1'
STATE_MACHINE_NAME = 'kidjamo-pipeline-orchestrator'

# Client Step Functions
sfn_client = boto3.client('stepfunctions', region_name=REGION)

print("=" * 80)
print("🧪 TEST MANUEL DU PIPELINE KIDJAMO")
print("=" * 80)
print(f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📍 Région: {REGION}")
print("=" * 80)

try:
    # Récupérer l'ARN de la State Machine
    list_response = sfn_client.list_state_machines()
    state_machine_arn = None

    for sm in list_response['stateMachines']:
        if sm['name'] == STATE_MACHINE_NAME:
            state_machine_arn = sm['stateMachineArn']
            break

    if not state_machine_arn:
        print(f"❌ State Machine '{STATE_MACHINE_NAME}' non trouvée!")
        print("💡 Exécutez d'abord: python orchestration/deploy_orchestration.py")
        exit(1)

    print(f"✅ State Machine trouvée: {state_machine_arn}")

    # Préparer l'input pour l'exécution
    execution_input = {
        "comment": "Test manuel du pipeline",
        "timestamp": datetime.now().isoformat(),
        "trigger": "manual"
    }

    # Démarrer l'exécution
    execution_name = f"manual-test-{int(time.time())}"

    print(f"\n🚀 Démarrage de l'exécution: {execution_name}")
    print(f"📄 Input: {json.dumps(execution_input, indent=2)}")

    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(execution_input)
    )

    execution_arn = response['executionArn']

    print(f"\n✅ Exécution démarrée avec succès!")
    print(f"🆔 Execution ARN: {execution_arn}")

    # Surveiller l'exécution
    print("\n" + "=" * 80)
    print("📊 SURVEILLANCE DE L'EXÉCUTION")
    print("=" * 80)

    status = 'RUNNING'
    start_time = time.time()

    while status == 'RUNNING':
        time.sleep(10)  # Vérifier toutes les 10 secondes

        describe_response = sfn_client.describe_execution(
            executionArn=execution_arn
        )

        status = describe_response['status']
        elapsed = int(time.time() - start_time)

        print(f"⏳ [{elapsed}s] État: {status}")

        if status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
            break

    # Résultat final
    print("\n" + "=" * 80)
    print("📊 RÉSULTAT FINAL")
    print("=" * 80)

    describe_response = sfn_client.describe_execution(
        executionArn=execution_arn
    )

    final_status = describe_response['status']
    total_time = int(time.time() - start_time)

    if final_status == 'SUCCEEDED':
        print(f"✅ PIPELINE RÉUSSI!")
        print(f"⏱️  Temps total: {total_time} secondes ({total_time // 60}m {total_time % 60}s)")

        if 'output' in describe_response:
            output = json.loads(describe_response['output'])
            print(f"\n📋 Résultats:")
            print(json.dumps(output, indent=2, default=str))

    elif final_status == 'FAILED':
        print(f"❌ PIPELINE ÉCHOUÉ!")
        print(f"⏱️  Temps d'exécution: {total_time} secondes")

        if 'error' in describe_response:
            print(f"\n❌ Erreur: {describe_response['error']}")
        if 'cause' in describe_response:
            print(f"💬 Cause: {describe_response['cause']}")

    else:
        print(f"⚠️  État final: {final_status}")
        print(f"⏱️  Temps d'exécution: {total_time} secondes")

    # Liens utiles
    print("\n" + "=" * 80)
    print("🔗 LIENS UTILES")
    print("=" * 80)

    console_url = f"https://{REGION}.console.aws.amazon.com/states/home?region={REGION}#/v2/executions/details/{execution_arn}"
    print(f"📊 Console Step Functions: {console_url}")

    # Récupérer l'historique des événements
    history_response = sfn_client.get_execution_history(
        executionArn=execution_arn,
        maxResults=50,
        reverseOrder=True
    )

    print(f"\n📜 Derniers événements:")
    for event in history_response['events'][:5]:
        event_type = event['type']
        timestamp = event['timestamp'].strftime('%H:%M:%S')
        print(f"   [{timestamp}] {event_type}")

    print("\n💡 Pour voir l'historique complet:")
    print(f"   aws stepfunctions get-execution-history --execution-arn {execution_arn} --region {REGION}")

    print("\n" + "=" * 80)

except Exception as e:
    print(f"\n❌ Erreur lors de l'exécution du test: {e}")
    import traceback
    traceback.print_exc()

