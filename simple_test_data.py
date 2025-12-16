#!/usr/bin/env python3
"""
Simple Test Data Generator for KidJamo Alerting System
Creates basic patient data and measurements to test the alerting system
"""

import psycopg2
import uuid
from datetime import datetime, timedelta
import random

def create_test_data():
    """Create simple test data for the alerting system"""

    # Database configuration matching your alerting system
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        cursor = conn.cursor()

        print("✅ Connected to KidJamo database")

        # Set a session variable for audit logging to avoid the foreign key issue
        cursor.execute("SET LOCAL kidjamo.current_user_id = '00000000-0000-0000-0000-000000000001';")

        # Create a test patient
        patient_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())

        # Insert test user first (this will be referenced by audit logs)
        cursor.execute("""
            INSERT INTO users (user_id, role, first_name, last_name, email, password_hash, country, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, 'patient', 'Test', 'Patient', 'test.patient@kidjamo.com', 'hash_test', 'France', True))

        # Update the session variable to use the actual user we just created
        cursor.execute(f"SET LOCAL kidjamo.current_user_id = '{user_id}';")

        # Insert test patient
        cursor.execute("""
            INSERT INTO patients (patient_id, user_id, genotype, birth_date, weight_kg, height_cm, 
                                emergency_contact_name, emergency_contact_phone, current_device_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (patient_id) DO NOTHING
        """, (patient_id, user_id, 'SS', datetime.now().date() - timedelta(days=365*10), 35.0, 140.0,
              'Parent Test', '+33123456789', device_id))

        print(f"✅ Created test patient: {patient_id}")

        # Create some recent measurements with varying vitals
        measurements = []
        now = datetime.now()

        for i in range(10):
            recorded_at = now - timedelta(minutes=i*30)  # Every 30 minutes

            # Create some normal and some concerning measurements
            if i % 3 == 0:  # Every 3rd measurement has concerning values
                spo2 = random.uniform(82, 87)  # Low oxygen - should trigger alert
                heart_rate = random.randint(120, 150)  # High heart rate
                temperature = random.uniform(38.0, 39.0)  # Fever
                pain_scale = random.randint(6, 9)  # High pain
            else:
                spo2 = random.uniform(95, 99)  # Normal oxygen
                heart_rate = random.randint(70, 100)  # Normal heart rate
                temperature = random.uniform(36.5, 37.2)  # Normal temperature
                pain_scale = random.randint(0, 3)  # Low pain

            measurement = (
                patient_id, device_id, recorded_at,
                heart_rate, random.randint(16, 24),  # respiratory_rate
                spo2, temperature, random.uniform(20, 25),  # ambient_temp
                random.uniform(75, 90), random.randint(3, 8),  # hydration, activity
                pain_scale, random.randint(60, 100),  # battery
                random.randint(80, 100), 'ok'  # signal_quality, quality_flag
            )
            measurements.append(measurement)

        # Insert measurements
        cursor.executemany("""
            INSERT INTO measurements (
                patient_id, device_id, recorded_at, heart_rate_bpm, respiratory_rate_min,
                spo2_percent, temperature_celsius, ambient_temp_celsius, hydration_percent,
                activity_level, pain_scale, battery_percent, signal_quality, quality_flag
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, measurements)

        print(f"✅ Created {len(measurements)} test measurements")

        # Commit all changes
        conn.commit()

        print("🎉 Test data created successfully!")
        print(f"📊 Patient ID: {patient_id}")
        print("📈 Measurements include both normal and concerning vitals")
        print("🚨 Some measurements should trigger alerts in your monitoring system")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        return False

if __name__ == "__main__":
    print("🏥 KIDJAMO - Simple Test Data Generator")
    print("=" * 50)

    if create_test_data():
        print("\n✅ Ready to test your alerting system!")
        print("Run your main_alerting_system.py again to see active patients and alerts")
    else:
        print("\n❌ Failed to create test data")
