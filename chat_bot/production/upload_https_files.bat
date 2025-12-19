@echo off
REM ============================================================================
REM Script Windows pour uploader les fichiers HTTPS sur EC2
REM ============================================================================

echo ============================================================
echo  UPLOAD DES FICHIERS HTTPS VERS EC2
echo ============================================================
echo.

set EC2_IP=52.30.79.88
set KEY_PATH=chat_bot\production\kidjamo-chatbot-access-20251002.pem
set REMOTE_USER=ubuntu

echo Configuration:
echo   IP EC2: %EC2_IP%
echo   Cle SSH: %KEY_PATH%
echo.

REM Vérifier que la clé existe
if not exist "%KEY_PATH%" (
    echo ERREUR: Cle SSH non trouvee!
    echo Chemin: %KEY_PATH%
    echo.
    echo Placez la cle dans: chat_bot\production\
    pause
    exit /b 1
)

echo [1/4] Upload du script principal setup_https.sh...
scp -i %KEY_PATH% chat_bot\production\setup_https.sh %REMOTE_USER%@%EC2_IP%:/tmp/
if errorlevel 1 (
    echo ERREUR lors de l'upload!
    pause
    exit /b 1
)
echo OK
echo.

echo [2/4] Upload de la configuration Nginx avancee...
scp -i %KEY_PATH% chat_bot\production\nginx-kidjamo-https-advanced.conf %REMOTE_USER%@%EC2_IP%:/tmp/
if errorlevel 1 (
    echo ERREUR lors de l'upload!
    pause
    exit /b 1
)
echo OK
echo.

echo [3/4] Upload du script de mise a jour...
scp -i %KEY_PATH% chat_bot\production\upgrade_nginx_config.sh %REMOTE_USER%@%EC2_IP%:/tmp/
if errorlevel 1 (
    echo ERREUR lors de l'upload!
    pause
    exit /b 1
)
echo OK
echo.

echo [4/4] Upload du guide...
scp -i %KEY_PATH% chat_bot\production\GUIDE_HTTPS_SETUP.md %REMOTE_USER%@%EC2_IP%:/tmp/
if errorlevel 1 (
    echo ERREUR lors de l'upload!
    pause
    exit /b 1
)
echo OK
echo.

echo ============================================================
echo  TOUS LES FICHIERS UPLOADES AVEC SUCCES!
echo ============================================================
echo.
echo Prochaines etapes:
echo.
echo 1. Verifier les DNS (sur votre machine Windows):
echo    python chat_bot\production\check_dns.py
echo.
echo 2. Se connecter a EC2:
echo    ssh -i %KEY_PATH% %REMOTE_USER%@%EC2_IP%
echo.
echo 3. Sur EC2, executer:
echo    chmod +x /tmp/setup_https.sh
echo    sudo /tmp/setup_https.sh
echo.
echo 4. Apres obtention des certificats, appliquer la config avancee:
echo    chmod +x /tmp/upgrade_nginx_config.sh
echo    sudo /tmp/upgrade_nginx_config.sh
echo.
pause

