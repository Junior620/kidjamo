# 📊 Formules DAX pour Dashboard PowerBI - Pipeline IoT Kidjamo

## 🎯 Vue d'Ensemble
Ce document contient toutes les formules DAX nécessaires pour créer le dashboard PowerBI de monitoring temps réel du pipeline IoT médical Kidjamo.

---

## 📋 **Structure des Tables de Données**

### **Table: Measurements**
```
patient_id (Text)
device_id (Text)
recorded_at (DateTime)
freq_card (Whole Number) - Fréquence cardiaque
freq_resp (Whole Number) - Fréquence respiratoire
spo2_pct (Decimal Number) - Saturation oxygène %
temp_corp (Decimal Number) - Température corporelle °C
temp_ambiante (Decimal Number) - Température ambiante °C
pct_hydratation (Decimal Number) - Pourcentage hydratation %
activity (Whole Number) - Niveau activité 0-100
heat_index (Decimal Number) - Index chaleur
quality_flag (Text) - Qualité signal
```

### **Table: Alerts**
```
id (Whole Number)
patient_id (Text)
alert_type (Text)
severity (Text)
title (Text)
message (Text)
vitals_snapshot (Text)
created_at (DateTime)
ack_deadline (DateTime)
```

---

## 🎯 **KPIs Principaux (Cartes)**

### **1. Patients Actifs (10 dernières minutes)**
```dax
// Mesure: Patients Actifs
Patients_Actifs = 
CALCULATE(
    DISTINCTCOUNT(Measurements[patient_id]),
    Measurements[recorded_at] >= NOW() - TIME(0,10,0)
)

// Mesure: Couleur Patients Actifs
Couleur_Patients_Actifs = 
VAR PatientsCount = [Patients_Actifs]
RETURN
    SWITCH(
        TRUE(),
        PatientsCount > 5, "Green",      // Vert
        PatientsCount >= 2, "Orange",    // Orange
        "Red"                           // Rouge
    )
```

### **2. Alertes Critiques Actives**
```dax
// Mesure: Alertes Critiques Actives
Alertes_Critiques_Actives = 
CALCULATE(
    COUNTROWS(Alerts),
    Alerts[severity] = "CRITICAL",
    ISBLANK(Alerts[ack_deadline])  // Non accusées
)

// Mesure: Couleur Alertes Critiques
Couleur_Alertes_Critiques = 
VAR AlertesCount = [Alertes_Critiques_Actives]
RETURN
    SWITCH(
        TRUE(),
        AlertesCount > 5, "Red",        // Rouge
        AlertesCount >= 1, "Orange",    // Orange
        "Green"                         // Vert
    )
```

### **3. SpO2 Moyen (24h)**
```dax
// Mesure: SpO2 Moyen 24h
SpO2_Moyen_24h = 
CALCULATE(
    AVERAGE(Measurements[spo2_pct]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur SpO2
Couleur_SpO2 = 
VAR SpO2Value = [SpO2_Moyen_24h]
RETURN
    SWITCH(
        TRUE(),
        SpO2Value >= 95, "Green",       // Vert ≥ 95%
        SpO2Value >= 90, "Orange",      // Orange 90-94%
        "Red"                           // Rouge < 90%
    )

// Mesure: SpO2 Formaté
SpO2_Affichage = 
FORMAT([SpO2_Moyen_24h], "0.0") & "%"
```

### **4. Fréquence Cardiaque Moyenne**
```dax
// Mesure: FC Moyenne 24h
FC_Moyenne_24h = 
CALCULATE(
    AVERAGE(Measurements[freq_card]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur FC
Couleur_FC = 
VAR FCValue = [FC_Moyenne_24h]
RETURN
    SWITCH(
        TRUE(),
        FCValue > 180, "Red",           // Rouge > 180
        FCValue >= 60 && FCValue <= 100, "Green",  // Vert 60-100
        "Orange"                        // Orange hors plage normale
    )

// Mesure: FC Affichage
FC_Affichage = 
FORMAT([FC_Moyenne_24h], "0") & " bpm"
```

### **5. Température Corporelle Moyenne**
```dax
// Mesure: Température Corporelle Moyenne 24h
Temp_Corp_Moyenne_24h = 
CALCULATE(
    AVERAGE(Measurements[temp_corp]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur Température Corporelle
Couleur_Temp_Corp = 
VAR TempValue = [Temp_Corp_Moyenne_24h]
RETURN
    SWITCH(
        TRUE(),
        TempValue > 38, "Red",          // Rouge > 38°C
        TempValue >= 37.5, "Orange",    // Orange 37.5-38°C
        TempValue >= 36, "Green",       // Vert 36-37.5°C
        "Orange"                        // Orange < 36°C (hypothermie)
    )

// Mesure: Température Corporelle Affichage
Temp_Corp_Affichage = 
FORMAT([Temp_Corp_Moyenne_24h], "0.1") & "°C"
```

### **6. Température Ambiante Moyenne**
```dax
// Mesure: Température Ambiante Moyenne 24h
Temp_Amb_Moyenne_24h = 
CALCULATE(
    AVERAGE(Measurements[temp_ambiante]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur Température Ambiante
Couleur_Temp_Amb = 
VAR TempAmbValue = [Temp_Amb_Moyenne_24h]
RETURN
    SWITCH(
        TRUE(),
        TempAmbValue > 30 || TempAmbValue < 15, "Red",      // Rouge > 30°C ou < 15°C
        TempAmbValue >= 25, "Orange",                       // Orange 25-30°C
        TempAmbValue >= 18, "Green",                        // Vert 18-25°C
        "Orange"                                            // Orange < 18°C
    )

// Mesure: Température Ambiante Affichage
Temp_Amb_Affichage = 
FORMAT([Temp_Amb_Moyenne_24h], "0.1") & "°C"
```

### **7. Hydratation Moyenne**
```dax
// Mesure: Hydratation Moyenne 24h
Hydratation_Moyenne_24h = 
CALCULATE(
    AVERAGE(Measurements[pct_hydratation]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur Hydratation
Couleur_Hydratation = 
VAR HydratValue = [Hydratation_Moyenne_24h]
RETURN
    SWITCH(
        TRUE(),
        HydratValue >= 70, "Green",     // Vert ≥ 70%
        HydratValue >= 60, "Orange",    // Orange 60-69%
        "Red"                           // Rouge < 60%
    )

// Mesure: Hydratation Affichage
Hydratation_Affichage = 
FORMAT([Hydratation_Moyenne_24h], "0") & "%"
```

### **8. Niveau d'Activité Moyen**
```dax
// Mesure: Activité Moyenne 24h
Activite_Moyenne_24h = 
CALCULATE(
    AVERAGE(Measurements[activity]),
    Measurements[recorded_at] >= NOW() - 1
)

// Mesure: Couleur Activité
Couleur_Activite = 
VAR ActivityValue = [Activite_Moyenne_24h]
RETURN
    SWITCH(
        TRUE(),
        ActivityValue > 90 || ActivityValue < 10, "Red",    // Rouge extrêmes
        ActivityValue >= 30 && ActivityValue <= 70, "Green", // Vert normal
        "Orange"                                             // Orange modéré
    )

// Mesure: Activité Affichage
Activite_Affichage = 
FORMAT([Activite_Moyenne_24h], "0")
```

### **9. Temps de Réponse Alertes**
```dax
// Mesure: Temps Réponse Moyen (minutes)
Temps_Reponse_Alertes = 
CALCULATE(
    AVERAGEX(
        Alerts,
        DATEDIFF(
            Alerts[created_at],
            COALESCE(Alerts[ack_deadline], NOW()),
            MINUTE
        )
    ),
    NOT(ISBLANK(Alerts[ack_deadline]))
)

// Mesure: Couleur Temps Réponse
Couleur_Temps_Reponse = 
VAR TempReponse = [Temps_Reponse_Alertes]
RETURN
    SWITCH(
        TRUE(),
        TempReponse < 5, "Green",       // Vert < 5 min
        TempReponse <= 15, "Orange",    // Orange 5-15 min
        "Red"                           // Rouge > 15 min
    )

// Mesure: Temps Réponse Affichage
Temps_Reponse_Affichage = 
FORMAT([Temps_Reponse_Alertes], "0.1") & " min"
```

---

## 📊 **Mesures pour Graphiques Temporels**

### **Graphiques Ligne - Mesures par Heure**
```dax
// Table Calendaire pour Axe Temps
Table_Temps = 
ADDCOLUMNS(
    CALENDAR(
        NOW() - 0.2,  // 4.8 heures en arrière
        NOW()
    ),
    "Heure", TIME(HOUR([Date]), MINUTE([Date]), 0)
)

// Mesure: SpO2 par Heure
SpO2_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[spo2_pct]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)

// Mesure: FC par Heure
FC_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[freq_card]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)

// Mesure: Température Corporelle par Heure
Temp_Corp_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[temp_corp]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)

// Mesure: Température Ambiante par Heure
Temp_Amb_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[temp_ambiante]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)

// Mesure: Fréquence Respiratoire par Heure
Freq_Resp_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[freq_resp]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)

// Mesure: Hydratation par Heure
Hydratation_Par_Heure = 
CALCULATE(
    AVERAGE(Measurements[pct_hydratation]),
    Measurements[recorded_at] >= SELECTEDVALUE(Table_Temps[Date]) - TIME(0,30,0),
    Measurements[recorded_at] < SELECTEDVALUE(Table_Temps[Date]) + TIME(0,30,0)
)
```

### **Activité par Buckets de 15 minutes**
```dax
// Mesure: Activité par 15 min
Activite_Par_15min = 
VAR BucketStart = 
    SELECTEDVALUE(Table_Temps[Date]) - 
    MOD(MINUTE(SELECTEDVALUE(Table_Temps[Date])), 15) / 1440
VAR BucketEnd = BucketStart + TIME(0,15,0)
RETURN
CALCULATE(
    AVERAGE(Measurements[activity]),
    Measurements[recorded_at] >= BucketStart,
    Measurements[recorded_at] < BucketEnd
)
```

---

## 🎯 **Mesures pour Lignes de Seuil (Reference Lines)**

### **Seuils SpO2**
```dax
// Ligne de seuil critique SpO2
Seuil_SpO2_Critique = 88

// Ligne de seuil bas SpO2
Seuil_SpO2_Bas = 90

// Ligne de seuil optimal SpO2
Seuil_SpO2_Optimal = 95
```

### **Seuils Fréquence Cardiaque**
```dax
// Ligne de seuil FC minimum
Seuil_FC_Min = 50

// Ligne de seuil FC maximum normal
Seuil_FC_Max_Normal = 100

// Ligne de seuil FC critique
Seuil_FC_Critique = 180
```

### **Seuils Température**
```dax
// Seuils Température Corporelle
Seuil_Temp_Corp_Normal = 37.5
Seuil_Temp_Corp_Fievre = 38.0
Seuil_Temp_Corp_Critique = 38.5

// Seuils Température Ambiante
Seuil_Temp_Amb_Min = 15
Seuil_Temp_Amb_Confort_Min = 18
Seuil_Temp_Amb_Confort_Max = 25
Seuil_Temp_Amb_Max = 30
```

---

## 📈 **Mesures pour Index de Chaleur (Gauge)**

```dax
// Mesure: Index Chaleur Moyen
Index_Chaleur_Moyen = 
CALCULATE(
    AVERAGE(Measurements[heat_index]),
    Measurements[recorded_at] >= NOW() - TIME(0,30,0)
)

// Mesure: Couleur Index Chaleur
Couleur_Index_Chaleur = 
VAR IndexValue = [Index_Chaleur_Moyen]
RETURN
    SWITCH(
        TRUE(),
        IndexValue > 40, "Red",         // Rouge > 40
        IndexValue >= 35, "Orange",     // Orange 35-40
        "Green"                         // Vert < 35
    )

// Mesure: Index Chaleur Min/Max pour Gauge
Index_Chaleur_Min = 0
Index_Chaleur_Max = 50
```

---

## 🍩 **Mesures pour Status Patients (Donut)**

```dax
// Table calculée: Status Patients
Status_Patients = 
SUMMARIZE(
    ADDCOLUMNS(
        VALUES(Measurements[patient_id]),
        "Derniere_Mesure", 
        CALCULATE(MAX(Measurements[recorded_at])),
        "SpO2_Recent", 
        CALCULATE(
            AVERAGE(Measurements[spo2_pct]),
            Measurements[recorded_at] >= NOW() - TIME(0,10,0)
        ),
        "Temp_Recent", 
        CALCULATE(
            AVERAGE(Measurements[temp_corp]),
            Measurements[recorded_at] >= NOW() - TIME(0,10,0)
        ),
        "Alertes_Actives",
        CALCULATE(
            COUNTROWS(Alerts),
            Alerts[severity] = "CRITICAL",
            ISBLANK(Alerts[ack_deadline]),
            Alerts[created_at] >= NOW() - TIME(0,30,0)
        )
    ),
    [patient_id],
    "Status", 
    SWITCH(
        TRUE(),
        [Derniere_Mesure] < NOW() - TIME(0,10,0), "Disconnected",
        [Alertes_Actives] > 0 || [SpO2_Recent] < 88 || [Temp_Recent] > 38.5, "Critical",
        [SpO2_Recent] < 90 || [Temp_Recent] > 38, "Warning",
        "Stable"
    )
)

// Mesures pour le donut
Patients_Stable = 
CALCULATE(
    DISTINCTCOUNT(Status_Patients[patient_id]),
    Status_Patients[Status] = "Stable"
)

Patients_Warning = 
CALCULATE(
    DISTINCTCOUNT(Status_Patients[patient_id]),
    Status_Patients[Status] = "Warning"
)

Patients_Critical = 
CALCULATE(
    DISTINCTCOUNT(Status_Patients[patient_id]),
    Status_Patients[Status] = "Critical"
)

Patients_Disconnected = 
CALCULATE(
    DISTINCTCOUNT(Status_Patients[patient_id]),
    Status_Patients[Status] = "Disconnected"
)
```

---

## 📊 **Mesures pour Distribution des Alertes (Barres)**

```dax
// Mesure: Alertes par Type
Alertes_SpO2 = 
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("SpO2", Alerts[alert_type], 1, 0) > 0 ||
    SEARCH("spo2", Alerts[message], 1, 0) > 0
)

Alertes_Temperature_Corp = 
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("temp", Alerts[alert_type], 1, 0) > 0 ||
    SEARCH("fever", Alerts[alert_type], 1, 0) > 0
)

Alertes_Frequence_Cardiaque = 
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("card", Alerts[alert_type], 1, 0) > 0 ||
    SEARCH("tachy", Alerts[alert_type], 1, 0) > 0
)

Alertes_Temperature_Ambiante = 
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("ambient", Alerts[alert_type], 1, 0) > 0 ||
    SEARCH("environment", Alerts[alert_type], 1, 0) > 0
)

Alertes_Hydratation = 
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("hydrat", Alerts[alert_type], 1, 0) > 0 ||
    SEARCH("deshydrat", Alerts[alert_type], 1, 0) > 0
)
```

---

## 📋 **Mesures pour Tableaux de Données**

### **Tableau Patients Actifs**
```dax
// Table calculée: Patients Actifs Détaillé
Patients_Actifs_Detail = 
SUMMARIZE(
    ADDCOLUMNS(
        FILTER(
            VALUES(Measurements[patient_id]),
            CALCULATE(
                MAX(Measurements[recorded_at])
            ) >= NOW() - TIME(0,10,0)
        ),
        "Last_Update", 
        FORMAT(
            CALCULATE(MAX(Measurements[recorded_at])),
            "hh:mm:ss"
        ),
        "SpO2_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[spo2_pct]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0"
        ) & "%",
        "FC_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[freq_card]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0"
        ),
        "Temp_Corp_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[temp_corp]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0.1"
        ) & "°C",
        "Temp_Amb_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[temp_ambiante]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0.1"
        ) & "°C",
        "Hydratation_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[pct_hydratation]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0"
        ) & "%",
        "Activity_Current", 
        FORMAT(
            CALCULATE(
                AVERAGE(Measurements[activity]),
                Measurements[recorded_at] >= NOW() - TIME(0,5,0)
            ),
            "0"
        ),
        "Alertes_Count",
        CALCULATE(
            COUNTROWS(Alerts),
            Alerts[severity] IN {"CRITICAL", "HIGH"},
            ISBLANK(Alerts[ack_deadline])
        )
    ),
    [patient_id],
    [Last_Update],
    [SpO2_Current],
    [FC_Current],
    [Temp_Corp_Current],
    [Temp_Amb_Current],
    [Hydratation_Current],
    [Activity_Current],
    [Alertes_Count]
)
```

### **Tableau Tendances par Mesure**
```dax
// Table calculée: Tendances par Mesure
Tendances_Mesures = 
{
    ("SpO2 (%)", 
     CALCULATE(MIN(Measurements[spo2_pct]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[spo2_pct]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[spo2_pct]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[spo2_pct]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    ),
    ("FC (bpm)", 
     CALCULATE(MIN(Measurements[freq_card]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[freq_card]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[freq_card]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[freq_card]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    ),
    ("Temp Corp (°C)", 
     CALCULATE(MIN(Measurements[temp_corp]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[temp_corp]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[temp_corp]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[temp_corp]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    ),
    ("Temp Amb (°C)", 
     CALCULATE(MIN(Measurements[temp_ambiante]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[temp_ambiante]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[temp_ambiante]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[temp_ambiante]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    ),
    ("Hydratation (%)", 
     CALCULATE(MIN(Measurements[pct_hydratation]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[pct_hydratation]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[pct_hydratation]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[pct_hydratation]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    ),
    ("Activité (0-100)", 
     CALCULATE(MIN(Measurements[activity]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(MAX(Measurements[activity]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(AVERAGE(Measurements[activity]), Measurements[recorded_at] >= NOW() - TIME(1,0,0)),
     CALCULATE(STDEV.P(Measurements[activity]), Measurements[recorded_at] >= NOW() - TIME(1,0,0))
    )
}
```

---

## 🔄 **Mesures de Refresh et Statut**

```dax
// Mesure: Dernière Mise à Jour
Derniere_MAJ = 
"Dernière MAJ: " & 
FORMAT(
    CALCULATE(MAX(Measurements[recorded_at])),
    "dd/mm/yyyy hh:mm:ss"
)

// Mesure: Statut Connexion
Statut_Connexion = 
VAR DerniereMAJ = CALCULATE(MAX(Measurements[recorded_at]))
VAR MinutesEcoule = DATEDIFF(DerniereMAJ, NOW(), MINUTE)
RETURN
    SWITCH(
        TRUE(),
        MinutesEcoule <= 2, "🟢 En ligne",
        MinutesEcoule <= 5, "🟡 Retard",
        "🔴 Hors ligne"
    )

// Mesure: Nombre Total Mesures Aujourd'hui
Total_Mesures_Aujourdhui = 
CALCULATE(
    COUNTROWS(Measurements),
    Measurements[recorded_at] >= TODAY()
)
```

---

## 🎨 **Configuration Couleurs et Formatage**

### **Palette de Couleurs Médicales**
```dax
// Configuration couleurs (à utiliser dans les paramètres visuels PowerBI)
Vert_Medical = "#28A745"      // Normal/Sain
Orange_Medical = "#FD7E14"    // Attention/Modéré  
Rouge_Medical = "#DC3545"     // Critique/Urgent
Gris_Medical = "#6C757D"      // Inactif/Déconnecté
Bleu_Medical = "#007BFF"      // Information
```

### **Formats d'Affichage**
```dax
// Formats pour cartes KPI
Format_Pourcentage = "0.0'%'"
Format_Temperature = "0.0'°C'"
Format_Frequence = "0' bpm'"
Format_Temps = "0.0' min'"
Format_Entier = "0"

// Formats pour axes graphiques
Format_Axe_SpO2 = "0'%'"
Format_Axe_Temperature = "0'°C'"
Format_Axe_Frequence = "0' bpm'"
Format_Axe_Temps = "hh:mm"
```

---

## 🚀 **Instructions d'Implémentation**

### **Étapes de Configuration PowerBI**

1. **Import des Données**
   - Connecter aux endpoints API: `/powerbi/measurements`, `/powerbi/alerts`, `/powerbi/kpis`
   - Configurer refresh automatique 30 secondes

2. **Création des Mesures**
   - Copier toutes les formules DAX ci-dessus dans PowerBI
   - Organiser en dossiers : "KPIs", "Graphiques", "Seuils", "Tableaux"

3. **Configuration des Visuels**
   - Appliquer couleurs conditionnelles avec mesures `Couleur_*`
   - Configurer lignes de référence avec mesures `Seuil_*`
   - Paramétrer refresh temps réel

4. **Optimisation Performance**
   - Utiliser DirectQuery pour données temps réel
   - Indexer colonnes `patient_id`, `recorded_at`, `severity`
   - Limiter historique à 24h pour performance

### **Test et Validation**
```dax
// Mesure de test pour validation données
Test_Coherence_Donnees = 
VAR TotalMesures = COUNTROWS(Measurements)
VAR MesuresValides = 
    COUNTROWS(
        FILTER(
            Measurements,
            Measurements[spo2_pct] >= 70 &&
            Measurements[spo2_pct] <= 100 &&
            Measurements[freq_card] >= 30 &&
            Measurements[freq_card] <= 250 &&
            Measurements[temp_corp] >= 30 &&
            Measurements[temp_corp] <= 45
        )
    )
RETURN
    DIVIDE(MesuresValides, TotalMesures) * 100
```

---

## 📋 **Checklist de Validation**

### **KPIs Fonctionnels** ✅
- [ ] 9 cartes KPI avec couleurs dynamiques
- [ ] Refresh automatique 30 secondes
- [ ] Formatage médical approprié
- [ ] Seuils critiques configurés

### **Graphiques Temps Réel** ✅
- [ ] 11 graphiques avec données 4h glissantes
- [ ] Lignes de seuil visibles
- [ ] Couleurs par zone (Vert/Orange/Rouge)
- [ ] Légendes patients claires

### **Tableaux Dynamiques** ✅
- [ ] Tableau patients actifs complet
- [ ] Tableau alertes récentes
- [ ] Tableau tendances statistiques
- [ ] Tri et filtres fonctionnels

### **Performance** ✅
- [ ] Latence < 2 secondes refresh
- [ ] Données cohérentes API ↔ PowerBI
- [ ] Gestion erreurs connexion
- [ ] Optimisation requêtes DAX

---

## 🎯 **Prêt pour Implémentation**

Ce fichier contient toutes les formules DAX nécessaires pour créer un dashboard PowerBI professionnel de monitoring médical temps réel. 

**Prochaines étapes** :
1. Créer les endpoints API PowerBI
2. Importer formules DAX dans PowerBI Desktop
3. Configurer les visuels selon le layout défini
4. Tester avec données temps réel
5. Déployer sur PowerBI Service

**Performance attendue** :
- ⚡ Refresh : 30 secondes
- 📊 Données : 24h glissantes
- 🎯 Précision : 99.9%
- 🚀 Disponibilité : 99.5%
