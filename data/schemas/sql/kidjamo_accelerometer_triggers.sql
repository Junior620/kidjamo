-- TRIGGERS AUTOMATIQUES POUR TRAITEMENT ACCÉLÉROMÈTRE
-- À ajouter après l'extension du schéma

-- =====================================================
-- TRIGGER AUTOMATIQUE POUR ANALYSE D'ACTIVITÉ
-- =====================================================

-- Fonction trigger pour traitement automatique des données d'accéléromètre
CREATE OR REPLACE FUNCTION process_accelerometer_measurement()
RETURNS TRIGGER AS $$
DECLARE
    analysis_id UUID;
BEGIN
    -- Traiter seulement si on a des données d'accéléromètre
    IF NEW.accel_x IS NOT NULL AND NEW.accel_y IS NOT NULL AND NEW.accel_z IS NOT NULL THEN

        -- Calculer la magnitude si pas déjà fait
        IF NEW.accel_magnitude IS NULL THEN
            NEW.accel_magnitude := SQRT(NEW.accel_x^2 + NEW.accel_y^2 + NEW.accel_z^2);
        END IF;

        -- Classifier l'activité si pas déjà fait
        IF NEW.activity_classification IS NULL THEN
            NEW.activity_classification := CASE
                WHEN NEW.accel_magnitude >= 15.0 THEN 'risque_chute'
                WHEN NEW.accel_magnitude >= 4.0 THEN 'activite_intense'
                WHEN NEW.accel_magnitude >= 1.5 THEN 'mouvement_leger'
                ELSE 'repos'
            END;

            NEW.activity_confidence := CASE
                WHEN NEW.accel_magnitude >= 15.0 OR NEW.accel_magnitude <= 1.5 THEN 0.9
                WHEN NEW.accel_magnitude >= 4.0 THEN 0.8
                ELSE 0.7
            END;
        END IF;

        -- Créer l'analyse détaillée en arrière-plan (après INSERT)
        IF TG_OP = 'INSERT' THEN
            PERFORM pg_notify(
                'accelerometer_analysis_needed',
                json_build_object(
                    'measurement_id', NEW.measurement_id,
                    'patient_id', NEW.patient_id,
                    'device_id', NEW.device_id,
                    'accel_x', NEW.accel_x,
                    'accel_y', NEW.accel_y,
                    'accel_z', NEW.accel_z,
                    'recorded_at', NEW.recorded_at
                )::text
            );
        END IF;

    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Appliquer le trigger sur les mesures
CREATE TRIGGER accelerometer_processing_trigger
    BEFORE INSERT OR UPDATE ON measurements
    FOR EACH ROW
    EXECUTE FUNCTION process_accelerometer_measurement();

-- =====================================================
-- TRIGGER POUR CRÉATION AUTOMATIQUE D'ALERTES CRITIQUES
-- =====================================================

-- Fonction pour alertes automatiques basées sur l'activité
CREATE OR REPLACE FUNCTION create_activity_alerts()
RETURNS TRIGGER AS $$
BEGIN
    -- Alerte critique pour risque de chute
    IF NEW.activity_classification = 'risque_chute' THEN
        INSERT INTO alerts (
            patient_id, alert_type, severity, title, message,
            vitals_snapshot, trigger_conditions, suggested_actions,
            ack_deadline, created_at
        ) VALUES (
            NEW.patient_id,
            'fall_risk_detected',
            'critical',
            '🚨 RISQUE DE CHUTE DÉTECTÉ',
            'Mouvement brusque détecté - Magnitude: ' || NEW.accel_magnitude::TEXT || ' m/s²',
            jsonb_build_object(
                'measurement_id', NEW.measurement_id,
                'magnitude', NEW.accel_magnitude,
                'accel_x', NEW.accel_x,
                'accel_y', NEW.accel_y,
                'accel_z', NEW.accel_z,
                'confidence', NEW.activity_confidence,
                'recorded_at', NEW.recorded_at
            ),
            ARRAY['magnitude_' || NEW.accel_magnitude::TEXT || '_exceeds_15'],
            ARRAY[
                'Vérifier immédiatement l''état du patient',
                'Contacter les services d''urgence si nécessaire',
                'Examiner les circonstances de la chute potentielle'
            ],
            now() + INTERVAL '5 minutes', -- Deadline critique
            NEW.recorded_at
        );

        -- Notification système urgente
        PERFORM pg_notify(
            'critical_alert',
            json_build_object(
                'type', 'fall_risk',
                'patient_id', NEW.patient_id,
                'magnitude', NEW.accel_magnitude,
                'timestamp', NEW.recorded_at
            )::text
        );
    END IF;

    -- Alerte pour activité intense prolongée
    IF NEW.activity_classification = 'activite_intense' THEN
        -- Vérifier s'il y a eu beaucoup d'activité intense récemment
        IF (
            SELECT COUNT(*)
            FROM measurements
            WHERE patient_id = NEW.patient_id
              AND recorded_at >= now() - INTERVAL '30 minutes'
              AND activity_classification = 'activite_intense'
        ) >= 5 THEN

            INSERT INTO alerts (
                patient_id, alert_type, severity, title, message,
                vitals_snapshot, trigger_conditions,
                created_at
            ) VALUES (
                NEW.patient_id,
                'intense_activity_prolonged',
                'warn',
                '⚠️ Activité Intense Prolongée',
                'Activité intense détectée pendant 30+ minutes',
                jsonb_build_object(
                    'recent_measurements', 5,
                    'duration_minutes', 30,
                    'current_magnitude', NEW.accel_magnitude
                ),
                ARRAY['intense_activity_count_5_in_30min'],
                NEW.recorded_at
            );
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour alertes automatiques
CREATE TRIGGER activity_alerts_trigger
    AFTER INSERT ON measurements
    FOR EACH ROW
    WHEN (NEW.activity_classification IS NOT NULL)
    EXECUTE FUNCTION create_activity_alerts();

-- =====================================================
-- FONCTION POUR TRAITEMENT BATCH DES ANALYSES
-- =====================================================

-- Fonction pour traiter les analyses en attente (appelée périodiquement)
CREATE OR REPLACE FUNCTION process_pending_accelerometer_analyses()
RETURNS INTEGER AS $$
DECLARE
    notification_record RECORD;
    analysis_count INTEGER := 0;
    measurement_data JSONB;
BEGIN
    -- Écouter les notifications en attente
    FOR notification_record IN
        SELECT payload FROM pg_stat_activity
        WHERE state = 'idle' AND query LIKE '%accelerometer_analysis_needed%'
        LIMIT 100
    LOOP
        BEGIN
            measurement_data := notification_record.payload::JSONB;

            -- Créer l'analyse détaillée
            PERFORM insert_activity_analysis(
                (measurement_data->>'patient_id')::UUID,
                (measurement_data->>'measurement_id')::BIGINT,
                (measurement_data->>'device_id')::UUID,
                (measurement_data->>'accel_x')::NUMERIC,
                (measurement_data->>'accel_y')::NUMERIC,
                (measurement_data->>'accel_z')::NUMERIC,
                (measurement_data->>'recorded_at')::TIMESTAMPTZ
            );

            analysis_count := analysis_count + 1;

        EXCEPTION WHEN OTHERS THEN
            -- Ignorer les erreurs et continuer
            CONTINUE;
        END;
    END LOOP;

    RETURN analysis_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VUES POUR DASHBOARD ET API
-- =====================================================

-- Vue optimisée pour l'API mobile (données légères)
CREATE OR REPLACE VIEW v_mobile_activity_status AS
SELECT
    p.patient_id,
    u.first_name,

    -- Activité actuelle
    m.activity_classification as current_activity,
    CASE m.activity_classification
        WHEN 'repos' THEN '😴'
        WHEN 'mouvement_leger' THEN '🚶'
        WHEN 'activite_intense' THEN '🏃'
        WHEN 'risque_chute' THEN '⚠️'
        ELSE '❓'
    END as activity_emoji,

    m.accel_magnitude as magnitude,
    m.activity_confidence as confidence,
    m.recorded_at as last_update,

    -- Résumé journalier
    (
        SELECT COUNT(*)
        FROM measurements m2
        WHERE m2.patient_id = p.patient_id
          AND DATE(m2.recorded_at) = CURRENT_DATE
          AND m2.activity_classification IS NOT NULL
    ) as measurements_today,

    -- Alertes actives
    (
        SELECT COUNT(*)
        FROM alerts a
        WHERE a.patient_id = p.patient_id
          AND a.resolved_at IS NULL
          AND a.alert_type LIKE '%activity%'
    ) as active_activity_alerts

FROM patients p
JOIN users u ON u.user_id = p.user_id
LEFT JOIN LATERAL (
    SELECT * FROM measurements m
    WHERE m.patient_id = p.patient_id
      AND m.activity_classification IS NOT NULL
    ORDER BY m.recorded_at DESC
    LIMIT 1
) m ON true
WHERE u.is_active = true;

-- Vue pour dashboard médical (données complètes)
CREATE OR REPLACE VIEW v_medical_dashboard_activity AS
SELECT
    p.patient_id,
    p.genotype,
    u.first_name || ' ' || u.last_name as patient_name,

    -- Activité actuelle avec détails
    m.activity_classification,
    m.accel_magnitude,
    m.activity_confidence,
    m.accel_x, m.accel_y, m.accel_z,
    m.recorded_at as last_measurement,

    -- Statistiques des 24 dernières heures
    stats.total_measurements,
    stats.avg_magnitude,
    stats.max_magnitude,
    stats.repos_percent,
    stats.mouvement_leger_percent,
    stats.activite_intense_percent,
    stats.fall_risk_count,

    -- Tendance (évolution magnitude moyenne sur 3 périodes de 8h)
    CASE
        WHEN stats.trend_slope > 0.5 THEN 'increasing'
        WHEN stats.trend_slope < -0.5 THEN 'decreasing'
        ELSE 'stable'
    END as activity_trend,

    -- Alertes non résolues
    (
        SELECT COUNT(*)
        FROM alerts a
        WHERE a.patient_id = p.patient_id
          AND a.resolved_at IS NULL
    ) as unresolved_alerts

FROM patients p
JOIN users u ON u.user_id = p.user_id
LEFT JOIN LATERAL (
    SELECT * FROM measurements m
    WHERE m.patient_id = p.patient_id
      AND m.activity_classification IS NOT NULL
    ORDER BY m.recorded_at DESC
    LIMIT 1
) m ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as total_measurements,
        AVG(accel_magnitude) as avg_magnitude,
        MAX(accel_magnitude) as max_magnitude,
        ROUND(COUNT(*) FILTER (WHERE activity_classification = 'repos') * 100.0 / COUNT(*), 1) as repos_percent,
        ROUND(COUNT(*) FILTER (WHERE activity_classification = 'mouvement_leger') * 100.0 / COUNT(*), 1) as mouvement_leger_percent,
        ROUND(COUNT(*) FILTER (WHERE activity_classification = 'activite_intense') * 100.0 / COUNT(*), 1) as activite_intense_percent,
        COUNT(*) FILTER (WHERE activity_classification = 'risque_chute') as fall_risk_count,
        -- Calcul simple de tendance
        (AVG(CASE WHEN recorded_at >= now() - INTERVAL '8 hours' THEN accel_magnitude END) -
         AVG(CASE WHEN recorded_at BETWEEN now() - INTERVAL '16 hours' AND now() - INTERVAL '8 hours' THEN accel_magnitude END)) as trend_slope
    FROM measurements
    WHERE patient_id = p.patient_id
      AND recorded_at >= now() - INTERVAL '24 hours'
      AND activity_classification IS NOT NULL
) stats ON true;
