#!/usr/bin/env python3
"""
Démonstration Complète du Simulateur IoT KIDJAMO
Ce script lance une simulation courte pour démontrer tous les composants en action
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def demo_complete_simulation():
    """Démonstration complète du système"""
    print("🏥 DÉMONSTRATION SYSTÈME IoT KIDJAMO")
    print("=" * 60)
    print("Simulation en temps réel avec 3 patients pendant 2 minutes")
    print()

    try:
        # Import des modules
        from simulator import PatientGenerator, PhysiologicalSimulator
        print("✅ Modules simulateur chargés")

        # Génération des patients
        gen = PatientGenerator()
        patients = gen.generate_patient_batch(3)
        print(f"✅ {len(patients)} patients virtuels créés")

        # Affichage des patients
        print("\n👥 PATIENTS VIRTUELS GÉNÉRÉS:")
        print("-" * 40)
        for i, patient in enumerate(patients):
            crisis_risk = "🔴 ÉLEVÉ" if patient.genotype == "SS" else "🟡 MODÉRÉ" if patient.genotype in ["SC", "Sβ0"] else "🟢 FAIBLE"
            print(f"   {i+1}. {patient.first_name} {patient.last_name}")
            print(f"      Âge: {patient.age} ans | Génotype: {patient.genotype}")
            print(f"      SpO2 base: {patient.base_spo2_range[0]}-{patient.base_spo2_range[1]}% | Risque: {crisis_risk}")
            print()

        # Simulation physiologique
        sim = PhysiologicalSimulator()
        print("📊 SIMULATION TEMPS RÉEL - 2 MINUTES")
        print("-" * 40)
        print("Génération de mesures toutes les 10 secondes...")
        print("Appuyez sur Ctrl+C pour arrêter\n")

        measurement_count = 0
        alert_count = 0
        start_time = datetime.now()

        try:
            for cycle in range(12):  # 12 cycles de 10 secondes = 2 minutes
                cycle_time = datetime.now()
                print(f"⏰ Cycle {cycle + 1}/12 - {cycle_time.strftime('%H:%M:%S')}")

                for patient in patients:
                    # Génération mesure
                    measurement = sim.generate_measurement(patient, cycle_time)
                    measurement_count += 1

                    # Détection alertes
                    alerts = []
                    if measurement.spo2_percent < 88:
                        alerts.append("🚨 SpO2 CRITIQUE")
                        alert_count += 1
                    elif measurement.spo2_percent < 92:
                        alerts.append("⚠️ SpO2 BAS")
                        alert_count += 1

                    if measurement.heart_rate_bpm > 120:
                        alerts.append("⚠️ TACHYCARDIE")
                        alert_count += 1
                    elif measurement.heart_rate_bpm < 50:
                        alerts.append("⚠️ BRADYCARDIE")
                        alert_count += 1

                    if measurement.temperature_celsius > 38.5:
                        alerts.append("⚠️ FIÈVRE")
                        alert_count += 1

                    # Affichage
                    status = "🚨" if any("CRITIQUE" in alert for alert in alerts) else "⚠️" if alerts else "✅"
                    print(f"   {status} {patient.first_name}: SpO2={measurement.spo2_percent:.1f}% | FC={measurement.heart_rate_bpm}bpm | T°={measurement.temperature_celsius:.1f}°C")

                    if alerts:
                        for alert in alerts:
                            print(f"      → {alert}")

                print()
                time.sleep(10)  # Attendre 10 secondes

        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé par l'utilisateur")

        # Statistiques finales
        duration = (datetime.now() - start_time).total_seconds() / 60
        print("\n📊 STATISTIQUES DE LA DÉMONSTRATION")
        print("=" * 50)
        print(f"⏱️  Durée: {duration:.1f} minutes")
        print(f"👥 Patients simulés: {len(patients)}")
        print(f"📈 Mesures générées: {measurement_count}")
        print(f"🚨 Alertes détectées: {alert_count}")
        print(f"📊 Fréquence mesures: {measurement_count/max(duration, 0.1):.1f} mesures/min")

        # Types de patients simulés
        genotype_counts = {}
        for patient in patients:
            genotype_counts[patient.genotype] = genotype_counts.get(patient.genotype, 0) + 1

        print(f"\n🧬 RÉPARTITION GÉNOTYPES:")
        for genotype, count in genotype_counts.items():
            severity = {
                "SS": "Drépanocytose sévère",
                "SC": "Drépanocytose modérée",
                "AS": "Porteur sain",
                "Sβ0": "Bêta-thalassémie"
            }.get(genotype, "Inconnu")
            print(f"   {genotype}: {count} patient(s) - {severity}")

        return True

    except Exception as e:
        print(f"❌ Erreur durant la démonstration: {e}")
        return False

def demo_database_integration():
    """Test de l'intégration base de données"""
    print("\n💾 TEST INTÉGRATION BASE DE DONNÉES")
    print("-" * 40)

    try:
        import psycopg2

        # Configuration
        db_config = {
            'host': 'localhost',
            'port': '5432',
            'database': 'kidjamo-db',
            'user': 'postgres',
            'password': 'kidjamo@',
            'client_encoding': 'UTF8'
        }

        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Comptage des données existantes
        cursor.execute("SELECT COUNT(*) FROM patients")
        patient_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM measurements")
        measurement_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]

        print(f"✅ Connexion PostgreSQL réussie")
        print(f"   📊 Patients en base: {patient_count}")
        print(f"   📈 Mesures en base: {measurement_count:,}")
        print(f"   🚨 Alertes en base: {alert_count}")

        # Dernières mesures
        cursor.execute("""
            SELECT p.first_name, p.last_name, m.spo2_percent, m.heart_rate_bpm, m.recorded_at
            FROM measurements m 
            JOIN patients p ON m.patient_id = p.patient_id
            ORDER BY m.recorded_at DESC 
            LIMIT 5
        """)

        recent_measurements = cursor.fetchall()
        if recent_measurements:
            print(f"\n📊 DERNIÈRES MESURES:")
            for measurement in recent_measurements:
                print(f"   {measurement[0]} {measurement[1]}: SpO2={measurement[2]}% FC={measurement[3]}bpm ({measurement[4]})")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur base de données: {e}")
        return False

def main():
    """Fonction principale de démonstration"""
    print("🚀 DÉMONSTRATION SIMULATEUR IoT KIDJAMO")
    print("=" * 60)
    print("Cette démonstration montre le système complet en action:")
    print("• Génération de patients virtuels")
    print("• Simulation de mesures physiologiques en temps réel")
    print("• Détection d'alertes médicales")
    print("• Intégration base de données PostgreSQL")
    print()

    # Démonstration complète
    success = demo_complete_simulation()

    if success:
        # Test intégration DB
        demo_database_integration()

        print("\n🎉 DÉMONSTRATION TERMINÉE AVEC SUCCÈS!")
        print("\n📖 PROCHAINES ÉTAPES:")
        print("   1. Simulation longue durée:")
        print("      python massive_simulation_integration.py --patients 50 --duration 24")
        print("   2. Dashboard web: http://localhost:8501")
        print("   3. Configuration notifications SMS/Email")
        print("\n📚 Documentation complète: README_SIMULATION_COMPLETE_FR.md")
    else:
        print("\n❌ La démonstration a échoué. Consultez les messages d'erreur ci-dessus.")

if __name__ == "__main__":
    main()
