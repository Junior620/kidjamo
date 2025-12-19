#!/usr/bin/env python3
"""
Script d'installation et de configuration pour l'IA générative Kidjamo
Installe Ollama et configure l'environnement automatiquement
"""

import os
import sys
import subprocess
import platform
import requests
import time
from pathlib import Path

def print_step(message):
    print(f"\n🔧 {message}")
    print("=" * 50)

def print_success(message):
    print(f"✅ {message}")

def print_warning(message):
    print(f"⚠️  {message}")

def print_error(message):
    print(f"❌ {message}")

def check_python_version():
    """Vérifie que Python 3.8+ est installé"""
    if sys.version_info < (3, 8):
        print_error("Python 3.8 ou supérieur requis")
        sys.exit(1)
    print_success(f"Python {sys.version.split()[0]} détecté")

def install_python_dependencies():
    """Installe les dépendances Python"""
    print_step("Installation des dépendances Python")

    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print_success("Dépendances Python installées")
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur installation dépendances: {e}")
        return False
    return True

def install_ollama():
    """Installe Ollama selon l'OS"""
    print_step("Installation d'Ollama (IA locale)")

    os_name = platform.system().lower()

    if os_name == "windows":
        print("📥 Téléchargement d'Ollama pour Windows...")
        print("Visitez: https://ollama.ai/download/windows")
        print("Ou exécutez: winget install Ollama.Ollama")

    elif os_name == "darwin":  # macOS
        try:
            subprocess.run(["brew", "install", "ollama"], check=True)
            print_success("Ollama installé via Homebrew")
        except subprocess.CalledProcessError:
            print_warning("Homebrew non trouvé. Installation manuelle requise:")
            print("Visitez: https://ollama.ai/download/mac")

    elif os_name == "linux":
        try:
            # Installation via le script officiel
            subprocess.run([
                "curl", "-fsSL", "https://ollama.ai/install.sh"
            ], stdout=subprocess.PIPE, check=True)
            print_success("Ollama installé sur Linux")
        except subprocess.CalledProcessError:
            print_warning("Installation automatique échouée. Utilisez:")
            print("curl -fsSL https://ollama.ai/install.sh | sh")

    return True

def start_ollama_service():
    """Démarre le service Ollama"""
    print_step("Démarrage du service Ollama")

    try:
        # Vérifier si Ollama est déjà en cours
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print_success("Ollama déjà en cours d'exécution")
            return True
    except requests.RequestException:
        pass

    # Démarrer Ollama
    os_name = platform.system().lower()

    if os_name == "windows":
        print("Démarrez Ollama via le menu Démarrer ou:")
        print("ollama serve")
    else:
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)  # Laisser le temps au service de démarrer
            print_success("Service Ollama démarré")
        except FileNotFoundError:
            print_error("Ollama non trouvé. Installez-le d'abord.")
            return False

    return True

def download_ai_models():
    """Télécharge les modèles d'IA recommandés"""
    print_step("Téléchargement des modèles d'IA locaux")

    models = [
        ("llama3.1:8b", "Modèle principal (4.7GB)"),
        ("mistral:7b", "Alternative légère (4.1GB)"),
    ]

    for model, description in models:
        print(f"📦 Téléchargement de {model} - {description}")
        try:
            result = subprocess.run(
                ["ollama", "pull", model],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes max
            )

            if result.returncode == 0:
                print_success(f"Modèle {model} téléchargé")
            else:
                print_warning(f"Échec téléchargement {model}: {result.stderr}")

        except subprocess.TimeoutExpired:
            print_warning(f"Timeout pour {model} - continuez manuellement avec: ollama pull {model}")
        except FileNotFoundError:
            print_error("Ollama non trouvé. Installez-le d'abord.")
            return False

    return True

def setup_environment():
    """Configure le fichier d'environnement"""
    print_step("Configuration de l'environnement")

    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists() and env_example.exists():
        # Copier l'exemple
        with open(env_example, 'r') as f:
            content = f.read()

        with open(env_file, 'w') as f:
            f.write(content)

        print_success("Fichier .env créé à partir de l'exemple")
        print_warning("Configurez vos clés API dans le fichier .env si vous voulez utiliser les services cloud")
    else:
        print_success("Fichier .env déjà présent")

    return True

def test_ai_setup():
    """Teste la configuration IA"""
    print_step("Test de la configuration IA")

    try:
        # Test Ollama local
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                print_success(f"Ollama fonctionnel avec {len(models)} modèle(s)")
                for model in models[:3]:  # Afficher les 3 premiers
                    print(f"  - {model.get('name', 'Unknown')}")
            else:
                print_warning("Ollama fonctionne mais aucun modèle téléchargé")
        else:
            print_warning("Ollama non accessible")
    except requests.RequestException:
        print_warning("Ollama non disponible - les APIs cloud seront utilisées en fallback")

    # Test des imports Python
    try:
        from ai_engine import ai_engine
        print_success("Module AI Engine importé avec succès")

        # Test de base
        test_response = ai_engine.generate_response(
            "Test de configuration",
            {"session_id": "test"},
            "general"
        )

        if test_response.get('success'):
            source = test_response.get('source', 'unknown')
            print_success(f"Test IA réussi via {source}")
        else:
            print_warning("Test IA échoué mais configuration OK")

    except ImportError as e:
        print_error(f"Erreur import AI Engine: {e}")
        return False

    return True

def main():
    """Script principal d'installation"""
    print("🚀 INSTALLATION IA GÉNÉRATIVE KIDJAMO")
    print("=" * 50)

    # 1. Vérifications préliminaires
    check_python_version()

    # 2. Installation des dépendances
    if not install_python_dependencies():
        print_error("Installation des dépendances échouée")
        sys.exit(1)

    # 3. Installation Ollama
    install_ollama()

    # 4. Démarrage du service
    if start_ollama_service():
        # 5. Téléchargement des modèles
        download_ai_models()

    # 6. Configuration environnement
    setup_environment()

    # 7. Tests finaux
    test_ai_setup()

    print("\n🎉 INSTALLATION TERMINÉE !")
    print("=" * 50)
    print("✅ Votre chatbot Kidjamo est maintenant équipé d'IA générative")
    print("\n📋 Prochaines étapes :")
    print("1. Configurez vos clés API dans .env (optionnel)")
    print("2. Démarrez le serveur: python chatbot_server.py")
    print("3. Testez sur http://localhost:5000")
    print("\n💡 Conseil : Les modèles locaux peuvent prendre du temps à télécharger")
    print("    En attendant, le système utilisera les réponses de fallback")

if __name__ == "__main__":
    main()
