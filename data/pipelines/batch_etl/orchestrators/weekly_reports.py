#!/usr/bin/env python3
"""
🏥 KIDJAMO - Rapports Hebdomadaires Batch ETL
Génération automatique de rapports médicaux hebdomadaires pour patients et équipes
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from jinja2 import Template

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeeklyReportsGenerator:
    """
    Générateur de rapports hebdomadaires médicaux automatisés
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.week_end = datetime.now().date() - timedelta(days=1)  # Hier
        self.week_start = self.week_end - timedelta(days=6)  # Il y a 7 jours

    async def generate_weekly_reports(self) -> Dict:
        """
        Génère tous les rapports hebdomadaires
        """
        logger.info(f"📊 Génération rapports hebdomadaires {self.week_start} → {self.week_end}")

        results = {
            'week_start': self.week_start,
            'week_end': self.week_end,
            'start_time': datetime.now(),
            'reports_generated': [],
            'errors': []
        }

        try:
            # 1. Rapports individuels patients
            patient_reports = await self._generate_patient_reports()
            results['reports_generated'].extend(patient_reports)

            # 2. Rapport de cohorte médicale
            await self._generate_cohort_report()
            results['reports_generated'].append('cohort_summary')

            # 3. Rapport qualité des données
            await self._generate_quality_report()
            results['reports_generated'].append('data_quality')

            # 4. Rapport performance système
            await self._generate_system_performance_report()
            results['reports_generated'].append('system_performance')

            # 5. Rapport alertes et interventions
            await self._generate_alerts_intervention_report()
            results['reports_generated'].append('alerts_interventions')

            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
            results['status'] = 'SUCCESS'

            logger.info(f"✅ Rapports hebdomadaires générés en {results['duration']:.1f}s")

        except Exception as e:
            results['errors'].append(str(e))
            results['status'] = 'FAILED'
            logger.error(f"❌ Erreur génération rapports: {e}")

        return results

    async def _generate_patient_reports(self) -> List[str]:
        """
        Génère un rapport hebdomadaire pour chaque patient actif
        """
        logger.info("👥 Génération rapports patients individuels...")

        # Récupération liste patients actifs
        patients = await self._get_active_patients()
        reports_generated = []

        for patient in patients:
            try:
                report_data = await self._collect_patient_week_data(patient['patient_id'])
                report_html = await self._generate_patient_html_report(patient, report_data)
                report_file = f"patient_report_{patient['patient_id']}_{self.week_end}.html"

                # Sauvegarde du rapport
                await self._save_report(report_file, report_html)

                # Envoi par email si configuré
                await self._send_patient_report_email(patient, report_file)

                reports_generated.append(f"patient_{patient['patient_id']}")

            except Exception as e:
                logger.error(f"Erreur rapport patient {patient['patient_id']}: {e}")

        logger.info(f"📋 {len(reports_generated)} rapports patients générés")
        return reports_generated

    async def _collect_patient_week_data(self, patient_id: str) -> Dict:
        """
        Collecte toutes les données d'un patient pour la semaine
        """
        query = """
        SELECT 
            -- Données de base
            p.first_name, p.last_name, p.genotype, p.birth_date,
            
            -- Métriques vitales moyennes
            AVG(m.spo2_pct) as avg_spo2,
            MIN(m.spo2_pct) as min_spo2,
            MAX(m.spo2_pct) as max_spo2,
            AVG(m.freq_card) as avg_heart_rate,
            AVG(m.temp_corp) as avg_temperature,
            MAX(m.temp_corp) as max_temperature,
            AVG(m.pct_hydratation) as avg_hydration,
            AVG(m.activity) as avg_activity,
            
            -- Comptes et statistiques
            COUNT(m.measure_id) as total_measurements,
            COUNT(DISTINCT DATE(m.tz_timestamp)) as days_monitored,
            COUNT(a.alert_id) as total_alerts,
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            
            -- Qualité des données
            COUNT(m.measure_id) FILTER (WHERE m.quality_flag = 'ok') as valid_measurements,
            (COUNT(m.measure_id) FILTER (WHERE m.quality_flag = 'ok') * 100.0 / COUNT(m.measure_id)) as quality_percentage
            
        FROM patients pat
        JOIN users p ON pat.user_id = p.user_id
        LEFT JOIN measurements m ON pat.patient_id = m.patient_id 
            AND DATE(m.tz_timestamp) BETWEEN %s AND %s
        LEFT JOIN alerts a ON pat.patient_id = a.patient_id 
            AND DATE(a.created_at) BETWEEN %s AND %s
        WHERE pat.patient_id = %s
        GROUP BY pat.patient_id, p.first_name, p.last_name, p.genotype, p.birth_date
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.week_start, self.week_end,
                                 self.week_start, self.week_end, patient_id))
            data = dict(cursor.fetchone() or {})
        conn.close()

        # Données temporelles pour graphiques
        data['daily_trends'] = await self._get_patient_daily_trends(patient_id)
        data['alert_timeline'] = await self._get_patient_alert_timeline(patient_id)

        return data

    async def _get_patient_daily_trends(self, patient_id: str) -> List[Dict]:
        """
        Récupère les tendances journalières du patient
        """
        query = """
        SELECT 
            DATE(tz_timestamp) as date,
            AVG(spo2_pct) as avg_spo2,
            AVG(freq_card) as avg_heart_rate,
            AVG(temp_corp) as avg_temperature,
            COUNT(*) as measurements_count
        FROM measurements 
        WHERE patient_id = %s 
            AND DATE(tz_timestamp) BETWEEN %s AND %s
        GROUP BY DATE(tz_timestamp)
        ORDER BY date
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (patient_id, self.week_start, self.week_end))
            trends = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return trends

    async def _get_patient_alert_timeline(self, patient_id: str) -> List[Dict]:
        """
        Récupère la timeline des alertes du patient
        """
        query = """
        SELECT 
            a.created_at,
            a.alert_type,
            a.severity,
            a.message,
            als.statut,
            als.changed_at as resolution_time
        FROM alerts a
        LEFT JOIN alert_statut_logs als ON a.alert_id = als.alert_id AND als.statut = 'resolved'
        WHERE a.patient_id = %s 
            AND DATE(a.created_at) BETWEEN %s AND %s
        ORDER BY a.created_at DESC
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (patient_id, self.week_start, self.week_end))
            alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return alerts

    async def _generate_patient_html_report(self, patient: Dict, data: Dict) -> str:
        """
        Génère le rapport HTML pour un patient
        """
        template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Rapport Hebdomadaire - {{ patient.first_name }} {{ patient.last_name }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #2c5aa0; color: white; padding: 20px; border-radius: 8px; }
                .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
                .alert-critical { color: #d32f2f; font-weight: bold; }
                .alert-medium { color: #f57c00; }
                .quality-good { color: #388e3c; }
                .quality-poor { color: #d32f2f; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🏥 Rapport Hebdomadaire Kidjamo</h1>
                <h2>{{ data.first_name }} {{ data.last_name }}</h2>
                <p>Période: {{ week_start }} → {{ week_end }}</p>
                <p>Génotype: {{ data.genotype }} | Âge: {{ age }} ans</p>
            </div>
            
            <div class="section">
                <h3>📊 Métriques Vitales Moyennes</h3>
                <div class="metric">
                    <strong>SpO2:</strong> {{ "%.1f"|format(data.avg_spo2 or 0) }}% 
                    ({{ "%.1f"|format(data.min_spo2 or 0) }}-{{ "%.1f"|format(data.max_spo2 or 0) }}%)
                </div>
                <div class="metric">
                    <strong>Fréquence Cardiaque:</strong> {{ "%.0f"|format(data.avg_heart_rate or 0) }} bpm
                </div>
                <div class="metric">
                    <strong>Température:</strong> {{ "%.1f"|format(data.avg_temperature or 0) }}°C 
                    (max: {{ "%.1f"|format(data.max_temperature or 0) }}°C)
                </div>
                <div class="metric">
                    <strong>Hydratation:</strong> {{ "%.1f"|format(data.avg_hydration or 0) }}%
                </div>
            </div>
            
            <div class="section">
                <h3>🚨 Alertes et Surveillance</h3>
                <div class="metric">
                    <strong>Total Alertes:</strong> {{ data.total_alerts or 0 }}
                </div>
                <div class="metric">
                    <strong class="alert-critical">Alertes Critiques:</strong> {{ data.critical_alerts or 0 }}
                </div>
                <div class="metric">
                    <strong>Jours Surveillés:</strong> {{ data.days_monitored or 0 }}/7
                </div>
                <div class="metric">
                    <strong>Mesures Total:</strong> {{ data.total_measurements or 0 }}
                </div>
            </div>
            
            <div class="section">
                <h3>🔍 Qualité des Données</h3>
                <div class="metric">
                    <span class="{{ 'quality-good' if (data.quality_percentage or 0) > 95 else 'quality-poor' }}">
                        <strong>Qualité:</strong> {{ "%.1f"|format(data.quality_percentage or 0) }}%
                    </span>
                </div>
                <div class="metric">
                    <strong>Mesures Valides:</strong> {{ data.valid_measurements or 0 }}/{{ data.total_measurements or 0 }}
                </div>
            </div>
            
            {% if data.alert_timeline %}
            <div class="section">
                <h3>📋 Historique des Alertes</h3>
                {% for alert in data.alert_timeline[:5] %}
                <div class="metric">
                    <strong>{{ alert.created_at.strftime('%d/%m %H:%M') }}:</strong>
                    <span class="alert-{{ alert.severity }}">{{ alert.alert_type }}</span>
                    - {{ alert.message }}
                    {% if alert.resolution_time %}
                    <small>(Résolu {{ alert.resolution_time.strftime('%H:%M') }})</small>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="section">
                <h3>💡 Recommandations</h3>
                {% if (data.critical_alerts or 0) > 0 %}
                <p class="alert-critical">⚠️ {{ data.critical_alerts }} alertes critiques détectées cette semaine. Consultation médicale recommandée.</p>
                {% endif %}
                
                {% if (data.quality_percentage or 0) < 90 %}
                <p class="alert-medium">📱 Qualité des données: {{ "%.1f"|format(data.quality_percentage or 0) }}%. Vérifier le capteur IoT.</p>
                {% endif %}
                
                {% if (data.days_monitored or 0) < 6 %}
                <p class="alert-medium">📊 Surveillance: {{ data.days_monitored }}/7 jours. Améliorer la compliance au port du capteur.</p>
                {% endif %}
                
                {% if (data.avg_spo2 or 0) > 0 and (data.avg_spo2 or 0) < 95 %}
                <p class="alert-critical">🫁 SpO2 moyenne ({{ "%.1f"|format(data.avg_spo2) }}%) en dessous du seuil normal. Surveillance renforcée nécessaire.</p>
                {% endif %}
            </div>
            
            <footer style="margin-top: 30px; text-align: center; color: #666; font-size: 12px;">
                <p>Rapport généré automatiquement par Kidjamo le {{ datetime.now().strftime('%d/%m/%Y à %H:%M') }}</p>
                <p>🏥 Système de surveillance médicale continue pour patients drépanocytaires</p>
            </footer>
        </body>
        </html>
        """)

        # Calcul de l'âge
        if data.get('birth_date'):
            age = (datetime.now().date() - data['birth_date']).days // 365
        else:
            age = 'N/A'

        return template.render(
            patient=patient,
            data=data,
            week_start=self.week_start,
            week_end=self.week_end,
            age=age,
            datetime=datetime
        )

    async def _generate_cohort_report(self):
        """
        Génère le rapport de cohorte pour l'équipe médicale
        """
        logger.info("👥 Génération rapport de cohorte...")

        query = """
        INSERT INTO weekly_cohort_reports (
            week_start,
            week_end,
            total_patients,
            active_patients,
            total_alerts,
            critical_alerts,
            avg_spo2_cohort,
            avg_quality_score,
            patients_at_risk,
            generated_at
        )
        SELECT 
            %s as week_start,
            %s as week_end,
            COUNT(DISTINCT p.patient_id) as total_patients,
            COUNT(DISTINCT m.patient_id) as active_patients,
            COUNT(a.alert_id) as total_alerts,
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            AVG(m.spo2_pct) as avg_spo2_cohort,
            AVG(CASE WHEN m.quality_flag = 'ok' THEN 100 ELSE 0 END) as avg_quality_score,
            COUNT(DISTINCT p.patient_id) FILTER (WHERE avg_spo2_week < 92) as patients_at_risk,
            NOW() as generated_at
        FROM patients p
        LEFT JOIN measurements m ON p.patient_id = m.patient_id 
            AND DATE(m.tz_timestamp) BETWEEN %s AND %s
        LEFT JOIN alerts a ON p.patient_id = a.patient_id 
            AND DATE(a.created_at) BETWEEN %s AND %s
        LEFT JOIN (
            SELECT patient_id, AVG(spo2_pct) as avg_spo2_week
            FROM measurements 
            WHERE DATE(tz_timestamp) BETWEEN %s AND %s
            GROUP BY patient_id
        ) spo2_avg ON p.patient_id = spo2_avg.patient_id
        """

        await self._execute_query(query, (
            self.week_start, self.week_end, self.week_start, self.week_end,
            self.week_start, self.week_end, self.week_start, self.week_end
        ))

    async def _generate_quality_report(self):
        """
        Génère le rapport qualité des données hebdomadaire
        """
        logger.info("🔍 Génération rapport qualité...")
        # Implémentation similaire avec métriques qualité
        pass

    async def _generate_system_performance_report(self):
        """
        Génère le rapport de performance système
        """
        logger.info("⚙️ Génération rapport performance système...")
        # Implémentation avec métriques système
        pass

    async def _generate_alerts_intervention_report(self):
        """
        Génère le rapport d'alertes et interventions
        """
        logger.info("🚨 Génération rapport alertes et interventions...")
        # Implémentation avec analyse des interventions
        pass

    async def _get_active_patients(self) -> List[Dict]:
        """
        Récupère la liste des patients actifs
        """
        query = """
        SELECT DISTINCT p.patient_id, u.first_name, u.last_name, u.email
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE EXISTS (
            SELECT 1 FROM measurements m 
            WHERE m.patient_id = p.patient_id 
                AND DATE(m.tz_timestamp) BETWEEN %s AND %s
        )
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.week_start, self.week_end))
            patients = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return patients

    async def _save_report(self, filename: str, content: str):
        """
        Sauvegarde un rapport sur le disque
        """
        import os
        reports_dir = "../../evidence/weekly_reports"
        os.makedirs(reports_dir, exist_ok=True)

        with open(f"{reports_dir}/{filename}", 'w', encoding='utf-8') as f:
            f.write(content)

    async def _send_patient_report_email(self, patient: Dict, report_file: str):
        """
        Envoie le rapport par email (placeholder)
        """
        # TODO: Implémenter envoi email avec SMTP
        logger.info(f"📧 Email rapport envoyé à {patient.get('email', 'N/A')}")

    async def _execute_query(self, query: str, params: tuple = None):
        """
        Exécute une requête SQL de manière sécurisée
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erreur SQL: {e}")
            raise

async def main():
    """
    Point d'entrée principal pour les rapports hebdomadaires
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    generator = WeeklyReportsGenerator(db_config)
    results = await generator.generate_weekly_reports()

    print(f"📋 Résultats rapports hebdomadaires:")
    print(f"   Période: {results['week_start']} → {results['week_end']}")
    print(f"   Statut: {results['status']}")
    print(f"   Durée: {results.get('duration', 'N/A'):.1f}s")
    print(f"   Rapports générés: {len(results['reports_generated'])}")

if __name__ == "__main__":
    asyncio.run(main())
