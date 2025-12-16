@echo off
echo 🚀 Démarrage de l'API IoT Kidjamo sur localhost:5000
echo.

cd /d "D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local"

echo Activation de l'environnement virtuel...
call .\venv\Scripts\activate.bat

echo Démarrage de l'API IoT...
python api\iot_ingestion_api.py

pause
