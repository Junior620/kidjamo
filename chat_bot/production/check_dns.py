#!/usr/bin/env python3
"""
Script de vérification de la configuration DNS pour kidjamo.app
Vérifie que tous les enregistrements pointent vers la bonne IP
"""

import socket
import subprocess
import sys
from typing import Dict, List, Tuple

# Configuration
EXPECTED_IP = "52.30.79.88"  # IP de votre EC2 chatbot
DOMAINS = [
    # Ne PAS toucher kidjamo.app (déjà utilisé ailleurs)
    # "kidjamo.app",  # ← Commenté pour ne pas vérifier
    "chatbot.kidjamo.app",      # Interface chatbot
    "api-chatbot.kidjamo.app"   # API chatbot
]

def check_dns_resolution(domain: str) -> Tuple[bool, str]:
    """Vérifie la résolution DNS d'un domaine"""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror:
        return False, "Non résolu"

def check_dns_with_nslookup(domain: str) -> Tuple[bool, str]:
    """Vérifie la résolution DNS avec nslookup"""
    try:
        result = subprocess.run(
            ['nslookup', domain],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Chercher l'adresse IP dans la sortie
        for line in result.stdout.split('\n'):
            if 'Address:' in line and '#' not in line:
                ip = line.split('Address:')[-1].strip()
                return True, ip

        return False, "Non résolu"
    except Exception as e:
        return False, str(e)

def main():
    print("🔍 Vérification DNS pour Kidjamo.app")
    print("=" * 60)
    print(f"IP attendue: {EXPECTED_IP}")
    print("")

    all_ok = True
    results = []

    for domain in DOMAINS:
        print(f"📡 Vérification de {domain}...", end=" ")

        # Vérification avec socket
        resolved, ip = check_dns_resolution(domain)

        if resolved:
            if ip == EXPECTED_IP:
                print(f"✅ OK ({ip})")
                results.append((domain, True, ip))
            else:
                print(f"⚠️  Mauvaise IP ({ip} au lieu de {EXPECTED_IP})")
                results.append((domain, False, ip))
                all_ok = False
        else:
            print(f"❌ ÉCHEC ({ip})")
            results.append((domain, False, ip))
            all_ok = False

    print("")
    print("=" * 60)

    if all_ok:
        print("✅ Tous les DNS sont correctement configurés!")
        print("")
        print("🚀 Vous pouvez maintenant exécuter setup_https.sh")
        print("")
        print("ℹ️  Note: kidjamo.app principal reste sur son IP actuelle")
        return 0
    else:
        print("❌ Configuration DNS incomplète")
        print("")
        print("📋 Actions requises:")
        print("")

        for domain, ok, ip in results:
            if not ok:
                print(f"   • Configurer {domain} → {EXPECTED_IP}")
                print(f"     Actuellement: {ip}")

        print("")
        print("🔧 Dans votre registrar de domaine, créez UNIQUEMENT:")
        print("")
        print("   Type | Nom           | Valeur          | TTL")
        print("   -----|---------------|-----------------|-----")
        print(f"   A    | chatbot       | {EXPECTED_IP} | 300")
        print(f"   A    | api-chatbot   | {EXPECTED_IP} | 300")
        print("")
        print("⚠️  NE PAS MODIFIER kidjamo.app (@ record) !")
        print("")
        print("⏰ Attendez 5-30 minutes pour la propagation DNS")
        print("   puis relancez ce script.")

        return 1

if __name__ == "__main__":
    sys.exit(main())

