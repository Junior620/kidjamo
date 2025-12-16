"""
Orchestration des 4 étapes dans l'ordre 01=>02=>03=>04.

Rôle :
    Exécuter séquentiellement les scripts de transformation du pipeline
    d'ingestion avec gestion d'erreurs, logs détaillés et contrôle de flux.

Comportement :
    - Ordre d'exécution strict : RAW → BRONZE → SILVER → GOLD
    - Vérification prérequis (Spark, jobs, données)
    - Exécution avec streaming des logs en temps réel
    - Gestion d'erreurs avec option de continuation
    - Résumé final avec métriques de performance

Entrées :
    - Scripts Python dans data/jobs/ (01_to_raw.py → 04_silver_to_gold.py)
    - Données source dans data/lake/landing/*.csv
    - Environnement Spark configuré

Sorties :
    - Exécution séquentielle des 4 étapes
    - Logs détaillés de progression et erreurs
    - Data Lake complet : raw → bronze → silver → gold
    - Rapport final de performance

Effets de bord :
    - Configuration environnement PYTHONPATH pour imports
    - Nettoyage variables Hadoop/Spark invalides
    - Création arborescence Data Lake complète
    - Interaction utilisateur pour continuation sur erreur
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

# Configuration des répertoires basée sur la localisation du script
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
LAKE_DIR = os.path.join(BASE_DIR, "lake")
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
INGESTION_DIR = os.path.join(PROJECT_ROOT, "ingestion")

# Configuration des chemins Spark possibles (Windows)
SPARK_CANDIDATES = [
    "spark-submit",  # Si dans le PATH
    "C:\\spark-3.5.5-bin-hadoop3\\spark-3.5.5-bin-hadoop3\\bin\\spark-submit.cmd",
    "C:\\spark-3.5.5-bin-hadoop3\\bin\\spark-submit.cmd",
    "C:\\spark\\bin\\spark-submit.cmd"
]

# Configuration du pipeline
PIPELINE_JOBS = [
    {
        "script": "01_to_raw.py",
        "name": "01 - Landing to Raw",
        "description": "Ingestion des données depuis landing vers raw"
    },
    {
        "script": "02_raw_to_bronze.py",
        "name": "02 - Raw to Bronze",
        "description": "Transformation et nettoyage vers bronze"
    },
    {
        "script": "03_bronze_to_silver.py",
        "name": "03 - Bronze to Silver",
        "description": "Enrichissement et validation vers silver"
    },
    {
        "script": "04_silver_to_gold.py",
        "name": "04 - Silver to Gold",
        "description": "Agrégations et features ML vers gold"
    }
]


def log_message(message: str, level: str = "INFO") -> None:
    """
    Affiche un message avec horodatage standardisé.

    Args:
        message: Message à afficher
        level: Niveau de log (INFO, ERROR, WARNING)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")


def _find_spark_installation() -> Optional[str]:
    """
    Recherche une installation Spark valide dans les chemins candidats.

    Returns:
        str: Chemin vers spark-submit si trouvé, None sinon
    """
    for spark_path in SPARK_CANDIDATES:
        try:
            subprocess.run([spark_path, "--version"],
                          capture_output=True, check=True, timeout=30)
            return spark_path
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _validate_job_files() -> bool:
    """
    Vérifie l'existence de tous les fichiers de jobs requis.

    Returns:
        bool: True si tous les jobs existent, False sinon
    """
    for job_config in PIPELINE_JOBS:
        job_path = os.path.join(JOBS_DIR, job_config["script"])
        if not os.path.exists(job_path):
            log_message(f"❌ Job manquant: {job_path}", "ERROR")
            return False
    return True


def check_prerequisites() -> Tuple[bool, Optional[str]]:
    """
    Vérifie que tous les prérequis sont présents pour l'exécution.

    Vérifications effectuées :
    - Installation Spark accessible
    - Répertoire des jobs existant
    - Tous les fichiers de jobs présents

    Returns:
        tuple: (success: bool, spark_command: Optional[str])
    """
    log_message("Vérification des prérequis...")

    # 1. Vérification installation Spark
    spark_command = _find_spark_installation()
    if spark_command is None:
        log_message("❌ Spark n'est pas disponible. Vérifiez votre installation.", "ERROR")
        log_message("Chemins testés:", "ERROR")
        for path in SPARK_CANDIDATES:
            log_message(f"  - {path}", "ERROR")
        return False, None

    log_message(f"✅ Spark trouvé à: {spark_command}")

    # 2. Vérification répertoire des jobs
    if not os.path.exists(JOBS_DIR):
        log_message(f"❌ Répertoire des jobs introuvable: {JOBS_DIR}", "ERROR")
        log_message("Veuillez exécuter ce script depuis data\\pipelines", "ERROR")
        return False, None

    # 3. Vérification fichiers de jobs
    if not _validate_job_files():
        return False, None

    log_message("✅ Tous les prérequis sont satisfaits")
    return True, spark_command


def check_data_availability() -> bool:
    """
    Vérifie la disponibilité des données sources dans landing.

    Returns:
        bool: True si données disponibles, False sinon
    """
    log_message("Vérification de la disponibilité des données...")

    landing_dir = os.path.join(LAKE_DIR, "landing")
    if os.path.exists(landing_dir) and os.listdir(landing_dir):
        files = os.listdir(landing_dir)
        log_message(f"✅ Données trouvées dans {landing_dir}: {len(files)} fichier(s)")

        # Affichage des premiers fichiers pour information
        for file in files[:5]:
            log_message(f"    - {file}")
        return True
    else:
        log_message(f"⚠️  Aucune donnée trouvée dans {landing_dir}", "WARNING")
        return False


def _setup_execution_environment() -> dict:
    """
    Configure l'environnement d'exécution pour les sous-processus.

    Configuration :
    - Ajout ingestion et data au PYTHONPATH
    - Propagation SPARK_HOME si détecté
    - Nettoyage HADOOP_HOME invalide

    Returns:
        dict: Environnement configuré pour subprocess
    """
    env = os.environ.copy()

    # Configuration PYTHONPATH pour imports cross-modules
    pythonpath = env.get("PYTHONPATH", "")
    add_paths = [INGESTION_DIR, BASE_DIR]
    for path in add_paths:
        if path and path not in pythonpath:
            pythonpath = (pythonpath + (os.pathsep if pythonpath else "") + path)
    env["PYTHONPATH"] = pythonpath

    return env


def _configure_spark_environment(env: dict, spark_command: Optional[str]) -> None:
    """
    Configure l'environnement Spark dans le dictionnaire d'environnement.

    Args:
        env: Dictionnaire d'environnement à modifier
        spark_command: Chemin vers spark-submit si disponible
    """
    try:
        if (spark_command and os.path.isabs(spark_command) and
            os.path.basename(spark_command).startswith("spark-submit")):

            bin_dir = os.path.dirname(spark_command)
            spark_home = os.path.abspath(os.path.join(bin_dir, ".."))
            env["SPARK_HOME"] = spark_home

            spark_bin = os.path.join(spark_home, "bin")
            current_path = env.get("PATH", "")
            if spark_bin and spark_bin not in current_path:
                env["PATH"] = spark_bin + os.pathsep + current_path
    except Exception:
        pass


def _cleanup_hadoop_environment(env: dict) -> None:
    """
    Nettoie HADOOP_HOME invalide pour éviter erreurs winutils sur Windows.

    Args:
        env: Dictionnaire d'environnement à nettoyer
    """
    try:
        hadoop_home = env.get("HADOOP_HOME")
        if hadoop_home and not os.path.isdir(hadoop_home):
            env.pop("HADOOP_HOME", None)
    except Exception:
        pass


def run_spark_job(job_path: str, job_name: str, spark_command: Optional[str]) -> bool:
    """
    Exécute un job Spark avec streaming des logs en temps réel.

    Configuration d'exécution :
    - Exécution directe avec Python (plus fiable que spark-submit)
    - Environnement configuré avec PYTHONPATH et variables Spark
    - Streaming des logs en temps réel avec préfixe d'indentation
    - Gestion timeout et codes de retour

    Args:
        job_path: Chemin vers le script Python à exécuter
        job_name: Nom du job pour logging
        spark_command: Chemin spark-submit pour configuration environnement

    Returns:
        bool: True si succès, False si échec
    """
    log_message(f"Démarrage du job: {job_name}")
    start_time = time.time()

    try:
        # Configuration environnement d'exécution
        env = _setup_execution_environment()
        _configure_spark_environment(env, spark_command)
        _cleanup_hadoop_environment(env)

        # Lancement du processus avec streaming des logs
        proc = subprocess.Popen(
            ["python", "-u", job_path],
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Streaming output en temps réel avec indentation
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                line = line.rstrip('\n')
                if line:
                    print(f"    {line}")

        return_code = proc.wait()
        end_time = time.time()
        duration = end_time - start_time

        # Évaluation résultat et logging
        if return_code == 0:
            log_message(f"✅ {job_name} terminé avec succès en {duration:.1f}s")
            return True
        else:
            log_message(f"❌ {job_name} a échoué après {duration:.1f}s", "ERROR")
            log_message("Voir les logs ci-dessus pour le détail des erreurs.", "ERROR")
            return False

    except Exception as e:
        log_message(f"❌ Erreur inattendue pour {job_name}: {str(e)}", "ERROR")
        return False


def _ask_user_continuation(step_number: int) -> bool:
    """
    Demande à l'utilisateur s'il souhaite continuer après une erreur.

    Args:
        step_number: Numéro de l'étape qui a échoué

    Returns:
        bool: True si l'utilisateur veut continuer, False sinon
    """
    try:
        response = input(f"\nÉtape {step_number} a échoué. Continuer avec l'étape suivante ? (y/N): ")
        return response.lower() == 'y'
    except (EOFError, KeyboardInterrupt):
        return False


def _print_pipeline_summary(successful_jobs: int, failed_jobs: int, total_duration: float) -> None:
    """
    Affiche le résumé final du pipeline avec métriques.

    Args:
        successful_jobs: Nombre de jobs réussis
        failed_jobs: Nombre de jobs échoués
        total_duration: Durée totale d'exécution en secondes
    """
    log_message("=" * 60)
    log_message("🏁 RÉSUMÉ DU PIPELINE")
    log_message(f"Durée totale: {total_duration:.1f} secondes")
    log_message(f"Jobs réussis: {successful_jobs}")
    log_message(f"Jobs échoués: {failed_jobs}")

    if failed_jobs == 0:
        log_message("PIPELINE TERMINÉ AVEC SUCCÈS !")
        log_message("Données disponibles dans le Data Lake:")
        log_message(f"  - {os.path.join(LAKE_DIR, 'raw')}     : Données brutes")
        log_message(f"  - {os.path.join(LAKE_DIR, 'bronze')}  : Données nettoyées")
        log_message(f"  - {os.path.join(LAKE_DIR, 'silver')}  : Données enrichies")
        log_message(f"  - {os.path.join(LAKE_DIR, 'gold')}    : Agrégations et features ML")
    else:
        log_message(f"⚠️  Pipeline terminé avec {failed_jobs} erreur(s)", "WARNING")
        log_message("Vérifiez les logs ci-dessus pour plus de détails")

    log_message("=" * 60)


def main() -> None:
    """
    Fonction principale d'orchestration du pipeline complet.

    Orchestration complète :
    1. Vérifications prérequis (Spark, jobs, données)
    2. Exécution séquentielle des 4 étapes du pipeline
    3. Gestion d'erreurs avec option de continuation
    4. Pauses entre étapes pour stabilité
    5. Résumé final avec métriques de performance

    Gestion d'erreurs :
    - Arrêt sur prérequis manquants
    - Option continuation sur échec d'étape
    - Interruption propre sur Ctrl+C
    """
    log_message("🚀 DÉMARRAGE DU PIPELINE D'INGESTION COMPLET")
    log_message("=" * 60)

    # 1. Vérifications préliminaires
    prereq_ok, spark_command = check_prerequisites()
    if not prereq_ok:
        log_message("❌ Les prérequis ne sont pas satisfaits. Arrêt du pipeline.", "ERROR")
        sys.exit(1)

    check_data_availability()

    # 2. Préparation configuration des jobs avec chemins complets
    jobs_with_paths = [
        {
            **job_config,
            "path": os.path.join(JOBS_DIR, job_config["script"])
        }
        for job_config in PIPELINE_JOBS
    ]

    # 3. Exécution séquentielle du pipeline
    pipeline_start_time = time.time()
    successful_jobs = 0
    failed_jobs = 0

    for i, job in enumerate(jobs_with_paths, 1):
        # Affichage en-tête étape
        log_message("=" * 60)
        log_message(f"ÉTAPE {i}/4: {job['name']}")
        log_message(f"Description: {job['description']}")
        log_message("-" * 40)

        # Exécution job avec mesure de performance
        success = run_spark_job(job["path"], job["name"], spark_command)

        if success:
            successful_jobs += 1
            log_message(f"✅ étape {i} terminée avec succès")
        else:
            failed_jobs += 1
            log_message(f"❌ Étape {i} a échoué", "ERROR")

            # Gestion continuation sur erreur
            if not _ask_user_continuation(i):
                log_message("Pipeline interrompu par l'utilisateur", "WARNING")
                break

        # Pause inter-étapes pour stabilité système
        if i < len(jobs_with_paths):
            log_message("Pause de 2 secondes avant l'étape suivante...")
            time.sleep(2)

    # 4. Résumé final avec métriques
    pipeline_end_time = time.time()
    total_duration = pipeline_end_time - pipeline_start_time
    _print_pipeline_summary(successful_jobs, failed_jobs, total_duration)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("\n🛑 Pipeline interrompu par l'utilisateur", "WARNING")
        sys.exit(1)
    except Exception as e:
        log_message(f"❌ Erreur inattendue: {str(e)}", "ERROR")
        sys.exit(1)
