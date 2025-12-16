# =====================================================
# SIMULATEUR MASSIF CONSOLIDÉ - TOUS LES MODULES
# =====================================================
# Ce fichier combine tous les modules du simulateur massif pour faciliter l'import

# Import de toutes les classes depuis les fichiers séparés
import sys
import os
from pathlib import Path

# Ajouter le chemin actuel au PYTHONPATH
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Imports des modules principaux
try:
    # Import des classes depuis les fichiers part1-4 avec encodage UTF-8
    exec(open(current_dir / "massive_patient_simulator.py", encoding='utf-8').read())
    exec(open(current_dir / "massive_patient_simulator_part2.py", encoding='utf-8').read())
    exec(open(current_dir / "massive_patient_simulator_part3.py", encoding='utf-8').read())
    exec(open(current_dir / "massive_patient_simulator_part4.py", encoding='utf-8').read())

    print("✅ Modules simulateur chargés avec succès")

except Exception as e:
    print(f"❌ Erreur chargement modules: {e}")
    print("Assurez-vous que tous les fichiers massive_patient_simulator_part*.py sont présents")

# Export des classes principales
__all__ = [
    'MassivePatientSimulationController',
    'PatientProfile',
    'MeasurementRecord',
    'AlertRecord',
    'NotificationService',
    'DatabaseManager',
    'AlertEngine',
    'PatientGenerator',
    'PhysiologicalSimulator'
]
