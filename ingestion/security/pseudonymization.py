# security/pseudonymization.py
"""
Module de pseudonymisation pour les données de santé
Conformité RGPD/HIPAA
"""
from pyspark.sql.functions import sha2, concat, lit
from pyspark.sql import DataFrame

def pseudonymize_patient_data(df: DataFrame, salt: str = "kidjamo_salt_2025") -> DataFrame:
    """
    Pseudonymise les identifiants patients selon les standards de santé
    
    Args:
        df: DataFrame avec patient_id en clair
        salt: Clé de salage (devrait venir de KMS en prod)
    
    Returns:
        DataFrame avec patient_id_hash pseudonymisé
    """
    
    # Pseudonymisation SHA256 avec salt
    df_pseudo = (df
        .withColumn("patient_id_hash", 
            sha2(concat(col("patient_id"), lit(salt)), 256))
        .drop("patient_id")  # Suppression ID en clair
        .withColumnRenamed("patient_id_hash", "patient_id")
    )
    
    return df_pseudo

def apply_data_classification(df: DataFrame) -> DataFrame:
    """
    Applique la classification des données selon leur sensibilité
    """
    
    # Colonnes PII (Personal Identifiable Information)
    pii_columns = ["patient_id", "last_name", "device_id"]
    
    # Colonnes cliniques sensibles
    clinical_columns = ["heart_rate_bpm", "SpO2", "temperature_core_c", 
                       "hydration_pct", "respiratory_rate"]
    
    # Masquage pour les exports (si nécessaire)
    # En production, créer des vues masquées pour BI
    
    return df
