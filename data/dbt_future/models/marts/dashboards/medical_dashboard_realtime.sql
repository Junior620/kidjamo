-- Modèle final : Dashboard médical en temps réel
-- Vue consolidée pour les équipes médicales

{{ config(
    materialized='table',
    tags=['marts', 'medical', 'dashboard', 'realtime'],
    indexes=[
      {'columns': ['patient_id', 'last_measurement_time'], 'type': 'btree'},
      {'columns': ['risk_level'], 'type': 'btree'}
    ]
) }}

WITH patient_current_status AS (
    SELECT
        p.patient_id,
        p.first_name,
        p.last_name,
        p.age_years,
        p.age_group,
        p.genotype,
        p.risk_category,
        p.city,
        p.country,

        -- Dernières mesures (dernière heure)
        h.hour_timestamp as last_measurement_time,
        h.measurement_count as recent_measurements,
        h.quality_percentage,

        -- Valeurs vitales actuelles
        h.avg_heart_rate as current_heart_rate,
        h.avg_spo2 as current_spo2,
        h.avg_temp_corp as current_temperature,
        h.avg_resp_rate as current_resp_rate,
        h.avg_hydration as current_hydration,
        h.avg_activity as current_activity,

        -- Tendances (comparaison avec les 24h précédentes)
        LAG(h.avg_heart_rate, 24) OVER (
            PARTITION BY p.patient_id
            ORDER BY h.hour_timestamp
        ) as heart_rate_24h_ago,

        LAG(h.avg_spo2, 24) OVER (
            PARTITION BY p.patient_id
            ORDER BY h.hour_timestamp
        ) as spo2_24h_ago,

        -- Alertes critiques
        CASE
            WHEN h.avg_spo2 < {{ var('critical_spo2_threshold') }} THEN 'CRITICAL_SPO2'
            WHEN h.avg_heart_rate < {{ var('critical_heart_rate_min') }}
                 OR h.avg_heart_rate > {{ var('critical_heart_rate_max') }} THEN 'CRITICAL_HR'
            WHEN h.avg_temp_corp > {{ var('fever_threshold') }} THEN 'FEVER'
            WHEN h.quality_percentage < 50 THEN 'POOR_DATA_QUALITY'
            ELSE 'STABLE'
        END as alert_status,

        -- Score de risque global (0-100)
        LEAST(100, GREATEST(0,
            CASE p.risk_category
                WHEN 'high_risk' THEN 50
                WHEN 'medium_risk' THEN 30
                WHEN 'low_risk' THEN 10
                ELSE 20
            END +
            CASE
                WHEN h.avg_spo2 < 95 THEN 20
                WHEN h.avg_spo2 < 90 THEN 40
                ELSE 0
            END +
            CASE
                WHEN h.avg_temp_corp > 38.5 THEN 15
                WHEN h.avg_temp_corp > 37.8 THEN 10
                ELSE 0
            END +
            CASE
                WHEN h.quality_percentage < 70 THEN 10
                ELSE 0
            END
        )) as risk_score,

        -- Classification finale du niveau de risque
        CASE
            WHEN LEAST(100, GREATEST(0,
                CASE p.risk_category
                    WHEN 'high_risk' THEN 50
                    WHEN 'medium_risk' THEN 30
                    WHEN 'low_risk' THEN 10
                    ELSE 20
                END +
                CASE
                    WHEN h.avg_spo2 < 95 THEN 20
                    WHEN h.avg_spo2 < 90 THEN 40
                    ELSE 0
                END +
                CASE
                    WHEN h.avg_temp_corp > 38.5 THEN 15
                    WHEN h.avg_temp_corp > 37.8 THEN 10
                    ELSE 0
                END +
                CASE
                    WHEN h.quality_percentage < 70 THEN 10
                    ELSE 0
                END
            )) >= 70 THEN 'HIGH'
            WHEN LEAST(100, GREATEST(0,
                CASE p.risk_category
                    WHEN 'high_risk' THEN 50
                    WHEN 'medium_risk' THEN 30
                    WHEN 'low_risk' THEN 10
                    ELSE 20
                END +
                CASE
                    WHEN h.avg_spo2 < 95 THEN 20
                    WHEN h.avg_spo2 < 90 THEN 40
                    ELSE 0
                END +
                CASE
                    WHEN h.avg_temp_corp > 38.5 THEN 15
                    WHEN h.avg_temp_corp > 37.8 THEN 10
                    ELSE 0
                END +
                CASE
                    WHEN h.quality_percentage < 70 THEN 10
                    ELSE 0
                END
            )) >= 40 THEN 'MEDIUM'
            ELSE 'LOW'
        END as risk_level

    FROM {{ ref('stg_patients') }} p
    LEFT JOIN {{ ref('int_measurements_hourly') }} h
        ON p.patient_id = h.patient_id
    WHERE h.hour_timestamp >= CURRENT_TIMESTAMP - INTERVAL '2 hours'
),

-- Ajout des statistiques de contexte
dashboard_final AS (
    SELECT
        *,
        -- Calcul des tendances
        CASE
            WHEN current_heart_rate > heart_rate_24h_ago + 10 THEN 'INCREASING'
            WHEN current_heart_rate < heart_rate_24h_ago - 10 THEN 'DECREASING'
            ELSE 'STABLE'
        END as heart_rate_trend,

        CASE
            WHEN current_spo2 < spo2_24h_ago - 2 THEN 'DECREASING'
            WHEN current_spo2 > spo2_24h_ago + 2 THEN 'INCREASING'
            ELSE 'STABLE'
        END as spo2_trend,

        -- Dernière connexion du dispositif
        CASE
            WHEN last_measurement_time < CURRENT_TIMESTAMP - INTERVAL '2 hours' THEN 'DISCONNECTED'
            WHEN last_measurement_time < CURRENT_TIMESTAMP - INTERVAL '30 minutes' THEN 'INTERMITTENT'
            ELSE 'CONNECTED'
        END as device_status,

        CURRENT_TIMESTAMP as dashboard_updated_at

    FROM patient_current_status
)

SELECT * FROM dashboard_final
