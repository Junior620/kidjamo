import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *

# Configuration optimisée
args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configuration Spark pour performance
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

print("DEBUT JOB RAW-TO-BRONZE ULTRA-OPTIMISE MPU CHRISTIAN")

try:
    # Lire avec pattern spécifique et limite
    bucket = "kidjamo-dev-datalake-e75d5213"
    
    # Pattern très spécifique pour éviter de lire tous les fichiers
    patterns = [
        f"s3://{bucket}/raw/iot-measurements/year=2025/month=09/day=17/hour=*/mpu_christian_*.json",
        f"s3://{bucket}/raw/iot-measurements/year=2025/month=09/day=18/hour=*/mpu_christian_*.json"
    ]
    
    df_parts = []
    for pattern in patterns:
        try:
            temp_df = spark.read.json(pattern)
            if temp_df.count() > 0:
                df_parts.append(temp_df)
                print(f"Pattern lu: {pattern} - {temp_df.count()} lignes")
        except Exception as e:
            print(f"Pattern ignoré: {pattern} - {e}")
            continue
    
    if not df_parts:
        print("AUCUN FICHIER MPU TROUVE")
        raise Exception("Aucun fichier MPU Christian trouvé")
    
    # Union des DataFrames
    df = df_parts[0]
    for temp_df in df_parts[1:]:
        df = df.union(temp_df)
    
    print(f"TOTAL LIGNES LUES: {df.count()}")
    
    # Filtrage strict MPU Christian
    mpu_df = df.filter(col("device_id") == "MPU_Christian_8266MOD")
    
    print(f"LIGNES MPU CHRISTIAN: {mpu_df.count()}")
    
    if mpu_df.count() == 0:
        raise Exception("Aucune donnée MPU Christian après filtrage")
    
    # Transformation minimale
    bronze_df = mpu_df.select(
        col("device_id"),
        col("accel_x").cast("double"),
        col("accel_y").cast("double"),
        col("accel_z").cast("double"),
        col("gyro_x").cast("double"),
        col("gyro_y").cast("double"),
        col("gyro_z").cast("double"),
        col("temp").cast("double").alias("temperature"),
        col("aws_timestamp").cast("long"),
        current_timestamp().alias("bronze_timestamp")
    ).withColumn("year", lit(2025)
    ).withColumn("month", lit(9)
    ).withColumn("day", lit(19)  # Jour actuel
    )
    
    print(f"DONNEES TRANSFORMEES: {bronze_df.count()}")
    
    # Écriture optimisée
    output_path = f"s3://{bucket}/bronze/mpu_christian/"
    
    bronze_df.coalesce(1).write.mode("overwrite").partitionBy("year", "month", "day").json(output_path)
    
    print(f"SUCCES: {bronze_df.count()} enregistrements écrits dans {output_path}")
    
    # Vérification
    verification = spark.read.json(output_path)
    print(f"VERIFICATION: {verification.count()} enregistrements lus depuis bronze")

except Exception as e:
    print(f"ERREUR CRITIQUE: {str(e)}")
    raise e

finally:
    job.commit()
    print("JOB ULTRA-OPTIMISE TERMINE")