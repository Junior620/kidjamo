-- Schema SQL pour le Journal de Symptômes et Événements Cliniques
-- Structure relationnelle pour données time-series de santé

-- Table principale des événements symptômes (time-series)
CREATE TABLE symptoms_journal (
    id VARCHAR(36) PRIMARY KEY,
    patient_id VARCHAR(36) NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    timezone_offset VARCHAR(6) DEFAULT '+00:00',
    pain_score INT CHECK (pain_score >= 0 AND pain_score <= 10),
    pain_scale ENUM('NRS0-10', 'VAS0-100', 'FACES') DEFAULT 'NRS0-10',
    pain_duration_minutes INT,
    notes TEXT,
    notes_encrypted BLOB,

    -- Contexte physiologique
    sleep_hours DECIMAL(3,1) CHECK (sleep_hours >= 0 AND sleep_hours <= 24),
    stress_level ENUM('low', 'moderate', 'high', 'severe'),
    physical_activity ENUM('sedentary', 'light', 'moderate', 'intense'),
    hydration_liters DECIMAL(3,1),
    menstruation BOOLEAN DEFAULT FALSE,

    -- Signes vitaux
    temperature_celsius DECIMAL(3,1),
    blood_pressure_systolic INT,
    blood_pressure_diastolic INT,
    heart_rate_bpm INT,
    oxygen_saturation_percent DECIMAL(4,1),

    -- Contexte météo
    weather_temperature DECIMAL(4,1),
    weather_humidity_percent INT,
    weather_conditions VARCHAR(50),

    -- Alimentation
    meals_count INT DEFAULT 0,
    alcohol_consumed BOOLEAN DEFAULT FALSE,
    caffeine_mg DECIMAL(6,1) DEFAULT 0,

    -- Source et confidentialité
    data_source_type ENUM('patient_input', 'caregiver_input', 'device', 'import'),
    device_id VARCHAR(36),
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    visibility ENUM('patient_only', 'care_team', 'family', 'research_anonymous') DEFAULT 'care_team',
    share_with_research BOOLEAN DEFAULT FALSE,
    retention_days INT,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(36) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version INT DEFAULT 1,

    INDEX idx_patient_time (patient_id, occurred_at DESC),
    INDEX idx_occurred_at (occurred_at DESC),
    INDEX idx_pain_score (pain_score),
    INDEX idx_data_source (data_source_type),
    INDEX idx_created_by (created_by),
    INDEX idx_patient_pain_time (patient_id, pain_score, occurred_at DESC)
);

-- Table des symptômes observés
CREATE TABLE symptoms_journal_symptoms (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    symptom_code VARCHAR(100) NOT NULL, -- SNOMED CT ou autre
    symptom_label VARCHAR(200) NOT NULL,
    severity ENUM('mild', 'moderate', 'severe'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_symptom_code (symptom_code),
    INDEX idx_severity (severity),
    UNIQUE KEY unique_journal_symptom (journal_id, symptom_code)
);

-- Table des localisations corporelles des symptômes
CREATE TABLE symptoms_body_locations (
    id VARCHAR(36) PRIMARY KEY,
    symptom_id VARCHAR(36) NOT NULL,
    body_location VARCHAR(100) NOT NULL,

    FOREIGN KEY (symptom_id) REFERENCES symptoms_journal_symptoms(id) ON DELETE CASCADE,
    INDEX idx_symptom_id (symptom_id),
    INDEX idx_body_location (body_location)
);

-- Table des localisations de douleur
CREATE TABLE pain_locations (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    location VARCHAR(100) NOT NULL,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_location (location)
);

-- Table des qualités de douleur
CREATE TABLE pain_qualities (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    quality ENUM('sharp', 'dull', 'burning', 'throbbing', 'cramping', 'stabbing') NOT NULL,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_quality (quality)
);

-- Table des déclencheurs
CREATE TABLE symptoms_triggers (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    trigger_name VARCHAR(100) NOT NULL,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_trigger_name (trigger_name),
    UNIQUE KEY unique_journal_trigger (journal_id, trigger_name)
);

-- Table des actions prises
CREATE TABLE symptoms_actions (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    action_name VARCHAR(100) NOT NULL,
    effectiveness ENUM('none', 'slight', 'moderate', 'significant', 'complete'),

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_action_name (action_name),
    INDEX idx_effectiveness (effectiveness)
);

-- Table des médicaments pris
CREATE TABLE symptoms_medications (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    medication_id VARCHAR(36),
    medication_name VARCHAR(200) NOT NULL,
    dose DECIMAL(10,3) NOT NULL,
    dose_unit VARCHAR(20) NOT NULL,
    route ENUM('oral', 'injectable', 'topique', 'inhalation', 'sublingual'),
    taken_at TIMESTAMP,
    effectiveness ENUM('none', 'slight', 'moderate', 'significant', 'complete'),

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_medication_id (medication_id),
    INDEX idx_medication_name (medication_name),
    INDEX idx_taken_at (taken_at)
);

-- Table des aliments spéciaux consommés
CREATE TABLE symptoms_special_foods (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    food_name VARCHAR(100) NOT NULL,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_food_name (food_name)
);

-- Table des événements liés
CREATE TABLE symptoms_linked_events (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    event_kind ENUM('alert', 'treatment', 'appointment', 'lab_result', 'medication_change') NOT NULL,
    event_id VARCHAR(36) NOT NULL,
    description TEXT,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_event_kind (event_kind),
    INDEX idx_event_id (event_id)
);

-- Table des pièces jointes
CREATE TABLE symptoms_attachments (
    id VARCHAR(36) PRIMARY KEY,
    journal_id VARCHAR(36) NOT NULL,
    attachment_type ENUM('photo', 'audio', 'document', 'chart') NOT NULL,
    url VARCHAR(500) NOT NULL,
    filename VARCHAR(255),
    size_bytes BIGINT,
    encryption_key_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (journal_id) REFERENCES symptoms_journal(id) ON DELETE CASCADE,
    INDEX idx_journal_id (journal_id),
    INDEX idx_attachment_type (attachment_type)
);

-- Vue pour l'analyse quotidienne des symptômes par patient
CREATE VIEW daily_symptoms_summary AS
SELECT
    sj.patient_id,
    DATE(sj.occurred_at) as symptom_date,
    COUNT(DISTINCT sj.id) as total_events,
    AVG(sj.pain_score) as avg_pain_score,
    MAX(sj.pain_score) as max_pain_score,
    COUNT(DISTINCT sjs.symptom_code) as unique_symptoms,
    COUNT(DISTINCT st.trigger_name) as unique_triggers,
    AVG(sj.sleep_hours) as avg_sleep_hours,
    AVG(sj.hydration_liters) as avg_hydration
FROM symptoms_journal sj
LEFT JOIN symptoms_journal_symptoms sjs ON sj.id = sjs.journal_id
LEFT JOIN symptoms_triggers st ON sj.id = st.journal_id
GROUP BY sj.patient_id, DATE(sj.occurred_at);

-- Vue pour l'analyse des déclencheurs les plus fréquents
CREATE VIEW trigger_frequency_analysis AS
SELECT
    sj.patient_id,
    st.trigger_name,
    COUNT(*) as frequency,
    AVG(sj.pain_score) as avg_pain_when_triggered,
    MAX(sj.pain_score) as max_pain_when_triggered,
    COUNT(DISTINCT DATE(sj.occurred_at)) as days_with_trigger
FROM symptoms_journal sj
JOIN symptoms_triggers st ON sj.id = st.journal_id
WHERE sj.pain_score IS NOT NULL
GROUP BY sj.patient_id, st.trigger_name
ORDER BY frequency DESC;

-- Vue pour l'efficacité des médicaments
CREATE VIEW medication_effectiveness AS
SELECT
    sm.medication_name,
    sm.dose,
    sm.dose_unit,
    sm.route,
    COUNT(*) as usage_count,
    AVG(CASE
        WHEN sm.effectiveness = 'none' THEN 0
        WHEN sm.effectiveness = 'slight' THEN 1
        WHEN sm.effectiveness = 'moderate' THEN 2
        WHEN sm.effectiveness = 'significant' THEN 3
        WHEN sm.effectiveness = 'complete' THEN 4
        ELSE NULL
    END) as avg_effectiveness_score,
    COUNT(DISTINCT sj.patient_id) as patients_count
FROM symptoms_medications sm
JOIN symptoms_journal sj ON sm.journal_id = sj.id
WHERE sm.effectiveness IS NOT NULL
GROUP BY sm.medication_name, sm.dose, sm.dose_unit, sm.route
HAVING usage_count >= 3
ORDER BY avg_effectiveness_score DESC;

-- Vue pour les patterns temporels de symptômes
CREATE VIEW temporal_symptom_patterns AS
SELECT
    sj.patient_id,
    HOUR(sj.occurred_at) as hour_of_day,
    DAYOFWEEK(sj.occurred_at) as day_of_week,
    CASE
        WHEN HOUR(sj.occurred_at) BETWEEN 6 AND 11 THEN 'morning'
        WHEN HOUR(sj.occurred_at) BETWEEN 12 AND 17 THEN 'afternoon'
        WHEN HOUR(sj.occurred_at) BETWEEN 18 AND 21 THEN 'evening'
        ELSE 'night'
    END as time_period,
    COUNT(*) as event_count,
    AVG(sj.pain_score) as avg_pain_score,
    COUNT(DISTINCT sjs.symptom_code) as unique_symptoms
FROM symptoms_journal sj
LEFT JOIN symptoms_journal_symptoms sjs ON sj.id = sjs.journal_id
GROUP BY sj.patient_id, hour_of_day, day_of_week, time_period;

-- Procédure stockée pour calculer les corrélations symptômes-déclencheurs
DELIMITER //
CREATE PROCEDURE CalculateSymptomTriggerCorrelations(IN patient_uuid VARCHAR(36))
BEGIN
    SELECT
        sjs.symptom_code,
        sjs.symptom_label,
        st.trigger_name,
        COUNT(*) as co_occurrence_count,
        (COUNT(*) * 100.0 / total_symptoms.total) as correlation_percentage
    FROM symptoms_journal sj
    JOIN symptoms_journal_symptoms sjs ON sj.id = sjs.journal_id
    JOIN symptoms_triggers st ON sj.id = st.journal_id
    CROSS JOIN (
        SELECT COUNT(DISTINCT sjs2.journal_id) as total
        FROM symptoms_journal_symptoms sjs2
        JOIN symptoms_journal sj2 ON sjs2.journal_id = sj2.id
        WHERE sj2.patient_id = patient_uuid
    ) as total_symptoms
    WHERE sj.patient_id = patient_uuid
    GROUP BY sjs.symptom_code, sjs.symptom_label, st.trigger_name, total_symptoms.total
    HAVING co_occurrence_count >= 2
    ORDER BY correlation_percentage DESC;
END //
DELIMITER ;
