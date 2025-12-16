-- Modèle intermédiaire : agrégations horaires des mesures
-- Calcule les moyennes, min, max par heure pour chaque patient

{{ config(
    materialized='table',
    tags=['intermediate', 'hourly', 'medical'],
    indexes=[
      {'columns': ['patient_id', 'hour_timestamp'], 'type': 'btree'},
    ]
) }}

WITH hourly_aggregates AS (
    SELECT
        patient_id,
        device_id,
        DATE_TRUNC('hour', tz_timestamp) as hour_timestamp,

        -- Statistiques par heure
        COUNT(*) as measurement_count,
        COUNT(CASE WHEN quality_category = 'good' THEN 1 END) as good_quality_count,

        -- Fréquence cardiaque
        AVG(freq_card_validated) as avg_heart_rate,
        MIN(freq_card_validated) as min_heart_rate,
        MAX(freq_card_validated) as max_heart_rate,
        STDDEV(freq_card_validated) as stddev_heart_rate,

        -- SpO2
        AVG(spo2_validated) as avg_spo2,
        MIN(spo2_validated) as min_spo2,
        MAX(spo2_validated) as max_spo2,

        -- Température corporelle
        AVG(temp_corp_validated) as avg_temp_corp,
        MIN(temp_corp_validated) as min_temp_corp,
        MAX(temp_corp_validated) as max_temp_corp,

        -- Fréquence respiratoire
        AVG(freq_resp_validated) as avg_resp_rate,
        MIN(freq_resp_validated) as min_resp_rate,
        MAX(freq_resp_validated) as max_resp_rate,

        -- Hydratation et activité
        AVG(pct_hydratation) as avg_hydration,
        AVG(activity) as avg_activity,
        AVG(heat_index) as avg_heat_index,

        -- Indicateurs de qualité
        ROUND(
            COUNT(CASE WHEN quality_category = 'good' THEN 1 END) * 100.0 / COUNT(*),
            2
        ) as quality_percentage,

        -- Détection d'anomalies (valeurs en dehors de 2 écarts-types)
        COUNT(CASE
            WHEN freq_card_validated > AVG(freq_card_validated) + 2 * STDDEV(freq_card_validated)
            OR freq_card_validated < AVG(freq_card_validated) - 2 * STDDEV(freq_card_validated)
            THEN 1
        END) as heart_rate_anomalies

    FROM {{ ref('stg_measurements') }}
    WHERE tz_timestamp >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY patient_id, device_id, DATE_TRUNC('hour', tz_timestamp)
)

SELECT * FROM hourly_aggregates
