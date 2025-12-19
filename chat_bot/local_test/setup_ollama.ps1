# Script d'installation d'Ollama pour l'IA locale
# Exécuter en tant qu'administrateur

Write-Host "🤖 INSTALLATION D'OLLAMA POUR L'IA LOCALE KIDJAMO" -ForegroundColor Green
Write-Host "=================================================="

# Télécharger Ollama
Write-Host "📥 Téléchargement d'Ollama..."
Invoke-WebRequest -Uri "https://ollama.ai/download/windows" -OutFile "$env:TEMP\ollama-windows-amd64.exe"

# Installer Ollama
Write-Host "🔧 Installation d'Ollama..."
Start-Process "$env:TEMP\ollama-windows-amd64.exe" -Wait

# Démarrer Ollama
Write-Host "🚀 Démarrage d'Ollama..."
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden

# Attendre le démarrage
Start-Sleep 10

# Télécharger le modèle médical
Write-Host "📚 Téléchargement du modèle IA médical (llama3.1:8b)..."
Write-Host "⚠️  Cela peut prendre 10-15 minutes selon votre connexion"
ollama pull llama3.1:8b

Write-Host "✅ Installation terminée !" -ForegroundColor Green
Write-Host "🔄 Redémarrez votre chatbot pour utiliser l'IA locale"
