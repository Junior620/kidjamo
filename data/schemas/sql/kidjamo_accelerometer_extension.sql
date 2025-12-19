-- EXTENSION DU SCHÉMA KIDJAMO POUR DONNÉES D'ACCÉLÉROMÈTRE
-- À ajouter à votre kidjamo_main_database_v2.sql

-- =====================================================
-- EXTENSION TABLE MEASUREMENTS POUR IOT ACCÉLÉROMÈTRE
-- =====================================================

-- Ajouter les colonnes d'accéléromètre à la table measurements existante
ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS accel_x NUMERIC(8,6) CHECK (accel_x >= -50 AND accel_x <= 50),
ADD COLUMN IF NOT EXISTS accel_y NUMERIC(8,6) CHECK (accel_y >= -50 AND accel_y <= 50),
ADD COLUMN IF NOT EXISTS accel_z NUMERIC(8,6) CHECK (accel_z >= -50 AND accel_z <= 50),
ADD COLUMN IF NOT EXISTS accel_magnitude NUMERIC(8,3) CHECK (accel_magnitude >= 0 AND accel_magnitude <= 100),
ADD COLUMN IF NOT EXISTS activity_classification TEXT CHECK (activity_classification IN ('repos', 'mouvement_leger', 'activite_intense', 'risque_chute')),
ADD COLUMN IF NOT EXISTS activity_confidence NUMERIC(3,2) CHECK (activity_confidence >= 0 AND activity_confidence <= 1),
ADD COLUMN IF NOT EXISTS gyro_x NUMERIC(8,6),
ADD COLUMN IF NOT EXISTS gyro_y NUMERIC(8,6),
ADD COLUMN IF NOT EXISTS gyro_z NUMERIC(8,6);

-- Index pour les requêtes d'activité
CREATE INDEX IF NOT EXISTS idx_measurements_activity
ON measurements(patient_id, activity_classification, recorded_at DESC)
WHERE activity_classification IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_measurements_fall_risk
ON measurements(patient_id, recorded_at DESC)
WHERE activity_classification = 'risque_chute';

CREATE INDEX IF NOT EXISTS idx_measurements_accel_magnitude
ON measurements(accel_magnitude DESC, recorded_at DESC)
WHERE accel_magnitude > 10.0;

-- =====================================================
-- TABLE SPÉCIALISÉE POUR ANALYSE D'ACTIVITÉ
-- =====================================================

CREATE TABLE IF NOT EXISTS public.activity_analysis (
    analysis_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    measurement_id BIGINT REFERENCES measurements(measurement_id) ON DELETE CASCADE,
    device_id UUID NOT NULL,

    -- Données brutes accéléromètre
    accel_x NUMERIC(8,6) NOT NULL,
    accel_y NUMERIC(8,6) NOT NULL,
    accel_z NUMERIC(8,6) NOT NULL,
    magnitude NUMERIC(8,3) NOT NULL,

    -- Classification d'activité
    activity_level TEXT NOT NULL CHECK (activity_level IN ('repos', 'mouvement_leger', 'activite_intense', 'risque_chute')),
    confidence_score NUMERIC(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Contexte temporel
    time_of_day TEXT CHECK (time_of_day IN ('morning', 'afternoon', 'evening', 'night')),
    day_of_week SMALLINT CHECK (day_of_week >= 1 AND day_of_week <= 7),
    is_weekend BOOLEAN DEFAULT false,

    -- Patterns détectés
    movement_pattern TEXT,
    anomaly_detected BOOLEAN DEFAULT false,
    fall_risk_indicators TEXT[],

    -- Métriques calculées
    movement_variability NUMERIC(6,3),
    stability_score NUMERIC(3,2),
    energy_expenditure_estimate NUMERIC(6,2),

    -- Métadonnées
    analysis_version TEXT DEFAULT 'v1.0',
    processed_at TIMESTAMPTZ DEFAULT now(),
    recorded_at TIMESTAMPTZ NOT NULL,

    UNIQUE(patient_id, measurement_id)
);

-- Index pour activity_analysis
CREATE INDEX idx_activity_analysis_patient_time ON activity_analysis(patient_id, recorded_at DESC);
CREATE INDEX idx_activity_analysis_level ON activity_analysis(activity_level, recorded_at DESC);
CREATE INDEX idx_activity_analysis_anomaly ON activity_analysis(patient_id, anomaly_detected, recorded_at DESC) WHERE anomaly_detected = true;
CREATE INDEX idx_activity_analysis_fall_risk ON activity_analysis(patient_id, recorded_at DESC) WHERE activity_level = 'risque_chute';

-- =====================================================
-- VUES POUR ANALYSE D'ACTIVITÉ
-- =====================================================

-- Vue des activités par patient avec contexte médical
CREATE OR REPLACE VIEW v_patient_activity_summary AS
SELECT
    p.patient_id,
    p.genotype,
    EXTRACT(YEAR FROM AGE(p.birth_date)) as age_years,

    -- Activité actuelle
    a_current.activity_level as current_activity,
    a_current.magnitude as current_magnitude,
    a_current.confidence_score as current_confidence,
    a_current.recorded_at as last_activity_time,

    -- Statistiques journalières
    COUNT(a_today.*) as measurements_today,
    AVG(a_today.magnitude) as avg_magnitude_today,
    MAX(a_today.magnitude) as max_magnitude_today,

    -- Répartition des activités (dernières 24h)
    COUNT(*) FILTER (WHERE a_today.activity_level = 'repos') as repos_count,
    COUNT(*) FILTER (WHERE a_today.activity_level = 'mouvement_leger') as mouvement_leger_count,
    COUNT(*) FILTER (WHERE a_today.activity_level = 'activite_intense') as activite_intense_count,
    COUNT(*) FILTER (WHERE a_today.activity_level = 'risque_chute') as risque_chute_count,

    -- Indicateurs de risque
    MAX(a_today.magnitude) > 15.0 as fall_risk_detected_today,
    COUNT(*) FILTER (WHERE a_today.anomaly_detected = true) as anomalies_today

FROM patients p
LEFT JOIN LATERAL (
    SELECT * FROM activity_analysis aa
    WHERE aa.patient_id = p.patient_id
    ORDER BY aa.recorded_at DESC
    LIMIT 1
) a_current ON true
LEFT JOIN activity_analysis a_today ON a_today.patient_id = p.patient_id
    AND a_today.recorded_at >= CURRENT_DATE
GROUP BY p.patient_id, p.genotype, p.birth_date,
         a_current.activity_level, a_current.magnitude,
         a_current.confidence_score, a_current.recorded_at;

-- Vue des alertes d'activité
CREATE OR REPLACE VIEW v_activity_alerts AS
SELECT
    aa.patient_id,
    p.genotype,
    u.first_name || ' ' || u.last_name as patient_name,
    aa.activity_level,
    aa.magnitude,
    aa.fall_risk_indicators,
    aa.recorded_at,

    -- Sévérité calculée
    CASE
        WHEN aa.activity_level = 'risque_chute' THEN 'critical'
        WHEN aa.magnitude > 12.0 THEN 'high'
        WHEN aa.anomaly_detected THEN 'medium'
        ELSE 'low'
    END as alert_severity,

    -- Message d'alerte
    CASE
        WHEN aa.activity_level = 'risque_chute' THEN
            'ALERTE CHUTE: Magnitude ' || aa.magnitude::TEXT || ' m/s² détectée'
        WHEN aa.magnitude > 12.0 THEN
            'Activité intense inhabituelle: ' || aa.magnitude::TEXT || ' m/s²'
        WHEN aa.anomaly_detected THEN
            'Anomalie de mouvement détectée'
        ELSE 'Activité normale'
    END as alert_message

FROM activity_analysis aa
JOIN patients p ON p.patient_id = aa.patient_id
JOIN users u ON u.user_id = p.user_id
WHERE aa.recorded_at >= now() - INTERVAL '24 hours'
  AND (aa.activity_level = 'risque_chute' OR aa.magnitude > 10.0 OR aa.anomaly_detected = true)
ORDER BY aa.recorded_at DESC;

-- =====================================================
-- FONCTIONS POUR ANALYSE D'ACTIVITÉ
-- =====================================================

-- Fonction pour classifier l'activité
CREATE OR REPLACE FUNCTION classify_activity(
    accel_x NUMERIC,
    accel_y NUMERIC,
    accel_z NUMERIC
) RETURNS TABLE(
    magnitude NUMERIC,
    activity_level TEXT,
    confidence NUMERIC,
    anomaly_detected BOOLEAN
) AS $$
DECLARE
    calculated_magnitude NUMERIC;
    activity_classification TEXT;
    confidence_score NUMERIC;
    is_anomaly BOOLEAN := false;
BEGIN
    -- Calculer la magnitude
    calculated_magnitude := SQRT(accel_x^2 + accel_y^2 + accel_z^2);

    -- Classifier selon les seuils
    IF calculated_magnitude >= 15.0 THEN
        activity_classification := 'risque_chute';
        confidence_score := 0.9;
        is_anomaly := true;
    ELSIF calculated_magnitude >= 4.0 THEN
        activity_classification := 'activite_intense';
        confidence_score := 0.8;
    ELSIF calculated_magnitude >= 1.5 THEN
        activity_classification := 'mouvement_leger';
        confidence_score := 0.7;
    ELSE
        activity_classification := 'repos';
        confidence_score := 0.8;
    END IF;

    -- Détecter anomalies additionnelles
    IF calculated_magnitude > 25.0 OR calculated_magnitude < 0.1 THEN
        is_anomaly := true;
        confidence_score := confidence_score * 0.5;
    END IF;

    RETURN QUERY SELECT
        calculated_magnitude,
        activity_classification,
        confidence_score,
        is_anomaly;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction pour insérer une analyse d'activité
CREATE OR REPLACE FUNCTION insert_activity_analysis(
    p_patient_id UUID,
    p_measurement_id BIGINT,
    p_device_id UUID,
    p_accel_x NUMERIC,
    p_accel_y NUMERIC,
    p_accel_z NUMERIC,
    p_recorded_at TIMESTAMPTZ DEFAULT now()
) RETURNS UUID AS $$
DECLARE
    analysis_result RECORD;
    analysis_id UUID;
    time_classification TEXT;
    hour_of_day INTEGER;
    day_num INTEGER;
BEGIN
    -- Classifier l'activité
    SELECT * INTO analysis_result
    FROM classify_activity(p_accel_x, p_accel_y, p_accel_z);

    -- Déterminer le contexte temporel
    hour_of_day := EXTRACT(HOUR FROM p_recorded_at);
    day_num := EXTRACT(DOW FROM p_recorded_at);

    time_classification := CASE
        WHEN hour_of_day BETWEEN 6 AND 11 THEN 'morning'
        WHEN hour_of_day BETWEEN 12 AND 17 THEN 'afternoon'
        WHEN hour_of_day BETWEEN 18 AND 21 THEN 'evening'
        ELSE 'night'
    END;

    -- Insérer l'analyse
    INSERT INTO activity_analysis (
        patient_id, measurement_id, device_id,
        accel_x, accel_y, accel_z, magnitude,
        activity_level, confidence_score,
        time_of_day, day_of_week, is_weekend,
        anomaly_detected, recorded_at
    ) VALUES (
        p_patient_id, p_measurement_id, p_device_id,
        p_accel_x, p_accel_y, p_accel_z, analysis_result.magnitude,
        analysis_result.activity_level, analysis_result.confidence,
        time_classification, day_num, (day_num IN (0, 6)),
        analysis_result.anomaly_detected, p_recorded_at
    ) RETURNING analysis_id INTO analysis_id;

    -- Créer une alerte si nécessaire
    IF analysis_result.activity_level = 'risque_chute' OR analysis_result.anomaly_detected THEN
        INSERT INTO alerts (
            patient_id, alert_type, severity, title, message,
            vitals_snapshot, created_at
        ) VALUES (
            p_patient_id,
            'activity_alert',
            CASE WHEN analysis_result.activity_level = 'risque_chute' THEN 'critical' ELSE 'warn' END,
            CASE WHEN analysis_result.activity_level = 'risque_chute' THEN 'Risque de Chute Détecté' ELSE 'Anomalie d''Activité' END,
            'Magnitude: ' || analysis_result.magnitude::TEXT || ' m/s² - Activité: ' || analysis_result.activity_level,
            jsonb_build_object(
                'magnitude', analysis_result.magnitude,
                'activity_level', analysis_result.activity_level,
                'confidence', analysis_result.confidence,
                'accel_x', p_accel_x,
                'accel_y', p_accel_y,
                'accel_z', p_accel_z
            ),
            p_recorded_at
        );
    END IF;

    RETURN analysis_id;
END;
$$ LANGUAGE plpgsql;
