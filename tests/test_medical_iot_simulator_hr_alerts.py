import unittest
from datetime import datetime

from data.pipelines.iot_streaming.pipeline_iot_streaming_kafka_local.simulator.medical_iot_simulator import (
    MedicalIoTSimulator,
    PatientProfile,
    IoTMeasurement,
)


class TestSimulatorHR(MedicalIoTSimulator):
    def __init__(self):
        super().__init__(api_endpoint="http://localhost:8001")
        # Disable Kafka to avoid external dependency during tests
        self.kafka_producer = None
        self.published_alerts = []

    def _publish_alert(self, alert):
        # Capture alerts in memory for assertions
        self.published_alerts.append(alert)


class HeartRateAlertTests(unittest.TestCase):
    def setUp(self):
        self.sim = TestSimulatorHR()
        self.patient = PatientProfile(
            patient_id="test-patient-hr-1",
            age=12,
            genotype="SS",
            risk_level="high",
            base_heart_rate=85,
            base_spo2=95.0,
            base_temperature=36.7,
            activity_pattern="moderate",
        )

    def make_measurement(self, hr_value: int) -> IoTMeasurement:
        return IoTMeasurement(
            device_id="dev-hr-1",
            patient_id=self.patient.patient_id,
            timestamp=datetime.now().isoformat(),
            measurements={
                "freq_resp": 18,
                "freq_card": hr_value,
                "spo2_pct": 97.0,
                "temp_corp": 37.0,
            },
            device_info={
                "device_id": "dev-hr-1",
                "battery_level": 80,
                "signal_strength": 90,
                "status": "connected",
            },
            quality_indicators={
                "quality_flag": "ok",
                "confidence_score": 95,
            },
        )

    def test_hr_alert_high_tachycardia_ge_150(self):
        m = self.make_measurement(150)
        self.sim._check_and_alert_heart_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        alert = self.sim.published_alerts[0]
        self.assertEqual(alert["alert_type"], "heart_rate")
        self.assertEqual(alert["severity"], "high")
        self.assertIn("Tachycardie", alert["message"])  # message contains label

    def test_hr_alert_critical_tachycardia_ge_170(self):
        m = self.make_measurement(175)
        self.sim._check_and_alert_heart_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        self.assertEqual(self.sim.published_alerts[0]["severity"], "critical")

    def test_hr_alert_high_bradycardia_le_50(self):
        m = self.make_measurement(50)
        self.sim._check_and_alert_heart_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        self.assertEqual(self.sim.published_alerts[0]["severity"], "high")
        self.assertIn("Bradycardie", self.sim.published_alerts[0]["message"]) 

    def test_hr_alert_critical_bradycardia_le_40(self):
        m = self.make_measurement(35)
        self.sim._check_and_alert_heart_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        self.assertEqual(self.sim.published_alerts[0]["severity"], "critical")

    def test_hr_no_alert_for_normal(self):
        m = self.make_measurement(85)
        self.sim._check_and_alert_heart_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 0)


if __name__ == "__main__":
    unittest.main()