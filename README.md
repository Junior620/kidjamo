# RAPPORT D'AUDIT - PIPELINE D'INGESTION LOCALE DRÉPANOCYTOSE

**Date d'audit**: 2025-08-17  
**Auditeur**: Système automatisé  
**Scope**: Pipeline ETL local (landing → raw → bronze → silver → gold)  
**Environnement**: Windows, PySpark 3.5.5, Python Anaconda  

---

## A. RÉSUMÉ EXÉCUTIF

🔴 **STATUT GLOBAL: ROUGE - NON CONFORME**

### Risques Majeurs Identifiés:
1. **CRITIQUE**: Structure de données bronze conflictuelle (répertoires bronze/quarantine incompatibles)
2. **CRITIQUE**: Absence totale des seuils physiologiques par âge requis par le cahier des charges
3. **CRITIQUE**: Aucune règle hors-ligne d'alerte vitale implémentée (SpO₂ < 88%, T° > 38,5°C)

### Actions Critiques (7 jours max):
1. Refactorer la structure bronze pour éliminer les conflits de partitionnement
2. Implémenter le JSON de configuration des seuils physiologiques par âge (G1-G6)
3. Développer le moteur d'alertes hors-ligne avec combinaisons critiques

---

## B. SCORECARD DÉTAILLÉE

| Catégorie | Règle | Résultat | Mesure | Preuve | Remédiation |
|-----------|--------|----------|---------|---------|-------------|
| **KPI & Performance** | Capacité ≥ 2× pic dimensionné | 🟡 WARN | Non testé (erreur structure) | test_minimal.py:15 | Corriger structure bronze avant bench |
| **KPI & Performance** | Latence P95 < 5s | ❌ FAIL | Non mesurable | Erreur Java Spark | Fix: Séparer bronze/quarantine |
| **Qualité Données** | % échantillons valides ≥ 95% | ❌ FAIL | Non calculé | Absence de DQ rules | Implémenter Great Expectations |
| **Seuils Physiologiques** | Tables JSON par âge G1-G6 | ❌ FAIL | 0/6 groupes | Aucun fichier JSON | Créer medical_thresholds.json |
| **Alertes Hors-ligne** | SpO₂ < 88% → alerte immédiate | ❌ FAIL | Non implémenté | 03_bronze_to_silver.py | Ajouter offline_alerts.py |
| **Alertes Hors-ligne** | T° ≥ 38,5°C → alerte critique | ❌ FAIL | Non implémenté | Seuil hardcodé 38.5 | Engine avec JSON config |
| **Combinaisons Critiques** | C1: Fièvre + SpO₂ basse | ❌ FAIL | 0/10 combos | Logique absente | Module combinations_engine.py |
| **Sécurité** | Secrets non hardcodés | 🟡 WARN | Salt hardcodé | pseudonymization.py:17 | Utiliser .env |
| **Sécurité** | Hachage patient_id | ✅ PASS | SHA256 + salt | security/pseudonymization.py | Bon |
| **Observabilité** | Métriques latence exportées | ❌ FAIL | Aucune métrique | Logs basiques uniquement | Module metrics_exporter.py |
| **Partitionnement** | Stockage Parquet+Snappy | ✅ PASS | Parquet confirmé | .parquet files | Bon |
| **Partitionnement** | Partition par date/heure | 🟡 WARN | Date seulement | event_date=2025-08-17 | Ajouter hour partition |

---

## C. MESURES CLÉS (ÉCHEC DU BENCHMARK)

**⚠️ IMPOSSIBLE DE MESURER LES KPI CRITIQUES** à cause de l'erreur structurelle:

```
java.lang.AssertionError: Conflicting directory structures detected:
- file:/d:/kidjamo-workspace/ingestion/bronze
- file:/d:/kidjamo-workspace/ingestion/bronze/quarantine
```

### Métriques Attendues vs Observées:
- **P50/P95/P99 latence**: INDISPONIBLE (doit être < 5s P95)
- **Throughput**: INDISPONIBLE (cible: 300 patients @ 0,2 Hz)
- **% valide**: INDISPONIBLE (requis: ≥ 95%)
- **Dérive SpO₂/T° 24h**: NON IMPLÉMENTÉ
- **#alertes par type**: ZÉRO (aucune alerte active)

---

## D. ANOMALIES & SEUILS

### Tests Unitaires Critiques Manquants (10 requis):

| Cas de Test | Valeur | Attendu | Observé | Verdict |
|-------------|--------|---------|---------|---------|
| SpO₂ critique | 87% | ALERTE immediate | Aucune | ❌ FAIL |
| SpO₂ limite | 90% | ALERTE si >30s | Aucune | ❌ FAIL |
| T° urgence adulte | 38.6°C | CRITICAL | Classification basic | ❌ FAIL |
| T° urgence enfant 0-1an | 38.0°C | CRITICAL | Non différencié | ❌ FAIL |
| FC tachycardie G5 | 120 bpm | ALERTE | "tachycardia" label | 🟡 WARN |
| FR enfant G2 | 45/min | URGENCE | Non implémenté | ❌ FAIL |
| Combo C1 | T°=38.2 + SpO₂=91% | CRITICAL combo | Aucune | ❌ FAIL |
| Hydratation critique | 45% | URGENCE | Score basic | ❌ FAIL |
| HI chaleur + activité | HI=41°C + activité élevée | ALERTE | Non calculé | ❌ FAIL |
| Flatline capteur | 90s identique | PANNE alerte | Non détecté | ❌ FAIL |

---

## E. SÉCURITÉ (LOCAL)

### Trouvailles Sécurité:

| Trouvaille | Gravité | Localisation | Action |
|------------|---------|--------------|---------|
| Salt hardcodé en clair | 🟡 MEDIUM | pseudonymization.py:11 | Migrer vers .env |
| Absence .env | 🟡 MEDIUM | Racine projet | Créer .env.template |
| Logs sensibles possibles | 🟠 LOW | Jobs Spark stdout | Audit logs médicaux |
| Idempotence manquante | 🔴 HIGH | Jobs ETL | Implémenter clés de déduplication |

### Checklist Sécurité:
- ❌ Secrets externalisés (.env)
- ✅ Hachage PII (SHA256)
- ❌ Rotation clés
- ❌ Audit logs accès
- 🟡 Chiffrement au repos (Parquet non chiffré)

---

## F. PLAN D'ACTION (7-14 JOURS)

### 🔥 PRIORITÉ 1 (2-3 jours)

**1. Corriger Structure Bronze**
- **Owner**: DevOps
- **Effort**: 4h
- **Action**: Séparer bronze/quarantine avec basePath distinct
- **Test**: `spark.read.option("basePath", "bronze").parquet("bronze/event_date=*")`

**2. Implémenter Seuils Physiologiques JSON**
- **Owner**: Data Engineer
- **Effort**: 8h
- **Action**: Créer `conf/medical_thresholds.json` avec groupes G1-G6
- **Test**: `python test_thresholds_compliance.py`

**3. Engine Alertes Hors-ligne**
- **Owner**: ML Engineer
- **Effort**: 12h
- **Action**: Module `offline_alerts_engine.py` avec 10 combinaisons critiques
- **Test**: `python test_critical_alerts.py --scenario emergency`

### 🟡 PRIORITÉ 2 (4-7 jours)

**4. Métriques & Observabilité**
- **Owner**: DevOps
- **Effort**: 6h
- **Action**: Exporter P50/P95/P99, throughput vers CSV
- **Test**: `python benchmark_performance.py --patients 300`

**5. Great Expectations DQ**
- **Owner**: Data Engineer
- **Effort**: 10h
- **Action**: Suite expectations avec ≥95% validation rate
- **Test**: `great_expectations checkpoint run medical_pipeline`

### 🔵 PRIORITÉ 3 (8-14 jours)

**6. Sécurité Avancée**
- **Effort**: 4h
- **Action**: .env, rotation salt, audit logs
- **Test**: Security scan + penetration test local

**7. Détection Anomalies Capteurs**
- **Effort**: 8h
- **Action**: Flatline 60s, pertes >20%/5min, batterie <15%
- **Test**: Injection de données synthétiques de panne

---

## G. ANNEXES

### Scripts de Test Générés:

```bash
# Performance Benchmark
python scripts/generate_synthetic_load.py --patients 300 --frequency 0.2Hz --duration 10min
python scripts/benchmark_pipeline.py --measure-latency --export-csv

# Validation Seuils
python scripts/test_physiological_thresholds.py --age-groups G1,G2,G3,G4,G5,G6
python scripts/test_critical_combinations.py --scenarios fever_hypoxia,dehydration_heat

# Tests de Pannes
python scripts/inject_sensor_failures.py --type flatline,battery_low,signal_loss
```

### Commandes de Correction Immédiate:

```bash
# 1. Fix structure bronze
mkdir -p bronze_clean
spark.read.option("basePath", "bronze").parquet("bronze/event_date=*").write.parquet("bronze_clean")

# 2. Créer template seuils
cp templates/medical_thresholds_template.json conf/medical_thresholds.json

# 3. Tester pipeline réparé
python run_pipeline.py --validate-thresholds --export-metrics
```

---

**CONCLUSION**: Le pipeline nécessite une refonte critique des composants d'alerte médicale et de structure de données avant toute mise en production. Les risques vitaux (absence d'alertes SpO₂/température) rendent le système non conforme aux exigences de santé.

**Signature audit**: Système automatisé kidjamo-workspace v2025.08.17
