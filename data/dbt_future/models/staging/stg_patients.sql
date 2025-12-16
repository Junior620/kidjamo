-- Modèle de staging pour les patients
-- Enrichit les données patients avec des informations calculées

{{ config(
    materialized='view',
    tags=['staging', 'patients', 'medical']
) }}

WITH patients_base AS (
    SELECT
        p.patient_id,
        p.user_id,
        p.genotype,
        p.birth_date,
        p.close_contact,
        p.device_id,
        u.first_name,
        u.last_name,
        u.gender,
        u.email,
        u.city,
        u.country,
        u.created_at,
        -- Calcul de l'âge
        EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date)) as age_years,
        EXTRACT(MONTH FROM AGE(CURRENT_DATE, p.birth_date)) as age_months,

        -- Classification par groupe d'âge
        CASE
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date)) < 2 THEN 'infant'
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date)) < 12 THEN 'child'
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date)) < 18 THEN 'adolescent'
            ELSE 'adult'
        END as age_group,

        -- Classification de risque basée sur le génotype
        CASE
            WHEN p.genotype = 'SS' THEN 'high_risk'
            WHEN p.genotype IN ('SC', 'Sβ0') THEN 'medium_risk'
            WHEN p.genotype IN ('AS', 'Sβ+') THEN 'low_risk'
            ELSE 'unknown_risk'
        END as risk_category

    FROM {{ source('public', 'patients') }} p
    LEFT JOIN {{ source('public', 'users') }} u ON p.user_id = u.user_id
    WHERE u.role = 'patient'
)

SELECT * FROM patients_base
