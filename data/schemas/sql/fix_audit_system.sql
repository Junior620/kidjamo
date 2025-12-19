-- KIDJAMO - CORRECTIF POUR LE SYSTÈME D'AUDIT
-- Résout le problème de clé étrangère avec get_current_user_id()
-- Date: 2025-08-18

-- =====================================================
-- 1. CRÉER UN UTILISATEUR SYSTÈME PAR DÉFAUT
-- =====================================================

-- Utilisateur système pour les opérations automatiques
INSERT INTO users (
    user_id,
    role,
    first_name,
    last_name,
    email,
    password_hash,
    country,
    is_active
) VALUES (
    '00000000-0000-0000-0000-000000000000',
    'admin',
    'System',
    'Audit',
    'system@kidjamo.internal',
    'no_password_system_user',
    'System',
    true
) ON CONFLICT (user_id) DO NOTHING;

-- =====================================================
-- 2. CORRIGER LA FONCTION D'AUDIT
-- =====================================================

-- Fonction d'audit corrigée pour gérer les utilisateurs inexistants
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    old_data JSONB;
    new_data JSONB;
    current_user_id UUID;
    pii_detected BOOLEAN := false;
    data_cat TEXT := 'technical';
    system_user_id UUID := '00000000-0000-0000-0000-000000000000';
BEGIN
    -- Récupérer l'ID utilisateur actuel ou utiliser le système
    BEGIN
        current_user_id := get_current_user_id();

        -- Vérifier si l'utilisateur existe
        IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = current_user_id) THEN
            current_user_id := system_user_id;
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            current_user_id := system_user_id;
    END;

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

    -- Insertion dans audit_logs avec utilisateur valide
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
        current_user_id,  -- Maintenant toujours un utilisateur valide
        old_data, new_data,
        pii_detected, data_cat,
        CASE WHEN pii_detected THEN CURRENT_DATE + INTERVAL '7 years' ELSE CURRENT_DATE + INTERVAL '3 years' END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 3. VÉRIFICATION DE LA CORRECTION
-- =====================================================

-- Vérifier que l'utilisateur système existe
SELECT
    user_id,
    role,
    first_name || ' ' || last_name as full_name,
    email
FROM users
WHERE user_id = '00000000-0000-0000-0000-000000000000';

-- Test de la fonction corrigée
SELECT get_current_user_id() as current_user_function_result;

\echo '✅ Correctif appliqué avec succès!'
\echo '✅ Utilisateur système créé pour audit automatique'
\echo '✅ Fonction audit_trigger_function() corrigée'
\echo ''
\echo '🔄 Vous pouvez maintenant relancer le générateur de données de test'
