# jobs/02_raw_to_bronze.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, regexp_replace, current_timestamp, to_date, sha2, concat, lit, to_utc_timestamp, coalesce
from pyspark.sql.types import (StructType, StructField, StringType, DoubleType, IntegerType, TimestampType)
import sys
import os

def main():
    spark = (SparkSession.builder
             .appName("tech4good-02-raw-to-bronze")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .config("spark.sql.adaptive.enabled", "true")
             .getOrCreate())

    try:
        # ✅ CHEMINS ABSOLUS POUR ÉVITER LES PROBLÈMES DE RÉPERTOIRE
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        raw_base = os.path.join(base_dir, "raw")
        bronze_base = os.path.join(base_dir, "bronze")
        quarantine_base = os.path.join(base_dir, "bronze", "quarantine")

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Raw base: {raw_base}")
        print(f"INFO: Bronze base: {bronze_base}")

        # Vérifier que le répertoire raw existe et contient des données
        if not os.path.exists(raw_base):
            print(f"ERROR: Raw directory not found: {raw_base}")
            sys.exit(1)

        # Chercher les fichiers parquet dans raw
        raw_pattern = os.path.join(raw_base, "*", "*.parquet")
        print(f"INFO: Looking for parquet files: {raw_pattern}")

        # ✅ CONTRAINTES MÉDICALES INTÉGRÉES
        MEDICAL_CONSTRAINTS = {
            "heart_rate_bpm": {"min": 40, "max": 200, "unit": "bpm"},
            "SpO2": {"min": 70, "max": 100, "unit": "%"},
            "temperature_core_c": {"min": 35.0, "max": 42.0, "unit": "°C"},
            "hydration_pct": {"min": 0, "max": 100, "unit": "%"},
            "respiratory_rate": {"min": 8, "max": 40, "unit": "/min"},
            "age": {"min": 0, "max": 120, "unit": "years"}
        }

        # Lecture des données raw avec gestion d'erreurs
        try:
            df = spark.read.parquet(raw_pattern)
            row_count = df.count()
            print(f"INFO: Loaded {row_count} rows from raw")
            print("INFO: Schema from raw data:")
            df.printSchema()

            if row_count == 0:
                print("ERROR: No data found in raw layer")
                sys.exit(1)

        except Exception as read_error:
            print(f"ERROR: Failed to read raw data - {str(read_error)}")
            sys.exit(1)

        # ✅ TIMESTAMPS CANONIQUES UTC
        bronze = (df
            .withColumn("event_ts", to_utc_timestamp(col("ingestion_ts"), "UTC"))
            .withColumn("event_date", to_date(col("event_ts")))
            .withColumn("ingestion_date", to_date(col("ingestion_ts")))
        )

        # Normalisation des noms de colonnes (si les colonnes existent)
        columns = bronze.columns

        if "temp_c" in columns:
            bronze = bronze.withColumnRenamed("temp_c", "temperature_core_c")
        if "fc" in columns:
            bronze = bronze.withColumnRenamed("fc", "heart_rate_bpm")
        if "hy_pct" in columns:
            bronze = bronze.withColumnRenamed("hy_pct", "hydration_pct")
        if "fr" in columns:
            bronze = bronze.withColumnRenamed("fr", "respiratory_rate")

        print("INFO: Column normalization completed")

        # ✅ VALIDATION DES CONTRAINTES MÉDICALES
        constraints = MEDICAL_CONSTRAINTS
        bronze_columns = bronze.columns

        # Construire les conditions de validation seulement pour les colonnes existantes
        valid_conditions = []

        # Conditions obligatoires
        if "patient_id" in bronze_columns:
            valid_conditions.append(col("patient_id").isNotNull())
        if "device_id" in bronze_columns:
            valid_conditions.append(col("device_id").isNotNull())
        if "age" in bronze_columns:
            valid_conditions.append(col("age").between(constraints["age"]["min"], constraints["age"]["max"]))

        # Conditions optionnelles (avec gestion des valeurs nulles)
        if "heart_rate_bpm" in bronze_columns:
            valid_conditions.append(
                (col("heart_rate_bpm").isNull()) |
                col("heart_rate_bpm").between(constraints["heart_rate_bpm"]["min"], constraints["heart_rate_bpm"]["max"])
            )

        if "SpO2" in bronze_columns:
            valid_conditions.append(
                (col("SpO2").isNull()) |
                col("SpO2").between(constraints["SpO2"]["min"], constraints["SpO2"]["max"])
            )

        if "temperature_core_c" in bronze_columns:
            valid_conditions.append(
                (col("temperature_core_c").isNull()) |
                col("temperature_core_c").between(constraints["temperature_core_c"]["min"], constraints["temperature_core_c"]["max"])
            )

        # Appliquer les filtres seulement s'il y a des conditions
        if valid_conditions:
            # Combiner toutes les conditions avec AND
            final_condition = valid_conditions[0]
            for condition in valid_conditions[1:]:
                final_condition = final_condition & condition

            bronze_valid = bronze.filter(final_condition)
            bronze_quarantine = bronze.filter(~final_condition)
        else:
            # Si aucune condition de validation, toutes les données sont valides
            bronze_valid = bronze
            bronze_quarantine = spark.createDataFrame([], bronze.schema)

        # ✅ SÉCURITÉ : Pseudonymisation des identifiants (si patient_id existe)
        if "patient_id" in bronze_valid.columns:
            bronze_valid = (bronze_valid
                .withColumn("patient_id_hash", sha2(concat(col("patient_id"), lit("kidjamo_salt_2025")), 256))
                .drop("patient_id")
                .withColumnRenamed("patient_id_hash", "patient_id")
            )
            print("INFO: Patient IDs pseudonymisés pour conformité RGPD")

        # Ajout timestamp de traitement bronze
        bronze_valid = bronze_valid.withColumn("bronze_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))

        # Retrait des doublons
        dedup_columns = ["patient_id", "event_ts"] if "patient_id" in bronze_valid.columns else ["event_ts"]
        if "device_id" in bronze_valid.columns:
            dedup_columns.append("device_id")

        bronze_final = bronze_valid.dropDuplicates(dedup_columns)

        # ✅ STATISTIQUES ET ÉCRITURE
        quarantine_count = bronze_quarantine.count()
        valid_count = bronze_final.count()

        print(f"INFO: Données valides: {valid_count}")
        print(f"INFO: Données en quarantaine: {quarantine_count}")

        # Créer les répertoires de sortie
        os.makedirs(bronze_base, exist_ok=True)
        os.makedirs(os.path.dirname(quarantine_base), exist_ok=True)

        # Écriture des données valides
        try:
            (bronze_final
             .write
             .mode("overwrite")
             .partitionBy("event_date")
             .parquet(bronze_base))

            print(f"SUCCESS: Wrote BRONZE -> {bronze_base}")

        except Exception as write_error:
            print(f"ERROR: Failed to write bronze data - {str(write_error)}")
            sys.exit(1)

        # Écriture de la quarantaine si nécessaire
        if quarantine_count > 0:
            try:
                (bronze_quarantine
                 .withColumn("quarantine_reason", lit("validation_failed"))
                 .withColumn("quarantine_ts", to_utc_timestamp(current_timestamp(), "UTC"))
                 .write
                 .mode("overwrite")
                 .partitionBy("ingestion_date")
                 .parquet(quarantine_base))
                print(f"WARNING: {quarantine_count} enregistrements mis en quarantaine")
            except Exception as q_error:
                print(f"WARNING: Failed to write quarantine data - {str(q_error)}")

        total_records = valid_count + quarantine_count
        data_quality = (valid_count / total_records * 100) if total_records > 0 else 0

        print(f"STATS: Valid rows processed: {valid_count}")
        print(f"STATS: Data quality: {data_quality:.1f}%")

    except Exception as e:
        print(f"ERROR in 02_raw_to_bronze: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
