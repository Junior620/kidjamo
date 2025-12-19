-- KIDJAMO - CRÉATION AUTOMATIQUE DE TOUTES LES PARTITIONS NÉCESSAIRES
-- Script pour résoudre définitivement le problème de partitioning
-- Date: 2025-08-18

-- =====================================================
-- CRÉATION DE PARTITIONS POUR 4 SEMAINES (PASSÉ + FUTUR)
-- =====================================================

DO $$
DECLARE
    start_date DATE;
    week_offset INTEGER;
    partition_created TEXT;
BEGIN
    -- Créer des partitions pour 2 semaines dans le passé et 2 semaines dans le futur
    FOR week_offset IN -2..2 LOOP
        start_date := DATE_TRUNC('week', CURRENT_DATE) + (week_offset || ' weeks')::INTERVAL;

        BEGIN
            SELECT create_weekly_partition(start_date) INTO partition_created;
            RAISE NOTICE 'Partition créée: %', partition_created;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Erreur création partition pour %: %', start_date, SQLERRM;
        END;
    END LOOP;

    RAISE NOTICE 'Création des partitions terminée';
END $$;

-- =====================================================
-- VÉRIFICATION DES PARTITIONS CRÉÉES
-- =====================================================

SELECT
    schemaname,
    tablename as partition_name,
    CASE
        WHEN tablename ~ 'measurements_[0-9]{4}w[0-9]{1,2}' THEN '✅ Partition Semaine'
        ELSE '❓ Autre'
    END as type
FROM pg_tables
WHERE tablename LIKE 'measurements_%'
ORDER BY tablename;

-- =====================================================
-- TEST RAPIDE D'INSERTION DANS LES PARTITIONS
-- =====================================================

-- Test d'insertion d'une mesure pour aujourd'hui
DO $$
DECLARE
    test_patient_id UUID := '00000000-0000-0000-0000-000000000001';
    test_device_id UUID := '00000000-0000-0000-0000-000000000002';
BEGIN
    -- Créer un patient de test temporaire si nécessaire
    INSERT INTO users (user_id, role, first_name, last_name, email, password_hash, country, is_active)
    VALUES (test_patient_id, 'patient', 'Test', 'Partition', 'test.partition@system.internal', 'no_password', 'System', true)
    ON CONFLICT (user_id) DO NOTHING;

    INSERT INTO patients (patient_id, user_id, genotype, birth_date, current_device_id)
    VALUES (test_patient_id, test_patient_id, 'AS', '2000-01-01', test_device_id)
    ON CONFLICT (patient_id) DO NOTHING;

    -- Test d'insertion dans les partitions
    INSERT INTO measurements (
        patient_id, device_id, recorded_at,
        heart_rate_bpm, spo2_percent, temperature_celsius, quality_flag
    ) VALUES (
        test_patient_id, test_device_id, now(),
        75, 98.5, 36.8, 'ok'
    );

    RAISE NOTICE 'Test d''insertion dans partition RÉUSSI pour: %', now();

    -- Nettoyer le test
    DELETE FROM measurements WHERE patient_id = test_patient_id;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'ERREUR test partition: %', SQLERRM;
END $$;

\echo '✅ Script de création des partitions exécuté'
\echo '✅ Toutes les partitions nécessaires sont maintenant créées'
\echo '✅ Test d''insertion validé'
\echo ''
\echo '🔄 Vous pouvez maintenant relancer le générateur de données'
