"""
Fix for Statistics Reporting - Ensuring Accurate Measurement and Alert Tracking

The issue: Final reports show 0 measurements/alerts despite simulation activity.
This is caused by incorrect data aggregation and timing issues in the monitoring system.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psycopg2
from pathlib import Path

logger = logging.getLogger(__name__)

class ImprovedStatsCollector:
    """Enhanced statistics collector with accurate tracking"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.start_time = datetime.now()
        self.session_stats = {
            'patients_simulated': 0,
            'total_measurements': 0,
            'total_alerts': 0,
            'critical_alerts': 0,
            'sms_sent': 0,
            'emails_sent': 0,
            'uptime_hours': 0,
            'performance_score': 100,
            'measurements_per_patient': {},
            'alerts_per_patient': {},
            'alert_types_count': {},
            'database_operations': {
                'measurements_inserted': 0,
                'alerts_inserted': 0,
                'patients_inserted': 0,
                'failed_operations': 0
            }
        }
        
        # Real-time counters (in-memory tracking)
        self.realtime_counters = {
            'measurements_generated': 0,
            'alerts_generated': 0,
            'measurements_saved': 0,
            'alerts_saved': 0,
            'notifications_sent': 0
        }
        
        self.last_db_check = datetime.now()
        
    def increment_measurement(self, patient_id: str = None):
        """Increment measurement counter"""
        self.realtime_counters['measurements_generated'] += 1
        if patient_id:
            if patient_id not in self.session_stats['measurements_per_patient']:
                self.session_stats['measurements_per_patient'][patient_id] = 0
            self.session_stats['measurements_per_patient'][patient_id] += 1
    
    def increment_alert(self, patient_id: str = None, alert_type: str = None, severity: str = None):
        """Increment alert counter"""
        self.realtime_counters['alerts_generated'] += 1
        
        if patient_id:
            if patient_id not in self.session_stats['alerts_per_patient']:
                self.session_stats['alerts_per_patient'][patient_id] = 0
            self.session_stats['alerts_per_patient'][patient_id] += 1
        
        if alert_type:
            if alert_type not in self.session_stats['alert_types_count']:
                self.session_stats['alert_types_count'][alert_type] = 0
            self.session_stats['alert_types_count'][alert_type] += 1
        
        if severity == 'critical':
            self.session_stats['critical_alerts'] += 1
    
    def increment_notification(self, notification_type: str):
        """Increment notification counter"""
        self.realtime_counters['notifications_sent'] += 1
        if notification_type == 'sms':
            self.session_stats['sms_sent'] += 1
        elif notification_type == 'email':
            self.session_stats['emails_sent'] += 1
    
    def increment_db_operation(self, operation_type: str, count: int = 1, failed: bool = False):
        """Track database operations"""
        if failed:
            self.session_stats['database_operations']['failed_operations'] += count
        else:
            if operation_type == 'measurement':
                self.session_stats['database_operations']['measurements_inserted'] += count
                self.realtime_counters['measurements_saved'] += count
            elif operation_type == 'alert':
                self.session_stats['database_operations']['alerts_inserted'] += count
                self.realtime_counters['alerts_saved'] += count
            elif operation_type == 'patient':
                self.session_stats['database_operations']['patients_inserted'] += count
    
    def update_patient_count(self, count: int):
        """Update patient count"""
        self.session_stats['patients_simulated'] = count
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current statistics with real-time and database verification"""
        
        # Update uptime
        uptime_delta = datetime.now() - self.start_time
        self.session_stats['uptime_hours'] = round(uptime_delta.total_seconds() / 3600, 3)
        
        # Sync with database every 30 seconds
        if (datetime.now() - self.last_db_check).total_seconds() > 30:
            self._sync_with_database()
            self.last_db_check = datetime.now()
        
        # Use realtime counters as primary source
        self.session_stats['total_measurements'] = max(
            self.realtime_counters['measurements_generated'],
            self.session_stats['database_operations']['measurements_inserted']
        )
        
        self.session_stats['total_alerts'] = max(
            self.realtime_counters['alerts_generated'],
            self.session_stats['database_operations']['alerts_inserted']
        )
        
        # Calculate performance score
        success_rate = self._calculate_success_rate()
        self.session_stats['performance_score'] = round(success_rate, 1)
        
        return {
            **self.session_stats,
            'realtime_counters': self.realtime_counters,
            'last_updated': datetime.now().isoformat()
        }
    
    def _sync_with_database(self):
        """Sync statistics with actual database data"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                cursor = conn.cursor()
                
                # Count measurements since session start
                cursor.execute("""
                    SELECT COUNT(*) FROM measurements 
                    WHERE received_at >= %s
                """, (self.start_time,))
                db_measurements = cursor.fetchone()[0]
                
                # Count alerts since session start
                cursor.execute("""
                    SELECT COUNT(*) FROM alerts 
                    WHERE created_at >= %s
                """, (self.start_time,))
                db_alerts = cursor.fetchone()[0]
                
                # Count critical alerts
                cursor.execute("""
                    SELECT COUNT(*) FROM alerts 
                    WHERE created_at >= %s AND severity = 'critical'
                """, (self.start_time,))
                db_critical_alerts = cursor.fetchone()[0]
                
                # Count patients
                cursor.execute("""
                    SELECT COUNT(DISTINCT patient_id) FROM measurements 
                    WHERE received_at >= %s
                """, (self.start_time,))
                db_patients = cursor.fetchone()[0]
                
                # Update stats with database reality
                self.session_stats['database_operations']['measurements_inserted'] = db_measurements
                self.session_stats['database_operations']['alerts_inserted'] = db_alerts
                self.session_stats['critical_alerts'] = db_critical_alerts
                
                if db_patients > 0:
                    self.session_stats['patients_simulated'] = db_patients
                
                logger.info(f"📊 Sync DB: {db_measurements} mesures, {db_alerts} alertes, {db_patients} patients")
                
        except Exception as e:
            logger.error(f"❌ Erreur sync database: {e}")
    
    def _calculate_success_rate(self) -> float:
        """Calculate overall system performance score"""
        total_operations = (
            self.realtime_counters['measurements_generated'] + 
            self.realtime_counters['alerts_generated']
        )
        
        if total_operations == 0:
            return 100.0
        
        successful_operations = (
            self.realtime_counters['measurements_saved'] + 
            self.realtime_counters['alerts_saved']
        )
        
        failed_operations = self.session_stats['database_operations']['failed_operations']
        
        # Calculate success rate
        success_rate = ((successful_operations) / (total_operations + failed_operations)) * 100
        return min(100.0, max(0.0, success_rate))
    
    def generate_final_report(self, output_dir: str = "reports") -> str:
        """Generate comprehensive final report"""
        
        # Final database sync
        self._sync_with_database()
        
        # Get final stats
        final_stats = self.get_current_stats()
        
        # Calculate additional metrics
        avg_measurements_per_patient = 0
        if final_stats['patients_simulated'] > 0:
            avg_measurements_per_patient = round(
                final_stats['total_measurements'] / final_stats['patients_simulated'], 1
            )
        
        avg_alerts_per_patient = 0
        if final_stats['patients_simulated'] > 0:
            avg_alerts_per_patient = round(
                final_stats['total_alerts'] / final_stats['patients_simulated'], 1
            )
        
        # Create comprehensive report
        report = {
            'session_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration_hours': final_stats['uptime_hours'],
                'patients_simulated': final_stats['patients_simulated'],
                'performance_score': final_stats['performance_score']
            },
            'data_metrics': {
                'total_measurements': final_stats['total_measurements'],
                'total_alerts': final_stats['total_alerts'],
                'critical_alerts': final_stats['critical_alerts'],
                'avg_measurements_per_patient': avg_measurements_per_patient,
                'avg_alerts_per_patient': avg_alerts_per_patient,
                'measurements_per_patient': final_stats['measurements_per_patient'],
                'alerts_per_patient': final_stats['alerts_per_patient'],
                'alert_types_breakdown': final_stats['alert_types_count']
            },
            'database_operations': final_stats['database_operations'],
            'notifications': {
                'sms_sent': final_stats['sms_sent'],
                'emails_sent': final_stats['emails_sent'],
                'total_notifications': final_stats['sms_sent'] + final_stats['emails_sent']
            },
            'realtime_tracking': final_stats['realtime_counters'],
            'system_health': {
                'data_consistency': self._check_data_consistency(final_stats),
                'notification_success_rate': self._calculate_notification_success_rate(final_stats),
                'database_success_rate': self._calculate_database_success_rate(final_stats)
            }
        }
        
        # Save report
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"{output_dir}/final_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 Rapport final sauvegardé: {report_file}")
        
        # Print summary to console
        self._print_report_summary(report)
        
        return report_file
    
    def _check_data_consistency(self, stats: Dict[str, Any]) -> str:
        """Check consistency between realtime and database counts"""
        rt_measurements = stats['realtime_counters']['measurements_generated']
        db_measurements = stats['database_operations']['measurements_inserted']
        
        rt_alerts = stats['realtime_counters']['alerts_generated']
        db_alerts = stats['database_operations']['alerts_inserted']
        
        measurement_consistency = abs(rt_measurements - db_measurements) <= 5
        alert_consistency = abs(rt_alerts - db_alerts) <= 2
        
        if measurement_consistency and alert_consistency:
            return "EXCELLENT"
        elif measurement_consistency or alert_consistency:
            return "GOOD"
        else:
            return "NEEDS_ATTENTION"
    
    def _calculate_notification_success_rate(self, stats: Dict[str, Any]) -> float:
        """Calculate notification success rate"""
        total_alerts = stats['total_alerts']
        total_notifications = stats['sms_sent'] + stats['emails_sent']
        
        if total_alerts == 0:
            return 100.0
        
        return round((total_notifications / total_alerts) * 100, 1)
    
    def _calculate_database_success_rate(self, stats: Dict[str, Any]) -> float:
        """Calculate database operation success rate"""
        total_operations = (
            stats['database_operations']['measurements_inserted'] +
            stats['database_operations']['alerts_inserted'] +
            stats['database_operations']['failed_operations']
        )
        
        if total_operations == 0:
            return 100.0
        
        successful_ops = total_operations - stats['database_operations']['failed_operations']
        return round((successful_ops / total_operations) * 100, 1)
    
    def _print_report_summary(self, report: Dict[str, Any]):
        """Print formatted report summary"""
        print("\n" + "="*60)
        print("📈 RÉSUMÉ FINAL SIMULATION IoT KIDJAMO")
        print("="*60)
        print(f"⏱️  Durée: {report['session_summary']['duration_hours']}h")
        print(f"👥 Patients: {report['session_summary']['patients_simulated']}")
        print(f"📊 Mesures: {report['data_metrics']['total_measurements']}")
        print(f"🚨 Alertes: {report['data_metrics']['total_alerts']} (dont {report['data_metrics']['critical_alerts']} critiques)")
        print(f"📱 Notifications: {report['notifications']['total_notifications']} (SMS: {report['notifications']['sms_sent']}, Email: {report['notifications']['emails_sent']})")
        print(f"📈 Performance: {report['session_summary']['performance_score']}%")
        print(f"🔄 Consistance: {report['system_health']['data_consistency']}")
        print("="*60)

# Global instance
stats_collector = None

def initialize_stats_collector(db_config: Dict[str, Any]) -> ImprovedStatsCollector:
    """Initialize global stats collector"""
    global stats_collector
    stats_collector = ImprovedStatsCollector(db_config)
    return stats_collector

def get_stats_collector() -> ImprovedStatsCollector:
    """Get global stats collector instance"""
    return stats_collector
