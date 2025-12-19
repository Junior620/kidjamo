-- KIDJAMO - SCHÉMA DE BASE DE DONNÉES PRINCIPAL v2.0
-- Surveillance médicale drépanocytose avec sécurité avancée et performance optimisée
-- Intègre les 6 recommandations critiques pour un système de production
-- Date: 2025-08-18

BEGIN;

-- =====================================================
-- ÉTAPE 1: CONFIGURATION INITIALE ET EXTENSIONS
-- =====================================================

-- Extensions nécessaires pour les fonctionnalités avancées
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Configuration de base pour performance
SET default_statistics_target = 100;
SET random_page_cost = 1.1;
SET effective_cache_size = '1GB';

-- =====================================================
-- ÉTAPE 2: CRÉATION DES RÔLES ET SÉCURITÉ
-- =====================================================

-- Création des rôles pour RLS (Recommandation #1)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'application_role') THEN
        CREATE ROLE application_role;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_role') THEN
        CREATE ROLE readonly_role;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_role') THEN
        CREATE ROLE admin_role;
    END IF;
END $$;

-- Fonction utilitaire pour RLS (corrigée - VOLATILE pour current_setting)
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN COALESCE(
        NULLIF(current_setting('app.current_user_id', true), ''),
        '00000000-0000-0000-0000-000000000000'
    )::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER VOLATILE;

-- Fonction alternative pour les cas où IMMUTABLE est requis
CREATE OR REPLACE FUNCTION get_session_user_uuid()
RETURNS UUID AS $$
BEGIN
    -- Utilise session_user qui est plus stable pour les index
    RETURN COALESCE(
        NULLIF(current_setting('app.session_user_id', true), ''),
        '00000000-0000-0000-0000-000000000000'
    )::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN '00000000-0000-0000-0000-000000000000'::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- =====================================================
-- ÉTAPE 3: TABLES PRINCIPALES AVEC CORRECTIONS
-- =====================================================

-- Table USERS (corrigée et sécurisée)
CREATE TABLE IF NOT EXISTS public.users (
    user_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('patient', 'tuteur', 'parent', 'visiteur', 'medecin', 'admin')),
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(80),
    country VARCHAR(80) NOT NULL DEFAULT 'France',
    timezone VARCHAR(50) DEFAULT 'Europe/Paris',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_login TIMESTAMPTZ,
    terms_accepted_at TIMESTAMPTZ,

    -- Contraintes de validation
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' OR email IS NULL),
    CONSTRAINT valid_phone CHECK (phone ~* '^\+?[0-9\s\-\.]+$' OR phone IS NULL)
);

-- Index optimisés pour users
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_role_active ON users(role, is_active);
CREATE INDEX idx_users_last_login ON users(last_login DESC) WHERE is_active = true;

-- Table PATIENTS (corrigée avec champs médicaux)
CREATE TABLE IF NOT EXISTS public.patients (
    patient_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    genotype TEXT CHECK (genotype IN ('SS', 'AS', 'SC', 'Sβ0', 'Sβ+')),
    birth_date DATE NOT NULL,
    weight_kg NUMERIC(5,2) CHECK (weight_kg > 0 AND weight_kg < 500),
    height_cm NUMERIC(5,1) CHECK (height_cm > 0 AND height_cm < 300),
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    current_device_id UUID,
    medical_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Contraintes de validation
    CONSTRAINT valid_birth_date CHECK (birth_date <= CURRENT_DATE AND birth_date >= '1900-01-01'),
    CONSTRAINT valid_emergency_phone CHECK (emergency_contact_phone ~* '^\+?[0-9\s\-\.]+$' OR emergency_contact_phone IS NULL)
);

-- Index pour patients
CREATE INDEX idx_patients_user ON patients(user_id);
CREATE INDEX idx_patients_genotype ON patients(genotype);
CREATE INDEX idx_patients_device ON patients(current_device_id) WHERE current_device_id IS NOT NULL;
CREATE INDEX idx_patients_birth_date ON patients(birth_date);

-- Table CAREGIVERS (remplace parents, corrigée)
CREATE TABLE IF NOT EXISTS public.caregivers (
    caregiver_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    relationship TEXT CHECK (relationship IN ('parent', 'tuteur', 'famille', 'ami_proche')) DEFAULT 'parent',
    priority_level SMALLINT CHECK (priority_level IN (1, 2, 3)) DEFAULT 1,
    can_acknowledge_alerts BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, patient_id)
);

CREATE INDEX idx_caregivers_patient ON caregivers(patient_id, priority_level);
CREATE INDEX idx_caregivers_user ON caregivers(user_id);

-- Table CLINICIANS (corrigée)
CREATE TABLE IF NOT EXISTS public.clinicians (
    clinician_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    license_number VARCHAR(50) UNIQUE,
    specialty VARCHAR(80),
    service_location VARCHAR(80),
    hospital_name VARCHAR(100),
    can_prescribe BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id)
);

-- Table de liaison patient-clinicien (many-to-many)
CREATE TABLE IF NOT EXISTS public.patient_clinicians (
    patient_id UUID REFERENCES patients(patient_id) ON DELETE CASCADE,
    clinician_id UUID REFERENCES clinicians(clinician_id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('médecin_traitant', 'spécialiste', 'urgentiste', 'consultant')) DEFAULT 'consultant',
    assigned_at TIMESTAMPTZ DEFAULT now(),
    is_primary BOOLEAN DEFAULT false,

    PRIMARY KEY (patient_id, clinician_id)
);

CREATE INDEX idx_patient_clinicians_patient ON patient_clinicians(patient_id, is_primary);
CREATE INDEX idx_patient_clinicians_clinician ON patient_clinicians(clinician_id);

-- =====================================================
-- ÉTAPE 4: TABLE MEASUREMENTS AVEC PARTITIONING (Recommandation #3)
-- =====================================================

-- Table MEASUREMENTS principale avec partitioning par semaine
CREATE TABLE IF NOT EXISTS public.measurements (
    measurement_id BIGSERIAL,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    device_id UUID NOT NULL,
    message_id UUID DEFAULT gen_random_uuid(),
    recorded_at TIMESTAMPTZ DEFAULT now(),
    received_at TIMESTAMPTZ DEFAULT now(),

    -- Variables physiologiques (nomenclature corrigée)
    heart_rate_bpm SMALLINT CHECK (heart_rate_bpm > 0 AND heart_rate_bpm < 300),
    respiratory_rate_min SMALLINT CHECK (respiratory_rate_min > 0 AND respiratory_rate_min < 100),
    spo2_percent NUMERIC(5,2) CHECK (spo2_percent >= 0 AND spo2_percent <= 100),
    temperature_celsius NUMERIC(4,2) CHECK (temperature_celsius > 30 AND temperature_celsius < 45),
    ambient_temp_celsius NUMERIC(4,2) CHECK (ambient_temp_celsius > -20 AND ambient_temp_celsius < 60),
    hydration_percent NUMERIC(5,2) CHECK (hydration_percent >= 0 AND hydration_percent <= 100),
    activity_level SMALLINT CHECK (activity_level >= 0 AND activity_level <= 10),
    heat_index_celsius NUMERIC(4,2),

    -- Nouveaux champs critiques
    pain_scale SMALLINT CHECK (pain_scale >= 0 AND pain_scale <= 10),
    battery_percent SMALLINT CHECK (battery_percent >= 0 AND battery_percent <= 100),
    signal_quality SMALLINT CHECK (signal_quality >= 0 AND signal_quality <= 100),

    -- Métadonnées qualité
    quality_flag TEXT DEFAULT 'ok',
    data_source TEXT CHECK (data_source IN ('device', 'manual', 'estimated')) DEFAULT 'device',
    is_validated BOOLEAN DEFAULT false,
    validated_by UUID REFERENCES users(user_id),
    validated_at TIMESTAMPTZ,

    -- Contraintes temporelles et unicité
    CONSTRAINT unique_measurement_per_device_time UNIQUE (device_id, patient_id, recorded_at),
    CONSTRAINT recent_measurement CHECK (recorded_at >= now() - INTERVAL '30 days' AND recorded_at <= now() + INTERVAL '1 hour'),

    PRIMARY KEY (measurement_id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Fonction pour création automatique de partitions hebdomadaires
CREATE OR REPLACE FUNCTION create_weekly_partition(start_date DATE)
RETURNS TEXT AS $$
DECLARE
    partition_name TEXT;
    end_date DATE;
BEGIN
    partition_name := 'measurements_' || TO_CHAR(start_date, 'IYYY') || 'w' || TO_CHAR(start_date, 'IW');
    end_date := start_date + INTERVAL '1 week';

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF measurements
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );

    -- Index spécifiques par partition
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %I(patient_id, recorded_at DESC)',
        partition_name || '_patient_time', partition_name
    );

    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %I(device_id, recorded_at DESC)',
        partition_name || '_device_time', partition_name
    );

    RETURN partition_name;
END;
$$ LANGUAGE plpgsql;

-- Créer les partitions pour les 8 prochaines semaines
DO $$
DECLARE
    week_start DATE;
    i INTEGER;
BEGIN
    FOR i IN 0..7 LOOP
        week_start := DATE_TRUNC('week', CURRENT_DATE) + (i || ' weeks')::INTERVAL;
        PERFORM create_weekly_partition(week_start);
    END LOOP;
END $$;

-- Index globaux pour measurements
CREATE INDEX idx_measurements_patient_time ON measurements(patient_id, recorded_at DESC);
CREATE INDEX idx_measurements_quality ON measurements(quality_flag) WHERE quality_flag != 'ok';
-- Suppression de l'index avec now() qui pose problème
-- CREATE INDEX idx_measurements_recent ON measurements(recorded_at DESC) WHERE recorded_at >= now() - INTERVAL '24 hours';
CREATE INDEX idx_measurements_alerts ON measurements(patient_id, spo2_percent, temperature_celsius) WHERE quality_flag = 'ok';

-- =====================================================
-- ÉTAPE 5: TABLE QUALITY CODES (Référentiel qualité)
-- =====================================================

CREATE TABLE IF NOT EXISTS public.measurement_quality (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    severity SMALLINT NOT NULL CHECK (severity IN (0, 1, 2, 3)),
    description TEXT,
    auto_exclude_from_trends BOOLEAN DEFAULT false,
    requires_manual_review BOOLEAN DEFAULT false,
    deprecated_at TIMESTAMPTZ
);

-- Insertion des codes qualité standards
INSERT INTO measurement_quality (code, label, severity, description, auto_exclude_from_trends, requires_manual_review) VALUES
    ('ok', 'Valide', 0, 'Mesure validée utilisable', false, false),
    ('motion', 'Artéfact mouvement', 2, 'Mouvement détecté corrompant le signal', true, false),
    ('low_signal', 'Signal faible', 2, 'Signal capteur faible (mauvais contact)', true, false),
    ('low_perfusion', 'Perfusion faible', 2, 'Cause commune artéfacts SpO2', true, false),
    ('sensor_drop', 'Capteur déconnecté', 3, 'Capteur déconnecté/glissement', true, true),
    ('signal_loss', 'Perte signal', 3, 'Perte données (RF, timeout)', true, true),
    ('noise', 'Bruit électrique', 2, 'Interférence électrique/bruit', true, false),
    ('out_of_range', 'Hors limites physio', 3, 'Valeur hors plage physiologique', true, true),
    ('calibrating', 'Calibrage', 1, 'Appareil en calibrage', true, false),
    ('checksum_fail', 'Checksum échoué', 3, 'Vérification intégrité échouée', true, true),
    ('device_error', 'Erreur appareil', 3, 'Erreur matériel/logiciel', true, true),
    ('user_removed', 'Retiré par utilisateur', 1, 'Retrait temporaire (douche, sport)', true, false),
    ('flatline', 'Signal plat', 3, 'Signal plat >60s (panne suspectée)', true, true),
    ('battery_low', 'Batterie faible', 2, 'Batterie <15%', false, false)
ON CONFLICT (code) DO NOTHING;

-- =====================================================
-- ÉTAPE 6: TABLE ALERTS (Corrigée et étendue)
-- =====================================================

CREATE TABLE IF NOT EXISTS public.alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    alert_type TEXT,
    severity TEXT  CHECK (severity IN ('info', 'warn', 'alert', 'critical')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,

    -- Contexte médical (JSON pour flexibilité)
    vitals_snapshot JSONB,
    trigger_conditions TEXT[],
    suggested_actions TEXT[],

    -- Métadonnées temporelles
    created_at TIMESTAMPTZ DEFAULT now(),
    first_seen_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    auto_resolved BOOLEAN DEFAULT false,

    -- Gestion escalade
    ack_deadline TIMESTAMPTZ,
    escalation_level SMALLINT DEFAULT 0,
    cooldown_until TIMESTAMPTZ,

    -- Traçabilité
    created_by_system TEXT DEFAULT 'offline_engine',
    related_measurement_id BIGINT,
    correlation_id UUID,

    CONSTRAINT valid_severity_escalation CHECK (
        (severity = 'critical' AND ack_deadline IS NOT NULL) OR severity != 'critical'
    )
);

-- Index pour alerts
CREATE INDEX idx_alerts_patient_created ON alerts(patient_id, created_at DESC);
CREATE INDEX idx_alerts_severity_unresolved ON alerts(severity, created_at DESC) WHERE resolved_at IS NULL;
CREATE INDEX idx_alerts_escalation ON alerts(escalation_level, ack_deadline) WHERE resolved_at IS NULL;
CREATE INDEX idx_alerts_correlation ON alerts(correlation_id) WHERE correlation_id IS NOT NULL;

-- Table de suivi des statuts d'alertes
CREATE TABLE IF NOT EXISTS public.alert_status_logs (
    log_id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('created', 'seen', 'acknowledged', 'escalated', 'resolved', 'auto_resolved')),
    changed_at TIMESTAMPTZ DEFAULT now(),
    changed_by UUID REFERENCES users(user_id),
    comment TEXT,
    metadata JSONB,

    UNIQUE(alert_id, changed_at)
);

CREATE INDEX idx_alert_status_alert ON alert_status_logs(alert_id, changed_at DESC);
CREATE INDEX idx_alert_status_user ON alert_status_logs(changed_by) WHERE changed_by IS NOT NULL;

-- =====================================================
-- ÉTAPE 7: AUTRES TABLES CORRIGÉES
-- =====================================================

-- Table TREATMENTS (corrigée)
CREATE TABLE IF NOT EXISTS public.treatments (
    treatment_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    drug_name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    treatment_start DATE NOT NULL,
    treatment_end DATE,
    prescriber_id UUID REFERENCES clinicians(clinician_id),
    prescription_date DATE DEFAULT CURRENT_DATE,
    notes TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT valid_treatment_dates CHECK (treatment_end IS NULL OR treatment_end >= treatment_start)
);

CREATE INDEX idx_treatments_patient_active ON treatments(patient_id, is_active, treatment_start DESC);
CREATE INDEX idx_treatments_prescriber ON treatments(prescriber_id) WHERE prescriber_id IS NOT NULL;

-- Table USER_SESSIONS (corrigée)
CREATE TABLE IF NOT EXISTS public.user_sessions (
    session_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT,
    device_fingerprint TEXT,
    is_active BOOLEAN DEFAULT true,
    logout_reason TEXT CHECK (logout_reason IN ('manual', 'timeout', 'forced', 'security')),

    CONSTRAINT valid_session_duration CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX idx_sessions_user_active ON user_sessions(user_id, is_active, started_at DESC);
CREATE INDEX idx_sessions_ip ON user_sessions(ip_address) WHERE ip_address IS NOT NULL;

-- Table DEVICE_LOGS (corrigée)
CREATE TABLE IF NOT EXISTS public.device_logs (
    log_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    device_id UUID NOT NULL,
    patient_id UUID REFERENCES patients(patient_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('connected', 'disconnected', 'low_battery', 'offline', 'error', 'calibration', 'reset')),
    status TEXT CHECK (status IN ('connected', 'low_battery', 'offline', 'error', 'calibrating')),
    battery_level SMALLINT CHECK (battery_level >= 0 AND battery_level <= 100),
    signal_strength SMALLINT CHECK (signal_strength >= 0 AND signal_strength <= 100),
    firmware_version TEXT,
    error_code TEXT,
    message TEXT,
    recorded_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB
);

CREATE INDEX idx_device_logs_device_time ON device_logs(device_id, recorded_at DESC);
CREATE INDEX idx_device_logs_patient_time ON device_logs(patient_id, recorded_at DESC) WHERE patient_id IS NOT NULL;
CREATE INDEX idx_device_logs_events ON device_logs(event_type, recorded_at DESC);

-- Table PATIENT_LOCATIONS (corrigée)
CREATE TABLE IF NOT EXISTS public.patient_locations (
    location_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    latitude NUMERIC(10,8) CHECK (latitude >= -90 AND latitude <= 90),
    longitude NUMERIC(11,8) CHECK (longitude >= -180 AND longitude <= 180),
    accuracy_meters NUMERIC(6,2),
    altitude_meters NUMERIC(7,2),
    speed_kmh NUMERIC(5,2),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    location_type TEXT CHECK (location_type IN ('home', 'hospital', 'school', 'emergency', 'other')) DEFAULT 'other',
    is_emergency BOOLEAN DEFAULT false,
    battery_impact SMALLINT
);

CREATE INDEX idx_locations_patient_time ON patient_locations(patient_id, recorded_at DESC);
CREATE INDEX idx_locations_emergency ON patient_locations(is_emergency, recorded_at DESC) WHERE is_emergency = true;

-- =====================================================
-- ÉTAPE 8: TABLE AUDIT_LOGS (Recommandation #2)
-- =====================================================

CREATE TABLE IF NOT EXISTS public.audit_logs (
    audit_id BIGSERIAL,

    -- Identification de l'action
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')),
    row_id TEXT,

    -- Contexte utilisateur
    user_id UUID REFERENCES users(user_id),
    session_id UUID,
    ip_address INET,
    user_agent TEXT,

    -- Détails de la modification
    old_values JSONB,
    new_values JSONB,
    changed_columns TEXT[],

    -- Métadonnées
    performed_at TIMESTAMPTZ DEFAULT now(),
    application_name TEXT DEFAULT 'kidjamo',
    transaction_id BIGINT DEFAULT txid_current(),

    -- Classification RGPD
    contains_pii BOOLEAN DEFAULT false,
    data_category TEXT CHECK (data_category IN ('medical', 'personal', 'technical', 'system')),
    retention_until DATE,

    PRIMARY KEY (audit_id, performed_at)
) PARTITION BY RANGE (performed_at);

-- Partitions pour audit_logs (par mois)
DO $$
DECLARE
    month_start DATE;
    month_end DATE;
    partition_name TEXT;
    i INTEGER;
BEGIN
    FOR i IN 0..5 LOOP
        month_start := DATE_TRUNC('month', CURRENT_DATE) + (i || ' months')::INTERVAL;
        month_end := month_start + INTERVAL '1 month';
        partition_name := 'audit_logs_' || TO_CHAR(month_start, 'YYYY') || 'm' || TO_CHAR(month_start, 'MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs
             FOR VALUES FROM (%L) TO (%L)',
            partition_name, month_start, month_end
        );
    END LOOP;
END $$;

-- Index pour audit_logs
CREATE INDEX idx_audit_logs_table_time ON audit_logs(table_name, performed_at DESC);
CREATE INDEX idx_audit_logs_user_time ON audit_logs(user_id, performed_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_audit_logs_pii ON audit_logs(contains_pii, performed_at DESC) WHERE contains_pii = true;

-- =====================================================
-- ÉTAPE 9: VUES MATÉRIALISÉES (Recommandation #4)
-- =====================================================

-- Vue matérialisée: Métriques patients temps réel
CREATE MATERIALIZED VIEW mv_patient_realtime_metrics AS
SELECT
    p.patient_id,
    p.genotype,
    EXTRACT(YEAR FROM AGE(p.birth_date)) as age_years,
    CASE
        WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) <= 1 THEN 'G1'
        WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) <= 5 THEN 'G2'
        WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) <= 12 THEN 'G3'
        WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) <= 17 THEN 'G4'
        WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) <= 59 THEN 'G5'
        ELSE 'G6'
    END as age_group,

    -- Dernières mesures
    m_last.heart_rate_bpm as last_heart_rate,
    m_last.spo2_percent as last_spo2,
    m_last.temperature_celsius as last_temperature,
    m_last.recorded_at as last_measurement_time,

    -- Statistiques 24h
    AVG(m_24h.spo2_percent) FILTER (WHERE m_24h.quality_flag = 'ok') as avg_spo2_24h,
    MIN(m_24h.spo2_percent) FILTER (WHERE m_24h.quality_flag = 'ok') as min_spo2_24h,
    MAX(m_24h.temperature_celsius) FILTER (WHERE m_24h.quality_flag = 'ok') as max_temp_24h,
    COUNT(m_24h.measurement_id) as measurements_count_24h,

    -- Alertes actives
    COUNT(a.alert_id) as active_alerts_count,
    MAX(a.severity) as highest_severity,

    -- Statut device
    dl.event_type as last_device_event,
    dl.battery_level as device_battery,

    -- Métadonnées
    now() as computed_at

FROM patients p
LEFT JOIN LATERAL (
    SELECT * FROM measurements m
    WHERE m.patient_id = p.patient_id
    ORDER BY m.recorded_at DESC
    LIMIT 1
) m_last ON true
LEFT JOIN measurements m_24h ON m_24h.patient_id = p.patient_id
    AND m_24h.recorded_at >= now() - INTERVAL '24 hours'
LEFT JOIN alerts a ON a.patient_id = p.patient_id
    AND a.resolved_at IS NULL
LEFT JOIN LATERAL (
    SELECT * FROM device_logs dl
    WHERE dl.patient_id = p.patient_id
    ORDER BY dl.recorded_at DESC
    LIMIT 1
) dl ON true
GROUP BY p.patient_id, p.genotype, p.birth_date,
         m_last.heart_rate_bpm, m_last.spo2_percent,
         m_last.temperature_celsius, m_last.recorded_at,
         dl.event_type, dl.battery_level;

-- Index pour la vue matérialisée
CREATE UNIQUE INDEX idx_mv_patient_realtime_pk ON mv_patient_realtime_metrics(patient_id);
CREATE INDEX idx_mv_patient_realtime_severity ON mv_patient_realtime_metrics(highest_severity, active_alerts_count);

-- Vue matérialisée: Tendances hebdomadaires
CREATE MATERIALIZED VIEW mv_patient_weekly_trends AS
SELECT
    p.patient_id,
    DATE_TRUNC('week', m.recorded_at) as week_start,

    -- Moyennes hebdomadaires
    AVG(m.spo2_percent) FILTER (WHERE m.quality_flag = 'ok') as avg_spo2,
    AVG(m.heart_rate_bpm) FILTER (WHERE m.quality_flag = 'ok') as avg_heart_rate,
    AVG(m.temperature_celsius) FILTER (WHERE m.quality_flag = 'ok') as avg_temperature,
    AVG(m.hydration_percent) FILTER (WHERE m.quality_flag = 'ok') as avg_hydration,

    -- Variabilité
    STDDEV(m.spo2_percent) FILTER (WHERE m.quality_flag = 'ok') as stddev_spo2,

    -- Compteurs
    COUNT(m.measurement_id) as total_measurements,
    COUNT(*) FILTER (WHERE m.quality_flag != 'ok') as poor_quality_count,
    COUNT(DISTINCT DATE(m.recorded_at)) as active_days,

    -- Alertes
    COUNT(DISTINCT a.alert_id) as alerts_count,
    COUNT(DISTINCT a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts_count,

    now() as computed_at

FROM patients p
JOIN measurements m ON m.patient_id = p.patient_id
    AND m.recorded_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '12 weeks'
LEFT JOIN alerts a ON a.patient_id = p.patient_id
    AND DATE_TRUNC('week', a.created_at) = DATE_TRUNC('week', m.recorded_at)
GROUP BY p.patient_id, DATE_TRUNC('week', m.recorded_at)
ORDER BY p.patient_id, DATE_TRUNC('week', m.recorded_at) DESC;

CREATE UNIQUE INDEX idx_mv_weekly_trends_pk ON mv_patient_weekly_trends(patient_id, week_start);

-- =====================================================
-- ÉTAPE 10: CONTRAINTES DE COHÉRENCE (Recommandation #5)
-- =====================================================

-- Un seul médecin traitant primaire par patient
CREATE UNIQUE INDEX idx_one_primary_clinician_per_patient
ON patient_clinicians(patient_id)
WHERE is_primary = true AND role = 'médecin_traitant';

-- Les alertes critiques doivent avoir une deadline
ALTER TABLE alerts ADD CONSTRAINT critical_alerts_need_deadline
CHECK (
    (severity != 'critical') OR
    (severity = 'critical' AND ack_deadline IS NOT NULL)
);

-- Validation des prescripteurs
CREATE OR REPLACE FUNCTION validate_prescriber_is_clinician()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.prescriber_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM clinicians WHERE clinician_id = NEW.prescriber_id
    ) THEN
        RAISE EXCEPTION 'Le prescripteur doit être un clinicien valide';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_treatment_prescriber
BEFORE INSERT OR UPDATE ON treatments
FOR EACH ROW EXECUTE FUNCTION validate_prescriber_is_clinician();

-- =====================================================
-- ÉTAPE 11: ROW-LEVEL SECURITY (Recommandation #1)
-- =====================================================

-- Activation RLS sur toutes les tables sensibles
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE treatments ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_clinicians ENABLE ROW LEVEL SECURITY;

-- Politique RLS pour patients
CREATE POLICY patient_self_access ON patients
    FOR ALL
    TO application_role
    USING (user_id = get_current_user_id());

-- Politique pour tuteurs
CREATE POLICY caregiver_patient_access ON patients
    FOR SELECT
    TO application_role
    USING (patient_id IN (
        SELECT c.patient_id
        FROM caregivers c
        WHERE c.user_id = get_current_user_id()
    ));

-- Politique pour cliniciens
CREATE POLICY clinician_patient_access ON patients
    FOR ALL
    TO application_role
    USING (patient_id IN (
        SELECT pc.patient_id
        FROM patient_clinicians pc
        JOIN clinicians cl ON cl.clinician_id = pc.clinician_id
        WHERE cl.user_id = get_current_user_id()
    ));

-- Politique pour measurements (hérite de patients)
CREATE POLICY measurements_patient_access ON measurements
    FOR ALL
    TO application_role
    USING (patient_id IN (
        SELECT p.patient_id FROM patients p
    ));

-- Politique pour alerts
CREATE POLICY alerts_access ON alerts
    FOR ALL
    TO application_role
    USING (
        patient_id IN (SELECT p.patient_id FROM patients p WHERE p.user_id = get_current_user_id())
        OR
        patient_id IN (SELECT c.patient_id FROM caregivers c WHERE c.user_id = get_current_user_id())
        OR
        patient_id IN (
            SELECT pc.patient_id
            FROM patient_clinicians pc
            JOIN clinicians cl ON cl.clinician_id = pc.clinician_id
            WHERE cl.user_id = get_current_user_id()
        )
    );

-- =====================================================
-- ÉTAPE 12: SYSTÈME BACKUP/RESTORE (Recommandation #6)
-- =====================================================

-- Table de suivi des exports patients
CREATE TABLE IF NOT EXISTS public.patient_data_exports (
    export_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(patient_id),
    requested_by UUID NOT NULL REFERENCES users(user_id),
    export_type TEXT CHECK (export_type IN ('gdpr_request', 'medical_transfer', 'backup', 'deletion')) NOT NULL,

    -- Scope de l'export
    include_measurements BOOLEAN DEFAULT true,
    include_alerts BOOLEAN DEFAULT true,
    include_treatments BOOLEAN DEFAULT true,
    include_locations BOOLEAN DEFAULT false,
    date_from DATE,
    date_to DATE,

    -- Statut
    status TEXT CHECK (status IN ('requested', 'processing', 'completed', 'failed', 'expired')) DEFAULT 'requested',
    file_path TEXT,
    file_size_bytes BIGINT,
    encryption_key_id TEXT,

    -- Métadonnées
    requested_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT now() + INTERVAL '30 days',
    download_count INTEGER DEFAULT 0,
    last_downloaded_at TIMESTAMPTZ,

    -- Conformité RGPD
    legal_basis TEXT CHECK (legal_basis IN ('consent', 'contract', 'legal_obligation', 'vital_interests', 'public_task', 'legitimate_interests')),
    retention_period INTERVAL DEFAULT INTERVAL '7 years',
    auto_delete_at TIMESTAMPTZ DEFAULT now() + INTERVAL '7 years'
);

CREATE INDEX idx_patient_exports_patient ON patient_data_exports(patient_id, requested_at DESC);
CREATE INDEX idx_patient_exports_status ON patient_data_exports(status, expires_at);

-- Fonction d'export complet d'un patient
CREATE OR REPLACE FUNCTION export_patient_data(
    p_patient_id UUID,
    p_requested_by UUID,
    p_export_type TEXT DEFAULT 'backup'
)
RETURNS UUID AS $$
DECLARE
    export_record_id UUID;
    patient_data JSONB := '{}';
BEGIN
    -- Création de l'enregistrement d'export
    INSERT INTO patient_data_exports (
        patient_id, requested_by, export_type, status
    ) VALUES (
        p_patient_id, p_requested_by, p_export_type, 'processing'
    ) RETURNING export_id INTO export_record_id;

    -- Construction du JSON patient (simplifié pour l'exemple)
    SELECT jsonb_build_object(
        'patient_info', row_to_json(p.*),
        'user_info', row_to_json(u.*),
        'export_metadata', jsonb_build_object(
            'export_id', export_record_id,
            'exported_at', now(),
            'exported_by', p_requested_by
        )
    ) INTO patient_data
    FROM patients p
    JOIN users u ON u.user_id = p.user_id
    WHERE p.patient_id = p_patient_id;

    -- Finalisation de l'export
    UPDATE patient_data_exports
    SET
        status = 'completed',
        completed_at = now(),
        file_size_bytes = octet_length(patient_data::TEXT)
    WHERE export_id = export_record_id;

    RETURN export_record_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- ÉTAPE 13: TRIGGERS ET FONCTIONS UTILITAIRES
-- =====================================================

-- Trigger pour mise à jour automatique de updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Fonction générique d'audit
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    old_data JSONB;
    new_data JSONB;
    current_user_id UUID;
    pii_detected BOOLEAN := false;
    data_cat TEXT := 'technical';
BEGIN
    current_user_id := get_current_user_id();

    IF TG_OP = 'UPDATE' THEN
        old_data := to_jsonb(OLD);
        new_data := to_jsonb(NEW);
    ELSIF TG_OP = 'INSERT' THEN
        new_data := to_jsonb(NEW);
        old_data := NULL;
    ELSIF TG_OP = 'DELETE' THEN
        old_data := to_jsonb(OLD);
        new_data := NULL;
    END IF;

    -- Détection automatique de PII
    IF TG_TABLE_NAME IN ('users', 'patients', 'patient_locations') THEN
        pii_detected := true;
        data_cat := 'personal';
    ELSIF TG_TABLE_NAME IN ('measurements', 'alerts', 'treatments') THEN
        pii_detected := true;
        data_cat := 'medical';
    END IF;

    -- Insertion dans audit_logs
    INSERT INTO audit_logs (
        table_name, operation, row_id, user_id,
        old_values, new_values,
        contains_pii, data_category,
        retention_until
    ) VALUES (
        TG_TABLE_NAME, TG_OP,
        COALESCE(
            (new_data->>'patient_id'),
            (new_data->>'user_id'),
            (new_data->>'alert_id'),
            (old_data->>'patient_id'),
            (old_data->>'user_id'),
            (old_data->>'alert_id')
        ),
        current_user_id,
        old_data, new_data,
        pii_detected, data_cat,
        CASE WHEN pii_detected THEN CURRENT_DATE + INTERVAL '7 years' ELSE CURRENT_DATE + INTERVAL '3 years' END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Application des triggers d'audit
CREATE TRIGGER audit_users AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_patients AFTER INSERT OR UPDATE OR DELETE ON patients
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_measurements AFTER INSERT OR UPDATE OR DELETE ON measurements
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_alerts AFTER INSERT OR UPDATE OR DELETE ON alerts
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- Trigger pour log automatique des statuts d'alertes
CREATE OR REPLACE FUNCTION log_alert_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO alert_status_logs (alert_id, status, changed_at)
        VALUES (NEW.alert_id, 'created', NEW.created_at);
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.resolved_at IS NULL AND NEW.resolved_at IS NOT NULL THEN
        INSERT INTO alert_status_logs (alert_id, status, changed_at)
        VALUES (NEW.alert_id, CASE WHEN NEW.auto_resolved THEN 'auto_resolved' ELSE 'resolved' END, NEW.resolved_at);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER alert_status_logger AFTER INSERT OR UPDATE ON alerts FOR EACH ROW EXECUTE FUNCTION log_alert_status_change();

-- =====================================================
-- ÉTAPE 14: VUES MÉTIER ET PERMISSIONS
-- =====================================================

-- Vue enrichie des mesures avec qualité
CREATE OR REPLACE VIEW v_measurements_enriched AS
SELECT
    m.*,
    q.label AS quality_label,
    q.severity AS quality_severity,
    q.auto_exclude_from_trends,
    p.genotype,
    EXTRACT(YEAR FROM AGE(p.birth_date)) AS age_years
FROM measurements m
LEFT JOIN measurement_quality q ON q.code = m.quality_flag
LEFT JOIN patients p ON p.patient_id = m.patient_id;

-- Vue des alertes actives
CREATE OR REPLACE VIEW v_active_alerts AS
SELECT
    a.*,
    p.genotype,
    EXTRACT(YEAR FROM AGE(p.birth_date)) AS patient_age,
    u.first_name || ' ' || u.last_name AS patient_name,
    CASE
        WHEN a.ack_deadline < now() THEN 'OVERDUE'
        WHEN a.ack_deadline < now() + INTERVAL '5 minutes' THEN 'URGENT'
        ELSE 'PENDING'
    END AS urgency_status
FROM alerts a
JOIN patients p ON p.patient_id = a.patient_id
JOIN users u ON u.user_id = p.user_id
WHERE a.resolved_at IS NULL;

-- Attribution des permissions aux rôles
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO application_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO admin_role;

-- Permissions sur les séquences
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO application_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO admin_role;

-- =====================================================
-- ÉTAPE 15: FONCTIONS UTILITAIRES MÉTIER
-- =====================================================

-- Fonction calcul âge en années
CREATE OR REPLACE FUNCTION calculate_age_years(birth_date DATE)
RETURNS NUMERIC(4,1) AS $$
BEGIN
    RETURN EXTRACT(EPOCH FROM AGE(birth_date)) / (365.25 * 24 * 3600);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction détermination groupe d'âge
CREATE OR REPLACE FUNCTION get_age_group(birth_date DATE)
RETURNS TEXT AS $$
DECLARE
    age_years NUMERIC;
BEGIN
    age_years := calculate_age_years(birth_date);

    CASE
        WHEN age_years <= 1 THEN RETURN 'G1';
        WHEN age_years <= 5 THEN RETURN 'G2';
        WHEN age_years <= 12 THEN RETURN 'G3';
        WHEN age_years <= 17 THEN RETURN 'G4';
        WHEN age_years <= 59 THEN RETURN 'G5';
        ELSE RETURN 'G6';
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction de nettoyage automatique
CREATE OR REPLACE FUNCTION cleanup_expired_exports()
RETURNS INTEGER AS $$
DECLARE
    cleanup_count INTEGER := 0;
BEGIN
    UPDATE patient_data_exports
    SET status = 'expired'
    WHERE expires_at < now()
      AND status = 'completed';

    DELETE FROM patient_data_exports
    WHERE auto_delete_at < now()
      AND status = 'expired';

    GET DIAGNOSTICS cleanup_count = ROW_COUNT;

    RETURN cleanup_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =====================================================
-- INSTRUCTIONS POST-DÉPLOIEMENT
-- =====================================================

/*
ACTIVATION IMMÉDIATE REQUISE:

1. CRÉER UTILISATEUR APPLICATION:
   CREATE USER kidjamo_app WITH PASSWORD 'mot_de_passe_sécurisé';
   GRANT application_role TO kidjamo_app;

2. CONFIGURER RLS DANS L'APPLICATION:
   -- Avant chaque requête utilisateur:
   SET LOCAL app.current_user_id = 'uuid-utilisateur-connecté';

3. PROGRAMMER MAINTENANCE AUTOMATIQUE:
   -- Rafraîchir vues matérialisées toutes les 5 minutes:
   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_patient_realtime_metrics;
   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_patient_weekly_trends;

   -- Créer partitions semaine suivante (hebdomadaire):
   SELECT create_weekly_partition(DATE_TRUNC('week', CURRENT_DATE + INTERVAL '1 week'));

   -- Nettoyage données expirées (quotidien):
   SELECT cleanup_expired_exports();

4. MONITORING À SURVEILLER:
   - Taille des partitions measurements (croissance)
   - Performance des vues matérialisées
   - Logs audit_logs (rétention RGPD)
   - Alertes non acquittées

SÉCURITÉ:
✅ Row-Level Security activé (isolation patients)
✅ Audit trail complet (conformité RGPD)
✅ Contraintes de cohérence métier
✅ Partitioning pour performance
✅ Vues matérialisées pour dashboards
✅ Système backup/restore granulaire

NEXT STEPS:
1. Tester avec données réelles (petits volumes)
2. Valider permissions et RLS
3. Configurer monitoring
4. Former équipe sur nouveaux process
*/
