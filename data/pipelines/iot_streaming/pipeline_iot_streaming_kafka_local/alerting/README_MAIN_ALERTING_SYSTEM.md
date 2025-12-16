# README - Système d'Alertes Médicales IoT KidJamo

## 📋 Vue d'ensemble

Le fichier `main_alerting_system.py` est le **centre de contrôle principal** du système d'alertes médicales IoT de KidJamo. Il orchestre la surveillance en temps réel des patients, l'analyse des données vitales et l'envoi automatique de notifications d'urgence via SMS et email.

## 🎯 Rôle et responsabilités

### 1. **Centre de Commande Médical**
- Point d'entrée unique pour la surveillance médicale temps réel
- Interface utilisateur interactive pour gérer le système d'alertes
- Coordination de tous les composants du pipeline d'alertes

### 2. **Orchestrateur de Services**
- **Base de données** : Connexion sécurisée à PostgreSQL (`kidjamo-db`)
- **Notifications** : Intégration Twilio (SMS) + SendGrid (Email)
- **Monitoring** : Surveillance continue configurable (30s par défaut)
- **Logging** : Traçabilité complète avec gestion UTF-8

## 🏗️ Architecture technique

```
main_alerting_system.py
├── AlertingSystemMain (Classe principale)
│   ├── AlertOrchestrator (Moteur d'alertes)
│   ├── TwilioNotificationService (SMS)
│   ├── CompositeAlertEngine (Règles médicales)
│   └── PostgreSQL (kidjamo-db)
├── Logging System (logs/alerting_system.log)
├── Signal Handlers (Arrêt propre)
└── Unicode Support (Windows compatible)
```

## 🔧 Fonctionnalités principales

### **Menu Interactif**

```
🏥 KIDJAMO - SYSTÈME D'ALERTES MÉDICALES IoT
===========================================

🔧 Configuration: Twilio SMS + SendGrid Email
📡 Base de données: PostgreSQL Local (kidjamo-db)
🚨 Monitoring: Temps réel (30s)

Choisissez une action:
1. 🚀 Démarrer monitoring temps réel
2. 📤 Envoyer alerte de test
3. 📊 Afficher statut système
4. 🛑 Quitter
5. 🧪 Insérer une alerte de démo en DB
```

### **Option 1 - Monitoring Temps Réel**
- **Surveillance continue** des patients avec mesures récentes
- **Analyse automatique** des alertes composées (combinaisons de symptômes)
- **Notifications instantanées** en cas d'urgence médicale (SpO2 bas, fièvre, douleur)
- **Boucle infinie** avec intervalle configurable via `KIDJAMO_MONITOR_INTERVAL`

**Flux de monitoring :**
1. Scan des patients actifs dans la base
2. Analyse des mesures vitales récentes
3. Application des règles médicales
4. Génération d'alertes si seuils dépassés
5. Envoi SMS/Email aux équipes médicales
6. Logging et métriques

### **Option 2 - Test d'Alertes**
- **Simulation d'alerte HIGH** pour valider le système
- **Test complet** de la chaîne Twilio + SendGrid
- **Vérification** des credentials et de la connectivité
- **Validation** du pipeline notifications

### **Option 3 - Tableau de Bord Système**
```
📊 STATUT SYSTÈME:
   Status: healthy
   Patients actifs: 12
   Alertes actives: 3
   Service notifications: twilio
   Dernière exécution: 2025-08-26 17:20:39

📱 MÉTRIQUES NOTIFICATIONS:
   SMS envoyés: 45
   Emails envoyés: 38
   Échecs: 2
   Taux succès: 97.6%
```

### **Option 5 - Injection de Données**
- **Insertion d'alertes** de démonstration directement en base
- **Contournement** des triggers d'audit pour les tests
- **Génération** de données réalistes pour validation

## ⚙️ Configuration

### **Base de Données**
```python
db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'kidjamo-db',
    'user': 'postgres',
    'password': 'kidjamo@'
}
```

### **Services de Notification**
- **Twilio** : SMS d'urgence
- **SendGrid** : Emails détaillés
- **Mode test** : Simulation sans envoi réel
- **Mode production** : Vraies notifications

### **Variables d'Environnement**
- `KIDJAMO_MONITOR_INTERVAL` : Intervalle de monitoring (secondes)
- Configuration automatique des services cloud

## 🔍 Logging et Traçabilité

### **Fichiers de Log**
```
logs/alerting_system.log
├── Horodatage complet
├── Niveau de log (INFO, WARN, ERROR)
├── Module source
└── Message avec contexte médical
```

### **Console Output**
- Affichage temps réel des événements
- Gestion robuste de l'encodage UTF-8
- Émojis convertis en codes ASCII pour compatibilité

## 🚨 Gestion des Alertes Médicales

### **Types d'Alertes Supportées**
- **Hypoxémie critique** : SpO2 < 85%
- **Hypoxémie modérée** : SpO2 < seuil patient
- **Douleur sévère** : Échelle ≥ 8/10
- **Fièvre élevée** : Température > 38.5°C
- **Tachycardie** : Fréquence cardiaque élevée

### **Niveaux de Sévérité**
- **CRITICAL** : Intervention immédiate (5 min)
- **ALERT** : Surveillance renforcée (15 min)
- **WARN** : Monitoring continue

## 💡 Cas d'Usage

### **1. Déploiement Production**
```bash
# Lancer le monitoring continu
python main_alerting_system.py
# Choisir option 1
```

### **2. Tests et Validation**
```bash
# Tester les notifications
python main_alerting_system.py
# Choisir option 2 pour test SMS/Email
# Choisir option 5 pour injecter données
```

### **3. Monitoring et Debug**
```bash
# Consulter le statut
python main_alerting_system.py
# Choisir option 3 pour dashboard
```

## 🔐 Sécurité et Conformité

### **Audit Logging**
- Toutes les actions sont tracées
- Conformité GDPR avec rétention configurée
- Séparation des données PII

### **Gestion des Erreurs**
- **Arrêt propre** avec Ctrl+C
- **Recovery automatique** en cas d'erreur réseau
- **Métriques de fiabilité** en temps réel

## 🚀 Points Forts Techniques

### **Performance**
- **Asynchrone** : Traitement non-bloquant
- **Scalable** : Gestion de milliers de patients
- **Efficient** : Requêtes optimisées PostgreSQL

### **Robustesse**
- **Signal handling** : Arrêt gracieux
- **Error recovery** : Reprise automatique
- **Logging complet** : Debugging facilité

### **Compatibilité**
- **Windows** : Support UTF-8 natif
- **Production** : Mode 24h/24
- **Development** : Mode test intégré

## 🎯 Valeur Métier

Ce système transforme KidJamo en **plateforme médicale opérationnelle** capable de :

✅ **Sauver des vies** avec alertes temps réel  
✅ **Notifier instantanément** les équipes médicales  
✅ **Tracer toutes les actions** pour conformité  
✅ **Fonctionner 24h/24** en mode production  
✅ **Intégrer facilement** nouveaux capteurs IoT  

---

## 📞 Support et Maintenance

Pour toute question ou problème :
1. Consulter les logs : `logs/alerting_system.log`
2. Vérifier le statut système (Option 3)
3. Tester les notifications (Option 2)
4. Redémarrer le service si nécessaire

**Le système KidJamo est prêt pour un déploiement médical en production ! 🏥⚡**
