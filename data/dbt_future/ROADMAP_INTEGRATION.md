# Evolution prévue : Quand intégrer dbt

## Phase actuelle ✅ (Vous êtes ici)
- Pipeline PySpark fonctionnelle (raw→bronze→silver→gold)
- Jobs ETL complets avec logique médicale
- Tests et monitoring de base
- **→ Continuez avec votre architecture actuelle**

## Phase 2 🔄 (Dans 3-6 mois)
**Signaux d'activation dbt :**
- Équipes médicales veulent modifier les seuils sans développeur
- Plus de 10+ transformations SQL répétitives
- Besoin de documentation automatique pour audits
- **→ Intégrez dbt en complément (pas en remplacement)**

## Phase 3 🚀 (Maturité)
**Migration hybride :**
- Jobs PySpark pour ingestion lourde (raw→bronze)
- dbt pour transformations business (bronze→silver→gold)
- Tests de qualité automatisés avec dbt
- Documentation et lineage complets

## Priorisation immédiate 🎯
1. **Finalisez votre batch_etl** (plus urgent)
2. **Stabilisez votre pipeline streaming**
3. **Complétez vos tests d'intégration**
4. **dbt plus tard** quand le besoin se fera sentir

Le dossier dbt_future reste disponible pour quand vous en aurez besoin.
