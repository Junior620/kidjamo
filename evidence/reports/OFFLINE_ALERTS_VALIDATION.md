# Rapport de Validation — Règles Offline & Observabilité (Kidjamo)

Date: 2025-08-18 18:41

A. Résumé exécutif
- Feu: ORANGE — Règles critiques offline implémentées côté API; observabilité de base en place; quelques lacunes sur HR/RR par âge et bench charge non exécuté.
- 3 risques majeurs:
  1) Fichier offline_alerts_engine.py partiellement corrompu — risque de régression si utilisé directement.
  2) Pseudonymisation legacy avec salt hardcodé (data/security/pseudonymization.py) — dette sécurité.
  3) Pas encore de bench charge 300 patients ni métrique FP/FN pannes calculées.
- 3 actions critiques:
  1) Finaliser règles FR/FC par âge dans moteur hors‑ligne + tests (7 jours).
  2) Retirer salt hardcodé et centraliser via pseudonymization_secure (1 jour).
  3) Script de bench + collecte métriques FP/FN et délais d’alerte (3–5 jours).

B. Scorecard
| Catégorie | Règle | Résultat | Mesure | Preuve | Remédiation |
|---|---|---|---|---|---|
| Seuils | SpO₂<88% => alerte immédiate | PASS | Déclenchement CRITICAL_SPO2 | tests/unit/test_offline_rules_api.py::test_spo2_87_triggers_critical_immediate | PR: iot_ingestion_api.py check_critical_vitals (diff)
| Seuils | SpO₂=89% pas d’alerte critique | PASS | Aucune alerte CRITICAL_SPO2 | tests/...::test_spo2_89_no_critical_immediate | idem
| Seuils | T°≥38.5°C => alerte immédiate | PASS | CRITICAL_TEMPERATURE | tests/...::test_temp_38_6_triggers_critical_immediate | idem
| Seuils | T°=38.0°C pas critique | PASS | Pas de CRITICAL_TEMPERATURE | tests/...::test_temp_38_0_not_critical_immediate | idem
| Combinaisons | Fièvre + SpO₂ basse | PASS | CRITICAL_COMBINATION_FEVER_SPO2 | tests/...::test_combo_fever_low_spo2_boundary | idem
| Schéma alerte | severity + reasons présents | PASS | Champs présents | tests/...::test_alert_schema_contains_severity_and_reasons | idem
| Offline | Sans cloud, alerte locale | PASS | Retour API contient critical_alerts même si Kafka down | logs/ (API), code ligne warn offline | iot_ingestion_api.py: warning + continuité locale
| Sécurité | PII masqué et hash | PASS | patient_id_hash dans erreurs/alertes | evidence/metrics/ingestion_metrics.csv; code process_critical_alerts | Appliquer partout (moteur offline)
| Sécurité | Secrets en clair | WARN | Salt hardcodé legacy | data/security/pseudonymization.py | Remplacer par secure (PR à faire)
| Observabilité | Export CSV métriques | PASS | ingestion_metrics.csv | evidence/metrics/ingestion_metrics.csv | Étendre avec alert delays

C. Mesures clés
- Latence (API, instantané via /metrics): P50/P95/P99 — voir /metrics JSON et evidence/metrics/ingestion_metrics.csv
- Throughput: events/sec (API) — champ throughput_eps (/metrics)
- %valide (qualité): %valid (/metrics)
- Dérive SpO₂/T°: à instrumenter via batch (proposé)
- #alertes par type: alerts_by_type (/metrics)
- Délais alerte (local/cloud simulé): local ≈ latence API; cloud = non mesuré (Kafka non requis offline)
- %FP pannes: non mesuré (scripts pannes à exécuter)

D. Anomalies & Seuils
- Cas → Attendu → Observé → Verdict:
  - SpO₂=87% → CRITICAL_SPO2 → CRITICAL_SPO2 → PASS
  - SpO₂=89% → pas CRITICAL_SPO2 → pas CRITICAL_SPO2 → PASS
  - T°=38.0°C → pas CRITICAL_TEMPERATURE → pas CRITICAL_TEMPERATURE → PASS
  - T°=38.6°C → CRITICAL_TEMPERATURE → CRITICAL_TEMPERATURE → PASS
  - Fièvre 38.0 + SpO₂ 92 → Combo CRITICAL → CRITICAL → PASS
  - Fièvre 38.4 + SpO₂ 93 → pas Combo → pas Combo → PASS
  - HR 181 → CRITICAL_HEART_RATE → CRITICAL → PASS
  - HR 39 → CRITICAL_HEART_RATE → CRITICAL → PASS
  - Schéma alerte → severity+reasons → présents → PASS
  - Tables âge → présentes JSON → OK → PASS
- 10 tests unitaires limites inclus: tests/unit/test_offline_rules_api.py

E. Sécurité (local)
- Trouvailles:
  - Pseudonymisation sécurisé OK (data/security/pseudonymization_secure.py) avec rotation basique. Gravité: Medium.
  - Module legacy avec salt hardcodé (data/security/pseudonymization.py). Gravité: High.
  - PII masqué dans erreurs API; hash présent dans alertes. Gravité: Low.
- Check-list: secrets (WARN legacy), PII (PASS), idempotence ingestion (WARN: non garanti), logs d’accès (BASIC), rotation clés (BASIC via .env, last_key_rotation.json)

F. Plan d’action (7–14 jours)
1) Remplacer pseudonymization.py par pseudonymization_secure (Owner: SecData, Effort: 1j) — PRD: retirer salt par défaut; Test: import + hash.
2) Corriger fichier ingestion/jobs/offline_alerts_engine.py (Owner: Ingestion, Effort: 2j) — PRD: réparer sections corrompues; Test: unit + flatline.
3) Implémenter FR/FC par âge dans API ou moteur (Owner: MedLogic, Effort: 2–3j) — PRD: mapping JSON; Test: seuils G1–G6.
4) Script bench 300 patients 0.2 Hz 10 min (Owner: Perf, Effort: 2j) — PRD: générateur + mesure p95<5s; Test: pytest mark perf.
5) Pannes synthétiques (flatline/pertes/batterie/heartbeat) (Owner: QA, Effort: 2j) — PRD: séries + %FP; Test: assertions.
6) Tableau de bord statique (Owner: Obs, Effort: 1j) — PRD: CSV→MD; Test: artifacts présents.
7) Idempotence ingestion (Owner: Platform, Effort: 1–2j) — PRD: message_id dédup; Test: envoi doublon.

G. Annexes
- Scripts de génération: evidence/scripts/generate_test_cases.py (à compléter pour charge/pannes)
- Commandes bench: pytest -q tests/unit/test_offline_rules_api.py; curl http://localhost:8001/metrics
- Exports CSV: evidence/metrics/ingestion_metrics.csv (s’alimente à l’appel API)
- Expectations GE: à définir (proposé dans PR ultérieure)

Preuves clés:
- Code: data/pipelines/iot_streaming/pipeline_iot_streaming_kafka_local/api/iot_ingestion_api.py (modifié)
- Tests: tests/unit/test_offline_rules_api.py
- Seuils: data/configs/medical_thresholds.json
- Métriques: evidence/metrics/ingestion_metrics.csv
