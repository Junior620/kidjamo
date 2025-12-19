@echo off
REM Script de vérification DNS avec serveurs publics
echo ============================================================
echo Verification DNS avec serveurs publics (Google DNS)
echo ============================================================
echo.

echo [1] Verification avec Google DNS (8.8.8.8)
echo ------------------------------------------------------------
nslookup chatbot.kidjamo.app 8.8.8.8
echo.
nslookup api-chatbot.kidjamo.app 8.8.8.8
echo.

echo [2] Verification avec Cloudflare DNS (1.1.1.1)
echo ------------------------------------------------------------
nslookup chatbot.kidjamo.app 1.1.1.1
echo.
nslookup api-chatbot.kidjamo.app 1.1.1.1
echo.

echo ============================================================
echo Si vous voyez "52.30.79.88" pour les deux, c'est OK!
echo Sinon, verifiez la configuration dans votre registrar.
echo ============================================================
pause

