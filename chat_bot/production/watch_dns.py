#!/usr/bin/env python3
"""
Script de surveillance DNS en temps réel
Vérifie automatiquement toutes les 30 secondes jusqu'à ce que tous les DNS soient configurés
"""

import socket
import time
import sys
from datetime import datetime

# Configuration
EXPECTED_IP = "52.30.79.88"
DOMAINS = [
    "chatbot.kidjamo.app",
    "api-chatbot.kidjamo.app"
]

def check_dns(domain: str) -> tuple[bool, str]:
    """Vérifie la résolution DNS d'un domaine"""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror:
        return False, "Non résolu"

def main():
    print("🔍 Surveillance DNS en temps réel pour Kidjamo")
    print("=" * 70)
    print(f"IP attendue: {EXPECTED_IP}")
    print("Vérification automatique toutes les 30 secondes...")
    print("Appuyez sur Ctrl+C pour arrêter")
    print("=" * 70)
    print()

    attempt = 0

    try:
        while True:
            attempt += 1
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] Tentative #{attempt}")
            print("-" * 70)

            all_ok = True
            results = []

            for domain in DOMAINS:
                resolved, ip = check_dns(domain)

                if resolved and ip == EXPECTED_IP:
                    status = "✅ OK"
                    ok = True
                elif resolved:
                    status = f"⚠️  Mauvaise IP ({ip})"
                    ok = False
                    all_ok = False
                else:
                    status = "❌ Non résolu"
                    ok = False
                    all_ok = False

                print(f"  {domain:30} {status}")
                results.append((domain, ok))

            print()

            if all_ok:
                print("=" * 70)
                print("🎉 SUCCÈS! Tous les DNS sont correctement configurés!")
                print("=" * 70)
                print()
                print("🚀 Prochaine étape:")
                print("   .\\chat_bot\\production\\upload_https_files.bat")
                print()
                return 0
            else:
                print(f"⏳ Attente de 30 secondes avant la prochaine vérification...")
                print()
                time.sleep(30)

    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("⏹️  Surveillance arrêtée par l'utilisateur")
        print()

        # Afficher le statut actuel
        print("📊 Statut actuel:")
        for domain in DOMAINS:
            resolved, ip = check_dns(domain)
            if resolved and ip == EXPECTED_IP:
                print(f"  ✅ {domain}")
            else:
                print(f"  ❌ {domain} → {ip}")
        print()

        return 1

if __name__ == "__main__":
    sys.exit(main())

