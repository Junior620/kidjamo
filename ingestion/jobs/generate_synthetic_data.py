"""
Script de génération de données synthétiques pour les prédictions ML - Kidjamo
Génère des données IoT médicales synthétiques pour l'entraînement et les tests de modèles ML
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid
import random
import os

# Configuration
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


class SyntheticDataGenerator:
    """Générateur de données synthétiques pour les patients drépanocytaires"""

    def __init__(self, num_patients=100, days=30):
        """
        Args:
            num_patients: Nombre de patients à simuler
            days: Nombre de jours de données à générer
        """
        self.num_patients = num_patients
        self.days = days
        self.patients = self._generate_patients()

    def _generate_patients(self):
        """Génère les profils de patients"""
        patients = []
        for _ in range(self.num_patients):
            patient = {
                'patient_id': str(uuid.uuid4()),
                'age': np.random.randint(5, 65),
                'gender': random.choice(['M', 'F']),
                'severity': random.choice(['mild', 'moderate', 'severe']),
                'baseline_hr': np.random.randint(60, 100),
                'baseline_temp': np.random.uniform(36.5, 37.2),
                'baseline_spo2': np.random.uniform(95, 99),
            }
            patients.append(patient)
        return patients

    def generate_iot_measurements(self):
        """Génère les mesures IoT (heart rate, temperature, SpO2, etc.)"""
        data = []

        for patient in self.patients:
            start_date = datetime.now() - timedelta(days=self.days)

            # Générer des mesures toutes les 5 minutes
            num_measurements = self.days * 24 * 12  # 12 mesures par heure

            for i in range(num_measurements):
                timestamp = start_date + timedelta(minutes=5*i)

                # Simuler des variations selon la sévérité
                severity_factor = {
                    'mild': 1.0,
                    'moderate': 1.2,
                    'severe': 1.5
                }[patient['severity']]

                # Probabilité de crise selon la sévérité
                crisis_prob = {
                    'mild': 0.01,
                    'moderate': 0.05,
                    'severe': 0.1
                }[patient['severity']]

                is_crisis = random.random() < crisis_prob

                # Générer les mesures avec variations
                if is_crisis:
                    # Pendant une crise
                    heart_rate = patient['baseline_hr'] + np.random.normal(30, 10)
                    temperature = patient['baseline_temp'] + np.random.normal(1.5, 0.3)
                    spo2 = patient['baseline_spo2'] - np.random.normal(5, 2)
                    pain_level = np.random.randint(7, 11)
                else:
                    # Conditions normales
                    heart_rate = patient['baseline_hr'] + np.random.normal(0, 5)
                    temperature = patient['baseline_temp'] + np.random.normal(0, 0.2)
                    spo2 = patient['baseline_spo2'] + np.random.normal(0, 1)
                    pain_level = np.random.randint(0, 4)

                # Mesures additionnelles
                systolic_bp = np.random.normal(120, 15)
                diastolic_bp = np.random.normal(80, 10)
                respiratory_rate = np.random.normal(16, 2)

                measurement = {
                    'measurement_id': str(uuid.uuid4()),
                    'patient_id': patient['patient_id'],
                    'timestamp': timestamp.isoformat(),
                    'heart_rate': max(40, min(200, heart_rate)),
                    'temperature': max(35.0, min(42.0, temperature)),
                    'spo2': max(70, min(100, spo2)),
                    'systolic_bp': max(80, min(200, systolic_bp)),
                    'diastolic_bp': max(50, min(120, diastolic_bp)),
                    'respiratory_rate': max(10, min(30, respiratory_rate)),
                    'pain_level': max(0, min(10, pain_level)),
                    'is_crisis': is_crisis,
                    'patient_age': patient['age'],
                    'patient_gender': patient['gender'],
                    'patient_severity': patient['severity']
                }
                data.append(measurement)

        return pd.DataFrame(data)

    def generate_clinical_events(self):
        """Génère les événements cliniques (hospitalisations, crises, etc.)"""
        events = []

        for patient in self.patients:
            # Nombre d'événements selon la sévérité
            num_events = {
                'mild': np.random.randint(1, 3),
                'moderate': np.random.randint(2, 5),
                'severe': np.random.randint(3, 8)
            }[patient['severity']]

            for _ in range(num_events):
                event_date = datetime.now() - timedelta(days=np.random.randint(0, self.days))

                event_type = random.choice([
                    'vaso_occlusive_crisis',
                    'acute_chest_syndrome',
                    'hospitalization',
                    'blood_transfusion',
                    'pain_episode'
                ])

                event = {
                    'event_id': str(uuid.uuid4()),
                    'patient_id': patient['patient_id'],
                    'event_type': event_type,
                    'event_date': event_date.isoformat(),
                    'duration_hours': np.random.randint(2, 72),
                    'severity_score': np.random.randint(1, 10),
                    'required_hospitalization': random.choice([True, False]),
                    'treatment_given': random.choice(['analgesics', 'hydration', 'oxygen', 'transfusion'])
                }
                events.append(event)

        return pd.DataFrame(events)

    def generate_heat_index_data(self):
        """Génère les données d'index de chaleur (facteur environnemental)"""
        data = []

        start_date = datetime.now() - timedelta(days=self.days)

        # Générer des données horaires
        for i in range(self.days * 24):
            timestamp = start_date + timedelta(hours=i)

            # Simuler un cycle jour/nuit
            hour = timestamp.hour
            if 6 <= hour <= 18:  # Jour
                temperature = np.random.normal(28, 5)
                humidity = np.random.normal(65, 10)
            else:  # Nuit
                temperature = np.random.normal(22, 3)
                humidity = np.random.normal(75, 8)

            # Calculer l'index de chaleur
            heat_index = temperature + 0.5555 * ((humidity/100) * 6.112 * np.exp(17.67 * temperature / (temperature + 243.5)) - 10)

            data.append({
                'timestamp': timestamp.isoformat(),
                'temperature_celsius': max(15, min(45, temperature)),
                'humidity_percent': max(20, min(100, humidity)),
                'heat_index': max(15, min(50, heat_index)),
                'risk_level': 'high' if heat_index > 32 else 'medium' if heat_index > 27 else 'low'
            })

        return pd.DataFrame(data)

    def generate_features_for_ml(self):
        """Génère un dataset avec features engineered pour le ML"""
        measurements = self.generate_iot_measurements()

        # Feature engineering
        measurements['hr_temp_ratio'] = measurements['heart_rate'] / measurements['temperature']
        measurements['oxygen_deficit'] = 100 - measurements['spo2']
        measurements['bp_product'] = measurements['systolic_bp'] * measurements['diastolic_bp']
        measurements['vital_score'] = (
            measurements['heart_rate'] / 100 +
            measurements['temperature'] / 37 +
            (100 - measurements['spo2']) / 10 +
            measurements['pain_level'] / 10
        )

        # Ajouter des features temporelles
        measurements['hour'] = pd.to_datetime(measurements['timestamp']).dt.hour
        measurements['day_of_week'] = pd.to_datetime(measurements['timestamp']).dt.dayofweek
        measurements['is_night'] = measurements['hour'].apply(lambda x: 1 if x < 6 or x > 22 else 0)

        # Features de tendance (sur les 5 dernières mesures)
        for col in ['heart_rate', 'temperature', 'spo2']:
            measurements[f'{col}_trend'] = measurements.groupby('patient_id')[col].transform(
                lambda x: x.rolling(window=5, min_periods=1).mean()
            )

        # Label pour la prédiction (prédire une crise dans les 2h)
        measurements['crisis_in_2h'] = measurements.groupby('patient_id')['is_crisis'].shift(-24)  # 24 mesures = 2h
        measurements['crisis_in_2h'] = measurements['crisis_in_2h'].fillna(0).astype(int)

        return measurements

    def save_all_datasets(self, output_dir='./synthetic_data'):
        """Sauvegarde tous les datasets générés"""
        os.makedirs(output_dir, exist_ok=True)

        print(f"🔄 Génération de données synthétiques pour {self.num_patients} patients sur {self.days} jours...")

        # 1. Mesures IoT
        print("📊 Génération des mesures IoT...")
        measurements = self.generate_iot_measurements()
        measurements.to_csv(f'{output_dir}/iot_measurements.csv', index=False)
        print(f"   ✅ {len(measurements)} mesures générées -> {output_dir}/iot_measurements.csv")

        # 2. Événements cliniques
        print("🏥 Génération des événements cliniques...")
        events = self.generate_clinical_events()
        events.to_csv(f'{output_dir}/clinical_events.csv', index=False)
        print(f"   ✅ {len(events)} événements générés -> {output_dir}/clinical_events.csv")

        # 3. Index de chaleur
        print("🌡️  Génération des données d'index de chaleur...")
        heat_index = self.generate_heat_index_data()
        heat_index.to_csv(f'{output_dir}/heat_index.csv', index=False)
        print(f"   ✅ {len(heat_index)} mesures générées -> {output_dir}/heat_index.csv")

        # 4. Features ML
        print("🤖 Génération des features pour le ML...")
        ml_features = self.generate_features_for_ml()
        ml_features.to_csv(f'{output_dir}/ml_features.csv', index=False)
        print(f"   ✅ {len(ml_features)} features générées -> {output_dir}/ml_features.csv")

        # 5. Sauvegarde des profils patients
        print("👥 Sauvegarde des profils patients...")
        patients_df = pd.DataFrame(self.patients)
        patients_df.to_csv(f'{output_dir}/patients.csv', index=False)
        print(f"   ✅ {len(patients_df)} patients -> {output_dir}/patients.csv")

        # Statistiques
        print("\n📈 Statistiques des données générées:")
        print(f"   - Patients: {self.num_patients}")
        print(f"   - Mesures IoT: {len(measurements):,}")
        print(f"   - Événements cliniques: {len(events)}")
        print(f"   - Crises détectées: {measurements['is_crisis'].sum()}")
        print(f"   - Taux de crises: {measurements['is_crisis'].mean()*100:.2f}%")
        print(f"\n✅ Tous les datasets sont sauvegardés dans: {output_dir}/")

        return {
            'measurements': measurements,
            'events': events,
            'heat_index': heat_index,
            'ml_features': ml_features,
            'patients': patients_df
        }


def main():
    """Fonction principale pour générer les données"""
    # Configuration
    NUM_PATIENTS = 100
    NUM_DAYS = 30
    OUTPUT_DIR = './synthetic_data'

    print("=" * 80)
    print("🚀 GÉNÉRATEUR DE DONNÉES SYNTHÉTIQUES - KIDJAMO")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  - Nombre de patients: {NUM_PATIENTS}")
    print(f"  - Période: {NUM_DAYS} jours")
    print(f"  - Dossier de sortie: {OUTPUT_DIR}")
    print("=" * 80 + "\n")

    # Générer les données
    generator = SyntheticDataGenerator(num_patients=NUM_PATIENTS, days=NUM_DAYS)
    datasets = generator.save_all_datasets(output_dir=OUTPUT_DIR)

    print("\n" + "=" * 80)
    print("✅ GÉNÉRATION TERMINÉE AVEC SUCCÈS!")
    print("=" * 80)
    print("\n💡 Utilisation des données:")
    print("   - Pour l'entraînement ML: ml_features.csv")
    print("   - Pour l'analyse clinique: clinical_events.csv")
    print("   - Pour les tests de pipeline: iot_measurements.csv")
    print("\n🔥 Les données sont prêtes pour les prédictions!")


if __name__ == "__main__":
    main()

