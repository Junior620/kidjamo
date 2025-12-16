#!/usr/bin/env python3
"""
KIDJAMO - GÉNÉRATEUR DE DONNÉES DE TEST À GRANDE ÉCHELLE
========================================================

Ce script génère des données de test réalistes pour valider :
- Performance avec gros volumes (10k+ mesures)
- Fonctionnement des partitions
- Système d'alertes sous charge
- Vues matérialisées avec données volumineuses
- Row-Level Security avec nombreux utilisateurs

Usage:
    python generate_test_data.py --measurements=10000 --patients=100
    python generate_test_data.py --measurements=50000 --patients=500 --days=30
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import psycopg2
from psycopg2.extras import execute_batch
import json
import sys
from pathlib import Path

# Configuration par défaut
DEFAULT_CONFIG = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "kidjamo_db",
        "user": "postgres",
        "password": "your_password"
    },
    "medical_profiles": {
        "SS": {  # Drépanocytose homozygote (grave)
            "spo2_range": (85, 98),
            "heart_rate_range": (70, 140),
            "crisis_probability": 0.15,
            "alert_threshold_spo2": 90
        },
        "SC": {  # Drépanocytose SC
            "spo2_range": (88, 99),
            "heart_rate_range": (65, 120),
            "crisis_probability": 0.08,
            "alert_threshold_spo2": 88
        },
        "AS": {  # Trait drépanocytaire (léger)
            "spo2_range": (95, 99),
            "heart_rate_range": (60, 100),
            "crisis_probability": 0.02,
            "alert_threshold_spo2": 85
        },
        "Sβ0": {  # Bêta-thalassémie sévère
            "spo2_range": (86, 97),
            "heart_rate_range": (75, 130),
            "crisis_probability": 0.12,
            "alert_threshold_spo2": 88
        },
        "Sβ+": {  # Bêta-thalassémie modérée
            "spo2_range": (90, 98),
            "heart_rate_range": (65, 115),
            "crisis_probability": 0.06,
            "alert_threshold_spo2": 87
        }
    }
}

class KidjamoTestDataGenerator:
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.medical_profiles = DEFAULT_CONFIG["medical_profiles"]

    def connect_db(self):
        """Connexion à la base de données PostgreSQL"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = False
            print("✅ Connexion à la base de données établie")
        except Exception as e:
            print(f"❌ Erreur de connexion DB: {e}")
            sys.exit(1)

    def close_db(self):
        """Fermeture de la connexion"""
        if self.conn:
            self.conn.close()

    def generate_realistic_names(self, count: int) -> List[Tuple[str, str]]:
        """Génère des noms français réalistes"""
        first_names = [
            "Alice", "Emma", "Léa", "Chloé", "Manon", "Sarah", "Jade", "Louise", "Lola", "Amber",
            "Lucas", "Hugo", "Tom", "Nathan", "Louis", "Arthur", "Gabriel", "Jules", "Noah", "Adam",
            "Inès", "Camille", "Marie", "Clara", "Zoé", "Lisa", "Anna", "Eva", "Mia", "Nina",
            "Raphaël", "Léo", "Maël", "Paul", "Victor", "Antoine", "Théo", "Alexandre", "Pierre", "Maxime"
        ]

        last_names = [
            "Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau", "Laurent",
            "Simon", "Michel", "Lefebvre", "Leroy", "Roux", "David", "Bertrand", "Morel", "Fournier", "Girard",
            "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau", "Vincent", "Muller", "Lefevre", "Faure", "Andre"
        ]

        names = []
        for _ in range(count):
            first = random.choice(first_names)
            last = random.choice(last_names)
            names.append((first, last))

        return names

    def generate_medical_profile(self, genotype: str, age_years: int) -> Dict:
        """Génère un profil médical réaliste selon le génotype et l'âge"""
        profile = self.medical_profiles[genotype].copy()

        # Ajustements selon l'âge
        if age_years < 5:
            # Enfants plus fragiles
            profile["heart_rate_range"] = (
                profile["heart_rate_range"][0] + 20,
                profile["heart_rate_range"][1] + 30
            )
            profile["crisis_probability"] *= 1.5
        elif age_years > 60:
            # Adultes âgés plus à risque
            profile["crisis_probability"] *= 1.3

        return profile

    def generate_users_and_patients(self, patient_count: int) -> List[Dict]:
        """Génère des utilisateurs et patients avec profils réalistes"""
        print(f"🧑‍🤝‍🧑 Génération de {patient_count} patients...")

        names = self.generate_realistic_names(patient_count * 3)  # Patients + parents
        genotypes = ["SS", "AS", "SC", "Sβ0", "Sβ+"]
        genotype_weights = [0.25, 0.40, 0.15, 0.12, 0.08]  # Distribution réaliste

        patients_data = []

        for i in range(patient_count):
            # Génération patient
            patient_first, patient_last = names[i]
            parent1_first, parent1_last = names[patient_count + i]
            parent2_first, parent2_last = names[patient_count * 2 + i]

            # Âge réaliste (0-80 ans, majorité enfants/ados)
            age_distribution = random.choices(
                [random.randint(0, 5), random.randint(6, 12), random.randint(13, 17),
                 random.randint(18, 40), random.randint(41, 80)],
                weights=[0.2, 0.3, 0.25, 0.15, 0.1]
            )[0]

            birth_date = datetime.now() - timedelta(days=age_distribution * 365.25 + random.randint(0, 365))

            # Génotype selon distribution épidémiologique
            genotype = random.choices(genotypes, weights=genotype_weights)[0]

            # Profil médical
            medical_profile = self.generate_medical_profile(genotype, age_distribution)

            patient_data = {
                "patient_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "parent1_id": str(uuid.uuid4()),
                "parent2_id": str(uuid.uuid4()),
                "first_name": patient_first,
                "last_name": patient_last,
                "parent1_name": f"{parent1_first} {parent1_last}",
                "parent2_name": f"{parent2_first} {parent2_last}",
                "genotype": genotype,
                "birth_date": birth_date.date(),
                "age_years": age_distribution,
                "weight_kg": max(3.0, age_distribution * 3.5 + random.uniform(-5, 10)),
                "height_cm": max(50, age_distribution * 6 + random.uniform(-10, 15)),
                "device_id": str(uuid.uuid4()),
                "medical_profile": medical_profile,
                "email": f"{patient_first.lower()}.{patient_last.lower()}@test.kidjamo.com"
            }

            patients_data.append(patient_data)

            if (i + 1) % 100 == 0:
                print(f"  ✓ {i + 1} patients générés...")

        return patients_data

    def insert_users_and_patients(self, patients_data: List[Dict]):
        """Insertion des utilisateurs et patients dans la DB"""
        print("💾 Insertion des utilisateurs et patients...")

        cursor = self.conn.cursor()

        # Insertion des utilisateurs (patients + parents)
        users_sql = """
        INSERT INTO users (user_id, role, first_name, last_name, email, password_hash, country, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """

        users_data = []
        patients_sql_data = []
        caregivers_sql_data = []

        for patient in patients_data:
            # Generate unique timestamp suffix to avoid email conflicts
            timestamp_suffix = str(int(datetime.now().timestamp()))

            # Patient user
            users_data.append((
                patient["user_id"], "patient", patient["first_name"], patient["last_name"],
                f"{patient['first_name'].lower()}.{patient['last_name'].lower()}.{timestamp_suffix}@test.kidjamo.com",
                "hash_test", "France", True
            ))

            # Parents users
            parent1_email = f"parent1.{patient['last_name'].lower()}.{timestamp_suffix}@test.kidjamo.com"
            parent2_email = f"parent2.{patient['last_name'].lower()}.{timestamp_suffix}@test.kidjamo.com"

            users_data.append((
                patient["parent1_id"], "parent", patient["parent1_name"].split()[0],
                patient["parent1_name"].split()[1], parent1_email, "hash_parent", "France", True
            ))

            users_data.append((
                patient["parent2_id"], "tuteur", patient["parent2_name"].split()[0],
                patient["parent2_name"].split()[1], parent2_email, "hash_tuteur", "France", True
            ))

            # Patient data
            patients_sql_data.append((
                patient["patient_id"], patient["user_id"], patient["genotype"],
                patient["birth_date"], patient["weight_kg"], patient["height_cm"],
                patient["parent1_name"], "+33" + "".join([str(random.randint(0, 9)) for _ in range(9)]),
                patient["device_id"]
            ))

            # Caregivers relationships
            caregivers_sql_data.append((
                patient["parent1_id"], patient["patient_id"], "parent", 1, True
            ))
            caregivers_sql_data.append((
                patient["parent2_id"], patient["patient_id"], "tuteur", 2, True
            ))

        # Execute insertions
        execute_batch(cursor, users_sql, users_data, page_size=1000)
        print(f"  ✓ {len(users_data)} utilisateurs insérés")

        patients_sql = """
        INSERT INTO patients (patient_id, user_id, genotype, birth_date, weight_kg, height_cm, 
                            emergency_contact_name, emergency_contact_phone, current_device_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (patient_id) DO NOTHING
        """
        execute_batch(cursor, patients_sql, patients_sql_data, page_size=1000)
        print(f"  ✓ {len(patients_sql_data)} patients insérés")

        caregivers_sql = """
        INSERT INTO caregivers (user_id, patient_id, relationship, priority_level, can_acknowledge_alerts)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id, patient_id) DO NOTHING
        """
        execute_batch(cursor, caregivers_sql, caregivers_sql_data, page_size=1000)
        print(f"  ✓ {len(caregivers_sql_data)} relations tuteur-patient insérées")

        self.conn.commit()
        cursor.close()

    def generate_realistic_measurements(self, patients_data: List[Dict], measurements_per_patient: int, days_back: int = 7) -> List[Dict]:
        """Génère des mesures médicales réalistes avec patterns temporels"""
        print(f"📊 Génération de {measurements_per_patient * len(patients_data)} mesures sur {days_back} jours...")

        measurements = []
        now = datetime.now()

        for patient in patients_data:
            profile = patient["medical_profile"]

            # Timeline réaliste : plus de mesures récentes
            for i in range(measurements_per_patient):
                # Distribution temporelle non-uniforme (plus récent = plus probable)
                time_weight = random.betavariate(0.5, 2)  # Bias vers temps récent
                hours_back = time_weight * days_back * 24
                recorded_at = now - timedelta(hours=hours_back)

                # Simulation de crise (selon probabilité du profil)
                is_crisis = random.random() < profile["crisis_probability"] / (days_back * 24 / measurements_per_patient)

                if is_crisis:
                    # Valeurs de crise
                    spo2 = random.uniform(75, profile["alert_threshold_spo2"])
                    heart_rate = random.uniform(
                        profile["heart_rate_range"][1] + 20,
                        profile["heart_rate_range"][1] + 60
                    )
                    temperature = random.uniform(37.8, 40.0)
                    pain_scale = random.randint(7, 10)
                    quality_flag = random.choices(
                        ["ok", "motion", "low_perfusion"],
                        weights=[0.6, 0.3, 0.1]
                    )[0]
                else:
                    # Valeurs normales avec variabilité
                    spo2 = random.uniform(*profile["spo2_range"])
                    heart_rate = random.uniform(*profile["heart_rate_range"])
                    temperature = random.uniform(36.1, 37.5)
                    pain_scale = random.randint(0, 3)
                    quality_flag = random.choices(
                        ["ok", "motion", "low_signal", "noise"],
                        weights=[0.85, 0.08, 0.05, 0.02]
                    )[0]

                # Autres paramètres physiologiques
                respiratory_rate = max(12, min(35, heart_rate // 4 + random.randint(-3, 5)))
                hydration = random.uniform(70, 95) if not is_crisis else random.uniform(60, 80)
                activity_level = random.randint(0, 10) if not is_crisis else random.randint(0, 3)

                measurement = {
                    "patient_id": patient["patient_id"],
                    "device_id": patient["device_id"],
                    "recorded_at": recorded_at,
                    "heart_rate_bpm": int(heart_rate),
                    "respiratory_rate_min": int(respiratory_rate),
                    "spo2_percent": round(spo2, 1),
                    "temperature_celsius": round(temperature, 1),
                    "ambient_temp_celsius": round(random.uniform(18, 28), 1),
                    "hydration_percent": round(hydration, 1),
                    "activity_level": activity_level,
                    "pain_scale": pain_scale,
                    "battery_percent": random.randint(20, 100),
                    "signal_quality": random.randint(70, 100),
                    "quality_flag": quality_flag,
                    "is_crisis": is_crisis
                }

                measurements.append(measurement)

        # Tri chronologique
        measurements.sort(key=lambda x: x["recorded_at"])
        return measurements

    def insert_measurements(self, measurements: List[Dict]):
        """Insertion des mesures avec gestion des partitions"""
        print("💾 Insertion des mesures (avec partitioning automatique)...")

        cursor = self.conn.cursor()

        measurements_sql = """
        INSERT INTO measurements (
            patient_id, device_id, recorded_at, heart_rate_bpm, respiratory_rate_min,
            spo2_percent, temperature_celsius, ambient_temp_celsius, hydration_percent,
            activity_level, pain_scale, battery_percent, signal_quality, quality_flag
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        measurements_data = [
            (
                m["patient_id"], m["device_id"], m["recorded_at"],
                m["heart_rate_bpm"], m["respiratory_rate_min"], m["spo2_percent"],
                m["temperature_celsius"], m["ambient_temp_celsius"], m["hydration_percent"],
                m["activity_level"], m["pain_scale"], m["battery_percent"],
                m["signal_quality"], m["quality_flag"]
            )
            for m in measurements
        ]

        # Insertion par batch pour performance
        batch_size = 1000
        total_inserted = 0

        for i in range(0, len(measurements_data), batch_size):
            batch = measurements_data[i:i + batch_size]
            execute_batch(cursor, measurements_sql, batch, page_size=batch_size)
            total_inserted += len(batch)

            if total_inserted % 5000 == 0:
                print(f"  ✓ {total_inserted} mesures insérées...")

        print(f"  ✓ {total_inserted} mesures insérées au total")

        self.conn.commit()
        cursor.close()

        return measurements

    def generate_alerts_from_measurements(self, measurements: List[Dict], patients_data: List[Dict]):
        """Génère des alertes basées sur les mesures critiques"""
        print("🚨 Génération d'alertes automatiques...")

        cursor = self.conn.cursor()
        patients_dict = {p["patient_id"]: p for p in patients_data}

        alerts_data = []
        crisis_measurements = [m for m in measurements if m["is_crisis"]]

        for measurement in crisis_measurements:
            patient = patients_dict[measurement["patient_id"]]

            # Déterminer type et sévérité d'alerte
            if measurement["spo2_percent"] < 85:
                severity = "critical"
                alert_type = "hypoxemia_critical"
                title = "SpO2 Critique - Intervention Immédiate"
            elif measurement["spo2_percent"] < patient["medical_profile"]["alert_threshold_spo2"]:
                severity = "alert"
                alert_type = "hypoxemia_moderate"
                title = "SpO2 Bas - Surveillance Renforcée"
            elif measurement["pain_scale"] >= 8:
                severity = "alert"
                alert_type = "pain_severe"
                title = "Douleur Sévère Détectée"
            elif measurement["temperature_celsius"] > 38.5:
                severity = "warn"
                alert_type = "fever_high"
                title = "Fièvre Élevée"
            else:
                continue

            vitals_snapshot = {
                "spo2": measurement["spo2_percent"],
                "heart_rate": measurement["heart_rate_bpm"],
                "temperature": measurement["temperature_celsius"],
                "pain_scale": measurement["pain_scale"],
                "recorded_at": measurement["recorded_at"].isoformat()
            }

            # Délai d'acquittement selon sévérité
            ack_deadline = None
            if severity == "critical":
                ack_deadline = measurement["recorded_at"] + timedelta(minutes=5)
            elif severity == "alert":
                ack_deadline = measurement["recorded_at"] + timedelta(minutes=15)

            alert = (
                measurement["patient_id"], alert_type, severity, title,
                f"Alerte générée par mesure: SpO2={measurement['spo2_percent']}%, FC={measurement['heart_rate_bpm']}bpm",
                json.dumps(vitals_snapshot), measurement["recorded_at"], ack_deadline
            )

            alerts_data.append(alert)

        if alerts_data:
            alerts_sql = """
            INSERT INTO alerts (
                patient_id, alert_type, severity, title, message,
                vitals_snapshot, created_at, ack_deadline
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            execute_batch(cursor, alerts_sql, alerts_data, page_size=500)
            print(f"  ✓ {len(alerts_data)} alertes générées")

        self.conn.commit()
        cursor.close()

    def refresh_materialized_views(self):
        """Rafraîchit les vues matérialisées avec les nouvelles données"""
        print("🔄 Rafraîchissement des vues matérialisées...")

        cursor = self.conn.cursor()

        try:
            cursor.execute("REFRESH MATERIALIZED VIEW mv_patient_realtime_metrics;")
            print("  ✓ mv_patient_realtime_metrics rafraîchie")

            cursor.execute("REFRESH MATERIALIZED VIEW mv_patient_weekly_trends;")
            print("  ✓ mv_patient_weekly_trends rafraîchie")

            self.conn.commit()
        except Exception as e:
            print(f"  ⚠️ Erreur rafraîchissement vues: {e}")

        cursor.close()

    def generate_performance_report(self):
        """Génère un rapport de performance après insertion"""
        print("📊 Génération du rapport de performance...")

        cursor = self.conn.cursor()

        # Statistiques générales
        stats_queries = {
            "Utilisateurs totaux": "SELECT COUNT(*) FROM users",
            "Patients totaux": "SELECT COUNT(*) FROM patients",
            "Mesures totales": "SELECT COUNT(*) FROM measurements",
            "Alertes actives": "SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL",
            "Partitions measurements": "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'measurements_%'",
            "Partitions audit_logs": "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'audit_logs_%'"
        }

        print("\n📈 STATISTIQUES FINALES:")
        print("=" * 40)

        for stat_name, query in stats_queries.items():
            cursor.execute(query)
            result = cursor.fetchone()[0]
            print(f"{stat_name:.<25} {result:>10}")

        # Performance des requêtes
        print("\n⚡ TESTS DE PERFORMANCE:")
        print("=" * 40)

        import time

        # Test requête dashboard
        start_time = time.time()
        cursor.execute("SELECT COUNT(*) FROM mv_patient_realtime_metrics")
        dashboard_time = time.time() - start_time
        print(f"Dashboard temps réel.......... {dashboard_time*1000:.1f}ms")

        # Test requête mesures récentes
        start_time = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM measurements 
            WHERE recorded_at >= now() - INTERVAL '24 hours'
        """)
        recent_measurements_time = time.time() - start_time
        print(f"Mesures 24h................... {recent_measurements_time*1000:.1f}ms")

        # Test alertes critiques
        start_time = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM alerts 
            WHERE severity = 'critical' AND resolved_at IS NULL
        """)
        critical_alerts_time = time.time() - start_time
        print(f"Alertes critiques............. {critical_alerts_time*1000:.1f}ms")

        cursor.close()

        print("\n🎉 GÉNÉRATION DE DONNÉES TERMINÉE AVEC SUCCÈS!")

def main():
    parser = argparse.ArgumentParser(description="Générateur de données de test Kidjamo")
    parser.add_argument("--measurements", type=int, default=1000, help="Nombre de mesures par patient")
    parser.add_argument("--patients", type=int, default=10, help="Nombre de patients à créer")
    parser.add_argument("--days", type=int, default=7, help="Historique en jours")
    parser.add_argument("--host", default="localhost", help="Host PostgreSQL")
    parser.add_argument("--port", type=int, default=5432, help="Port PostgreSQL")
    parser.add_argument("--database", default="kidjamo_db", help="Nom de la base")
    parser.add_argument("--user", default="postgres", help="Utilisateur PostgreSQL")
    parser.add_argument("--password", default="your_password", help="Mot de passe PostgreSQL")

    args = parser.parse_args()

    # Configuration DB
    db_config = {
        "host": args.host,
        "port": args.port,
        "database": args.database,
        "user": args.user,
        "password": args.password
    }

    print("🏥 KIDJAMO - GÉNÉRATEUR DE DONNÉES DE TEST")
    print("=" * 50)
    print(f"Patients à créer: {args.patients}")
    print(f"Mesures par patient: {args.measurements}")
    print(f"Historique: {args.days} jours")
    print(f"Total mesures: {args.patients * args.measurements:,}")
    print("=" * 50)

    # Confirmation
    response = input("Continuer? (y/N): ")
    if response.lower() != 'y':
        print("Annulé.")
        return

    # Génération
    generator = KidjamoTestDataGenerator(db_config)

    try:
        generator.connect_db()

        # 1. Génération des patients
        patients_data = generator.generate_users_and_patients(args.patients)
        generator.insert_users_and_patients(patients_data)

        # 2. Génération des mesures
        measurements = generator.generate_realistic_measurements(
            patients_data, args.measurements, args.days
        )
        generator.insert_measurements(measurements)

        # 3. Génération des alertes
        generator.generate_alerts_from_measurements(measurements, patients_data)

        # 4. Rafraîchissement des vues
        generator.refresh_materialized_views()

        # 5. Rapport final
        generator.generate_performance_report()

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.close_db()

if __name__ == "__main__":
    main()
