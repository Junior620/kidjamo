"""
Module simulateur IoT massif pour patients virtuels
"""

# Import des classes principales depuis le simulateur combiné
try:
    from .massive_patient_simulator_combined import (
        MassivePatientSimulationController,
        PatientProfile,
        MeasurementRecord,
        AlertRecord,
        NotificationService,
        DatabaseManager,
        AlertEngine,
        PatientGenerator,
        PhysiologicalSimulator
    )

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

except ImportError as e:
    print(f"⚠️ Erreur d'import du simulateur: {e}")
    # Classes par défaut pour éviter les erreurs
    __all__ = []
