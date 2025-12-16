# jobs/03_bronze_to_silver_debug.py
# Version de debug pour identifier le problème de l'étape 3
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window
import sys

def main():
    print("DEBUG: Démarrage de l'étape 3 debug")

    spark = (SparkSession.builder
             .appName("debug-bronze-to-silver")
             .config("spark.sql.session.timeZone", "UTC")
             .getOrCreate())

    try:
        print("DEBUG: Spark session créée")

        # Test de lecture des données bronze
        bronze_base = "bronze"
        print(f"DEBUG: Tentative de lecture de {bronze_base}")

        bronze = spark.read.parquet(bronze_base)
        print(f"DEBUG: Lecture réussie, {bronze.count()} lignes")

        print("DEBUG: Schéma des données bronze:")
        bronze.printSchema()

        print("DEBUG: Colonnes disponibles:")
        for col_name in bronze.columns:
            print(f"  - {col_name}")

        # Test simple d'écriture
        print("DEBUG: Test d'écriture simple...")
        sample_data = bronze.limit(100)

        (sample_data
         .write
         .mode("overwrite")
         .parquet("silver_debug"))

        print("DEBUG: Écriture test réussie")
        print("SUCCESS: Debug terminé avec succès")

    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
