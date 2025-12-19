# Script de déploiement du Chatbot Kidjamo
# ========================================

Write-Host "🚀 Déploiement du Chatbot Kidjamo avec Amazon Kendra" -ForegroundColor Green
Write-Host ""

# Vérification des prérequis
Write-Host "📋 Vérification des prérequis..." -ForegroundColor Yellow
if (!(Get-Command terraform -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Terraform n'est pas installé ou pas dans le PATH" -ForegroundColor Red
    exit 1
}

if (!(Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Host "❌ AWS CLI n'est pas installé ou pas dans le PATH" -ForegroundColor Red
    exit 1
}

# Vérification des credentials AWS
Write-Host "🔑 Vérification des credentials AWS..." -ForegroundColor Yellow
try {
    aws sts get-caller-identity | Out-Null
    Write-Host "✅ Credentials AWS configurés" -ForegroundColor Green
} catch {
    Write-Host "❌ Erreur avec les credentials AWS" -ForegroundColor Red
    exit 1
}

# Initialisation Terraform
Write-Host ""
Write-Host "🔧 Initialisation de Terraform..." -ForegroundColor Yellow
terraform init

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors de l'initialisation Terraform" -ForegroundColor Red
    exit 1
}

# Plan Terraform
Write-Host ""
Write-Host "📋 Génération du plan Terraform..." -ForegroundColor Yellow
terraform plan -out=tfplan

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors du plan Terraform" -ForegroundColor Red
    exit 1
}

# Demande de confirmation
Write-Host ""
$confirm = Read-Host "Voulez-vous appliquer ce plan ? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "❌ Déploiement annulé" -ForegroundColor Red
    exit 0
}

# Application du plan
Write-Host ""
Write-Host "🚀 Application du plan Terraform..." -ForegroundColor Yellow
terraform apply tfplan

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Déploiement réussi !" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Informations de sortie :" -ForegroundColor Cyan
    terraform output
} else {
    Write-Host "❌ Erreur lors du déploiement" -ForegroundColor Red
    exit 1
}
