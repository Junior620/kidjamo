-- Tests de qualité pour les mesures IoT
-- Valide l'intégrité des données médicales critiques

-- Test 1: Vérifier que les valeurs SpO2 sont dans la plage physiologique
SELECT patient_id, tz_timestamp, spo2_pct
FROM {{ ref('stg_measurements') }}
WHERE spo2_validated IS NOT NULL
  AND (spo2_validated < 70 OR spo2_validated > 100)
