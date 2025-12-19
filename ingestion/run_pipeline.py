# run_pipeline.py
"""
Script d'orchestration pour exécuter l'ensemble du pipeline d'ingestion
Ordre d'exécution: raw → bronze → silver → gold
"""

import subprocess
import sys
import time
from datetime import datetime
import os

def log_message(message, level="INFO"):
    """Affiche un message avec horodatage"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def run_spark_job(job_path, job_name, spark_command):
    """Exécute un job Spark et retourne True si succès, False sinon"""
    log_message(f"Démarrage du job: {job_name}")
    start_time = time.time()

    try:
        # ✅ EXÉCUTION DIRECTE AVEC PYTHON (plus fiable que spark-submit)
        result = subprocess.run(
            ["python", job_path],
            capture_output=True,
            text=True,
            check=True
        )

        end_time = time.time()
        duration = end_time - start_time

        log_message(f"✅ {job_name} terminé avec succès en {duration:.1f}s")

        # Affichage des messages importants du job
        output_lines = result.stdout.split('\n')
        for line in output_lines:
            if line.strip() and any(keyword in line for keyword in
                ["SUCCESS", "INFO:", "STATS:", "ERROR:", "WARNING:", "lignes", "rows"]):
                print(f"    {line.strip()}")

        return True

    except subprocess.CalledProcessError as e:
        end_time = time.time()
        duration = end_time - start_time

        log_message(f"❌ {job_name} a échoué après {duration:.1f}s", "ERROR")

        # Affichage des vraies erreurs
        print("Erreurs:")
        if e.stderr:
            stderr_lines = e.stderr.split('\n')
            for line in stderr_lines[-20:]:  # Dernières 20 lignes d'erreur
                if line.strip():
                    print(f"    {line.strip()}")

        if e.stdout:
            stdout_lines = e.stdout.split('\n')
            for line in stdout_lines[-10:]:  # Dernières 10 lignes de sortie
                if line.strip() and ("ERROR" in line or "Exception" in line or "Traceback" in line):
                    print(f"    {line.strip()}")

        return False

    except Exception as e:
        log_message(f"❌ Erreur inattendue pour {job_name}: {str(e)}", "ERROR")
        return False

def check_prerequisites():
    """Vérifie que les prérequis sont présents"""
    log_message("Vérification des prérequis...")

    # Chemins possibles pour Spark
    spark_paths = [
        "spark-submit",  # Si dans le PATH
        "C:\\spark-3.5.5-bin-hadoop3\\spark-3.5.5-bin-hadoop3\\bin\\spark-submit.cmd",
        "C:\\spark-3.5.5-bin-hadoop3\\bin\\spark-submit.cmd",
        "C:\\spark\\bin\\spark-submit.cmd"
    ]

    spark_command = None

    # Vérifier que spark-submit est disponible
    for path in spark_paths:
        try:
            subprocess.run([path, "--version"],
                          capture_output=True, check=True, timeout=30)
            spark_command = path
            log_message(f"✅ Spark trouvé à: {path}")
            break
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if spark_command is None:
        log_message("❌ Spark n'est pas disponible. Vérifiez votre installation.", "ERROR")
        log_message("Chemins testés:", "ERROR")
        for path in spark_paths:
            log_message(f"  - {path}", "ERROR")
        return False, None

    # Vérifier que nous sommes dans le bon répertoire
    if not os.path.exists("jobs"):
        log_message("❌ Répertoire 'jobs' non trouvé. Exécutez ce script depuis le dossier ingestion/", "ERROR")
        return False, None

    # Vérifier que tous les jobs existent
    jobs = [
        "jobs/01_to_raw.py",
        "jobs/02_raw_to_bronze.py",
        "jobs/03_bronze_to_silver.py",
        "jobs/04_silver_to_gold.py"
    ]

    for job in jobs:
        if not os.path.exists(job):
            log_message(f"❌ Job manquant: {job}", "ERROR")
            return False, None

    log_message("✅ Tous les prérequis sont satisfaits")
    return True, spark_command

def cleanup_old_data():
    """Nettoie les anciennes données (optionnel)"""
    log_message("Nettoyage des anciennes données...")

    # Suppression des dossiers de sortie (optionnel - décommenter si besoin)
    # directories_to_clean = ["raw", "bronze", "silver", "gold"]
    # for directory in directories_to_clean:
    #     if os.path.exists(directory):
    #         import shutil
    #         shutil.rmtree(directory)
    #         log_message(f"Supprimé: {directory}")

    log_message("✅ Nettoyage terminé")

def check_data_availability():
    """Vérifie que les données sources sont disponibles"""
    log_message("Vérification de la disponibilité des données...")

    # Vérifier le répertoire landing
    if os.path.exists("landing") and os.listdir("landing"):
        files = os.listdir("landing")
        log_message(f"✅ Données trouvées dans landing: {len(files)} fichier(s)")
        for file in files[:5]:  # Afficher les 5 premiers
            log_message(f"    - {file}")
        return True
    else:
        log_message("⚠️  Aucune donnée trouvée dans le répertoire landing", "WARNING")
        return False

def main():
    """Fonction principale d'orchestration"""
    log_message("🚀 DÉMARRAGE DU PIPELINE D'INGESTION COMPLET")
    log_message("=" * 60)

    # Vérifications préliminaires
    prereq_ok, spark_command = check_prerequisites()
    if not prereq_ok:
        log_message("❌ Les prérequis ne sont pas satisfaits. Arrêt du pipeline.", "ERROR")
        sys.exit(1)

    check_data_availability()

    # Définition des jobs dans l'ordre d'exécution
    pipeline_jobs = [
        {
            "path": "jobs/01_to_raw.py",
            "name": "01 - Landing to Raw",
            "description": "Ingestion des données depuis landing vers raw"
        },
        {
            "path": "jobs/02_raw_to_bronze.py",
            "name": "02 - Raw to Bronze",
            "description": "Transformation et nettoyage vers bronze"
        },
        {
            "path": "jobs/03_bronze_to_silver.py",
            "name": "03 - Bronze to Silver",
            "description": "Enrichissement et validation vers silver"
        },  # ✅ RÉACTIVÉ - L'étape 3 fonctionne maintenant parfaitement !
        {
            "path": "jobs/04_silver_to_gold.py",
            "name": "04 - Silver to Gold",
            "description": "Agrégations et features ML vers gold"
        }
    ]

    # Exécution séquentielle des jobs
    pipeline_start_time = time.time()
    successful_jobs = 0
    failed_jobs = 0

    for i, job in enumerate(pipeline_jobs, 1):
        log_message("=" * 60)
        log_message(f"ÉTAPE {i}/4: {job['name']}")
        log_message(f"Description: {job['description']}")
        log_message("-" * 40)

        success = run_spark_job(job["path"], job["name"], spark_command)

        if success:
            successful_jobs += 1
            log_message(f"✅ étape {i} terminée avec succès")
        else:
            failed_jobs += 1
            log_message(f"❌ Étape {i} a échoué", "ERROR")

            # Demander si on continue malgré l'erreur
            response = input(f"\nÉtape {i} a échoué. Continuer avec l'étape suivante ? (y/N): ")
            if response.lower() != 'y':
                log_message("Pipeline interrompu par l'utilisateur", "WARNING")
                break

        # Pause entre les jobs
        if i < len(pipeline_jobs):
            log_message("Pause de 2 secondes avant l'étape suivante...")
            time.sleep(2)

    # Résumé final
    pipeline_end_time = time.time()
    total_duration = pipeline_end_time - pipeline_start_time

    log_message("=" * 60)
    log_message("🏁 RÉSUMÉ DU PIPELINE")
    log_message(f"Durée totale: {total_duration:.1f} secondes")
    log_message(f"Jobs réussis: {successful_jobs}")
    log_message(f"Jobs échoués: {failed_jobs}")

    if failed_jobs == 0:
        log_message("PIPELINE TERMINÉ AVEC SUCCÈS !")
        log_message("Données disponibles dans:")
        log_message("  - raw/     : Données brutes")
        log_message("  - bronze/  : Données nettoyées")
        log_message("  - silver/  : Données enrichies")
        log_message("  - gold/    : Agrégations et features ML")
    else:
        log_message(f"⚠️  Pipeline terminé avec {failed_jobs} erreur(s)", "WARNING")
        log_message("Vérifiez les logs ci-dessus pour plus de détails")

    log_message("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("\n🛑 Pipeline interrompu par l'utilisateur", "WARNING")
        sys.exit(1)
    except Exception as e:
        log_message(f"❌ Erreur inattendue: {str(e)}", "ERROR")
        sys.exit(1)
