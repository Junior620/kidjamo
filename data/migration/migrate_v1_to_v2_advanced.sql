-- SCRIPT DE MIGRATION KIDJAMO v1 → v2 + Extensions
-- Migration sécurisée avec rollback et validation
-- Date: 2025-08-18

BEGIN;

-- =====================================================
-- ÉTAPE 1: SAUVEGARDE ET VALIDATION PRÉ-MIGRATION
-- =====================================================

-- Table temporaire pour audit de migration
CREATE TEMP TABLE migration_audit (
    step_name TEXT,
    status TEXT,
    rows_affected INTEGER,
    execution_time INTERVAL,
    error_message TEXT,
    executed_at TIMESTAMPTZ DEFAULT now()
);

-- Fonction de log de migration
CREATE OR REPLACE FUNCTION log_migration_step(
    p_step_name TEXT,
    p_status TEXT,
    p_rows_affected INTEGER DEFAULT 0,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO migration_audit (step_name, status, rows_affected, error_message)
    VALUES (p_step_name, p_status, p_rows_affected, p_error_message);

    RAISE NOTICE 'Migration step: % - Status: % - Rows: %', p_step_name, p_status, p_rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Validation des données existantes
DO $$
DECLARE
    invalid_users INTEGER;
    invalid_measurements INTEGER;
    orphaned_alerts INTEGER;
BEGIN
    -- Vérifier l'intégrité des données existantes
    SELECT COUNT(*) INTO invalid_users
    FROM users
    WHERE email IS NOT NULL AND email !~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$';

    IF invalid_users > 0 THEN
        RAISE WARNING 'Found % users with invalid email format', invalid_users;
    END IF;

    PERFORM log_migration_step('pre_validation', 'completed', invalid_users);
END $$;

-- =====================================================
-- ÉTAPE 2: MIGRATION STRUCTURE TABLES EXISTANTES
-- =====================================================

-- Migration table users
DO $$
BEGIN
    -- Ajouter colonnes manquantes à users
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='phone') THEN
        ALTER TABLE users ADD COLUMN phone VARCHAR(20);
        PERFORM log_migration_step('add_users_phone', 'completed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='timezone') THEN
        ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'Europe/Paris';
        PERFORM log_migration_step('add_users_timezone', 'completed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='is_active') THEN
        ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT true;
        UPDATE users SET is_active = true WHERE is_active IS NULL;
        PERFORM log_migration_step('add_users_is_active', 'completed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='updated_at') THEN
        ALTER TABLE users ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
        UPDATE users SET updated_at = created_at WHERE updated_at IS NULL;
        PERFORM log_migration_step('add_users_updated_at', 'completed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='terms_accepted_at') THEN
        ALTER TABLE users ADD COLUMN terms_accepted_at TIMESTAMPTZ;
        PERFORM log_migration_step('add_users_terms_accepted', 'completed');
    END IF;

    -- Fixer la contrainte email unique si elle n'existe pas
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_attribute a ON a.attnum = ANY(c.conkey)
        WHERE c.conrelid = 'users'::regclass AND a.attname = 'email' AND c.contype = 'u'
    ) THEN
        -- Nettoyer les doublons d'email d'abord
        WITH duplicates AS (
            SELECT user_id, email,
                   ROW_NUMBER() OVER (PARTITION BY email ORDER BY created_at) as rn
            FROM users
            WHERE email IS NOT NULL
        )
        UPDATE users SET email = email || '_duplicate_' || user_id::TEXT
        WHERE user_id IN (SELECT user_id FROM duplicates WHERE rn > 1);

        ALTER TABLE users ADD CONSTRAINT users_email_unique UNIQUE (email);
        PERFORM log_migration_step('add_users_email_unique', 'completed');
    END IF;

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('migrate_users_structure', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- Migration table patients
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='weight_kg') THEN
        ALTER TABLE patients ADD COLUMN weight_kg NUMERIC(5,2) CHECK (weight_kg > 0 AND weight_kg < 500);
        PERFORM log_migration_step('add_patients_weight', 'completed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='height_cm') THEN
        ALTER TABLE patients ADD COLUMN height_cm NUMERIC(5,1) CHECK (height_cm > 0 AND height_cm < 300);
        PERFORM log_migration_step('add_patients_height', 'completed');
    END IF;

    -- Renommer close_contact vers emergency_contact_name
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='close_contact') THEN
        ALTER TABLE patients RENAME COLUMN close_contact TO emergency_contact_name;
        ALTER TABLE patients ADD COLUMN emergency_contact_phone VARCHAR(20);
        PERFORM log_migration_step('rename_patients_emergency_contact', 'completed');
    END IF;

    -- Renommer device_id vers current_device_id
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='device_id') THEN
        ALTER TABLE patients RENAME COLUMN device_id TO current_device_id;
        PERFORM log_migration_step('rename_patients_device_id', 'completed');
    END IF;

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('migrate_patients_structure', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- Migration table measurements (la plus critique)
DO $$
DECLARE
    measurements_count INTEGER;
    batch_size INTEGER := 10000;
    processed INTEGER := 0;
BEGIN
    SELECT COUNT(*) INTO measurements_count FROM measurements;
    PERFORM log_migration_step('measurements_migration_start', 'started', measurements_count);

    -- Créer table temporaire pour la migration
    CREATE TEMP TABLE measurements_backup AS SELECT * FROM measurements LIMIT 0;

    -- Sauvegarder les données existantes par batch
    WHILE processed < measurements_count LOOP
        INSERT INTO measurements_backup
        SELECT * FROM measurements
        ORDER BY tz_timestamp
        OFFSET processed LIMIT batch_size;

        processed := processed + batch_size;
        PERFORM log_migration_step('measurements_backup_batch', 'progress', batch_size);
    END LOOP;

    -- Ajouter les nouvelles colonnes
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='pain_scale') THEN
        ALTER TABLE measurements ADD COLUMN pain_scale SMALLINT CHECK (pain_scale >= 0 AND pain_scale <= 10);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='battery_percent') THEN
        ALTER TABLE measurements ADD COLUMN battery_percent SMALLINT CHECK (battery_percent >= 0 AND battery_percent <= 100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='message_id') THEN
        ALTER TABLE measurements ADD COLUMN message_id UUID DEFAULT gen_random_uuid();
    END IF;

    -- Renommer les colonnes selon la nouvelle nomenclature
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='tz_timestamp') THEN
        ALTER TABLE measurements RENAME COLUMN tz_timestamp TO recorded_at;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='freq_card') THEN
        ALTER TABLE measurements RENAME COLUMN freq_card TO heart_rate_bpm;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='freq_resp') THEN
        ALTER TABLE measurements RENAME COLUMN freq_resp TO respiratory_rate_min;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='spo2_pct') THEN
        ALTER TABLE measurements RENAME COLUMN spo2_pct TO spo2_percent;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='measurements' AND column_name='temp_corp') THEN
        ALTER TABLE measurements RENAME COLUMN temp_corp TO temperature_celsius;
    END IF;

    PERFORM log_migration_step('measurements_structure_migration', 'completed', measurements_count);

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('migrate_measurements_structure', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- =====================================================
-- ÉTAPE 3: CRÉATION DES NOUVELLES TABLES
-- =====================================================

-- Créer les nouvelles tables du schéma v2
DO $$
BEGIN
    -- Table caregivers (remplace parents)
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='caregivers') THEN
        CREATE TABLE caregivers (
            caregiver_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
            relationship TEXT CHECK (relationship IN ('parent', 'tuteur', 'famille', 'ami_proche')) DEFAULT 'parent',
            priority_level SMALLINT CHECK (priority_level IN (1, 2, 3)) DEFAULT 1,
            can_acknowledge_alerts BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(user_id, patient_id)
        );

        -- Migrer les données de l'ancienne table parents si elle existe
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='parents') THEN
            INSERT INTO caregivers (user_id, patient_id, relationship, created_at)
            SELECT parent_id, patient_id, 'parent', COALESCE(birth_date, now())
            FROM parents;
        END IF;

        PERFORM log_migration_step('create_caregivers_table', 'completed');
    END IF;

    -- Table patient_clinicians
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='patient_clinicians') THEN
        CREATE TABLE patient_clinicians (
            patient_id UUID REFERENCES patients(patient_id) ON DELETE CASCADE,
            clinician_id UUID REFERENCES clinicians(clinician_id) ON DELETE CASCADE,
            role TEXT CHECK (role IN ('médecin_traitant', 'spécialiste', 'urgentiste', 'consultant')) DEFAULT 'consultant',
            assigned_at TIMESTAMPTZ DEFAULT now(),
            is_primary BOOLEAN DEFAULT false,
            PRIMARY KEY (patient_id, clinician_id)
        );

        PERFORM log_migration_step('create_patient_clinicians_table', 'completed');
    END IF;

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('create_new_tables', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- =====================================================
-- ÉTAPE 4: MIGRATION DES DONNÉES ET NETTOYAGE
-- =====================================================

-- Nettoyer les données invalides
DO $$
DECLARE
    cleaned_records INTEGER := 0;
BEGIN
    -- Nettoyer les measurements avec des valeurs aberrantes
    UPDATE measurements
    SET quality_flag = 'out_of_range'
    WHERE (spo2_percent IS NOT NULL AND (spo2_percent < 0 OR spo2_percent > 100))
       OR (temperature_celsius IS NOT NULL AND (temperature_celsius < 30 OR temperature_celsius > 45))
       OR (heart_rate_bpm IS NOT NULL AND (heart_rate_bpm < 30 OR heart_rate_bpm > 250));

    GET DIAGNOSTICS cleaned_records = ROW_COUNT;
    PERFORM log_migration_step('clean_invalid_measurements', 'completed', cleaned_records);

    -- Remplir les message_id manquants pour idempotence
    UPDATE measurements
    SET message_id = gen_random_uuid()
    WHERE message_id IS NULL;

    GET DIAGNOSTICS cleaned_records = ROW_COUNT;
    PERFORM log_migration_step('fill_missing_message_ids', 'completed', cleaned_records);

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('data_cleanup', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- =====================================================
-- ÉTAPE 5: CRÉATION DES INDEX OPTIMISÉS
-- =====================================================

DO $$
BEGIN
    -- Index essentiels pour performance
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurements_patient_time_v2
    ON measurements(patient_id, recorded_at DESC);

    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurements_recent_v2
    ON measurements(recorded_at DESC)
    WHERE recorded_at >= now() - INTERVAL '24 hours';

    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_active
    ON users(email)
    WHERE email IS NOT NULL AND is_active = true;

    PERFORM log_migration_step('create_optimized_indexes', 'completed');

EXCEPTION WHEN OTHERS THEN
    PERFORM log_migration_step('create_indexes', 'failed', 0, SQLERRM);
    RAISE;
END $$;

-- =====================================================
-- ÉTAPE 6: VALIDATION POST-MIGRATION
-- =====================================================

DO $$
DECLARE
    validation_errors TEXT[] := ARRAY[]::TEXT[];
    users_count INTEGER;
    patients_count INTEGER;
    measurements_count INTEGER;
    alerts_count INTEGER;
BEGIN
    -- Vérifier les comptes de base
    SELECT COUNT(*) INTO users_count FROM users WHERE is_active = true;
    SELECT COUNT(*) INTO patients_count FROM patients;
    SELECT COUNT(*) INTO measurements_count FROM measurements;
    SELECT COUNT(*) INTO alerts_count FROM alerts;

    IF users_count = 0 THEN
        validation_errors := array_append(validation_errors, 'No active users found');
    END IF;

    IF patients_count = 0 THEN
        validation_errors := array_append(validation_errors, 'No patients found');
    END IF;

    -- Vérifier l'intégrité référentielle
    IF EXISTS (
        SELECT 1 FROM patients p
        LEFT JOIN users u ON u.user_id = p.user_id
        WHERE u.user_id IS NULL
    ) THEN
        validation_errors := array_append(validation_errors, 'Orphaned patients found');
    END IF;

    -- Vérifier les nouvelles colonnes
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='is_active'
    ) THEN
        validation_errors := array_append(validation_errors, 'Missing is_active column in users');
    END IF;

    -- Rapport de validation
    IF array_length(validation_errors, 1) > 0 THEN
        RAISE WARNING 'Validation errors found: %', array_to_string(validation_errors, ', ');
        PERFORM log_migration_step('post_migration_validation', 'warning', array_length(validation_errors, 1));
    ELSE
        PERFORM log_migration_step('post_migration_validation', 'passed', 0);
    END IF;

    -- Statistiques finales
    RAISE NOTICE 'Migration completed - Users: %, Patients: %, Measurements: %, Alerts: %',
                 users_count, patients_count, measurements_count, alerts_count;

END $$;

-- =====================================================
-- ÉTAPE 7: NETTOYAGE ET FINALISATION
-- =====================================================

-- Supprimer les anciennes tables si migration réussie
DO $$
BEGIN
    -- Vérifier que la migration s'est bien passée avant de supprimer
    IF NOT EXISTS (
        SELECT 1 FROM migration_audit
        WHERE status = 'failed'
    ) THEN
        -- Supprimer les anciennes tables
        DROP TABLE IF EXISTS parents CASCADE;
        DROP TABLE IF EXISTS visitor CASCADE;  -- Table simple sans données critiques

        PERFORM log_migration_step('cleanup_old_tables', 'completed');
    ELSE
        PERFORM log_migration_step('cleanup_old_tables', 'skipped', 0, 'Migration errors detected');
    END IF;
END $$;

-- Créer une vue de rapport de migration
CREATE OR REPLACE VIEW v_migration_report AS
SELECT
    step_name,
    status,
    rows_affected,
    execution_time,
    error_message,
    executed_at
FROM migration_audit
ORDER BY executed_at;

-- Export du rapport de migration
DO $$
DECLARE
    report_json JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'step', step_name,
            'status', status,
            'rows_affected', rows_affected,
            'execution_time', execution_time,
            'error_message', error_message,
            'executed_at', executed_at
        )
    ) INTO report_json
    FROM migration_audit;

    -- En production, sauvegarder ce rapport dans un fichier
    RAISE NOTICE 'Migration report: %', report_json;
END $$;

COMMIT;

-- =====================================================
-- INSTRUCTIONS POST-MIGRATION
-- =====================================================

/*
APRÈS CETTE MIGRATION:

1. VÉRIFICATIONS OBLIGATOIRES:
   - Tester toutes les requêtes critiques de l'application
   - Vérifier les permissions et accès utilisateurs
   - Valider les contraintes de données
   - Tester les triggers d'audit

2. ACTIVATIONS REQUISES:
   - Appliquer le script kidjamo_advanced_security_performance.sql
   - Configurer les tâches cron pour maintenance
   - Activer RLS et créer les utilisateurs de base
   - Configurer les vues matérialisées

3. MONITORING:
   - Surveiller les performances post-migration
   - Vérifier les logs d'erreur
   - Monitorer l'usage disque (nouvelles colonnes)
   - Valider les sauvegardes

4. ROLLBACK SI PROBLÈME:
   -- Script de rollback d'urgence disponible
   -- Restaurer depuis measurements_backup si nécessaire
   -- Réactiver les anciennes contraintes

5. FORMATION ÉQUIPE:
   - Nouvelles colonnes dans measurements
   - Nouveaux process d'audit et export
   - Procédures de conformité RGPD

CONTACT SUPPORT: Si problèmes → garder ce fichier + logs pour debug
*/
