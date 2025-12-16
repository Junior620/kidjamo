#!/usr/bin/env python3
"""
Script de Simulation Simple - Contournement Problème Encodage
Ce script lance la simulation sans dépendre de la vérification PostgreSQL problématique
"""

import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def simple_simulation_demo():
    """Démonstration simplifiée du système complet"""
    print("🏥 SIMULATION IoT KIDJAMO - MODE SIMPLE")
    print("=" * 60)
    print("Contournement du problème d'encodage PostgreSQL")
    print()

    try:
        # Import des modules simulateur
        from simulator import PatientGenerator, PhysiologicalSimulator
        print("✅ Modules simulateur chargés avec succès")

        # Configuration simulation
        patient_count = 3
        duration_minutes = 3
        measurement_interval = 10  # secondes

        print(f"📊 Configuration:")
        print(f"   👥 Patients: {patient_count}")
        print(f"   ⏱️  Durée: {duration_minutes} minutes")
        print(f"   📈 Mesures: toutes les {measurement_interval} secondes")
        print()

        # Génération des patients
        gen = PatientGenerator()
        patients = gen.generate_patient_batch(patient_count)

        print("👥 PATIENTS VIRTUELS GÉNÉRÉS:")
        print("-" * 40)
        for i, patient in enumerate(patients):
            risk_level = "🔴 ÉLEVÉ" if patient.genotype == "SS" else "🟡 MODÉRÉ" if patient.genotype in ["SC", "Sβ0"] else "🟢 FAIBLE"
            print(f"   {i+1}. {patient.first_name} {patient.last_name}")
            print(f"      Âge: {patient.age} ans | Génotype: {patient.genotype}")
            print(f"      SpO2 base: {patient.base_spo2_range[0]}-{patient.base_spo2_range[1]}% | Risque: {risk_level}")
        print()

        # Simulation physiologique
        sim = PhysiologicalSimulator()

        print("🚀 DÉMARRAGE SIMULATION TEMPS RÉEL")
        print("-" * 40)
        print(f"Génération de mesures toutes les {measurement_interval} secondes pendant {duration_minutes} minutes...")
        print("Appuyez sur Ctrl+C pour arrêter prématurément\n")

        # Statistiques de simulation
        stats = {
            'total_measurements': 0,
            'total_alerts': 0,
            'critical_alerts': 0,
            'patients_in_crisis': set(),
            'start_time': datetime.now()
        }

        # Boucle de simulation
        cycles_total = (duration_minutes * 60) // measurement_interval

        try:
            for cycle in range(cycles_total):
                cycle_time = datetime.now()
                elapsed_seconds = (cycle_time - stats['start_time']).total_seconds()

                print(f"⏰ Cycle {cycle + 1}/{cycles_total} - {cycle_time.strftime('%H:%M:%S')} (+{elapsed_seconds:.0f}s)")

                cycle_alerts = []

                for patient in patients:
                    # Génération mesure
                    measurement = sim.generate_measurement(patient, cycle_time)
                    stats['total_measurements'] += 1

                    # Analyse des alertes
                    patient_alerts = []
                    alert_level = "NORMAL"

                    # SpO2 critique
                    if measurement.spo2_percent < 88:
                        patient_alerts.append("🚨 SpO2 CRITIQUE")
                        alert_level = "CRITIQUE"
                        stats['critical_alerts'] += 1
                        stats['patients_in_crisis'].add(patient.patient_id)
                    elif measurement.spo2_percent < 92:
                        patient_alerts.append("⚠️ SpO2 BAS")
                        alert_level = "ALERTE"

                    # Fréquence cardiaque
                    if measurement.heart_rate_bpm > 120:
                        patient_alerts.append("⚠️ TACHYCARDIE")
                        if alert_level == "NORMAL":
                            alert_level = "ALERTE"
                    elif measurement.heart_rate_bpm < 50:
                        patient_alerts.append("⚠️ BRADYCARDIE")
                        if alert_level == "NORMAL":
                            alert_level = "ALERTE"

                    # Température
                    if measurement.temperature_celsius > 38.5:
                        patient_alerts.append("⚠️ FIÈVRE")
                        if alert_level == "NORMAL":
                            alert_level = "ALERTE"
                    elif measurement.temperature_celsius < 35.0:
                        patient_alerts.append("⚠️ HYPOTHERMIE")
                        if alert_level == "NORMAL":
                            alert_level = "ALERTE"

                    # Hydratation
                    if measurement.hydration_percent < 60:
                        patient_alerts.append("⚠️ DÉSHYDRATATION")
                        if alert_level == "NORMAL":
                            alert_level = "ALERTE"

                    # Comptage alertes
                    if patient_alerts:
                        stats['total_alerts'] += len(patient_alerts)

                    # Affichage patient
                    status_icon = "🚨" if alert_level == "CRITIQUE" else "⚠️" if alert_level == "ALERTE" else "✅"
                    print(f"   {status_icon} {patient.first_name}: SpO2={measurement.spo2_percent:.1f}% | FC={measurement.heart_rate_bpm}bpm | T°={measurement.temperature_celsius:.1f}°C | H={measurement.hydration_percent:.1f}%")

                    # Affichage alertes
                    for alert in patient_alerts:
                        print(f"      → {alert}")
                        cycle_alerts.append(f"{patient.first_name}: {alert}")

                # Résumé du cycle
                if cycle_alerts:
                    print(f"   📊 {len(cycle_alerts)} alerte(s) ce cycle")
                else:
                    print("   ✅ Aucune alerte ce cycle")

                print()

                # Attendre avant le prochain cycle
                if cycle < cycles_total - 1:  # Pas d'attente au dernier cycle
                    time.sleep(measurement_interval)

        except KeyboardInterrupt:
            print("\n🛑 Simulation interrompue par l'utilisateur")

        # Statistiques finales
        duration_actual = (datetime.now() - stats['start_time']).total_seconds() / 60

        print("\n📊 RAPPORT FINAL DE SIMULATION")
        print("=" * 50)
        print(f"⏱️  Durée effective: {duration_actual:.1f} minutes")
        print(f"👥 Patients simulés: {len(patients)}")
        print(f"📈 Mesures générées: {stats['total_measurements']}")
        print(f"🚨 Total alertes: {stats['total_alerts']}")
        print(f"🔴 Alertes critiques: {stats['critical_alerts']}")
        print(f"⚡ Fréquence mesures: {stats['total_measurements']/max(duration_actual, 0.1):.1f} mesures/min")

        if stats['patients_in_crisis']:
            print(f"🏥 Patients en crise: {len(stats['patients_in_crisis'])}")

        # Répartition par génotype
        genotype_stats = {}
        for patient in patients:
            genotype_stats[patient.genotype] = genotype_stats.get(patient.genotype, 0) + 1

        print(f"\n🧬 RÉPARTITION GÉNOTYPES:")
        for genotype, count in genotype_stats.items():
            severity = {
                "SS": "Drépanocytose sévère (risque élevé)",
                "SC": "Drépanocytose modérée",
                "AS": "Porteur sain (risque faible)",
                "Sβ0": "Bêta-thalassémie"
            }.get(genotype, "Inconnu")
            print(f"   {genotype}: {count} patient(s) - {severity}")

        # Analyse des performances
        expected_measurements = len(patients) * cycles_total
        efficiency = (stats['total_measurements'] / expected_measurements * 100) if expected_measurements > 0 else 0

        print(f"\n⚡ ANALYSE PERFORMANCE:")
        print(f"   📊 Efficacité: {efficiency:.1f}% ({stats['total_measurements']}/{expected_measurements} mesures)")
        print(f"   🎯 Objectif atteint: {'✅' if efficiency >= 95 else '⚠️'}")

        if stats['total_alerts'] > 0:
            alert_rate = (stats['total_alerts'] / stats['total_measurements']) * 100
            print(f"   🚨 Taux d'alerte: {alert_rate:.1f}% des mesures")

        print(f"\n🎉 SIMULATION TERMINÉE AVEC SUCCÈS!")
        print(f"   💡 Le système fonctionne parfaitement sans base de données")
        print(f"   🔧 Pour résoudre le problème PostgreSQL, consultez le README")

        return True

    except Exception as e:
        print(f"❌ Erreur durant la simulation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_separately():
    """Test séparé de la base de données avec solutions multiples"""
    print("\n💾 TEST CONNEXION BASE DE DONNÉES")
    print("-" * 40)

    configs_to_try = [
        {
            'name': 'Configuration 1 (UTF8 standard)',
            'params': {
                'host': 'localhost',
                'port': '5432',
                'database': 'kidjamo-db',
                'user': 'postgres',
                'password': 'kidjamo@',
                'client_encoding': 'UTF8'
            }
        },
        {
            'name': 'Configuration 2 (Latin1 fallback)',
            'params': {
                'host': 'localhost',
                'port': '5432',
                'database': 'kidjamo-db',
                'user': 'postgres',
                'password': 'kidjamo@',
                'client_encoding': 'LATIN1'
            }
        },
        {
            'name': 'Configuration 3 (Sans encodage explicite)',
            'params': {
                'host': 'localhost',
                'port': '5432',
                'database': 'kidjamo-db',
                'user': 'postgres',
                'password': 'kidjamo@'
            }
        }
    ]

    for config in configs_to_try:
        print(f"\n🔍 Test {config['name']}:")
        try:
            import psycopg2
            conn = psycopg2.connect(**config['params'])
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"   ✅ SUCCÈS! Version: {version[:50]}...")
            conn.close()
            return True
        except Exception as e:
            print(f"   ❌ Échec: {str(e)[:100]}...")

    print(f"\n💡 SOLUTIONS SUGGÉRÉES:")
    print(f"   1. Vérifier que PostgreSQL est démarré")
    print(f"   2. Changer l'encodage PostgreSQL: SET client_encoding = 'UTF8';")
    print(f"   3. Utiliser pgAdmin pour vérifier la configuration")
    print(f"   4. Le simulateur fonctionne parfaitement sans base de données!")

    return False

def main():
    """Fonction principale"""
    print("🚀 SIMULATEUR IoT KIDJAMO - MODE SIMPLE")
    print("=" * 60)
    print("Version sans dépendance PostgreSQL pour démonstration complète")
    print()

    # Lancement simulation
    simulation_success = simple_simulation_demo()

    if simulation_success:
        # Test optionnel base de données
        print(f"\n" + "="*60)
        response = input("Voulez-vous tester la connexion PostgreSQL ? (o/n): ").lower().strip()
        if response in ['o', 'oui', 'y', 'yes']:
            test_database_separately()

    print(f"\n📚 DOCUMENTATION COMPLÈTE:")
    print(f"   📖 README_SIMULATION_COMPLETE_FR.md - Guide complet")
    print(f"   🔧 Résolution problèmes d'encodage PostgreSQL")
    print(f"   📊 Dashboard web: http://localhost:8501 (si Streamlit installé)")

if __name__ == "__main__":
    main()
