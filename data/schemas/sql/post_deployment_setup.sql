
SELECT
    schemaname,
    tablename,
    rowsecurity as "RLS Enabled"
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Vérifier les partitions measurements
SELECT
    schemaname,
    tablename as partition_name
FROM pg_tables
WHERE tablename LIKE 'measurements_%'
ORDER BY tablename;

-- Vérifier les vues matérialisées
SELECT
    schemaname,
    matviewname,
    ispopulated
FROM pg_matviews
WHERE schemaname = 'public';

-- =====================================================
-- ÉTAPE 3: TESTS BASIQUES DE FONCTIONNEMENT
-- =====================================================

-- Test insertion utilisateur basique
INSERT INTO users (role, first_name, last_name, email, password_hash, country)
VALUES ('admin', 'Admin', 'System', 'admin@kidjamo.com', 'hash_test', 'France');

-- Test des codes qualité
SELECT code, label, severity FROM measurement_quality ORDER BY severity, code;

-- Test fonction utilitaire
SELECT get_age_group('2010-01-01'::date) as age_group_test;

-- =====================================================
-- ÉTAPE 4: CONFIGURATION RLS POUR TESTS
-- =====================================================

-- Configurer un utilisateur test pour RLS
SET app.current_user_id = '00000000-0000-0000-0000-000000000000';

-- Test politique RLS (doit retourner 0 lignes si RLS fonctionne)
SELECT COUNT(*) as patient_count_with_rls FROM patients;

-- =====================================================
-- INSTRUCTIONS SUIVANTES
-- =====================================================

/*
CONFIGURATION APPLICATION REQUISE:

1. Dans votre application, avant chaque requête utilisateur:
   SET LOCAL app.current_user_id = 'uuid-de-l-utilisateur-connecté';

2. Programmer les tâches de maintenance (CRON/Scheduler):

   TOUTES LES 5 MINUTES:
   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_patient_realtime_metrics;

   TOUTES LES HEURES:
   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_patient_weekly_trends;

   CHAQUE DIMANCHE (créer partition semaine suivante):
   SELECT create_weekly_partition(DATE_TRUNC('week', CURRENT_DATE + INTERVAL '1 week'));

   QUOTIDIEN (nettoyage):
   SELECT cleanup_expired_exports();

3. Monitoring à mettre en place:
   - Taille des partitions (croissance)
   - Performance des vues matérialisées
   - Alertes non résolues
   - Conformité RGPD (rétention audit_logs)

4. Sauvegarde recommandée:
   - Backup quotidien avec pg_dump
   - Réplication streaming pour HA
   - Test de restore mensuel
*/
