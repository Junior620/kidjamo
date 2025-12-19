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

print("JOB RAW-TO-BRONZE SIMPLE POUR MPU CHRISTIAN")

try:
    # Lire les donnees MPU specifiques
    input_pattern = "s3://kidjamo-dev-datalake-e75d5213/raw/iot-measurements/year=2025/month=09/day=*/hour=*/mpu_christian_*.json"

    df = spark.read.json(input_pattern)

    print(f"Lignes lues: {df.count()}")

    # Filtrer et transformer
    mpu_df = df.filter(col("device_id") == "MPU_Christian_8266MOD")

    print(f"Lignes MPU Christian: {mpu_df.count()}")

    if mpu_df.count() > 0:
        bronze_df = mpu_df.select(
            col("device_id"),
            col("accel_x"),
            col("accel_y"),
            col("accel_z"),
            col("gyro_x"),
            col("gyro_y"),
            col("gyro_z"),
            col("temp").alias("temperature"),
            col("aws_timestamp"),
            current_timestamp().alias("bronze_processing_timestamp")
        ).withColumn("year", lit(2025)
        ).withColumn("month", lit(9)
        ).withColumn("day", lit(18))

        # Ecriture
        bronze_df.coalesce(1).write.mode("overwrite").partitionBy("year", "month", "day").json("s3://kidjamo-dev-datalake-e75d5213/bronze/mpu_christian/")

        print(f"Enregistrements ecrits: {bronze_df.count()}")
    else:
        print("Aucune donnee MPU Christian")

except Exception as e:
    print(f"ERREUR: {str(e)}")
    raise e

finally:
    job.commit()
    print("Job simple termine")
