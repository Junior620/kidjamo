-- Schema SQL pour les Articles Éducatifs
-- Gestion du contenu éditorial avec versioning et i18n

-- Table principale des articles
CREATE TABLE articles_education (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    titre VARCHAR(200) NOT NULL,
    resume VARCHAR(500),
    contenu_html LONGTEXT NOT NULL,
    source VARCHAR(200),
    source_url VARCHAR(500),
    auteur_id VARCHAR(36) NOT NULL,
    status ENUM('draft', 'review', 'published', 'archived') DEFAULT 'draft',
    date_publication TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Versioning
    version VARCHAR(20) DEFAULT '1.0.0',
    previous_version_id VARCHAR(36),
    changelog TEXT,
    is_major_update BOOLEAN DEFAULT FALSE,

    -- SEO
    meta_description VARCHAR(160),
    canonical_url VARCHAR(500),

    -- Engagement
    views_count INT DEFAULT 0,
    likes_count INT DEFAULT 0,
    shares_count INT DEFAULT 0,
    reading_time_minutes INT,

    -- Modération
    reviewed_by VARCHAR(36),
    reviewed_at TIMESTAMP NULL,
    medical_validation BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,

    INDEX idx_slug (slug),
    INDEX idx_status_date (status, date_publication DESC),
    INDEX idx_auteur (auteur_id),
    INDEX idx_created_desc (created_at DESC),
    INDEX idx_status_audience (status),
    INDEX idx_version (version),
    INDEX idx_source (source),
    INDEX idx_views (views_count DESC)
);

-- Table des tags
CREATE TABLE article_tags (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,
    tag_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (article_id) REFERENCES articles_education(id) ON DELETE CASCADE,
    UNIQUE KEY unique_article_tag (article_id, tag_name),
    INDEX idx_tag_name (tag_name),
    INDEX idx_article_id (article_id)
);

-- Table des audiences cibles
CREATE TABLE article_audiences (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,
    audience_type ENUM('patients', 'parents', 'cliniciens', 'grand_public') NOT NULL,

    FOREIGN KEY (article_id) REFERENCES articles_education(id) ON DELETE CASCADE,
    UNIQUE KEY unique_article_audience (article_id, audience_type),
    INDEX idx_audience_type (audience_type),
    INDEX idx_article_id (article_id)
);

-- Table des mots-clés SEO
CREATE TABLE article_seo_keywords (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,
    keyword VARCHAR(100) NOT NULL,

    FOREIGN KEY (article_id) REFERENCES articles_education(id) ON DELETE CASCADE,
    INDEX idx_article_id (article_id),
    INDEX idx_keyword (keyword)
);

-- Table pour l'internationalisation
CREATE TABLE article_i18n (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,
    langue_code VARCHAR(2) NOT NULL, -- fr, en, etc.
    titre VARCHAR(200),
    resume VARCHAR(500),
    contenu_html LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (article_id) REFERENCES articles_education(id) ON DELETE CASCADE,
    UNIQUE KEY unique_article_lang (article_id, langue_code),
    INDEX idx_article_id (article_id),
    INDEX idx_langue (langue_code)
);

-- Table des blocs de contenu structuré
CREATE TABLE article_blocs (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,
    langue_code VARCHAR(2) DEFAULT 'fr',
    ordre INT NOT NULL,
    bloc_type ENUM('p', 'h1', 'h2', 'h3', 'ul', 'ol', 'blockquote', 'image', 'video', 'code') NOT NULL,
    text_content LONGTEXT,
    src_url VARCHAR(500), -- Pour images/vidéos
    alt_text VARCHAR(200), -- Pour accessibilité
    language_code VARCHAR(20), -- Pour blocs de code
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (article_id) REFERENCES articles_education(id) ON DELETE CASCADE,
    INDEX idx_article_lang (article_id, langue_code),
    INDEX idx_ordre (article_id, ordre),
    INDEX idx_bloc_type (bloc_type)
);

-- Table des items de liste (pour ul/ol)
CREATE TABLE article_bloc_items (
    id VARCHAR(36) PRIMARY KEY,
    bloc_id VARCHAR(36) NOT NULL,
    item_ordre INT NOT NULL,
    item_text TEXT NOT NULL,

    FOREIGN KEY (bloc_id) REFERENCES article_blocs(id) ON DELETE CASCADE,
    INDEX idx_bloc_ordre (bloc_id, item_ordre)
);

-- Vue pour les articles publiés avec statistiques
CREATE VIEW published_articles_stats AS
SELECT
    a.id,
    a.slug,
    a.titre,
    a.resume,
    a.auteur_id,
    a.date_publication,
    a.views_count,
    a.likes_count,
    a.shares_count,
    a.reading_time_minutes,
    a.version,
    a.medical_validation,
    COUNT(DISTINCT at.id) as tags_count,
    COUNT(DISTINCT aa.id) as audiences_count,
    GROUP_CONCAT(DISTINCT at.tag_name) as tags_list,
    GROUP_CONCAT(DISTINCT aa.audience_type) as audiences_list
FROM articles_education a
LEFT JOIN article_tags at ON a.id = at.article_id
LEFT JOIN article_audiences aa ON a.id = aa.article_id
WHERE a.status = 'published'
    AND (a.date_publication IS NULL OR a.date_publication <= NOW())
GROUP BY a.id;

-- Vue pour les articles multilingues
CREATE VIEW multilingual_articles AS
SELECT
    a.id,
    a.slug,
    a.status,
    a.date_publication,
    COUNT(DISTINCT ai.langue_code) as languages_count,
    GROUP_CONCAT(DISTINCT ai.langue_code) as available_languages,
    a.titre as titre_original,
    a.created_at
FROM articles_education a
LEFT JOIN article_i18n ai ON a.id = ai.article_id
GROUP BY a.id;

-- Vue pour les articles populaires
CREATE VIEW popular_articles AS
SELECT
    a.*,
    (a.views_count * 0.4 + a.likes_count * 2 + a.shares_count * 3) as popularity_score
FROM articles_education a
WHERE a.status = 'published'
ORDER BY popularity_score DESC;

-- Procédure pour calculer le temps de lecture
DELIMITER //
CREATE PROCEDURE CalculateReadingTime(IN article_uuid VARCHAR(36))
BEGIN
    DECLARE content_length INT;
    DECLARE words_per_minute INT DEFAULT 200; -- Lecture moyenne adulte

    SELECT CHAR_LENGTH(REGEXP_REPLACE(contenu_html, '<[^>]*>', '')) INTO content_length
    FROM articles_education
    WHERE id = article_uuid;

    UPDATE articles_education
    SET reading_time_minutes = GREATEST(1, CEIL((content_length / 5) / words_per_minute))
    WHERE id = article_uuid;
END //
DELIMITER ;

-- Trigger pour mettre à jour automatically le reading_time
DELIMITER //
CREATE TRIGGER update_reading_time_on_content_change
    BEFORE UPDATE ON articles_education
    FOR EACH ROW
BEGIN
    IF NEW.contenu_html != OLD.contenu_html THEN
        SET NEW.reading_time_minutes = GREATEST(1,
            CEIL((CHAR_LENGTH(REGEXP_REPLACE(NEW.contenu_html, '<[^>]*>', '')) / 5) / 200)
        );
    END IF;
END //
DELIMITER ;
