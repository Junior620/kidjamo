import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *

args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("DEBUT JOB BRONZE-TO-SILVER MPU CHRISTIAN")

try:
    # Lire les données bronze MPU Christian
    bronze_path = "s3://kidjamo-dev-datalake-e75d5213/bronze/mpu_christian/"
    
    df = spark.read.json(bronze_path)
    
    print(f"LIGNES BRONZE LUES: {df.count()}")
    
    if df.count() > 0:
        # Enrichissement des données pour Silver
        silver_df = df.select(
            col("device_id"),
            col("accel_x"),
            col("accel_y"),
            col("accel_z"),
            col("gyro_x"),
            col("gyro_y"), 
            col("gyro_z"),
            col("temperature"),
            col("aws_timestamp"),
            col("bronze_timestamp"),
            
            # Calculs d'enrichissement
            sqrt(
                col("accel_x") * col("accel_x") + 
                col("accel_y") * col("accel_y") + 
                col("accel_z") * col("accel_z")
            ).alias("acceleration_magnitude"),
            
            sqrt(
                col("gyro_x") * col("gyro_x") + 
                col("gyro_y") * col("gyro_y") + 
                col("gyro_z") * col("gyro_z")
            ).alias("gyro_magnitude"),
            
            # Classification de mouvement
            when(
                sqrt(col("accel_x") * col("accel_x") + 
                     col("accel_y") * col("accel_y") + 
                     col("accel_z") * col("accel_z")) > 15.0, "high_activity"
            ).when(
                sqrt(col("accel_x") * col("accel_x") + 
                     col("accel_y") * col("accel_y") + 
                     col("accel_z") * col("accel_z")) > 12.0, "medium_activity"  
            ).otherwise("low_activity").alias("activity_level"),
            
            # Classification température
            when(col("temperature") > 37.5, "fever")
            .when(col("temperature") < 35.0, "hypothermia")
            .otherwise("normal").alias("temperature_status"),
            
            # Détection d'anomalies
            when(
                sqrt(col("accel_x") * col("accel_x") + 
                     col("accel_y") * col("accel_y") + 
                     col("accel_z") * col("accel_z")) > 15.0, "potential_fall"
            ).when(
                sqrt(col("accel_x") * col("accel_x") + 
                     col("accel_y") * col("accel_y") + 
                     col("accel_z") * col("accel_z")) < 2.0, "inactivity"
            ).otherwise("normal_movement").alias("movement_type"),
            
            # Timestamps Silver
            current_timestamp().alias("silver_timestamp")
        ).withColumn("year", lit(2025)
        ).withColumn("month", lit(9)
        ).withColumn("day", lit(19))
        
        print(f"DONNEES SILVER TRANSFORMEES: {silver_df.count()}")
        
        # Écriture en silver
        silver_output = "s3://kidjamo-dev-datalake-e75d5213/silver/mpu_christian_enriched/"
        
        silver_df.coalesce(1).write.mode("overwrite").partitionBy("year", "month", "day").json(silver_output)
        
        print(f"SUCCES: {silver_df.count()} enregistrements écrits en silver")
    else:
        raise Exception("Aucune donnée bronze trouvée")

except Exception as e:
    print(f"ERREUR: {str(e)}")
    raise e

finally:
    job.commit()
    print("JOB BRONZE-TO-SILVER TERMINE")