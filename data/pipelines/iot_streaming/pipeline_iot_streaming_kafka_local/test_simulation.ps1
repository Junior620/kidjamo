# Guide de simulation Pipeline IoT Kidjamo
# ==========================================

# ÉTAPE 1: Ouvrir les interfaces de monitoring
echo "🌐 Ouvrir dans votre navigateur:"
echo "   • Kafka UI: http://localhost:8090"
echo "   • API IoT Health: http://localhost:5000/health"
echo ""

# ÉTAPE 2: Tester l'API IoT avec des données simulées
echo "📡 Test d'envoi de données IoT..."

# Données de test pour un patient avec drépanocytose
$testData = @{
    patient_id = "123e4567-e89b-12d3-a456-426614174000"
    device_id = "device_001"
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
    measurements = @{
        heart_rate = 85
        respiratory_rate = 18
        spo2 = 96.5
        body_temperature = 37.2
        ambient_temperature = 23.5
        hydration_level = 82.3
        activity_level = 3
        heat_index = 25.8
    }
    location = @{
        latitude = 14.6928
        longitude = -17.4467
    }
} | ConvertTo-Json -Depth 3

# Envoyer les données via l'API
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/api/iot/data" -Method POST -Body $testData -ContentType "application/json"
    echo "✅ Données envoyées avec succès!"
    echo $response
} catch {
    echo "❌ Erreur lors de l'envoi: $($_.Exception.Message)"
}

echo ""
echo "🔍 ÉTAPES DE VÉRIFICATION:"
echo "1. Kafka UI (http://localhost:8090) - Vérifier les topics 'iot-raw-data'"
echo "2. Dossier data_lake/raw - Voir les fichiers JSON générés"
echo "3. Dossier data_lake/bronze - Données nettoyées"
echo "4. Logs du simulateur - Activité en temps réel"
echo ""

