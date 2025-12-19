@echo off
echo 🚀 KIDJAMO DASHBOARDS - DEMARRAGE
echo ===================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    echo Installez Python depuis https://python.org
    pause
    exit /b 1
)

echo ✅ Python détecté

REM Vérifier si les requirements sont installés
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo 📦 Installation des dépendances...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Erreur installation des dépendances
        pause
        exit /b 1
    )
) else (
    echo ✅ Dépendances Streamlit installées
)

REM Vérifier le fichier .env
if not exist ".env" (
    echo ⚠️  Fichier .env manquant
    echo Copie du fichier exemple...
    copy ".env.example" ".env"
    echo.
    echo 🔧 IMPORTANT: Éditez le fichier .env avec vos vraies valeurs AWS et DB
    echo Appuyez sur une touche quand c'est fait...
    pause
)

echo.
echo 🌐 Lancement des dashboards Kidjamo...
echo 📱 L'application s'ouvrira dans votre navigateur
echo 🛑 Appuyez sur Ctrl+C pour arrêter
echo.

streamlit run kidjamo_dashboards_main.py

pause
