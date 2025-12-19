-- Schema SQL pour les Posts Communautaires
-- Gestion des témoignages, questions et conseils

-- Table principale des posts
CREATE TABLE community_posts (
    id VARCHAR(36) PRIMARY KEY,
    type ENUM('temoignage', 'question', 'conseil') NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    author_id VARCHAR(36) NOT NULL,
    category VARCHAR(100),
    visibility ENUM('public', 'private', 'community') DEFAULT 'public',
    status ENUM('draft', 'published', 'archived', 'reported') DEFAULT 'draft',
    views_count INT DEFAULT 0,
    shares_count INT DEFAULT 0,
    is_reported BOOLEAN DEFAULT FALSE,
    report_count INT DEFAULT 0,
    moderator_notes TEXT,
    location_city VARCHAR(100),
    location_country VARCHAR(100),
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at TIMESTAMP NULL,
    last_reviewed_at TIMESTAMP NULL,

    INDEX idx_type_created (type, created_at DESC),
    INDEX idx_author (author_id),
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_created_desc (created_at DESC),
    INDEX idx_reported (is_reported),
    INDEX idx_visibility (visibility)
);

-- Table des tags
CREATE TABLE community_post_tags (
    id VARCHAR(36) PRIMARY KEY,
    post_id VARCHAR(36) NOT NULL,
    tag_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_post_tag (post_id, tag_name),
    INDEX idx_tag_name (tag_name),
    INDEX idx_post_id (post_id)
);

-- Table des likes
CREATE TABLE community_post_likes (
    id VARCHAR(36) PRIMARY KEY,
    post_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_post_like (post_id, user_id),
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id)
);

-- Table des commentaires
CREATE TABLE community_post_comments (
    id VARCHAR(36) PRIMARY KEY,
    post_id VARCHAR(36) NOT NULL,
    author_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    is_reported BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_author_id (author_id),
    INDEX idx_created_desc (created_at DESC),
    INDEX idx_reported (is_reported)
);

-- Table des pièces jointes
CREATE TABLE community_post_attachments (
    id VARCHAR(36) PRIMARY KEY,
    post_id VARCHAR(36) NOT NULL,
    type ENUM('image', 'video', 'document') NOT NULL,
    url VARCHAR(500) NOT NULL,
    filename VARCHAR(255),
    file_size BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_type (type)
);

-- Vue pour obtenir les statistiques des posts
CREATE VIEW community_posts_stats AS
SELECT
    cp.id,
    cp.title,
    cp.type,
    cp.category,
    cp.status,
    cp.views_count,
    cp.shares_count,
    COUNT(DISTINCT cpl.id) as likes_count,
    COUNT(DISTINCT cpc.id) as comments_count,
    COUNT(DISTINCT cpt.id) as tags_count,
    COUNT(DISTINCT cpa.id) as attachments_count,
    cp.created_at,
    cp.published_at
FROM community_posts cp
LEFT JOIN community_post_likes cpl ON cp.id = cpl.post_id
LEFT JOIN community_post_comments cpc ON cp.id = cpc.post_id
LEFT JOIN community_post_tags cpt ON cp.id = cpt.post_id
LEFT JOIN community_post_attachments cpa ON cp.id = cpa.post_id
GROUP BY cp.id;

-- Vue pour les posts populaires
CREATE VIEW popular_community_posts AS
SELECT
    cp.*,
    (COUNT(DISTINCT cpl.id) * 3 + COUNT(DISTINCT cpc.id) * 2 + cp.views_count * 0.1) as popularity_score
FROM community_posts cp
LEFT JOIN community_post_likes cpl ON cp.id = cpl.post_id
LEFT JOIN community_post_comments cpc ON cp.id = cpc.post_id
WHERE cp.status = 'published'
    AND cp.visibility = 'public'
GROUP BY cp.id
ORDER BY popularity_score DESC;
