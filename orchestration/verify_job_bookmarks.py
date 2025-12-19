"""
🔍 VÉRIFICATION DU STATUT DES JOB BOOKMARKS
============================================
Vérifie que tous les jobs Glue ont bien Job Bookmark activé
"""

import boto3
from datetime import datetime

# Configuration
REGION = 'eu-west-1'

# Liste des jobs Glue
GLUE_JOBS = [
    'kidjamo-dev-bronze-to-silver',
    'kidjamo-dev-silver-to-gold-analytics',
    'kidjamo-dev-silver-to-gold-hourly',
    'kidjamo-dev-silver-to-gold-daily',
    'kidjamo-dev-silver-to-postgres',
    'kidjamo-dev-gold-analytics-to-postgres',
    'kidjamo-dev-gold-hourly-to-postgres',
    'kidjamo-dev-gold-daily-to-postgres'
]

# Client AWS Glue
glue_client = boto3.client('glue', region_name=REGION)

print("=" * 80)
print("🔍 VÉRIFICATION DU STATUT DES JOB BOOKMARKS")
print("=" * 80)
print(f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📍 Région: {REGION}")
print("=" * 80)

results = {
    'enabled': [],
    'disabled': [],
    'not_found': []
}

for job_name in GLUE_JOBS:
    try:
        # Récupérer la configuration du job
        response = glue_client.get_job(JobName=job_name)
        job_config = response['Job']

        # Vérifier le statut du Job Bookmark
        default_args = job_config.get('DefaultArguments', {})
        bookmark_status = default_args.get('--job-bookmark-option', 'job-bookmark-disable')

        if bookmark_status == 'job-bookmark-enable':
            results['enabled'].append(job_name)
            print(f"✅ {job_name}: ACTIVÉ")
        else:
            results['disabled'].append((job_name, bookmark_status))
            print(f"❌ {job_name}: {bookmark_status}")

    except glue_client.exceptions.EntityNotFoundException:
        results['not_found'].append(job_name)
        print(f"⚠️  {job_name}: JOB NON TROUVÉ")

    except Exception as e:
        print(f"❌ {job_name}: Erreur - {str(e)[:50]}")

# ============================================================================
# RÉSUMÉ
# ============================================================================

print("\n" + "=" * 80)
print("📊 RÉSUMÉ")
print("=" * 80)

print(f"\n✅ Jobs avec Job Bookmark ACTIVÉ: {len(results['enabled'])}/{len(GLUE_JOBS)}")
for job_name in results['enabled']:
    print(f"   • {job_name}")

if results['disabled']:
    print(f"\n❌ Jobs avec Job Bookmark DÉSACTIVÉ: {len(results['disabled'])}")
    for job_name, status in results['disabled']:
        print(f"   • {job_name} ({status})")

    print("\n💡 Pour activer Job Bookmark sur tous les jobs:")
    print("   python orchestration/enable_job_bookmarks.py")

if results['not_found']:
    print(f"\n⚠️  Jobs non trouvés: {len(results['not_found'])}")
    for job_name in results['not_found']:
        print(f"   • {job_name}")

# Vérifier aussi les dernières exécutions et l'utilisation du bookmark
print("\n" + "=" * 80)
print("📋 VÉRIFICATION DE L'UTILISATION DU BOOKMARK")
print("=" * 80)

for job_name in results['enabled'][:3]:  # Vérifier les 3 premiers jobs
    try:
        runs_response = glue_client.get_job_runs(
            JobName=job_name,
            MaxResults=1
        )

        if runs_response['JobRuns']:
            last_run = runs_response['JobRuns'][0]
            args = last_run.get('Arguments', {})
            bookmark_used = args.get('--job-bookmark-option', 'N/A')

            print(f"\n📌 {job_name}")
            print(f"   Dernière exécution: {last_run['StartedOn'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Job Bookmark utilisé: {bookmark_used}")

    except Exception as e:
        print(f"\n⚠️  {job_name}: Impossible de récupérer l'historique")

print("\n" + "=" * 80)

if len(results['enabled']) == len(GLUE_JOBS):
    print("✅ TOUS LES JOBS ONT JOB BOOKMARK ACTIVÉ!")
    print("=" * 80)
    print("\n🎯 Le pipeline est configuré pour le traitement incrémental")
    print("   • Seuls les nouveaux fichiers seront traités")
    print("   • Pas de retraitement des données déjà processées")
    print("   • Performances optimisées")
else:
    print("⚠️  CERTAINS JOBS N'ONT PAS JOB BOOKMARK ACTIVÉ")
    print("=" * 80)
    print("\n💡 Action requise:")
    print("   python orchestration/enable_job_bookmarks.py")

print("\n" + "=" * 80)

