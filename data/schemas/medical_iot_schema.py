# schemas/medical_iot_schema.py
"""
Schémas Spark fixes pour les données IoT médicales
Conformité production - pas d'inferSchema
"""

from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, TimestampType, DateType, BooleanType
)

# Schéma pour les données raw (depuis CSV landing)
RAW_MEDICAL_SCHEMA = StructType([
    # Identifiants
    StructField("patient_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("age", IntegerType(), True),

    # Données vitales principales
    StructField("fc", DoubleType(), True),  # Fréquence cardiaque (raw name)
    StructField("SpO2", DoubleType(), True),  # Saturation oxygène
    StructField("temp_c", DoubleType(), True),  # Température corporelle (raw name)
    StructField("hy_pct", DoubleType(), True),  # Hydratation % (raw name)
    StructField("fr", DoubleType(), True),  # Fréquence respiratoire (raw name)

    # Données environnementales
    StructField("temp_a", StringType(), True),  # Température ambiante (peut être string)
    StructField("activity", DoubleType(), True),  # Niveau d'activité
    StructField("heat_index_c", DoubleType(), True),  # Indice de chaleur original

    # Métadonnées d'ingestion (ajoutées par 01_to_raw)
    StructField("ingestion_ts", TimestampType(), True),
    StructField("source_file", StringType(), True)
])

# Schéma pour bronze (après nettoyage et pseudonymisation)
BRONZE_MEDICAL_SCHEMA = StructType([
    # Identifiants pseudonymis��s
    StructField("patient_id", StringType(), False),  # Hash SHA256
    StructField("device_id", StringType(), False),
    StructField("last_name", StringType(), True),
    StructField("age", IntegerType(), False),

    # Données vitales normalisées
    StructField("heart_rate_bpm", DoubleType(), True),
    StructField("SpO2", DoubleType(), True),
    StructField("temperature_core_c", DoubleType(), True),
    StructField("hydration_pct", DoubleType(), True),
    StructField("respiratory_rate", DoubleType(), True),

    # Données environnementales
    StructField("temp_a", StringType(), True),
    StructField("activity", DoubleType(), True),
    StructField("heat_index_c", DoubleType(), True),

    # Timestamps canoniques UTC
    StructField("event_ts", TimestampType(), False),  # Timestamp événement en UTC
    StructField("ingestion_ts", TimestampType(), False),  # Timestamp ingestion
    StructField("bronze_processed_ts", TimestampType(), False),

    # Partitioning
    StructField("event_date", DateType(), False),  # Dérivée de event_ts
    StructField("ingestion_date", DateType(), False),  # Dérivée de ingestion_ts

    # Métadonnées
    StructField("source_file", StringType(), True)
])

# Schéma pour silver (après enrichissement et validation)
SILVER_MEDICAL_SCHEMA = StructType([
    # Hérite de bronze + enrichissements
    StructField("patient_id", StringType(), False),
    StructField("device_id", StringType(), False),
    StructField("last_name", StringType(), True),
    StructField("age", IntegerType(), False),

    # Données vitales
    StructField("heart_rate_bpm", DoubleType(), True),
    StructField("SpO2", DoubleType(), True),
    StructField("temperature_core_c", DoubleType(), True),
    StructField("hydration_pct", DoubleType(), True),
    StructField("respiratory_rate", DoubleType(), True),

    # Données environnementales enrichies
    StructField("temp_a", StringType(), True),
    StructField("activity", DoubleType(), True),
    StructField("heat_index_c", DoubleType(), True),
    StructField("heat_index_calculated", DoubleType(), True),  # Calculé

    # Flags de qualité des données
    StructField("q_heart_rate_valid", IntegerType(), False),
    StructField("q_spo2_valid", IntegerType(), False),
    StructField("q_temp_core_valid", IntegerType(), False),
    StructField("q_hydration_valid", IntegerType(), False),
    StructField("q_respiratory_valid", IntegerType(), False),
    StructField("quality_score", DoubleType(), False),

    # Moyennes mobiles 10 minutes
    StructField("hr_avg_10min", DoubleType(), True),
    StructField("spo2_avg_10min", DoubleType(), True),
    StructField("temp_avg_10min", DoubleType(), True),
    StructField("hydration_avg_10min", DoubleType(), True),

    # Détection de variations
    StructField("hr_variation", DoubleType(), True),
    StructField("temp_variation", DoubleType(), True),

    # Alertes médicales
    StructField("alert_fever", IntegerType(), False),
    StructField("alert_tachycardia", IntegerType(), False),
    StructField("alert_hypoxia", IntegerType(), False),
    StructField("alert_dehydration", IntegerType(), False),
    StructField("alert_hr_spike", IntegerType(), False),

    # Classification
    StructField("age_group", StringType(), False),

    # Timestamps
    StructField("event_ts", TimestampType(), False),
    StructField("ingestion_ts", TimestampType(), False),
    StructField("bronze_processed_ts", TimestampType(), False),
    StructField("silver_processed_ts", TimestampType(), False),
    StructField("processing_delay_minutes", DoubleType(), True),

    # Partitioning
    StructField("event_date", DateType(), False),
    StructField("ingestion_date", DateType(), False),

    # Métadonnées
    StructField("source_file", StringType(), True)
])

# Contraintes de validation médicale
MEDICAL_CONSTRAINTS = {
    "heart_rate_bpm": {"min": 40, "max": 200, "unit": "bpm"},
    "SpO2": {"min": 70, "max": 100, "unit": "%"},
    "temperature_core_c": {"min": 35.0, "max": 42.0, "unit": "°C"},
    "hydration_pct": {"min": 0, "max": 100, "unit": "%"},
    "respiratory_rate": {"min": 8, "max": 40, "unit": "/min"},
    "age": {"min": 0, "max": 120, "unit": "years"}
}

# Seuils d'alerte médicale
MEDICAL_ALERT_THRESHOLDS = {
    "fever": {"temperature_core_c": 38.5},
    "hyperthermia": {"temperature_core_c": 40.0},
    "tachycardia": {"heart_rate_bpm": 120},
    "critical_tachycardia": {"heart_rate_bpm": 150},
    "hypoxia": {"SpO2": 90},
    "critical_hypoxia": {"SpO2": 85},
    "dehydration_moderate": {"hydration_pct": 40},
    "dehydration_severe": {"hydration_pct": 20},
    "hr_spike": {"hr_variation": 30}
}
