#!/usr/bin/env python3
"""
Script de test HTTPS complet pour Kidjamo
Vérifie que la configuration HTTPS fonctionne correctement
"""

import requests
import json
import sys
from typing import Dict, List, Tuple
from urllib.parse import urljoin

# Configuration
BASE_DOMAINS = {
    # "main": "https://kidjamo.app",  # Pas touché - utilisé ailleurs
    "chat": "https://chatbot.kidjamo.app",
    "api": "https://api-chatbot.kidjamo.app"
}

def test_ssl_certificate(url: str) -> Tuple[bool, str]:
    """Teste si le certificat SSL est valide"""
    try:
        response = requests.get(url, timeout=5)
        return True, f"SSL OK (Status: {response.status_code})"
    except requests.exceptions.SSLError as e:
        return False, f"Erreur SSL: {str(e)}"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def test_http_redirect(domain: str) -> Tuple[bool, str]:
    """Vérifie la redirection HTTP -> HTTPS"""
    http_url = domain.replace("https://", "http://")
    try:
        response = requests.get(http_url, allow_redirects=False, timeout=5)
        if response.status_code in [301, 302]:
            location = response.headers.get('Location', '')
            if location.startswith('https://'):
                return True, f"Redirection OK -> {location}"
            else:
                return False, f"Redirection incorrecte: {location}"
        else:
            return False, f"Pas de redirection (Status: {response.status_code})"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def test_api_health(api_url: str) -> Tuple[bool, str]:
    """Teste le endpoint /health de l'API"""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            return True, f"API fonctionnelle: {response.text[:50]}"
        else:
            return False, f"Status: {response.status_code}"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def test_security_headers(url: str) -> Dict[str, bool]:
    """Vérifie les headers de sécurité"""
    try:
        response = requests.get(url, timeout=5)
        headers = response.headers

        return {
            "HSTS": "strict-transport-security" in headers,
            "X-Frame-Options": "x-frame-options" in headers,
            "X-Content-Type-Options": "x-content-type-options" in headers,
            "X-XSS-Protection": "x-xss-protection" in headers,
            "Content-Security-Policy": "content-security-policy" in headers
        }
    except Exception:
        return {}

def test_chat_api(api_url: str) -> Tuple[bool, str]:
    """Teste l'endpoint chat"""
    try:
        payload = {
            "message": "Test de connexion HTTPS",
            "session_id": "test_https_123"
        }
        response = requests.post(
            f"{api_url}/api/v1/chat",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return True, f"Chat OK: {data.get('response', '')[:50]}"
        else:
            return False, f"Status: {response.status_code}"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def main():
    print("🧪 Tests HTTPS pour Kidjamo Chatbot")
    print("=" * 70)
    print()

    all_tests_passed = True

    # Test 1: Certificats SSL
    print("📋 Test 1: Certificats SSL")
    print("-" * 70)
    for name, url in BASE_DOMAINS.items():
        print(f"  Testing {name:10} ({url})... ", end="")
        success, message = test_ssl_certificate(url)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            all_tests_passed = False
    print()

    # Test 2: Redirections HTTP -> HTTPS
    print("📋 Test 2: Redirections HTTP -> HTTPS")
    print("-" * 70)
    for name, url in BASE_DOMAINS.items():
        print(f"  Testing {name:10}... ", end="")
        success, message = test_http_redirect(url)
        if success:
            print(f"✅ {message}")
        else:
            print(f"⚠️  {message}")
    print()

    # Test 3: Health Check API
    print("📋 Test 3: Health Check API")
    print("-" * 70)
    print(f"  Testing API health... ", end="")
    success, message = test_api_health(BASE_DOMAINS['api'])
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        all_tests_passed = False
    print()

    # Test 4: Headers de sécurité
    print("📋 Test 4: Headers de sécurité")
    print("-" * 70)
    headers = test_security_headers(BASE_DOMAINS['chat'])
    if headers:
        for header, present in headers.items():
            status = "✅" if present else "⚠️ "
            print(f"  {header:30} {status}")
    else:
        print("  ❌ Impossible de vérifier les headers")
    print()

    # Test 5: Endpoint Chat
    print("📋 Test 5: Endpoint Chat")
    print("-" * 70)
    print(f"  Testing chat endpoint... ", end="")
    success, message = test_chat_api(BASE_DOMAINS['api'])
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        all_tests_passed = False
    print()

    # Résumé
    print("=" * 70)
    if all_tests_passed:
        print("✅ TOUS LES TESTS SONT PASSÉS!")
        print()
        print("🎉 Votre chatbot est correctement configuré en HTTPS")
        print()
        print("🔗 Liens d'accès:")
        print(f"   Interface: {BASE_DOMAINS['chat']}")
        print(f"   API: {BASE_DOMAINS['api']}/api/v1/chat")
        print()
        print("ℹ️  Note: kidjamo.app principal reste sur son IP actuelle")
        print()
        print("🔐 Testez votre score SSL:")
        print("   https://www.ssllabs.com/ssltest/analyze.html?d=chatbot.kidjamo.app")
        return 0
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        print()
        print("Vérifiez:")
        print("  • Les certificats SSL sont installés")
        print("  • Le service chatbot est démarré")
        print("  • Nginx est correctement configuré")
        print("  • Les DNS pointent vers la bonne IP")
        return 1

if __name__ == "__main__":
    sys.exit(main())

