# 📊 Dashboard PowerBI Minimaliste - Spécifications Détaillées

## 🎯 Vue d'ensemble

Dashboard temps réel pour le monitoring médical IoT avec focus sur les signes vitaux essentiels et la température ambiante. Conçu pour une visualisation claire et une prise de décision rapide.

---

## 📋 Étape 2: Spécifications Dashboard PowerBI Minimaliste (6h)

### **Phase 1: Connexion et Sources de Données (1h)**

#### **Source de Données Principale:**
- **Type:** PostgreSQL Local
- **Serveur:** localhost:5432
- **Base:** kidjamo-db
- **Tables principales:**
  - `measurements` (données temps réel)
  - `alerts` (alertes simples)
  - `composite_alerts` (alertes composées)

#### **Requêtes DirectQuery Optimisées:**
```sql
-- Vue principale temps réel (dernières 24h)
CREATE VIEW dashboard_realtime AS
SELECT 
    patient_id,
    device_id,
    recorded_at,
    freq_card,
    spo2_pct,
    temp_corp,
    temp_ambiante,
    freq_resp,
    pct_hydratation,
    activity,
    heat_index,
    quality_flag
FROM measurements 
WHERE recorded_at >= NOW() - INTERVAL '24 hours'
AND quality_flag != 'ERROR';

-- Vue alertes actives
CREATE VIEW dashboard_alerts AS
SELECT 
    a.patient_id,
    a.severity,
    a.alert_type,
    a.title,
    a.created_at,
    COUNT(*) OVER (PARTITION BY a.patient_id) as alert_count
FROM alerts a
WHERE a.ack_deadline > NOW()
UNION ALL
SELECT 
    ca.patient_id,
    ca.severity,
    'COMPOSITE' as alert_type,
    ca.title,
    ca.created_at,
    COUNT(*) OVER (PARTITION BY ca.patient_id) as alert_count
FROM composite_alerts ca
WHERE ca.expires_at > NOW();
```

---

## 🏗️ Structure du Dashboard

### **Page 1: Vue Globale Temps Réel**

#### **📊 Graphiques Essentiels (Chaque mesure = 1 graphique)**

**1. 💓 Fréquence Cardiaque (freq_card)**
- **Type:** Graphique en courbes avec zones de seuils
- **Axe X:** Temps (dernières 4h, rafraîchi toutes les 30s)
- **Axe Y:** BPM (0-200)
- **Zones colorées:**
  - 🔴 Critique: < 40 ou > 140 bpm
  - 🟠 Attention: 40-60 ou 120-140 bpm
  - 🟢 Normal: 60-120 bpm
- **KPIs associés:**
  - Valeur actuelle (grande police)
  - Min/Max dernières 24h
  - Tendance (↗️↘️➡️)
  - Temps depuis dernière mesure

**2. 🫁 Saturation Oxygène (spo2_pct)**
- **Type:** Gauge semi-circulaire + courbe temporelle
- **Plage:** 80-100%
- **Zones colorées:**
  - 🔴 Critique: < 85%
  - 🟠 Bas: 85-92%
  - 🟡 Attention: 92-95%
  - 🟢 Normal: 95-100%
- **KPIs associés:**
  - % actuel (grande police)
  - Nombre de désaturations/jour
  - Durée moyenne des épisodes bas
  - Alerte si < 90% pendant > 5min

**3. 🌡️ Température Corporelle (temp_corp)**
- **Type:** Thermomètre virtuel + courbe temporelle
- **Plage:** 32-42°C
- **Zones colorées:**
  - 🔴 Critique: < 34°C ou > 40°C
  - 🟠 Attention: 34-36°C ou 38.5-40°C
  - 🟢 Normal: 36-37.2°C
  - 🟡 Fièvre: 37.2-38.5°C
- **KPIs associés:**
  - Température actuelle (1 décimale)
  - Variation dernières 6h
  - Pic fébrile (si > 38°C)
  - Durée épisode fébrile

**4. 🏠 Température Ambiante (temp_ambiante)**
- **Type:** Gauge horizontale + historique 24h
- **Plage:** 10-40°C
- **Zones colorées:**
  - 🔴 Extrême: < 15°C ou > 32°C
  - 🟠 Inconfortable: 15-18°C ou 28-32°C
  - 🟢 Confort: 18-25°C
  - 🟡 Chaud: 25-28°C
- **KPIs associés:**
  - Température ambiante actuelle
  - Min/Max journaliers
  - Écart optimal (vs 20-22°C)
  - Impact potentiel sur patient
  - Corrélation avec temp corporelle

**5. 🫀 Fréquence Respiratoire (freq_resp)**
- **Type:** Graphique à barres temporelles
- **Plage:** 5-35 respirations/min
- **Zones colorées:**
  - 🔴 Critique: < 8 ou > 30
  - 🟠 Attention: 8-12 ou 25-30
  - 🟢 Normal: 12-20
  - 🟡 Élevé: 20-25
- **KPIs associés:**
  - Fréquence actuelle
  - Variabilité respiratoire
  - Episodes de tachypnée (>25/min)
  - Synchronisation avec FC

**6. 💧 Hydratation (pct_hydratation)**
- **Type:** Barre de progression + tendance
- **Plage:** 30-100%
- **Zones colorées:**
  - 🔴 Déshydratation sévère: < 45%
  - 🟠 Déshydratation: 45-60%
  - 🟢 Normal: 60-80%
  - 🔵 Hyperhydratation: > 90%
- **KPIs associés:**
  - % hydratation actuel
  - Variation 12h
  - Besoin hydratation estimé
  - Corrélation avec température

---

### **📈 KPIs Globaux Dashboard**

#### **Vue d'ensemble (Header Dashboard):**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🏥 KIDJAMO - Monitoring Temps Réel                    ⏰ 14:32:15      │
├─────────────────────────────────────────────────────────────────────────┤
│ 👥 5 Patients  │ 🔴 2 Alertes  │ 🟡 1 Attention  │ ✅ Système OK    │
└─────────────────────────────────────────────────────────────────────────┘
```

#### **KPIs Principaux:**

**🎯 Indicateurs Patients:**
- **Patients connectés:** Nombre total avec données récentes (< 5min)
- **Patients critiques:** Avec alertes niveau CRITICAL
- **Patients stables:** Tous paramètres dans normes
- **Dernière mise à jour:** Timestamp de la dernière mesure

**⚠️ Indicateurs Alertes:**
- **Alertes actives:** Nombre total non acquittées
- **Alertes critiques:** Niveau CRITICAL non traitées
- **Temps réponse moyen:** Délai entre alerte et acquittement
- **Taux faux positifs:** % alertes annulées rapidement

**🌡️ Indicateurs Environnementaux:**
- **Température ambiante moyenne:** Across all devices
- **Zones hors confort:** Nombre de devices > 32°C ou < 16°C
- **Corrélation temp:** Impact temp ambiante sur temp corporelle
- **Alerte climatisation:** Si temp ambiante critique

**📊 Indicateurs Performance:**
- **Qualité données:** % mesures avec quality_flag = 'GOOD'
- **Connectivité devices:** % devices actifs vs total
- **Latence système:** Temps traitement dernière mesure
- **Disponibilité:** Uptime système alertes

---

### **🎨 Éléments Visuels Spécialisés**

#### **1. Matrice de Corrélation Temps Réel:**
```
        FC    SpO2   T°Corp  T°Amb  F°Resp  Hydr
FC      1.0   -0.3    0.7    0.2    0.5    -0.2
SpO2   -0.3    1.0   -0.1   -0.1   -0.6     0.1
T°Corp  0.7   -0.1    1.0    0.4    0.3    -0.3
T°Amb   0.2   -0.1    0.4    1.0    0.1    -0.1
F°Resp  0.5   -0.6    0.3    0.1    1.0    -0.2
Hydr   -0.2    0.1   -0.3   -0.1   -0.2     1.0
```

#### **2. Heatmap État Patients:**
```
Patient    FC   SpO2  T°Corp  T°Amb  F°Resp  Hydr  Status
P001      🟢    🟢     🟡     🟢     🟢     🟢    Stable
P002      🔴    🟠     🔴     🟠     🟠     🟡    CRITIQUE
P003      🟢    🟢     🟢     🟢     🟢     🟢    Optimal
P004      🟡    🟢     🟢     🔴     🟢     🟢    Attention
P005      🟢    🟡     🟡     🟢     🟢     🟢    Surveillance
```

#### **3. Timeline Alertes Interactive:**
```
Timeline 24h:  |----🔴---|-----🟡----|--------🟢--------|
               00:00    06:00      12:00           18:00   24:00
Événements:    3 Crit   1 High     Stable          
```

---

### **📱 Layout Responsive**

#### **Vue Desktop (1920x1080):**
```
┌─────────────────────────────────────────────────────────────┐
│ Header KPIs Globaux                                         │
├──────────────┬──────────────┬──────────────┬───────────────┤
│ FC Chart     │ SpO2 Gauge   │ T°Corp Therm │ T°Amb Gauge   │
├──────────────┼──────────────┼──────────────┼───────────────┤
│ F°Resp Bars  │ Hydrat Prog  │ Corrélation  │ Alertes List  │
├──────────────┴──────────────┴──────────────┴───────────────┤
│ Heatmap Patients + Timeline Alertes                        │
└─────────────────────────────────────────────────────────────┘
```

#### **Vue Tablet (1024x768):**
```
┌─────────────────────────────────────┐
│ Header KPIs                         │
├─────────────────┬───────────────────┤
│ FC Chart        │ SpO2 Gauge        │
├─────────────────┼───────────────────┤
│ T°Corp Therm    │ T°Amb Gauge       │
├─────────────────┼───────────────────┤
│ F°Resp Bars     │ Hydrat Progress   │
├─────────────────┴───────────────────┤
│ Alertes + Status Patients          │
└─────────────────────────────────────┘
```

---

### **🔄 Rafraîchissement et Temps Réel**

#### **Stratégie de Mise à Jour:**
- **DirectQuery:** Connection temps réel à PostgreSQL
- **Rafraîchissement:** Toutes les 30 secondes
- **Cache intelligent:** Données historiques mises en cache
- **Push notifications:** Alertes critiques en popup

#### **Paramètres de Performance:**
```powerquery
// Optimisation requêtes
let
    Source = PostgreSQL.Database("localhost", "kidjamo-db"),
    LastMeasurements = Source{[Schema="public",Item="dashboard_realtime"]}[Data],
    FilteredRows = Table.SelectRows(LastMeasurements, 
        each DateTime.IsInPreviousNHours([recorded_at], 4)),
    SortedRows = Table.Sort(FilteredRows, {{"recorded_at", Order.Descending}})
in
    SortedRows
```

---

### **⚠️ Système d'Alertes Visuelles**

#### **Codes Couleurs Standardisés:**
- 🔴 **CRITICAL:** Rouge vif (#FF0000) - Action immédiate
- 🟠 **HIGH:** Orange (#FF8C00) - Attention urgente  
- 🟡 **MEDIUM:** Jaune (#FFD700) - Surveillance
- 🟢 **NORMAL:** Vert (#00FF00) - Optimal
- ⚫ **OFFLINE:** Gris (#808080) - Pas de données

#### **Animations d'Alerte:**
- **Critique:** Clignotement rouge + son (si activé)
- **High:** Pulsation orange
- **Medium:** Surbrillance jaune
- **Nouvelle alerte:** Slide-in notification

---

### **📊 Métriques Avancées Température Ambiante**

#### **KPIs Spécialisés:**

**🌡️ Confort Thermique:**
- **Index de confort:** Score 0-100 basé sur plage optimale
- **Zones problématiques:** % temps hors confort (< 18°C ou > 25°C)
- **Variation journalière:** Amplitude thermique sur 24h
- **Prédiction:** Tendance température prochaines 2h

**🏠 Impact Environnemental:**
- **Corrélation T°Amb → T°Corp:** Coefficient de corrélation
- **Stress thermique:** Patients avec T°Corp anormale ET T°Amb extrême
- **Recommandations:** Actions climatisation suggérées
- **Efficacité régulation:** Temps retour zone confort

**📈 Tendances Temporelles:**
- **Patterns journaliers:** Courbe moyenne température par heure
- **Variations saisonnières:** Comparaison avec moyennes historiques
- **Pics d'usage:** Heures où température dépasse seuils
- **Maintenance préventive:** Alertes dysfonctionnement climatisation

---

### **🎯 Widgets Dashboard Prioritaires**

#### **Widget 1: Status Instantané**
```
┌─────────────────────────────────┐
│ Patient P001 - Chambre 201      │
├─────────────────────────────────┤
│ 💓 FC: 78 bpm     🟢           │
│ 🫁 SpO2: 97%      🟢           │
│ 🌡️ T°: 36.8°C     🟢           │
│ 🏠 Amb: 22.1°C    🟢           │
│ 🫀 FR: 16/min     🟢           │
│ 💧 Hydr: 72%      🟢           │
└─────────────────────────────────┘
```

#### **Widget 2: Alertes Actives**
```
┌─────────────────────────────────┐
│ 🔴 ALERTE CRITIQUE             │
├─────────────────────────────────┤
│ P002: Hypoxémie sévère          │
│ SpO2: 84% (< 85%)              │
│ 🕐 14:28 (il y a 4 min)        │
│                                 │
│ [ACQUITTER] [DÉTAILS]          │
└─────────────────────────────────┘
```

#### **Widget 3: Tendances Environnementales**
```
┌─────────────────────────────────┐
│ 🌡️ CONTRÔLE CLIMATIQUE         │
├─────────────────────────────────┤
│ T° Moyenne: 23.2°C 🟢          │
│ Zones Confort: 4/5 🟢          │
│ Zone Alerte: Chambre 203 🔴     │
│ T° Critique: 34.5°C             │
│                                 │
│ [AJUSTER CLIM] [RAPPORT]        │
└─────────────────────────────────┘
```

---

### **🚀 Phase d'Implémentation (6h)**

#### **Heure 1: Setup et Connexions**
- Installation PowerBI Desktop
- Configuration connexion PostgreSQL
- Test requêtes de base
- Import tables principales

#### **Heure 2-3: Graphiques Vitaux Essentiels** 
- Création graphique Fréquence Cardiaque
- Implémentation gauge SpO2
- Thermomètre température corporelle
- Configuration zones de seuils

#### **Heure 4: Température Ambiante et Environnement**
- Gauge température ambiante
- Corrélations environnementales
- KPIs confort thermique
- Alertes climatisation

#### **Heure 5: Finalisation et Alertes**
- Fréquence respiratoire
- Hydratation
- Système alertes visuelles
- Tests temps réel

#### **Heure 6: Optimisation et Tests**
- Performance DirectQuery
- Responsive design
- Validation données
- Documentation

---

**📅 Livrable Final:** Dashboard PowerBI opérationnel avec monitoring temps réel de tous les paramètres vitaux incluant surveillance avancée de la température ambiante.

**🎯 Objectif:** Outil de monitoring médical professionnel permettant détection immédiate des anomalies et prise de décision éclairée.
