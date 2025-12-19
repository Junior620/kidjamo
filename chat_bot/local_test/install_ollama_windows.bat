@echo off
echo 🚀 Installation automatique d'Ollama pour Windows
echo ============================================

REM Vérifier si winget est disponible
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Winget non disponible. Installation manuelle requise.
    echo.
    echo  Veuillez télécharger Ollama manuellement depuis :
    echo https://ollama.ai/download/windows
    echo.
    echo Ou utilisez le lien direct :
    echo https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe
    pause
    exit /b 1
)

echo  Winget détecté, installation en cours...
winget install Ollama.Ollama

if %errorlevel% equ 0 (
    echo.
    echo  Ollama installé avec succès !
    echo.
    echo  Démarrage du service Ollama...
    start "" "ollama" serve

    timeout /t 5 /nobreak >nul

    echo.
    echo 📦 Téléchargement du modèle Llama 3.1 (recommandé)...
    echo ⏳ Cela peut prendre 10-30 minutes selon votre connexion...
    ollama pull llama3.1:8b

    echo.
    echo  Installation terminée !
    echo  Ollama est maintenant prêt à utiliser

) else (
    echo  Échec de l'installation automatique
    echo.
    echo  Installation manuelle depuis :
    echo https://ollama.ai/download/windows
)

echo.
echo 📋 Prochaines étapes :
echo 1. Redémarrez votre terminal PowerShell
echo 2. Testez avec : ollama --version
echo 3. Relancez votre chatbot : python chatbot_server.py
echo.
pause
