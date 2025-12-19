"""
📊 MONITORING EN TEMPS RÉEL DU PIPELINE KIDJAMO
================================================
Surveille les exécutions automatiques du pipeline Step Functions
"""

import boto3
import time
from datetime import datetime, timedelta

# Configuration
REGION = 'eu-west-1'
STATE_MACHINE_NAME = 'kidjamo-pipeline-orchestrator'

# Client Step Functions
sfn_client = boto3.client('stepfunctions', region_name=REGION)

def get_state_machine_arn():
    """Récupère l'ARN de la State Machine"""
    list_response = sfn_client.list_state_machines()
    for sm in list_response['stateMachines']:
        if sm['name'] == STATE_MACHINE_NAME:
            return sm['stateMachineArn']
    return None

def get_recent_executions(state_machine_arn, hours=24):
    """Récupère les exécutions récentes"""
    executions = []

    # Récupérer les exécutions en cours et récentes
    for status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT']:
        response = sfn_client.list_executions(
            stateMachineArn=state_machine_arn,
            statusFilter=status,
            maxResults=50
        )

        for execution in response['executions']:
            # Filtrer par date (dernières N heures)
            if execution['startDate'] > datetime.now(execution['startDate'].tzinfo) - timedelta(hours=hours):
                executions.append(execution)

    # Trier par date décroissante
    executions.sort(key=lambda x: x['startDate'], reverse=True)
    return executions

def format_duration(start_date, stop_date=None):
    """Formate la durée en format lisible"""
    if stop_date:
        duration = (stop_date - start_date).total_seconds()
    else:
        duration = (datetime.now(start_date.tzinfo) - start_date).total_seconds()

    minutes = int(duration // 60)
    seconds = int(duration % 60)

    if minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_execution_details(execution_arn):
    """Récupère les détails d'une exécution"""
    describe_response = sfn_client.describe_execution(
        executionArn=execution_arn
    )

    # Récupérer les événements récents
    history_response = sfn_client.get_execution_history(
        executionArn=execution_arn,
        maxResults=10,
        reverseOrder=True
    )

    return describe_response, history_response

def print_execution_summary(execution):
    """Affiche un résumé d'une exécution"""
    name = execution['name']
    status = execution['status']
    start_date = execution['startDate']
    stop_date = execution.get('stopDate')

    # Icône selon le statut
    status_icons = {
        'RUNNING': '⏳',
        'SUCCEEDED': '✅',
        'FAILED': '❌',
        'TIMED_OUT': '⏰',
        'ABORTED': '🛑'
    }
    icon = status_icons.get(status, '❓')

    # Durée
    duration = format_duration(start_date, stop_date)

    # Date de début
    start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n{icon} {name}")
    print(f"   État: {status}")
    print(f"   Démarré: {start_str}")
    print(f"   Durée: {duration}")

def monitor_loop():
    """Boucle de monitoring continue"""
    print("=" * 80)
    print("📊 MONITORING EN TEMPS RÉEL DU PIPELINE KIDJAMO")
    print("=" * 80)
    print(f"⏰ Démarré: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Région: {REGION}")
    print("=" * 80)

    # Récupérer l'ARN de la State Machine
    state_machine_arn = get_state_machine_arn()

    if not state_machine_arn:
        print(f"❌ State Machine '{STATE_MACHINE_NAME}' non trouvée!")
        return

    print(f"✅ State Machine: {state_machine_arn}")
    print("\n💡 Appuyez sur Ctrl+C pour arrêter le monitoring\n")

    try:
        while True:
            # Effacer l'écran (optionnel - commenté pour Windows)
            # print("\033[H\033[J")

            print("\n" + "=" * 80)
            print(f"📊 ÉTAT DU PIPELINE - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 80)

            # Récupérer les exécutions récentes (dernières 24h)
            executions = get_recent_executions(state_machine_arn, hours=24)

            if not executions:
                print("\n⚠️  Aucune exécution trouvée dans les dernières 24 heures")
            else:
                # Statistiques globales
                total = len(executions)
                running = sum(1 for e in executions if e['status'] == 'RUNNING')
                succeeded = sum(1 for e in executions if e['status'] == 'SUCCEEDED')
                failed = sum(1 for e in executions if e['status'] == 'FAILED')

                print(f"\n📈 STATISTIQUES (dernières 24h):")
                print(f"   Total: {total} | ⏳ En cours: {running} | ✅ Réussis: {succeeded} | ❌ Échoués: {failed}")

                # Afficher les 5 dernières exécutions
                print(f"\n📋 DERNIÈRES EXÉCUTIONS:")
                for execution in executions[:5]:
                    print_execution_summary(execution)

                # Si des exécutions sont en cours, afficher plus de détails
                running_executions = [e for e in executions if e['status'] == 'RUNNING']

                if running_executions:
                    print("\n" + "=" * 80)
                    print("⏳ EXÉCUTIONS EN COURS - DÉTAILS")
                    print("=" * 80)

                    for execution in running_executions:
                        print(f"\n🔄 {execution['name']}")

                        try:
                            details, history = get_execution_details(execution['executionArn'])

                            # Afficher les derniers événements
                            print(f"   📜 Derniers événements:")
                            for event in history['events'][:3]:
                                event_type = event['type']
                                timestamp = event['timestamp'].strftime('%H:%M:%S')
                                print(f"      [{timestamp}] {event_type}")

                        except Exception as e:
                            print(f"   ⚠️  Impossible de récupérer les détails: {str(e)[:50]}")

            # Prochaine exécution planifiée
            print("\n" + "=" * 80)
            print("⏰ PROCHAINE EXÉCUTION AUTOMATIQUE")
            print("=" * 80)

            now = datetime.now()
            current_minute = now.minute

            # Calculer la prochaine exécution (00 ou 30)
            if current_minute < 30:
                next_minute = 30
                next_hour = now.hour
            else:
                next_minute = 0
                next_hour = (now.hour + 1) % 24

            next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
            if next_run <= now:
                next_run = next_run.replace(hour=(next_hour + 1) % 24)

            time_until = (next_run - now).total_seconds()
            minutes_until = int(time_until // 60)

            print(f"   📅 Prochaine exécution: {next_run.strftime('%H:%M:%S')}")
            print(f"   ⏱️  Dans: {minutes_until} minutes")

            print("\n💡 Rafraîchissement dans 30 secondes...")
            print("=" * 80)

            # Attendre avant la prochaine mise à jour
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring arrêté par l'utilisateur")
        print("=" * 80)

def show_statistics():
    """Affiche des statistiques détaillées"""
    state_machine_arn = get_state_machine_arn()

    if not state_machine_arn:
        print(f"❌ State Machine '{STATE_MACHINE_NAME}' non trouvée!")
        return

    print("=" * 80)
    print("📊 STATISTIQUES DÉTAILLÉES DU PIPELINE")
    print("=" * 80)

    # Statistiques sur différentes périodes
    periods = [
        (1, "Dernière heure"),
        (6, "Dernières 6 heures"),
        (24, "Dernières 24 heures"),
        (168, "Dernière semaine")
    ]

    for hours, label in periods:
        executions = get_recent_executions(state_machine_arn, hours=hours)

        if executions:
            total = len(executions)
            succeeded = sum(1 for e in executions if e['status'] == 'SUCCEEDED')
            failed = sum(1 for e in executions if e['status'] == 'FAILED')
            success_rate = (succeeded / total * 100) if total > 0 else 0

            # Calculer la durée moyenne
            completed = [e for e in executions if 'stopDate' in e]
            if completed:
                avg_duration = sum(
                    (e['stopDate'] - e['startDate']).total_seconds()
                    for e in completed
                ) / len(completed)
                avg_duration_str = f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s"
            else:
                avg_duration_str = "N/A"

            print(f"\n📈 {label}:")
            print(f"   Total: {total} exécutions")
            print(f"   ✅ Réussis: {succeeded} ({success_rate:.1f}%)")
            print(f"   ❌ Échoués: {failed}")
            print(f"   ⏱️  Durée moyenne: {avg_duration_str}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        show_statistics()
    else:
        monitor_loop()

