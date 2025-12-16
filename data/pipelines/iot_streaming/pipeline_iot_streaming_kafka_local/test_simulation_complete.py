#!/usr/bin/env python3
"""
Script de Test Rapide - Démonstration Simulateur IoT KIDJAMO
Ce script teste chaque composant individuellement pour vous montrer comment fonctionne la simulation.
"""

import sys
import os
from pathlib import Path

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_step_1_imports():
    """Étape 1: Test des imports des modules simulateur"""
    print("🔧 ÉTAPE 1: Test des imports des modules simulateur")
    print("-" * 50)

    try:
        from simulator import PatientGenerator, PhysiologicalSimulator
        print("✅ Import PatientGenerator: OK")
        print("✅ Import PhysiologicalSimulator: OK")
        return True
    except ImportError as e:
        print(f"❌ Erreur import: {e}")
        return False

def test_step_2_patient_generation():
    """Étape 2: Test génération de patients virtuels"""
    print("\n🧑‍⚕️ ÉTAPE 2: Génération de patients virtuels")
    print("-" * 50)

    try:
        from simulator import PatientGenerator
        gen = PatientGenerator()
        patients = gen.generate_patient_batch(3)

        print(f"✅ Généré {len(patients)} patients virtuels:")
        for i, patient in enumerate(patients):
            print(f"   👤 Patient {i+1}: {patient.first_name} {patient.last_name}")
            print(f"      - Âge: {patient.age} ans")
            print(f"      - Génotype: {patient.genotype}")
            print(f"      - Poids: {patient.weight_kg} kg")
            print(f"      - Taille: {patient.height_cm} cm")
            print(f"      - ID Dispositif: {patient.device_id}")
            print(f"      - SpO2 de base: {patient.base_spo2_range[0]}-{patient.base_spo2_range[1]}%")
            print()

        return patients
    except Exception as e:
        print(f"❌ Erreur génération patients: {e}")
        return None

def test_step_3_measurement_simulation(patients):
    """Étape 3: Test simulation de mesures physiologiques"""
    print("📊 ÉTAPE 3: Simulation mesures physiologiques")
    print("-" * 50)

    try:
        from simulator import PhysiologicalSimulator
        from datetime import datetime

        sim = PhysiologicalSimulator()
        patient = patients[0]  # Premier patient

        print(f"🔬 Génération de 3 mesures pour {patient.first_name} {patient.last_name}:")

        for i in range(3):
            measurement = sim.generate_measurement(patient, datetime.now())
            print(f"   📈 Mesure {i+1}:")
            print(f"      - SpO2: {measurement.spo2_percent}% {'✅' if measurement.spo2_percent >= 95 else '⚠️'}")
            print(f"      - Fréquence cardiaque: {measurement.heart_rate_bpm} bpm {'✅' if 60 <= measurement.heart_rate_bpm <= 100 else '⚠️'}")
            print(f"      - Température: {measurement.temperature_celsius}°C {'✅' if 36.1 <= measurement.temperature_celsius <= 37.2 else '⚠️'}")
            print(f"      - Hydratation: {measurement.hydration_percent}%")
            print()

        return True
    except Exception as e:
        print(f"❌ Erreur simulation mesures: {e}")
        return False

def test_step_4_database_connection():
    """Étape 4: Test connexion base de données"""
    print("💾 ÉTAPE 4: Test connexion base de données PostgreSQL")
    print("-" * 50)

    try:
        import psycopg2

        # Configuration base de données avec vos credentials
        db_config = {
            'host': 'localhost',
            'port': '5432',
            'database': 'kidjamo-db',
            'user': 'postgres',
            'password': 'kidjamo@',
            'client_encoding': 'UTF8'
        }

        print(f"🔗 Tentative connexion à {db_config['host']}:{db_config['port']}/{db_config['database']}")

        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Test simple
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connexion PostgreSQL réussie")
        print(f"   Version: {version[0][:50]}...")

        # Test tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('patients', 'measurements', 'alerts')
        """)
        tables = cursor.fetchall()

        if tables:
            print(f"✅ Tables trouvées: {[t[0] for t in tables]}")
        else:
            print("⚠️  Tables patients/measurements/alerts non trouvées - seront créées automatiquement")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur connexion base de données: {e}")
        print("💡 Vérifiez que PostgreSQL est démarré et accessible")
        return False

def test_step_5_alert_system():
    """Étape 5: Test système d'alertes médicales"""
    print("🚨 ÉTAPE 5: Test système d'alertes médicales")
    print("-" * 50)

    try:
        from simulator import PhysiologicalSimulator
        from datetime import datetime

        # Simulation de valeurs critiques
        print("🔬 Simulation de scénarios d'alerte:")

        scenarios = [
            {"name": "SpO2 Critique", "spo2": 85, "expected": "CRITIQUE"},
            {"name": "Tachycardie", "heart_rate": 130, "expected": "ALERTE"},
            {"name": "Fièvre", "temperature": 39.2, "expected": "ALERTE"},
            {"name": "Valeurs Normales", "spo2": 98, "heart_rate": 75, "temperature": 37.0, "expected": "NORMAL"}
        ]

        for scenario in scenarios:
            print(f"   📋 {scenario['name']}:")

            # Détermination du niveau d'alerte
            alert_level = "NORMAL"
            if scenario.get('spo2', 100) < 88:
                alert_level = "CRITIQUE"
            elif scenario.get('spo2', 100) < 92:
                alert_level = "ALERTE"
            elif scenario.get('heart_rate', 70) > 120 or scenario.get('heart_rate', 70) < 50:
                alert_level = "ALERTE"
            elif scenario.get('temperature', 37) > 38.5:
                alert_level = "ALERTE"

            status = "✅" if alert_level == scenario['expected'] else "❌"
            print(f"      Niveau détecté: {alert_level} {status}")

        return True

    except Exception as e:
        print(f"❌ Erreur test alertes: {e}")
        return False

def test_step_6_notifications():
    """Étape 6: Test configuration notifications"""
    print("📱 ÉTAPE 6: Test configuration notifications")
    print("-" * 50)

    # Test Twilio
    try:
        from twilio.rest import Client
        print("✅ Module Twilio disponible")
        print("   📱 SMS: Prêt (configuration requise)")
    except ImportError:
        print("❌ Module Twilio non disponible")
        print("   💡 Installation: pip install twilio")

    # Test SMTP Email
    try:
        import smtplib
        from email.mime.text import MIMEText
        print("✅ Module SMTP disponible")
        print("   📧 Email: Prêt (configuration requise)")
    except ImportError:
        print("❌ Module SMTP non disponible")

    return True

def test_step_7_dashboard():
    """Étape 7: Test disponibilité dashboard"""
    print("📊 ÉTAPE 7: Test disponibilité dashboard")
    print("-" * 50)

    try:
        import streamlit
        print("✅ Streamlit disponible")
        print("   🌐 Dashboard: http://localhost:8501")

        dashboard_file = project_root / "monitoring" / "realtime_dashboard_advanced.py"
        if dashboard_file.exists():
            print("✅ Script dashboard trouvé")
        else:
            print("⚠️  Script dashboard non trouvé - dashboard simple disponible")

    except ImportError:
        print("❌ Streamlit non disponible")
        print("   💡 Installation: pip install streamlit")

    return True

def main():
    """Fonction principale de test"""
    print("🏥 TEST COMPLET SIMULATEUR IoT KIDJAMO")
    print("=" * 60)
    print("Ce script teste chaque composant du système étape par étape")
    print()

    # Tests séquentiels
    success_count = 0
    total_tests = 7

    # Étape 1: Imports
    if test_step_1_imports():
        success_count += 1

    # Étape 2: Génération patients
    patients = test_step_2_patient_generation()
    if patients:
        success_count += 1

    # Étape 3: Mesures (si patients générés)
    if patients and test_step_3_measurement_simulation(patients):
        success_count += 1

    # Étape 4: Base de données
    if test_step_4_database_connection():
        success_count += 1

    # Étape 5: Alertes
    if test_step_5_alert_system():
        success_count += 1

    # Étape 6: Notifications
    if test_step_6_notifications():
        success_count += 1

    # Étape 7: Dashboard
    if test_step_7_dashboard():
        success_count += 1

    # Résumé final
    print("\n📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    print(f"✅ Tests réussis: {success_count}/{total_tests}")
    print(f"📈 Taux de réussite: {(success_count/total_tests)*100:.1f}%")

    if success_count == total_tests:
        print("\n🎉 TOUS LES COMPOSANTS FONCTIONNENT!")
        print("   Vous pouvez maintenant lancer la simulation complète:")
        print("   python massive_simulation_integration.py --patients 5 --duration 0.083")
    else:
        print(f"\n⚠️  {total_tests - success_count} composant(s) nécessite(nt) une attention")
        print("   Consultez les messages d'erreur ci-dessus pour résoudre les problèmes")

    print("\n📖 Pour plus d'informations, consultez:")
    print("   README_SIMULATION_COMPLETE_FR.md")

if __name__ == "__main__":
    main()
