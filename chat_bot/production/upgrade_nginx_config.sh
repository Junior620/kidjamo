#!/bin/bash
# ============================================================================
# 🔧 Script de mise à jour de la configuration Nginx avancée
# ============================================================================
# Ce script applique la configuration Nginx optimisée avec SSL/TLS renforcé
# ============================================================================

set -e

echo "🔧 Mise à jour de la configuration Nginx vers version avancée"
echo "============================================================="
echo ""

# Vérifier les privilèges root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté en tant que root (sudo)"
    exit 1
fi

# Vérifier que les certificats existent
if [ ! -f /etc/letsencrypt/live/chatbot.kidjamo.app/fullchain.pem ]; then
    echo "❌ Certificats SSL non trouvés!"
    echo "   Veuillez d'abord exécuter setup_https.sh"
    exit 1
fi

echo "✅ Certificats SSL trouvés"
echo ""

# Backup de la configuration actuelle
BACKUP_DIR="/etc/nginx/backups"
mkdir -p $BACKUP_DIR
BACKUP_FILE="$BACKUP_DIR/kidjamo-chatbot.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f /etc/nginx/sites-available/kidjamo-chatbot ]; then
    cp /etc/nginx/sites-available/kidjamo-chatbot $BACKUP_FILE
    echo "✅ Backup créé: $BACKUP_FILE"
fi

# Créer le répertoire de cache
mkdir -p /var/cache/nginx
chown -R www-data:www-data /var/cache/nginx

# Générer les paramètres Diffie-Hellman si nécessaire
if [ ! -f /etc/ssl/certs/dhparam.pem ]; then
    echo "🔐 Génération des paramètres Diffie-Hellman (peut prendre 2-3 minutes)..."
    openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048
    echo "✅ Paramètres DH générés"
fi

# Télécharger la nouvelle configuration (à adapter selon votre méthode)
echo "📥 Installation de la nouvelle configuration..."

# Option 1: Si le fichier est uploadé
if [ -f /tmp/nginx-kidjamo-https-advanced.conf ]; then
    cp /tmp/nginx-kidjamo-https-advanced.conf /etc/nginx/sites-available/kidjamo-chatbot
else
    echo "⚠️  Fichier de configuration non trouvé dans /tmp/"
    echo "   Veuillez d'abord l'uploader avec:"
    echo "   scp nginx-kidjamo-https-advanced.conf ubuntu@YOUR_IP:/tmp/"
    exit 1
fi

# Tester la configuration
echo "🧪 Test de la configuration Nginx..."
nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuration valide"

    # Recharger Nginx
    echo "♻️  Rechargement de Nginx..."
    systemctl reload nginx

    echo ""
    echo "============================================================="
    echo "✅ MISE À JOUR TERMINÉE!"
    echo "============================================================="
    echo ""
    echo "📋 Améliorations appliquées:"
    echo "   • SSL/TLS renforcé (TLSv1.2 et TLSv1.3)"
    echo "   • HSTS activé"
    echo "   • Headers de sécurité avancés"
    echo "   • Rate limiting sur les endpoints"
    echo "   • Compression Gzip optimisée"
    echo "   • Cache pour ressources statiques"
    echo "   • WebSocket support"
    echo ""
    echo "🧪 Testez votre configuration SSL:"
    echo "   https://www.ssllabs.com/ssltest/analyze.html?d=chatbot.kidjamo.app"
    echo ""
    echo "📊 Monitoring Nginx (local):"
    echo "   curl http://127.0.0.1:8080/nginx_status"
    echo ""
else
    echo "❌ Erreur de configuration!"
    echo "   Restauration du backup..."
    cp $BACKUP_FILE /etc/nginx/sites-available/kidjamo-chatbot
    systemctl reload nginx
    echo "   Configuration précédente restaurée"
    exit 1
fi

