-- Migration SQL : Ajout des colonnes audio à chatbot_conversations
-- Date: 2025-10-06
-- Description: Support complet audio (transcription + synthèse vocale)

-- Ajouter les colonnes pour la fonctionnalité audio
ALTER TABLE chatbot_conversations
ADD COLUMN IF NOT EXISTS audio_transcription TEXT,
ADD COLUMN IF NOT EXISTS audio_response_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS audio_duration_seconds INTEGER,
ADD COLUMN IF NOT EXISTS transcription_confidence DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS voice_model VARCHAR(50),
ADD COLUMN IF NOT EXISTS detected_language VARCHAR(10),
ADD COLUMN IF NOT EXISTS s3_audio_input_key VARCHAR(500),
ADD COLUMN IF NOT EXISTS s3_audio_output_key VARCHAR(500),
ADD COLUMN IF NOT EXISTS audio_from_cache BOOLEAN DEFAULT FALSE;

-- Ajouter des index pour recherches efficaces
CREATE INDEX IF NOT EXISTS idx_conversations_audio_language ON chatbot_conversations(detected_language);
CREATE INDEX IF NOT EXISTS idx_conversations_has_audio ON chatbot_conversations(audio_transcription) WHERE audio_transcription IS NOT NULL;

-- Table pour statistiques cache audio (optionnel)
CREATE TABLE IF NOT EXISTS audio_cache_stats (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(32) UNIQUE NOT NULL,
    text_hash VARCHAR(32) NOT NULL,
    language VARCHAR(10) NOT NULL,
    audio_url VARCHAR(500) NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP + INTERVAL '24 hours'
);

CREATE INDEX IF NOT EXISTS idx_audio_cache_language ON audio_cache_stats(language);
CREATE INDEX IF NOT EXISTS idx_audio_cache_expires ON audio_cache_stats(expires_at);

-- Commentaires pour documentation
COMMENT ON COLUMN chatbot_conversations.audio_transcription IS 'Texte transcrit depuis l audio utilisateur (AWS Transcribe)';
COMMENT ON COLUMN chatbot_conversations.audio_response_url IS 'URL S3 pre-signed de la réponse audio (AWS Polly)';
COMMENT ON COLUMN chatbot_conversations.audio_duration_seconds IS 'Durée estimée de l audio de réponse en secondes';
COMMENT ON COLUMN chatbot_conversations.transcription_confidence IS 'Score de confiance AWS Transcribe (0-1)';
COMMENT ON COLUMN chatbot_conversations.voice_model IS 'Modèle de voix utilisé (ex: Lea-Neural-fr-FR)';
COMMENT ON COLUMN chatbot_conversations.detected_language IS 'Langue détectée automatiquement (fr-FR, en-US, etc.)';
COMMENT ON COLUMN chatbot_conversations.s3_audio_input_key IS 'Clé S3 du fichier audio d entrée';
COMMENT ON COLUMN chatbot_conversations.s3_audio_output_key IS 'Clé S3 du fichier audio de sortie';
COMMENT ON COLUMN chatbot_conversations.audio_from_cache IS 'Indique si l audio provient du cache';

-- Afficher le résultat
SELECT 'Migration audio appliquée avec succès!' as status;

