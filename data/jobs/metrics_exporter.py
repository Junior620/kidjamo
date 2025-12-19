"""
Module d'export et de monitoring des métriques pipeline d'ingestion.
Calcule P50/P95/P99 latence, throughput, % validité, dérive SpO₂/T°.
"""

import time
import json
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics
import pandas as pd

@dataclass
class PipelineMetrics:
    """Structure des métriques de performance du pipeline."""
    timestamp: datetime
    job_name: str
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_records_per_sec: float
    completeness_pct: float
    validity_pct: float
    spo2_drift_24h: Optional[float]
    temp_drift_24h: Optional[float]
    alerts_count_by_type: Dict[str, int]
    false_positive_rate: Optional[float]
    processing_time_ms: float
    data_quality_score: float

class MetricsCollector:
    
    def __init__(self, output_dir: str = "evidence"):
        self.output_dir = output_dir
        self.metrics_history = []
        self.start_times = {}
        
        # Créer le dossier evidence s'il n'existe pas
        os.makedirs(output_dir, exist_ok=True)
        
    def start_timing(self, operation_name: str) -> None:
        """Démarre le chronométrage d'une opération."""
        self.start_times[operation_name] = time.time()
        
    def end_timing(self, operation_name: str) -> float:
        """Termine le chronométrage et retourne la durée en ms."""
        if operation_name not in self.start_times:
            return 0.0
        duration_ms = (time.time() - self.start_times[operation_name]) * 1000
        del self.start_times[operation_name]
        return duration_ms
        
    def calculate_latency_percentiles(self, latencies_ms: List[float]) -> Tuple[float, float, float]:
        """Calcule P50, P95, P99 des latences."""
        if not latencies_ms:
            return 0.0, 0.0, 0.0
            
        sorted_latencies = sorted(latencies_ms)
        n = len(sorted_latencies)
        
        p50 = sorted_latencies[int(0.50 * n)]
        p95 = sorted_latencies[int(0.95 * n)]
        p99 = sorted_latencies[int(0.99 * n)]
        
        return p50, p95, p99
        
    def calculate_throughput(self, record_count: int, duration_s: float) -> float:
        """Calcule le throughput en records/seconde."""
        if duration_s <= 0:
            return 0.0
        return record_count / duration_s
        
    def calculate_data_quality_metrics(self, df_metrics: pd.DataFrame) -> Dict[str, float]:
        """
        Calcule les métriques de qualité des données à partir d'un DataFrame.
        
        Expected columns: patient_id, spo2, temperature, heart_rate, timestamp, is_valid
        """
        if df_metrics.empty:
            return {
                "completeness_pct": 0.0,
                "validity_pct": 0.0,
                "spo2_drift_24h": None,
                "temp_drift_24h": None,
                "data_quality_score": 0.0
            }
            
        total_records = len(df_metrics)
        
        # Complétude (% de records avec toutes les vitales)
        complete_records = df_metrics.dropna(subset=['spo2', 'temperature', 'heart_rate'])
        completeness_pct = (len(complete_records) / total_records) * 100
        
        # Validité (% de records dans les plages physiologiques)
        valid_records = df_metrics[
            (df_metrics['spo2'].between(70, 100)) &
            (df_metrics['temperature'].between(35, 42)) &
            (df_metrics['heart_rate'].between(40, 200))
        ]
        validity_pct = (len(valid_records) / total_records) * 100
        
        # Calcul des dérives 24h par patient
        spo2_drifts = []
        temp_drifts = []
        
        for patient_id in df_metrics['patient_id'].unique():
            patient_data = df_metrics[df_metrics['patient_id'] == patient_id].copy()
            
            if len(patient_data) < 2:
                continue
                
            # Trier par timestamp
            patient_data = patient_data.sort_values('timestamp')
            
            # Calculer dérive sur 24h (dernières vs premières valeurs)
            if len(patient_data) >= 24:  # Au moins 24 points
                first_24h = patient_data.head(24)
                last_24h = patient_data.tail(24)
                
                spo2_drift = last_24h['spo2'].mean() - first_24h['spo2'].mean()
                temp_drift = last_24h['temperature'].mean() - first_24h['temperature'].mean()
                
                spo2_drifts.append(abs(spo2_drift))
                temp_drifts.append(abs(temp_drift))
        
        # Moyennes des dérives
        avg_spo2_drift = statistics.mean(spo2_drifts) if spo2_drifts else None
        avg_temp_drift = statistics.mean(temp_drifts) if temp_drifts else None
        
        # Score qualité global (0-100)
        quality_score = (completeness_pct * 0.4 + validity_pct * 0.6)
        
        return {
            "completeness_pct": round(completeness_pct, 2),
            "validity_pct": round(validity_pct, 2),
            "spo2_drift_24h": round(avg_spo2_drift, 3) if avg_spo2_drift else None,
            "temp_drift_24h": round(avg_temp_drift, 3) if avg_temp_drift else None,
            "data_quality_score": round(quality_score, 2)
        }
        
    def count_alerts_by_type(self, alerts_data: List[Dict]) -> Dict[str, int]:
        """Compte les alertes par type de sévérité."""
        alert_counts = {
            "critical": 0,
            "alert": 0,
            "warn": 0,
            "info": 0,
            "sensor_failure": 0,
            "combination_critical": 0
        }
        
        for alert in alerts_data:
            severity = alert.get("severity", "info")
            alert_counts[severity] = alert_counts.get(severity, 0) + 1
            
            # Compter les combinaisons critiques spécifiquement
            if any(reason.startswith("C") for reason in alert.get("reasons", [])):
                alert_counts["combination_critical"] += 1
                
        return alert_counts
        
    def calculate_false_positive_rate(self, alerts: List[Dict], ground_truth: Optional[List[Dict]] = None) -> Optional[float]:
        """
        Calcule le taux de faux positifs pour les alertes.
        En l'absence de ground truth, utilise des heuristiques.
        """
        if not alerts:
            return 0.0
            
        if ground_truth is None:
            # Heuristique : alertes avec SpO₂ > 94% ET T° < 37.5°C = potentiels FP
            potential_fp = 0
            for alert in alerts:
                vitals = alert.get("vitals", {})
                spo2 = vitals.get("spo2", 0)
                temp = vitals.get("temperature", 36.5)
                
                if spo2 > 94 and temp < 37.5 and alert.get("severity") in ["critical", "alert"]:
                    potential_fp += 1
                    
            return round((potential_fp / len(alerts)) * 100, 2)
        
        # Avec ground truth (à implémenter si disponible)
        return None
        
    def collect_pipeline_metrics(self, 
                                job_name: str,
                                latencies_ms: List[float],
                                record_count: int,
                                processing_duration_s: float,
                                data_df: Optional[pd.DataFrame] = None,
                                alerts_data: Optional[List[Dict]] = None) -> PipelineMetrics:
        """
        Collecte toutes les métriques pour un job de pipeline.
        """
        
        # Latences
        p50, p95, p99 = self.calculate_latency_percentiles(latencies_ms)
        
        # Throughput
        throughput = self.calculate_throughput(record_count, processing_duration_s)
        
        # Qualité des données
        if data_df is not None:
            quality_metrics = self.calculate_data_quality_metrics(data_df)
        else:
            quality_metrics = {
                "completeness_pct": 0.0,
                "validity_pct": 0.0,
                "spo2_drift_24h": None,
                "temp_drift_24h": None,
                "data_quality_score": 0.0
            }
            
        # Alertes
        alerts_count = {}
        fp_rate = None
        if alerts_data:
            alerts_count = self.count_alerts_by_type(alerts_data)
            fp_rate = self.calculate_false_positive_rate(alerts_data)
        
        metrics = PipelineMetrics(
            timestamp=datetime.now(),
            job_name=job_name,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            throughput_records_per_sec=throughput,
            completeness_pct=quality_metrics["completeness_pct"],
            validity_pct=quality_metrics["validity_pct"],
            spo2_drift_24h=quality_metrics["spo2_drift_24h"],
            temp_drift_24h=quality_metrics["temp_drift_24h"],
            alerts_count_by_type=alerts_count,
            false_positive_rate=fp_rate,
            processing_time_ms=processing_duration_s * 1000,
            data_quality_score=quality_metrics["data_quality_score"]
        )
        
        self.metrics_history.append(metrics)
        return metrics
        
    def export_metrics_csv(self, filename: str = "pipeline_metrics.csv") -> str:
        """Exporte les métriques au format CSV."""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if not self.metrics_history:
                return filepath
                
            # Headers
            fieldnames = [
                'timestamp', 'job_name', 'latency_p50_ms', 'latency_p95_ms', 'latency_p99_ms',
                'throughput_records_per_sec', 'completeness_pct', 'validity_pct',
                'spo2_drift_24h', 'temp_drift_24h', 'processing_time_ms', 'data_quality_score',
                'false_positive_rate', 'critical_alerts', 'alert_alerts', 'warn_alerts',
                'combination_critical_alerts', 'sensor_failure_alerts'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for metrics in self.metrics_history:
                row = {
                    'timestamp': metrics.timestamp.isoformat(),
                    'job_name': metrics.job_name,
                    'latency_p50_ms': metrics.latency_p50_ms,
                    'latency_p95_ms': metrics.latency_p95_ms,
                    'latency_p99_ms': metrics.latency_p99_ms,
                    'throughput_records_per_sec': metrics.throughput_records_per_sec,
                    'completeness_pct': metrics.completeness_pct,
                    'validity_pct': metrics.validity_pct,
                    'spo2_drift_24h': metrics.spo2_drift_24h,
                    'temp_drift_24h': metrics.temp_drift_24h,
                    'processing_time_ms': metrics.processing_time_ms,
                    'data_quality_score': metrics.data_quality_score,
                    'false_positive_rate': metrics.false_positive_rate,
                    'critical_alerts': metrics.alerts_count_by_type.get('critical', 0),
                    'alert_alerts': metrics.alerts_count_by_type.get('alert', 0),
                    'warn_alerts': metrics.alerts_count_by_type.get('warn', 0),
                    'combination_critical_alerts': metrics.alerts_count_by_type.get('combination_critical', 0),
                    'sensor_failure_alerts': metrics.alerts_count_by_type.get('sensor_failure', 0)
                }
                writer.writerow(row)
                
        return filepath
        
    def generate_compliance_report(self) -> Dict[str, str]:
        """
        Génère un rapport de conformité basé sur les dernières métriques.
        
        Returns:
            Dict avec les verdicts PASS/WARN/FAIL pour chaque règle
        """
        if not self.metrics_history:
            return {"status": "NO_DATA"}
            
        latest = self.metrics_history[-1]
        report = {}
        
        # Règle: Latence P95 < 5s (5000ms)
        if latest.latency_p95_ms < 5000:
            report["latency_p95"] = "PASS"
        elif latest.latency_p95_ms < 10000:
            report["latency_p95"] = "WARN"
        else:
            report["latency_p95"] = "FAIL"
            
        # Règle: % validité ≥ 95%
        if latest.validity_pct >= 95:
            report["validity_rate"] = "PASS"
        elif latest.validity_pct >= 90:
            report["validity_rate"] = "WARN"
        else:
            report["validity_rate"] = "FAIL"
            
        # Règle: Dérive SpO₂ ≤ 2 pts/24h
        if latest.spo2_drift_24h is not None:
            if latest.spo2_drift_24h <= 2.0:
                report["spo2_drift"] = "PASS"
            elif latest.spo2_drift_24h <= 3.0:
                report["spo2_drift"] = "WARN"
            else:
                report["spo2_drift"] = "FAIL"
        else:
            report["spo2_drift"] = "NO_DATA"
            
        # Règle: Dérive T° ≤ 0.5°C/24h
        if latest.temp_drift_24h is not None:
            if latest.temp_drift_24h <= 0.5:
                report["temp_drift"] = "PASS"
            elif latest.temp_drift_24h <= 1.0:
                report["temp_drift"] = "WARN"
            else:
                report["temp_drift"] = "FAIL"
        else:
            report["temp_drift"] = "NO_DATA"
            
        # Règle: Taux FP < 5%
        if latest.false_positive_rate is not None:
            if latest.false_positive_rate < 5.0:
                report["false_positive_rate"] = "PASS"
            elif latest.false_positive_rate < 10.0:
                report["false_positive_rate"] = "WARN"
            else:
                report["false_positive_rate"] = "FAIL"
        else:
            report["false_positive_rate"] = "NO_DATA"
            
        return report
        
    def export_compliance_json(self, filename: str = "compliance_report.json") -> str:
        """Exporte le rapport de conformité en JSON."""
        filepath = os.path.join(self.output_dir, filename)
        compliance = self.generate_compliance_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "compliance_status": compliance,
                "latest_metrics": self.metrics_history[-1].__dict__ if self.metrics_history else None
            }, f, indent=2, default=str)
            
        return filepath

# Utilitaire pour intégration Spark
def collect_spark_job_metrics(spark_context, job_name: str, collector: MetricsCollector):
    """
    Collecte les métriques d'un job Spark en cours.
    """
    status_tracker = spark_context.statusTracker()
    
    # IDs des jobs actifs
    active_jobs = status_tracker.getActiveJobIds()
    completed_jobs = status_tracker.getJobInfos()
    
    latencies = []
    total_tasks = 0
    
    for job_info in completed_jobs:
        if job_info and job_info.status == "SUCCEEDED":
            # Durée du job en ms
            if job_info.submissionTime and job_info.completionTime:
                duration_ms = job_info.completionTime - job_info.submissionTime
                latencies.append(duration_ms)
                
            # Nombre de tâches
            total_tasks += job_info.numTasks
    
    return latencies, total_tasks

if __name__ == "__main__":
    # Test du collecteur de métriques
    collector = MetricsCollector()
    
    # Simulation de données
    test_latencies = [100, 150, 200, 180, 220, 300, 250]
    test_data = pd.DataFrame({
        'patient_id': ['P001'] * 100,
        'spo2': [95, 96, 94, 93, 97] * 20,
        'temperature': [36.8, 37.0, 36.9, 37.1, 36.7] * 20,
        'heart_rate': [80, 85, 82, 88, 79] * 20,
        'timestamp': pd.date_range('2025-01-01', periods=100, freq='1min')
    })
    
    # Collecte des métriques
    metrics = collector.collect_pipeline_metrics(
        job_name="test_bronze_to_silver",
        latencies_ms=test_latencies,
        record_count=100,
        processing_duration_s=30.0,
        data_df=test_data
    )
    
    # Export
    csv_file = collector.export_metrics_csv()
    json_file = collector.export_compliance_json()
    
    print(f"Métriques exportées:")
    print(f"- CSV: {csv_file}")
    print(f"- JSON: {json_file}")
    print(f"- P95 latence: {metrics.latency_p95_ms}ms")
    print(f"- Validité: {metrics.validity_pct}%")
