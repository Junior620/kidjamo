#!/usr/bin/env python3
# Test minimal pour identifier le problème
print("TEST 1: Python démarre OK")

try:
    print("TEST 2: Import pyspark...")
    from pyspark.sql import SparkSession
    print("TEST 3: Import pyspark OK")

    print("TEST 4: Création session Spark...")
    spark = SparkSession.builder.appName("test-minimal").getOrCreate()
    print("TEST 5: Session Spark créée OK")

    print("TEST 6: Test lecture bronze...")
    bronze = spark.read.parquet("bronze")
    print(f"TEST 7: Bronze lu OK - {bronze.count()} lignes")

    spark.stop()
    print("TEST 8: SUCCESS - Tous les tests passés")

except Exception as e:
    print(f"ERREUR: {e}")
    import traceback
    traceback.print_exc()
