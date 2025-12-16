-- Modèle de staging pour les mesures IoT brutes
-- Nettoie et standardise les données des capteurs

{{ config(
    materialized='view',
    tags=['staging', 'iot', 'medical']
) }}

WITH raw_measurements AS (
    SELECT
        measure_id,
        patient_id,
        tz_timestamp,
        device_id,
        freq_card,
        freq_resp,
        spo2_pct,
        temp_corp,
        temp_abiante,
        pct_hydratation,
        activity,
        heat_index,
        quality_flag,
        -- Ajout de métadonnées de traçabilité
        current_timestamp as dbt_created_at,
        '{{ invocation_id }}' as dbt_run_id
    FROM {{ source('public', 'measurements') }}
    WHERE tz_timestamp >= current_date - interval '30 days'  -- Fenêtre glissante
),

cleaned_measurements AS (
    SELECT
        *,
        -- Validation des plages physiologiques
        CASE
            WHEN freq_card BETWEEN 40 AND 200 THEN freq_card
            ELSE NULL
        END as freq_card_validated,

        CASE
            WHEN freq_resp BETWEEN 8 AND 60 THEN freq_resp
            ELSE NULL
        END as freq_resp_validated,

        CASE
            WHEN spo2_pct BETWEEN 70 AND 100 THEN spo2_pct
            ELSE NULL
        END as spo2_validated,

        CASE
            WHEN temp_corp BETWEEN 32 AND 45 THEN temp_corp
            ELSE NULL
        END as temp_corp_validated,

        -- Classification de la qualité
        CASE
            WHEN quality_flag IN ('ok', 'calibrating') THEN 'good'
            WHEN quality_flag IN ('motion', 'low_signal', 'noise') THEN 'warning'
            WHEN quality_flag IN ('sensor_drop', 'signal_loss', 'device_error') THEN 'poor'
            ELSE 'unknown'
        END as quality_category

    FROM raw_measurements
)

SELECT * FROM cleaned_measurements
