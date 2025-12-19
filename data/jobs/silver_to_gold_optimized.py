import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("DEBUT JOB SILVER-TO-GOLD MPU CHRISTIAN")

try:
    # Lire les données silver
    silver_path = "s3://kidjamo-dev-datalake-e75d5213/silver/mpu_christian_enriched/"
    
    df = spark.read.json(silver_path)
    
    print(f"LIGNES SILVER LUES: {df.count()}")
    
    if df.count() > 0:
        # Window pour moyennes mobiles
        window_spec = Window.partitionBy("device_id").orderBy("silver_timestamp").rowsBetween(-4, 0)
        
        gold_df = df.select(
            col("device_id"),
            col("aws_timestamp"),
            col("silver_timestamp"),
            col("acceleration_magnitude"),
            col("gyro_magnitude"),
            col("temperature"),
            col("activity_level"),
            col("temperature_status"),
            col("movement_type"),
            
            # Moyennes mobiles
            avg("acceleration_magnitude").over(window_spec).alias("avg_acceleration_5min"),
            avg("gyro_magnitude").over(window_spec).alias("avg_gyro_5min"),
            avg("temperature").over(window_spec).alias("avg_temperature_5min"),
            
            # Score de santé composite
            (
                when(col("temperature") > 37.5, 20)
                .when(col("temperature") < 35.0, 20)
                .otherwise(100) +
                
                when(col("acceleration_magnitude") > 20.0, -30)
                .when(col("acceleration_magnitude") < 1.0, -20)
                .otherwise(0)
            ).alias("health_score"),
            
            # Business KPIs
            when(col("movement_type") == "potential_fall", 1).otherwise(0).alias("fall_alert_flag"),
            when(col("temperature_status") != "normal", 1).otherwise(0).alias("temp_alert_flag"),
            when(col("activity_level") == "high_activity", 1).otherwise(0).alias("high_activity_flag"),
            
            current_timestamp().alias("gold_timestamp")
        ).withColumn("year", lit(2025)
        ).withColumn("month", lit(9)
        ).withColumn("day", lit(19)
        ).withColumn("hour", hour(current_timestamp()))
        
        print(f"DONNEES GOLD TRANSFORMEES: {gold_df.count()}")
        
        # Écriture en gold
        gold_output = "s3://kidjamo-dev-datalake-e75d5213/gold/mpu_christian_analytics/"
        
        gold_df.coalesce(1).write.mode("overwrite").partitionBy("year", "month", "day", "hour").json(gold_output)
        
        print(f"SUCCES: {gold_df.count()} enregistrements écrits en gold")
        
        # Créer résumé quotidien
        daily_summary = gold_df.groupBy("device_id").agg(
            count("*").alias("total_measurements"),
            avg("acceleration_magnitude").alias("avg_daily_acceleration"),
            max("acceleration_magnitude").alias("max_daily_acceleration"),
            avg("temperature").alias("avg_daily_temperature"),
            sum("fall_alert_flag").alias("daily_fall_alerts"),
            sum("temp_alert_flag").alias("daily_temp_alerts"),
            avg("health_score").alias("avg_daily_health_score")
        ).withColumn("summary_date", current_date()
        ).withColumn("summary_timestamp", current_timestamp())
        
        summary_output = "s3://kidjamo-dev-datalake-e75d5213/gold/mpu_christian_daily_summary/"
        
        daily_summary.coalesce(1).write.mode("overwrite").json(summary_output)
        
        print(f"RESUME QUOTIDIEN CREE: {daily_summary.count()} entrées")
    else:
        raise Exception("Aucune donnée silver trouvée")

except Exception as e:
    print(f"ERREUR: {str(e)}")
    raise e

finally:
    job.commit()
    print("JOB SILVER-TO-GOLD TERMINE")