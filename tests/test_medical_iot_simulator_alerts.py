import unittest
from datetime import datetime

from data.pipelines.iot_streaming.pipeline_iot_streaming_kafka_local.simulator.medical_iot_simulator import (
    MedicalIoTSimulator,
    PatientProfile,
    IoTMeasurement,
)


class TestSimulator(MedicalIoTSimulator):
    def __init__(self):
        super().__init__(api_endpoint="http://localhost:8001")
        # Disable Kafka to avoid external dependency during tests
        self.kafka_producer = None
        self.published_alerts = []

    def _publish_alert(self, alert):
        # Capture alerts in memory for assertions
        self.published_alerts.append(alert)


class RespiratoryAlertTests(unittest.TestCase):
    def setUp(self):
        self.sim = TestSimulator()
        self.patient = PatientProfile(
            patient_id="test-patient-1234",
            age=10,
            genotype="SS",
            risk_level="high",
            base_heart_rate=90,
            base_spo2=95.0,
            base_temperature=36.8,
            activity_pattern="moderate",
        )

    def make_measurement(self, rr_value: int) -> IoTMeasurement:
        return IoTMeasurement(
            device_id="dev-1",
            patient_id=self.patient.patient_id,
            timestamp=datetime.now().isoformat(),
            measurements={
                "freq_resp": rr_value,
                "freq_card": 100,
                "spo2_pct": 97.0,
                "temp_corp": 37.0,
            },
            device_info={
                "device_id": "dev-1",
                "battery_level": 80,
                "signal_strength": 90,
                "status": "connected",
            },
            quality_indicators={
                "quality_flag": "ok",
                "confidence_score": 95,
            },
        )

    def test_alert_emitted_for_tachypnea_ge_30(self):
        m = self.make_measurement(31)
        self.sim._check_and_alert_resp_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        alert = self.sim.published_alerts[0]
        self.assertEqual(alert["alert_type"], "respiratory_rate")
        self.assertEqual(alert["severity"], "high")
        self.assertIn("Tachypnée", alert["message"])  # message contains label

    def test_no_alert_for_normal_rr(self):
        m = self.make_measurement(16)
        self.sim._check_and_alert_resp_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 0)

    def test_critical_alert_for_severe_tachypnea_ge_40(self):
        m = self.make_measurement(45)
        self.sim._check_and_alert_resp_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        self.assertEqual(self.sim.published_alerts[0]["severity"], "critical")

    def test_alert_for_bradypnea_le_8(self):
        m = self.make_measurement(8)
        self.sim._check_and_alert_resp_rate(self.patient, m)
        self.assertEqual(len(self.sim.published_alerts), 1)
        self.assertEqual(self.sim.published_alerts[0]["severity"], "high")


if __name__ == "__main__":
    unittest.main()