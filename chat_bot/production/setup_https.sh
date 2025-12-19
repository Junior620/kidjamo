#!/bin/bash
# ============================================================================
# 🔒 Configuration HTTPS avec Let's Encrypt pour Kidjamo Chatbot
# ============================================================================
# Domaine: kidjamo.app
# Sous-domaines: chat.kidjamo.app, api.kidjamo.app
# ============================================================================

set -e  # Arrêter en cas d'erreur

echo "🔒 Configuration HTTPS pour Kidjamo Chatbot"
echo "============================================"
echo ""

# Vérifier les privilèges root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté en tant que root (sudo)"
    exit 1
fi

# Variables
CHAT_SUBDOMAIN="chatbot.kidjamo.app"
API_SUBDOMAIN="api-chatbot.kidjamo.app"
EMAIL="christianouragan@gmail.com"  # Remplacez par votre email

echo "📋 Configuration:"
echo "   Chat interface: $CHAT_SUBDOMAIN"
echo "   API endpoint: $API_SUBDOMAIN"
echo "   Email admin: $EMAIL"
echo ""
echo "⚠️  Note: kidjamo.app principal n'est PAS modifié"
echo ""

# ============================================================================
# ÉTAPE 1: Installation de Certbot et Nginx
# ============================================================================
echo "📦 Étape 1/6: Installation des dépendances..."

# Mettre à jour les paquets
apt-get update -qq

# Installer Nginx si pas déjà installé
if ! command -v nginx &> /dev/null; then
    echo "   📥 Installation de Nginx..."
    apt-get install -y nginx
else
    echo "   ✅ Nginx déjà installé"
fi

# Installer Certbot et le plugin Nginx
if ! command -v certbot &> /dev/null; then
    echo "   📥 Installation de Certbot..."
    apt-get install -y certbot python3-certbot-nginx
else
    echo "   ✅ Certbot déjà installé"
fi

echo "   ✅ Dépendances installées"
echo ""

# ============================================================================
# ÉTAPE 2: Configuration Nginx de base (HTTP)
# ============================================================================
echo "📝 Étape 2/6: Configuration Nginx de base..."

# Backup de la config existante
if [ -f /etc/nginx/sites-available/default ]; then
    cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup.$(date +%Y%m%d_%H%M%S)
fi

# Créer la configuration Nginx pour le chatbot
cat > /etc/nginx/sites-available/kidjamo-chatbot << 'EOF'
# Configuration Nginx pour Kidjamo Chatbot - HTTP (temporaire)
# Will be upgraded to HTTPS by Certbot

upstream chatbot_backend {
    server 127.0.0.1:5000;
    keepalive 32;
}

# Redirection www vers non-www
server {
    listen 80;
    server_name www.chatbot.kidjamo.app www.api-chatbot.kidjamo.app;
    return 301 http://$host$request_uri;
}

# Configuration principale
server {
    listen 80;
    server_name chatbot.kidjamo.app api-chatbot.kidjamo.app;

    # Logs
    access_log /var/log/nginx/kidjamo-access.log;
    error_log /var/log/nginx/kidjamo-error.log;

    # Taille max des requêtes (pour audio)
    client_max_body_size 10M;

    # Headers de sécurité de base
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        allow all;
    }

    # Interface web (chatbot.kidjamo.app uniquement)
    location / {
        if ($host = api-chatbot.kidjamo.app) {
            return 404;
        }

        root /var/www/kidjamo/web;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API endpoints
    location /api/ {
        proxy_pass http://chatbot_backend/api/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Timeouts pour audio processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://chatbot_backend/health;
        access_log off;
    }

    # WebSocket support (si nécessaire)
    location /ws {
        proxy_pass http://chatbot_backend/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

echo "   ✅ Configuration Nginx créée"
echo ""

# ============================================================================
# ÉTAPE 3: Créer le répertoire web
# ============================================================================
echo "📁 Étape 3/6: Création du répertoire web..."

mkdir -p /var/www/kidjamo/web
chown -R www-data:www-data /var/www/kidjamo

# Créer une page index temporaire
cat > /var/www/kidjamo/web/index.html << 'EOF'
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kidjamo - Assistant Santé Drépanocytose</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            color: white;
            padding: 2rem;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        .status {
            background: rgba(255,255,255,0.2);
            padding: 1rem 2rem;
            border-radius: 10px;
            margin-top: 2rem;
            backdrop-filter: blur(10px);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Kidjamo</h1>
        <p>Assistant de Santé pour la Drépanocytose</p>
        <div class="status">
            <p>✅ Configuration HTTPS en cours...</p>
        </div>
    </div>
</body>
</html>
EOF

chown www-data:www-data /var/www/kidjamo/web/index.html

echo "   ✅ Répertoire web créé"
echo ""

# ============================================================================
# ÉTAPE 4: Activer la configuration
# ============================================================================
echo "🔗 Étape 4/6: Activation de la configuration..."

# Désactiver la config par défaut
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi

# Activer notre configuration
ln -sf /etc/nginx/sites-available/kidjamo-chatbot /etc/nginx/sites-enabled/

# Tester la configuration
nginx -t

# Redémarrer Nginx
systemctl restart nginx
systemctl enable nginx

echo "   ✅ Configuration activée"
echo ""

# ============================================================================
# ÉTAPE 5: Obtenir les certificats SSL
# ============================================================================
echo "🔐 Étape 5/6: Obtention des certificats Let's Encrypt..."
echo ""
echo "⚠️  IMPORTANT: Assurez-vous que vos DNS pointent vers cette IP:"
echo "   chatbot.kidjamo.app → $(curl -s ifconfig.me)"
echo "   api-chatbot.kidjamo.app → $(curl -s ifconfig.me)"
echo ""
echo "ℹ️  Note: kidjamo.app principal n'est PAS modifié"
echo ""
read -p "Les DNS sont-ils correctement configurés? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Veuillez d'abord configurer vos DNS, puis relancez ce script."
    exit 1
fi

# Obtenir les certificats
certbot --nginx \
    -d $CHAT_SUBDOMAIN \
    -d $API_SUBDOMAIN \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    --redirect

echo "   ✅ Certificats SSL obtenus et configurés"
echo ""

# ============================================================================
# ÉTAPE 6: Configuration du renouvellement automatique
# ============================================================================
echo "♻️  Étape 6/6: Configuration du renouvellement automatique..."

# Tester le renouvellement
certbot renew --dry-run

# Créer un cron job pour le renouvellement
cat > /etc/cron.d/certbot-renew << EOF
# Renouvellement automatique des certificats Let's Encrypt
# Tous les jours à 3h du matin
0 3 * * * root certbot renew --quiet --post-hook "systemctl reload nginx"
EOF

chmod 644 /etc/cron.d/certbot-renew

echo "   ✅ Renouvellement automatique configuré"
echo ""

# ============================================================================
# RÉSUMÉ
# ============================================================================
echo "============================================"
echo "✅ CONFIGURATION HTTPS TERMINÉE!"
echo "============================================"
echo ""
echo "🌐 Votre chatbot est maintenant accessible via:"
echo "   • https://chatbot.kidjamo.app"
echo "   • https://api-chatbot.kidjamo.app/api/v1/chat"
echo ""
echo "ℹ️  Note: kidjamo.app principal reste inchangé"
echo ""
echo "🔒 Certificats SSL:"
echo "   • Émis par: Let's Encrypt"
echo "   • Valides pour: 90 jours"
echo "   • Renouvellement automatique: ✅ Activé"
echo ""
echo "📋 Commandes utiles:"
echo "   • Tester Nginx: sudo nginx -t"
echo "   • Recharger Nginx: sudo systemctl reload nginx"
echo "   • Statut certificats: sudo certbot certificates"
echo "   • Renouveler manuellement: sudo certbot renew"
echo "   • Logs Nginx: tail -f /var/log/nginx/kidjamo-*.log"
echo ""
echo "🧪 Test de l'API:"
echo "   curl https://api-chatbot.kidjamo.app/health"
echo ""

