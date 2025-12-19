# security/pseudonymization.py
"""
Module de pseudonymisation pour les données de santé - Transformations Spark.

Rôle :
    Pseudonymiser les identifiants patients côté PySpark pour usages analytiques.
    Applique SHA256 + salt sur les DataFrames Spark pour conformité RGPD/HIPAA
    dans les zones Bronze/Silver du data lake.

Objectifs :
    - Transformation `patient_id` en clair → `patient_id` pseudonymisé (SHA256+salt)
    - Classification des colonnes selon sensibilité (PII, clinique)
    - Conservation du schéma DataFrame avec remplacement in-place
    - Support zones analytiques où l'ID original n'est plus nécessaire

Entrées :
    - DataFrame Spark avec colonne `patient_id` en clair
    - Salt de pseudonymisation (paramètre avec valeur par défaut)
    - Configuration de classification des données sensibles

Sorties :
    - DataFrame Spark avec `patient_id` pseudonymisé (SHA256 hex)
    - Structure identique, seule la valeur de la colonne est transformée
    - Pas de création de nouvelle colonne (remplacement in-place)

Effets de bord :
    - Aucun I/O : transformations en mémoire uniquement
    - Pas de logs ni fichiers créés (transformation Spark pure)
    - Pas d'accès réseau ni variables d'environnement

Garanties :
    - Schéma DataFrame identique (même nom de colonne, type string)
    - Comportement déterministe : même input → même output
    - API publique inchangée (signature des fonctions)
    - Valeur par défaut du salt conservée pour rétrocompatibilité

Limites sécurité :
    - Pseudonymisation ≠ anonymisation : réversible avec table de correspondance
    - Salt hardcodé visible (pour développement uniquement)
    - Risque de re-identification si combiné avec autres données
    - Pour production : utiliser pseudonymization_secure.py avec .env
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, concat, lit, sha2

# Salt par défaut (développement) - REMPLACÉ par .env en production
DEFAULT_SALT = "kidjamo_salt_2025"

# Classification des colonnes par niveau de sensibilité
PII_COLUMNS = ["patient_id", "last_name", "device_id"]
CLINICAL_COLUMNS = [
    "heart_rate_bpm", "SpO2", "temperature_core_c",
    "hydration_pct", "respiratory_rate"
]


def pseudonymize_patient_data(df: DataFrame, salt: str = DEFAULT_SALT) -> DataFrame:
    """
    Pseudonymise les identifiants patients selon les standards de santé.

    Applique un hachage SHA256 avec salt sur la colonne patient_id pour
    permettre les analyses tout en protégeant l'identité directe des patients.
    Conforme aux exigences RGPD article 4(5) et HIPAA Safe Harbor.

    Args:
        df: DataFrame Spark contenant une colonne 'patient_id'
        salt: Clé de salage pour renforcer le hachage (défaut: développement)
              En production, devrait provenir de KMS ou variables sécurisées

    Returns:
        DataFrame: Même structure avec patient_id pseudonymisé en SHA256

    Raises:
        AnalysisException: Si la colonne 'patient_id' n'existe pas dans le DataFrame

    Example:
        >>> df_patients = spark.createDataFrame([("PAT001",), ("PAT002",)], ["patient_id"])
        >>> df_pseudo = pseudonymize_patient_data(df_patients)
        >>> df_pseudo.select("patient_id").show()
        +------------------------------------------------------------+
        |patient_id                                                  |
        +------------------------------------------------------------+
        |a1b2c3d4e5f6... (SHA256 hash)                             |
        +------------------------------------------------------------+

    Note sécurité:
        - Cette fonction utilise un salt hardcodé pour le développement
        - En production, utiliser pseudonymization_secure.py avec salt depuis .env
        - La pseudonymisation permet la re-identification avec table de correspondance
        - Pour anonymisation complète, appliquer des techniques supplémentaires
    """
    # Vérification présence colonne patient_id (laisse Spark gérer l'exception)
    # Application transformation SHA256 avec salt
    df_pseudo = (df
                 .withColumn("patient_id_hash",
                            sha2(concat(col("patient_id"), lit(salt)), 256))
                 .drop("patient_id")  # Suppression ID en clair
                 .withColumnRenamed("patient_id_hash", "patient_id")
                 )

    return df_pseudo


def apply_data_classification(df: DataFrame) -> DataFrame:
    """
    Applique la classification des données selon leur sensibilité.

    Identifie et catégorise les colonnes selon les standards de protection
    des données de santé. Cette fonction sert actuellement d'inventaire
    et peut être étendue pour appliquer des transformations spécifiques.

    Args:
        df: DataFrame Spark à classifier

    Returns:
        DataFrame: DataFrame inchangé (fonction d'inventaire actuellement)
                  Peut être étendue pour appliquer masquage, chiffrement, etc.

    Note:
        - Colonnes PII : Identifiants directs (patient_id, device_id, noms)
        - Colonnes cliniques : Données médicales sensibles (vitaux, diagnostics)
        - En production : créer des vues masquées pour BI et reporting
        - Cette classification peut alimenter des politiques de gouvernance
    """
    # Inventaire des colonnes sensibles présentes
    df_columns = df.columns
    pii_present = [col for col in PII_COLUMNS if col in df_columns]
    clinical_present = [col for col in CLINICAL_COLUMNS if col in df_columns]

    # Future extension : appliquer transformations selon classification
    # - Masquage pour exports BI
    # - Chiffrement pour stockage long terme
    # - Tokenisation pour systèmes tiers
    # - Audit des accès par niveau de sensibilité

    # Actuellement : retour du DataFrame inchangé (inventaire seulement)
    return df
