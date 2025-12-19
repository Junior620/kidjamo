"""
📚 ACTIVATION DU JOB BOOKMARK SUR TOUS LES JOBS GLUE
=====================================================
Active le Job Bookmark pour traitement incrémental (nouveaux fichiers uniquement)
"""

import boto3
from datetime import datetime

# Configuration
REGION = 'eu-west-1'

# Liste des jobs Glue
GLUE_JOBS = [
    'kidjamo-dev-raw-to-bronze',
    'kidjamo-dev-bronze-to-silver',
    'kidjamo-dev-silver-to-gold',
    'kidjamo-dev-silver-to-postgres',
    'kidjamo-dev-gold-analytics-to-postgres',
    'kidjamo-dev-gold-hourly-to-postgres',
    'kidjamo-dev-gold-daily-summary-to-postgres'
]

# Client AWS Glue
glue_client = boto3.client('glue', region_name=REGION)

print("=" * 80)
print("📚 ACTIVATION DU JOB BOOKMARK SUR TOUS LES JOBS GLUE")
print("=" * 80)
print(f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📍 Région: {REGION}")
print(f"🎯 Nombre de jobs à traiter: {len(GLUE_JOBS)}")
print("=" * 80)

results = {
    'success': [],
    'already_enabled': [],
    'errors': []
}

for job_name in GLUE_JOBS:
    print(f"\n🔧 Traitement: {job_name}")

    try:
        # Récupérer la configuration actuelle du job
        response = glue_client.get_job(JobName=job_name)
        job_config = response['Job']

        # Vérifier si Job Bookmark est déjà activé
        current_default_args = job_config.get('DefaultArguments', {})
        current_bookmark = current_default_args.get('--job-bookmark-option', 'job-bookmark-disable')

        if current_bookmark == 'job-bookmark-enable':
            print(f"   ✅ Job Bookmark déjà activé")
            results['already_enabled'].append(job_name)
            continue

        # Activer Job Bookmark
        new_default_args = current_default_args.copy()
        new_default_args['--job-bookmark-option'] = 'job-bookmark-enable'

        # Préparer les paramètres de mise à jour
        job_update = {
            'Role': job_config['Role'],
            'Command': job_config['Command'],
            'DefaultArguments': new_default_args,
            'MaxRetries': job_config.get('MaxRetries', 3),
            'Timeout': job_config.get('Timeout', 2880),
            'GlueVersion': job_config.get('GlueVersion', '3.0')
        }

        # Ajouter soit MaxCapacity SOIT (WorkerType + NumberOfWorkers), pas les deux
        if job_config.get('WorkerType') and job_config.get('NumberOfWorkers'):
            job_update['WorkerType'] = job_config['WorkerType']
            job_update['NumberOfWorkers'] = job_config['NumberOfWorkers']
        elif job_config.get('MaxCapacity'):
            job_update['MaxCapacity'] = job_config['MaxCapacity']

        update_params = {
            'JobName': job_name,
            'JobUpdate': job_update
        }

        glue_client.update_job(**update_params)

        print(f"   ✅ Job Bookmark activé avec succès")
        print(f"   📋 Ancienne valeur: {current_bookmark}")
        print(f"   📋 Nouvelle valeur: job-bookmark-enable")
        results['success'].append(job_name)

    except glue_client.exceptions.EntityNotFoundException:
        print(f"   ❌ Job non trouvé")
        results['errors'].append((job_name, "Job non trouvé"))
    except Exception as e:
        print(f"   ❌ Erreur: {str(e)[:100]}")
        results['errors'].append((job_name, str(e)))

# ============================================================================
# RÉSUMÉ
# ============================================================================

print("\n" + "=" * 80)
print("📊 RÉSUMÉ DE L'ACTIVATION")
print("=" * 80)

print(f"\n✅ Jobs mis à jour avec succès: {len(results['success'])}")
for job_name in results['success']:
    print(f"   • {job_name}")

print(f"\n✅ Jobs déjà configurés: {len(results['already_enabled'])}")
for job_name in results['already_enabled']:
    print(f"   • {job_name}")

if results['errors']:
    print(f"\n❌ Erreurs: {len(results['errors'])}")
    for job_name, error in results['errors']:
        print(f"   • {job_name}: {error}")

print("\n💡 VÉRIFICATION:")
print("   Pour vérifier le statut des Job Bookmarks:")
print("   python orchestration/verify_job_bookmarks.py")

print("\n🎯 PROCHAINE ÉTAPE:")
print("   Tester le pipeline complet:")
print("   python orchestration/test_pipeline.py")

print("\n" + "=" * 80)
print("✅ ACTIVATION TERMINÉE!")
print("=" * 80)

