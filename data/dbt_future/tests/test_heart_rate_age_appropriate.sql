-- Tests de qualité pour la fréquence cardiaque
SELECT patient_id, tz_timestamp, freq_card, age_years
FROM {{ ref('stg_measurements') }} m
JOIN {{ ref('stg_patients') }} p ON m.patient_id = p.patient_id
WHERE freq_card_validated IS NOT NULL
  AND (
    -- Nouveau-nés (0-1 an): 100-160 bpm
    (p.age_years < 1 AND (freq_card_validated < 100 OR freq_card_validated > 160))
    OR
    -- Enfants (1-10 ans): 70-120 bpm
    (p.age_years BETWEEN 1 AND 10 AND (freq_card_validated < 70 OR freq_card_validated > 120))
    OR
    -- Adolescents/Adultes (>10 ans): 60-100 bpm
    (p.age_years > 10 AND (freq_card_validated < 60 OR freq_card_validated > 100))
  )

