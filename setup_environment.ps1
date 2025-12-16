# KIDJAMO - SCRIPT DE CONFIGURATION ENVIRONNEMENT
# Automatise la configuration des variables d'environnement pour IoT cloud

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("local", "cloud", "production")]
    [string]$Environment = "local",

    [Parameter(Mandatory=$false)]
    [switch]$SetupAWS,

    [Parameter(Mandatory=$false)]
    [switch]$TestConnection
)

Write-Host "🚀 KIDJAMO - Configuration Environnement IoT" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""

# Fonction pour charger les variables d'environnement
function Load-EnvironmentFile {
    param([string]$FilePath)

    if (Test-Path $FilePath) {
        Get-Content $FilePath | ForEach-Object {
            if ($_ -match '^([^#][^=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
                Write-Host "✅ $name configuré" -ForegroundColor Green
            }
        }
        Write-Host "📁 Fichier $FilePath chargé avec succès" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Fichier $FilePath introuvable" -ForegroundColor Red
        exit 1
    }
}

# Fonction pour vérifier les credentials AWS
function Test-AWSCredentials {
    Write-Host "🔍 Vérification des credentials AWS..." -ForegroundColor Yellow

    try {
        $env:AWS_ACCESS_KEY_ID = $env:AWS_ACCESS_KEY_ID
        $env:AWS_SECRET_ACCESS_KEY = $env:AWS_SECRET_ACCESS_KEY

        if ([string]::IsNullOrEmpty($env:AWS_ACCESS_KEY_ID)) {
            Write-Host "⚠️  AWS_ACCESS_KEY_ID non configuré - Mode local activé" -ForegroundColor Yellow
            return $false
        }

        # Test simple de connexion AWS (nécessite AWS CLI)
        $result = aws sts get-caller-identity 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Credentials AWS valides" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Credentials AWS invalides" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "⚠️  AWS CLI non installé - Mode local recommandé" -ForegroundColor Yellow
        return $false
    }
}

# Fonction pour tester la connexion base de données
function Test-DatabaseConnection {
    Write-Host "🗄️  Test connexion base de données..." -ForegroundColor Yellow

    $dbHost = $env:DB_HOST
    $dbPort = $env:DB_PORT
    $dbName = $env:DB_NAME
    $dbUser = $env:DB_USER
    $dbPassword = $env:DB_PASSWORD

    # Test de connexion simple avec psql (si disponible)
    try {
        $env:PGPASSWORD = $dbPassword
        $result = psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c "SELECT 1;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Connexion base de données réussie" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Impossible de se connecter à la base de données" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "⚠️  psql non disponible - Test de connexion ignoré" -ForegroundColor Yellow
        return $false
    }
}

# Fonction principale de configuration
function Setup-Environment {
    param([string]$EnvType)

    Write-Host "⚙️  Configuration pour environnement: $EnvType" -ForegroundColor Cyan

    switch ($EnvType) {
        "local" {
            Load-EnvironmentFile ".env.local"
            Write-Host "🏠 Mode local configuré - Utilisation des fichiers CSV" -ForegroundColor Green
        }
        "cloud" {
            if (Test-Path ".env") {
                Load-EnvironmentFile ".env"
            } else {
                Write-Host "❌ Fichier .env introuvable" -ForegroundColor Red
                Write-Host "💡 Créez .env en copiant .env.template et en remplissant vos valeurs" -ForegroundColor Yellow
                exit 1
            }
            Write-Host "☁️  Mode cloud configuré - Utilisation d'AWS" -ForegroundColor Green
        }
        "production" {
            if (Test-Path ".env.production") {
                Load-EnvironmentFile ".env.production"
            } else {
                Write-Host "❌ Fichier .env.production introuvable" -ForegroundColor Red
                exit 1
            }
            Write-Host "🏭 Mode production configuré" -ForegroundColor Green
        }
    }
}

# Fonction pour créer les ressources AWS (optionnel)
function Setup-AWSResources {
    Write-Host "🌩️  Configuration des ressources AWS..." -ForegroundColor Cyan

    # Créer le bucket S3
    if (![string]::IsNullOrEmpty($env:LANDING_BUCKET)) {
        Write-Host "📦 Création du bucket S3: $($env:LANDING_BUCKET)" -ForegroundColor Yellow
        aws s3 mb s3://$($env:LANDING_BUCKET) --region $($env:AWS_DEFAULT_REGION) 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Bucket S3 créé/vérifié" -ForegroundColor Green
        }
    }

    # Créer la file SQS
    if (![string]::IsNullOrEmpty($env:SQS_QUEUE_NAME)) {
        Write-Host "📬 Création de la file SQS: $($env:SQS_QUEUE_NAME)" -ForegroundColor Yellow
        aws sqs create-queue --queue-name $($env:SQS_QUEUE_NAME) --region $($env:AWS_DEFAULT_REGION) 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ File SQS créée/vérifiée" -ForegroundColor Green
        }
    }
}

# Fonction pour afficher le résumé de configuration
function Show-ConfigSummary {
    Write-Host ""
    Write-Host "📋 RÉSUMÉ DE LA CONFIGURATION" -ForegroundColor Green
    Write-Host "============================" -ForegroundColor Green
    Write-Host "Environnement: $Environment" -ForegroundColor Cyan
    Write-Host "Mode pipeline: $($env:PIPELINE_MODE)" -ForegroundColor Cyan
    Write-Host "Base de données: $($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)" -ForegroundColor Cyan

    if ($env:PIPELINE_MODE -eq "cloud") {
        Write-Host "Bucket S3: $($env:LANDING_BUCKET)" -ForegroundColor Cyan
        Write-Host "File SQS: $($env:SQS_QUEUE_NAME)" -ForegroundColor Cyan
    } else {
        Write-Host "Données locales: $($env:LOCAL_DATA_PATH)" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "🚀 Configuration terminée !" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 PROCHAINES ÉTAPES:" -ForegroundColor Yellow
    Write-Host "1. Testez la pipeline: python ingestion/run_pipeline.py" -ForegroundColor White
    Write-Host "2. Lancez l'API IoT: python api/iot_ingestion/main.py" -ForegroundColor White
    Write-Host "3. Simulez des données: python generate_test_data.py --patients=5" -ForegroundColor White
}

# SCRIPT PRINCIPAL
# ================

try {
    # Configuration de l'environnement
    Setup-Environment -EnvType $Environment

    # Tests de connexion si demandé
    if ($TestConnection) {
        Write-Host ""
        Write-Host "🔍 TESTS DE CONNEXION" -ForegroundColor Yellow
        Write-Host "=====================" -ForegroundColor Yellow

        if ($env:PIPELINE_MODE -eq "cloud") {
            Test-AWSCredentials
        }
        Test-DatabaseConnection
    }

    # Configuration AWS si demandé
    if ($SetupAWS -and $env:PIPELINE_MODE -eq "cloud") {
        if (Test-AWSCredentials) {
            Setup-AWSResources
        } else {
            Write-Host "❌ Impossible de configurer AWS sans credentials valides" -ForegroundColor Red
        }
    }

    # Affichage du résumé
    Show-ConfigSummary

} catch {
    Write-Host "❌ Erreur lors de la configuration: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Exemples d'utilisation
Write-Host "📖 EXEMPLES D'UTILISATION:" -ForegroundColor Cyan
Write-Host ".\setup_environment.ps1 -Environment local" -ForegroundColor Gray
Write-Host ".\setup_environment.ps1 -Environment cloud -SetupAWS -TestConnection" -ForegroundColor Gray
Write-Host ".\setup_environment.ps1 -Environment production -TestConnection" -ForegroundColor Gray
