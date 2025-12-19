"""
Unit tests for offline immediate rules and edge cases.
Covers: SpO₂ thresholds, Temperature thresholds, combinations, HR extremes, and alert schema fields.
Also validates age-based thresholds presence in data\configs\medical_thresholds.json.
"""
import os
import json
import importlib.util
from datetime import datetime
from typing import List, Dict

# Path to the API module
API_FILE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'pipelines', 'iot_streaming',
    'pipeline_iot_streaming_kafka_local', 'api', 'iot_ingestion_api.py'
))


def _load_api_module():
    spec = importlib.util.spec_from_file_location("iot_ingestion_api", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def _build_measurement(module, *, spo2=98.0, temp=36.8, hr=75, rr=18,
                       battery=90, signal=90, quality=95.0, contact=90.0):
    now = datetime.now().isoformat()
    return module.IoTMeasurement(
        device_id="dev-1",
        patient_id="patient-123",
        timestamp=now,
        measurements=module.MedicalMeasurements(
            freq_card=hr,
            freq_resp=rr,
            spo2_pct=spo2,
            temp_corp=temp,
            temp_ambiente=22.0,
            pct_hydratation=75.0,
            activity=10,
            heat_index=24.0,
        ),
        device_info=module.DeviceInfo(
            device_id="dev-1",
            firmware_version="1.0.0",
            battery_level=battery,
            signal_strength=signal,
            status="connected",
            last_sync=now,
        ),
        quality_indicators=module.QualityIndicators(
            quality_flag="ok",
            confidence_score=quality,
            data_completeness=100.0,
            sensor_contact_quality=contact,
        ),
    )


def _types(alerts: List[Dict]):
    return [a.get("type") for a in alerts]


def _find(alerts: List[Dict], type_name: str):
    return next((a for a in alerts if a.get("type") == type_name), None)


def test_spo2_87_triggers_critical_immediate():
    api = _load_api_module()
    m = _build_measurement(api, spo2=87.0)
    alerts = api.check_critical_vitals(m)
    assert any(t == "CRITICAL_SPO2" for t in _types(alerts)), "Expected CRITICAL_SPO2 for SpO2=87%"


def test_spo2_89_no_critical_immediate():
    api = _load_api_module()
    m = _build_measurement(api, spo2=89.0)
    alerts = api.check_critical_vitals(m)
    assert not any(t == "CRITICAL_SPO2" for t in _types(alerts)), "No CRITICAL_SPO2 expected for SpO2=89%"


def test_temp_38_0_not_critical_immediate():
    api = _load_api_module()
    m = _build_measurement(api, temp=38.0)
    alerts = api.check_critical_vitals(m)
    assert not any(t == "CRITICAL_TEMPERATURE" for t in _types(alerts)), "No CRITICAL_TEMPERATURE expected at 38.0°C"


def test_temp_38_6_triggers_critical_immediate():
    api = _load_api_module()
    m = _build_measurement(api, temp=38.6)
    alerts = api.check_critical_vitals(m)
    assert any(t == "CRITICAL_TEMPERATURE" for t in _types(alerts)), "Expected CRITICAL_TEMPERATURE for 38.6°C"


def test_combo_fever_low_spo2_boundary():
    api = _load_api_module()
    m = _build_measurement(api, spo2=92.0, temp=38.0)
    alerts = api.check_critical_vitals(m)
    assert any(t == "CRITICAL_COMBINATION_FEVER_SPO2" for t in _types(alerts)), "Expected combo alert at SpO2<=92 and T>=38.0"


def test_combo_not_triggered_when_spo2_93():
    api = _load_api_module()
    m = _build_measurement(api, spo2=93.0, temp=38.4)
    alerts = api.check_critical_vitals(m)
    assert not any(t == "CRITICAL_COMBINATION_FEVER_SPO2" for t in _types(alerts)), "No combo expected when SpO2>92"


def test_hr_extreme_high_triggers_critical():
    api = _load_api_module()
    m = _build_measurement(api, hr=181)
    alerts = api.check_critical_vitals(m)
    assert any(t == "CRITICAL_HEART_RATE" for t in _types(alerts)), "Expected critical HR alert for HR>180"


def test_hr_extreme_low_triggers_critical():
    api = _load_api_module()
    m = _build_measurement(api, hr=39)
    alerts = api.check_critical_vitals(m)
    assert any(t == "CRITICAL_HEART_RATE" for t in _types(alerts)), "Expected critical HR alert for HR<40"


def test_alert_schema_contains_severity_and_reasons():
    api = _load_api_module()
    m = _build_measurement(api, spo2=87.0)
    alerts = api.check_critical_vitals(m)
    a = _find(alerts, "CRITICAL_SPO2")
    assert a is not None, "Alert missing"
    assert a.get("severity") == "critical", "Severity should be critical"
    assert isinstance(a.get("reasons", []), list) and len(a["reasons"]) > 0, "Reasons should be present"


def test_thresholds_json_age_based_tables_and_edges():
    # Validate that the JSON contains expected groups and specific edge thresholds
    config_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'data', 'configs', 'medical_thresholds.json'
    ))
    assert os.path.exists(config_path), f"Missing thresholds file at {config_path}"
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    assert "age_groups" in cfg and "thresholds" in cfg
    ag = cfg["age_groups"]
    assert set(ag.keys()) >= {"G1", "G2", "G3", "G4", "G5", "G6"}
    # Check temperature emergency thresholds for G1 and G6 edges
    temp = cfg["thresholds"]["temperature"]
    assert temp["G1"]["emergency"] == 38.5
    assert temp["G6"]["emergency"] == 38.5
    # Check SpO2 critical threshold common value
    spo2 = cfg["thresholds"]["spo2"]
    assert spo2["G5"]["critical"] == 88
    # Check RR alert thresholds for G4
    rr = cfg["thresholds"]["respiratory_rate"]
    assert rr["G4"]["alert"] >= 23

