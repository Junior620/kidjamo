"""
🚀 DÉPLOIEMENT DE L'ORCHESTRATION PIPELINE KIDJAMO
====================================================
Crée l'infrastructure AWS Step Functions + EventBridge pour automatiser le pipeline
"""

import boto3
import json
import time
from datetime import datetime

# Configuration
REGION = 'eu-west-1'
STATE_MACHINE_NAME = 'kidjamo-pipeline-orchestrator'
EVENTBRIDGE_RULE_NAME = 'kidjamo-pipeline-scheduler'
ROLE_NAME = 'kidjamo-stepfunctions-execution-role'

# Clients AWS
iam_client = boto3.client('iam', region_name=REGION)
sfn_client = boto3.client('stepfunctions', region_name=REGION)
events_client = boto3.client('events', region_name=REGION)
sts_client = boto3.client('sts', region_name=REGION)

# Récupérer l'ID du compte AWS
account_id = sts_client.get_caller_identity()['Account']

print("=" * 80)
print("🚀 DÉPLOIEMENT DE L'ORCHESTRATION KIDJAMO")
print("=" * 80)
print(f"📍 Région: {REGION}")
print(f"🆔 Compte AWS: {account_id}")
print(f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# ============================================================================
# ÉTAPE 1: CRÉER LE RÔLE IAM POUR STEP FUNCTIONS
# ============================================================================

print("\n📋 ÉTAPE 1: Création du rôle IAM pour Step Functions...")

# Trust policy pour Step Functions
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "states.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

# Policy pour exécuter les jobs Glue
execution_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "glue:StartJobRun",
                "glue:GetJobRun",
                "glue:GetJobRuns",
                "glue:BatchStopJobRun"
            ],
            "Resource": f"arn:aws:glue:{REGION}:{account_id}:job/kidjamo-dev-*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": f"arn:aws:logs:{REGION}:{account_id}:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords"
            ],
            "Resource": "*"
        }
    ]
}

try:
    # Vérifier si le rôle existe déjà
    try:
        role = iam_client.get_role(RoleName=ROLE_NAME)
        role_arn = role['Role']['Arn']
        print(f"   ✅ Rôle existant trouvé: {role_arn}")
    except iam_client.exceptions.NoSuchEntityException:
        # Créer le rôle
        print(f"   🔧 Création du rôle: {ROLE_NAME}")
        role_response = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for Step Functions to orchestrate Kidjamo Glue jobs'
        )
        role_arn = role_response['Role']['Arn']
        print(f"   ✅ Rôle créé: {role_arn}")

        # Attendre que le rôle soit disponible
        print("   ⏳ Attente de la propagation du rôle (10 secondes)...")
        time.sleep(10)

    # Créer ou mettre à jour la policy inline
    policy_name = 'StepFunctionsGlueExecutionPolicy'
    iam_client.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(execution_policy)
    )
    print(f"   ✅ Policy attachée: {policy_name}")

except Exception as e:
    print(f"   ❌ Erreur lors de la création du rôle: {e}")
    raise

# ============================================================================
# ÉTAPE 2: CRÉER LA STATE MACHINE STEP FUNCTIONS
# ============================================================================

print("\n📋 ÉTAPE 2: Création de la State Machine Step Functions...")

try:
    # Charger la définition de la state machine
    with open('orchestration/stepfunctions_state_machine.json', 'r', encoding='utf-8') as f:
        state_machine_definition = f.read()

    print(f"   📄 Définition chargée: {len(state_machine_definition)} caractères")

    # Vérifier si la state machine existe déjà
    list_response = sfn_client.list_state_machines()
    existing_sm = None
    for sm in list_response['stateMachines']:
        if sm['name'] == STATE_MACHINE_NAME:
            existing_sm = sm
            break

    if existing_sm:
        # Mettre à jour la state machine existante
        print(f"   🔧 Mise à jour de la state machine existante...")
        sfn_client.update_state_machine(
            stateMachineArn=existing_sm['stateMachineArn'],
            definition=state_machine_definition,
            roleArn=role_arn
        )
        state_machine_arn = existing_sm['stateMachineArn']
        print(f"   ✅ State Machine mise à jour: {state_machine_arn}")
    else:
        # Créer une nouvelle state machine
        print(f"   🔧 Création de la state machine: {STATE_MACHINE_NAME}")
        sm_response = sfn_client.create_state_machine(
            name=STATE_MACHINE_NAME,
            definition=state_machine_definition,
            roleArn=role_arn,
            type='STANDARD'
        )
        state_machine_arn = sm_response['stateMachineArn']
        print(f"   ✅ State Machine créée: {state_machine_arn}")
        print(f"   💡 Logs disponibles dans l'historique d'exécution de la State Machine")

except FileNotFoundError:
    print("   ❌ Erreur: Fichier stepfunctions_state_machine.json non trouvé")
    print("   📁 Vérifiez que le fichier existe dans: orchestration/stepfunctions_state_machine.json")
    raise
except Exception as e:
    print(f"   ❌ Erreur lors de la création de la State Machine: {e}")
    raise

# ============================================================================
# ÉTAPE 3: CRÉER LA RÈGLE EVENTBRIDGE (CRON TOUTES LES 30 MINUTES)
# ============================================================================

print("\n📋 ÉTAPE 3: Création de la règle EventBridge (toutes les 30 minutes)...")

try:
    # Créer ou mettre à jour la règle EventBridge
    rule_response = events_client.put_rule(
        Name=EVENTBRIDGE_RULE_NAME,
        ScheduleExpression='cron(0,30 * * * ? *)',  # Toutes les 30 minutes (00 et 30)
        State='ENABLED',
        Description='Déclenche le pipeline Kidjamo toutes les 30 minutes'
    )

    rule_arn = rule_response['RuleArn']
    print(f"   ✅ Règle EventBridge créée: {rule_arn}")
    print(f"   ⏰ Schedule: Toutes les 30 minutes (cron: 0,30 * * * ? *)")

    # Créer le rôle pour EventBridge si nécessaire
    eventbridge_role_name = 'kidjamo-eventbridge-stepfunctions-role'

    eventbridge_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "events.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    eventbridge_execution_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "states:StartExecution"
                ],
                "Resource": state_machine_arn
            }
        ]
    }

    try:
        eb_role = iam_client.get_role(RoleName=eventbridge_role_name)
        eventbridge_role_arn = eb_role['Role']['Arn']
        print(f"   ✅ Rôle EventBridge existant: {eventbridge_role_arn}")
    except iam_client.exceptions.NoSuchEntityException:
        print(f"   🔧 Création du rôle EventBridge: {eventbridge_role_name}")
        eb_role_response = iam_client.create_role(
            RoleName=eventbridge_role_name,
            AssumeRolePolicyDocument=json.dumps(eventbridge_trust_policy),
            Description='Role for EventBridge to trigger Step Functions'
        )
        eventbridge_role_arn = eb_role_response['Role']['Arn']
        print(f"   ✅ Rôle EventBridge créé: {eventbridge_role_arn}")
        time.sleep(10)

    # Attacher la policy
    iam_client.put_role_policy(
        RoleName=eventbridge_role_name,
        PolicyName='EventBridgeStepFunctionsPolicy',
        PolicyDocument=json.dumps(eventbridge_execution_policy)
    )

    # Ajouter la cible (State Machine) à la règle
    events_client.put_targets(
        Rule=EVENTBRIDGE_RULE_NAME,
        Targets=[
            {
                'Id': '1',
                'Arn': state_machine_arn,
                'RoleArn': eventbridge_role_arn,
                'Input': json.dumps({
                    "comment": "Execution automatique toutes les 30 minutes",
                    "timestamp": "$.time"
                })
            }
        ]
    )

    print(f"   ✅ Cible configurée: State Machine")

except Exception as e:
    print(f"   ❌ Erreur lors de la création de la règle EventBridge: {e}")
    raise

# ============================================================================
# RÉSUMÉ DU DÉPLOIEMENT
# ============================================================================

print("\n" + "=" * 80)
print("✅ DÉPLOIEMENT TERMINÉ AVEC SUCCÈS!")
print("=" * 80)

print("\n📊 RESSOURCES CRÉÉES:")
print(f"   1. Rôle IAM Step Functions: {role_arn}")
print(f"   2. State Machine: {state_machine_arn}")
print(f"   3. Règle EventBridge: {rule_arn}")
print(f"   4. Rôle IAM EventBridge: {eventbridge_role_arn}")

print("\n⏰ CONFIGURATION DU SCHEDULE:")
print("   • Fréquence: Toutes les 30 minutes")
print("   • Heures d'exécution: 00:00, 00:30, 01:00, 01:30, ...")
print("   • État: ACTIVÉ")

print("\n🔗 LIENS UTILES:")
print(f"   • State Machine Console: https://{REGION}.console.aws.amazon.com/states/home?region={REGION}#/statemachines/view/{state_machine_arn}")
print(f"   • EventBridge Console: https://{REGION}.console.aws.amazon.com/events/home?region={REGION}#/rules/{EVENTBRIDGE_RULE_NAME}")
print(f"   • CloudWatch Logs: https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Fstepfunctions$252F{STATE_MACHINE_NAME}")

print("\n🎯 PROCHAINES ÉTAPES:")
print("   1. Activer Job Bookmark sur tous les jobs Glue:")
print("      python orchestration/enable_job_bookmarks.py")
print("   2. Tester manuellement le pipeline:")
print("      python orchestration/test_pipeline.py")
print("   3. Surveiller les exécutions:")
print("      python orchestration/monitor_pipeline.py")

print("\n💡 NOTES:")
print("   • Le pipeline s'exécutera automatiquement toutes les 30 minutes")
print("   • Job Bookmark activé = traitement incrémental (nouveaux fichiers uniquement)")
print("   • Les erreurs sont automatiquement retryées (3 tentatives avec backoff)")
print("   • Logs disponibles dans CloudWatch Logs")

print("\n" + "=" * 80)

