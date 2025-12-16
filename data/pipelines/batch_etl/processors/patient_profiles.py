#!/usr/bin/env python3
"""
🏥 KIDJAMO - Processeur Profils Patients Consolidés
Création de profils patients complets pour analyses médicales avancées
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from dateutil.relativedelta import relativedelta

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PatientProfilesProcessor:
    """
    Processeur pour créer des profils patients consolidés avec historique complet
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config

    async def generate_comprehensive_patient_profiles(self, patient_ids: List[str] = None) -> Dict:
        """
        Génère des profils patients complets pour analyse médicale
        """
        logger.info("👥 Génération profils patients consolidés")

        # Si aucun patient spécifié, traiter tous les patients actifs
        if not patient_ids:
            patient_ids = await self._get_active_patients()

        profiles_report = {
            'generation_date': datetime.now(),
            'patients_processed': len(patient_ids),
            'profiles': [],
            'cohort_analytics': {},
            'risk_stratification': {},
            'status': 'SUCCESS'
        }

        # Génération des profils individuels
        for patient_id in patient_ids:
            try:
                profile = await self._create_patient_profile(patient_id)
                profiles_report['profiles'].append(profile)
                logger.info(f"✅ Profil généré pour patient {patient_id}")
            except Exception as e:
                logger.error(f"❌ Erreur profil patient {patient_id}: {e}")

        # Analyses de cohorte
        if profiles_report['profiles']:
            profiles_report['cohort_analytics'] = await self._analyze_patient_cohort(profiles_report['profiles'])
            profiles_report['risk_stratification'] = await self._stratify_patient_risks(profiles_report['profiles'])

        # Sauvegarde des profils
        await self._save_patient_profiles(profiles_report)

        return profiles_report

    async def _create_patient_profile(self, patient_id: str) -> Dict:
        """
        Crée un profil complet pour un patient
        """
        profile = {
            'patient_id': patient_id,
            'profile_date': datetime.now(),
            'status': 'SUCCESS'
        }

        # 1. Informations démographiques et médicales de base
        profile['demographics'] = await self._get_patient_demographics(patient_id)

        # 2. Historique médical et traitements
        profile['medical_history'] = await self._get_medical_history(patient_id)

        # 3. Profil physiologique (moyennes, tendances)
        profile['physiological_profile'] = await self._calculate_physiological_profile(patient_id)

        # 4. Patterns comportementaux
        profile['behavioral_patterns'] = await self._analyze_behavioral_patterns(patient_id)

        # 5. Historique des crises et alertes
        profile['crisis_history'] = await self._analyze_crisis_history(patient_id)

        # 6. Compliance et engagement
        profile['compliance_metrics'] = await self._calculate_compliance_metrics(patient_id)

        # 7. Scores de risque personnalisés
        profile['risk_scores'] = await self._calculate_risk_scores(patient_id, profile)

        # 8. Évolution temporelle (3, 6, 12 mois)
        profile['temporal_evolution'] = await self._analyze_temporal_evolution(patient_id)

        # 9. Recommandations personnalisées
        profile['personalized_recommendations'] = await self._generate_personalized_recommendations(profile)

        return profile

    async def _get_patient_demographics(self, patient_id: str) -> Dict:
        """
        Récupère les informations démographiques et médicales de base
        """
        query = """
        SELECT 
            u.first_name, u.last_name, u.gender, u.city, u.country,
            u.created_at as registration_date,
            p.genotype, p.birth_date, p.close_contact,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age_years,
            CASE 
                WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) < 18 THEN 'pediatric'
                WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) < 65 THEN 'adult'
                ELSE 'elderly'
            END as age_category
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.patient_id = %s
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (patient_id,))
            demographics = dict(cursor.fetchone() or {})
        conn.close()

        return demographics

    async def _get_medical_history(self, patient_id: str) -> Dict:
        """
        Récupère l'historique médical complet
        """
        # Traitements actuels et passés
        treatments_query = """
        SELECT 
            drug_name, treatment_start, treatment_end,
            CASE WHEN treatment_end IS NULL THEN 'ongoing' ELSE 'completed' END as status,
            EXTRACT(DAYS FROM COALESCE(treatment_end, NOW()) - treatment_start) as duration_days
        FROM treatments 
        WHERE patient_id = %s
        ORDER BY treatment_start DESC
        """

        # Médecins assignés
        clinicians_query = """
        SELECT 
            c.speciality, c.service_location,
            u.first_name, u.last_name
        FROM clinicians c
        JOIN users u ON c.clinician_id = u.user_id
        WHERE c.patient_id = %s
        """

        conn = psycopg2.connect(**self.db_config)

        # Traitements
        treatments_df = pd.read_sql_query(treatments_query, conn, params=(patient_id,))
        treatments = treatments_df.to_dict('records') if not treatments_df.empty else []

        # Médecins
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(clinicians_query, (patient_id,))
            clinicians = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'treatments': treatments,
            'assigned_clinicians': clinicians,
            'current_treatments': [t for t in treatments if t['status'] == 'ongoing'],
            'treatment_history_count': len(treatments)
        }

    async def _calculate_physiological_profile(self, patient_id: str) -> Dict:
        """
        Calcule le profil physiologique avec moyennes et percentiles
        """
        # Données des 6 derniers mois pour profil stable
        six_months_ago = datetime.now() - relativedelta(months=6)

        query = """
        SELECT 
            -- SpO2 statistiques
            AVG(spo2_pct) as spo2_mean,
            STDDEV(spo2_pct) as spo2_std,
            PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY spo2_pct) as spo2_p10,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY spo2_pct) as spo2_median,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY spo2_pct) as spo2_p90,
            
            -- Fréquence cardiaque
            AVG(freq_card) as hr_mean,
            STDDEV(freq_card) as hr_std,
            PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY freq_card) as hr_p10,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY freq_card) as hr_p90,
            
            -- Température
            AVG(temp_corp) as temp_mean,
            STDDEV(temp_corp) as temp_std,
            MAX(temp_corp) as temp_max,
            
            -- Activité et hydratation
            AVG(activity) as activity_mean,
            AVG(pct_hydratation) as hydration_mean,
            
            -- Comptes
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE spo2_pct < 90) as hypoxemia_episodes,
            COUNT(*) FILTER (WHERE temp_corp > 38) as fever_episodes,
            COUNT(*) FILTER (WHERE freq_card > 100) as tachycardia_episodes
            
        FROM measurements 
        WHERE patient_id = %s 
            AND tz_timestamp >= %s
            AND quality_flag = 'ok'
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (patient_id, six_months_ago))
            physio_data = dict(cursor.fetchone() or {})
        conn.close()

        # Calculs dérivés
        if physio_data.get('total_measurements', 0) > 0:
            total = physio_data['total_measurements']
            physio_data['hypoxemia_rate'] = (physio_data.get('hypoxemia_episodes', 0) / total) * 100
            physio_data['fever_rate'] = (physio_data.get('fever_episodes', 0) / total) * 100
            physio_data['tachycardia_rate'] = (physio_data.get('tachycardia_episodes', 0) / total) * 100

            # Classification SpO2 baseline
            spo2_mean = physio_data.get('spo2_mean', 0)
            if spo2_mean >= 97:
                physio_data['spo2_baseline_category'] = 'excellent'
            elif spo2_mean >= 95:
                physio_data['spo2_baseline_category'] = 'good'
            elif spo2_mean >= 92:
                physio_data['spo2_baseline_category'] = 'acceptable'
            else:
                physio_data['spo2_baseline_category'] = 'concerning'

        return physio_data

    async def _analyze_behavioral_patterns(self, patient_id: str) -> Dict:
        """
        Analyse les patterns comportementaux et de compliance
        """
        # Patterns temporels sur 3 mois
        three_months_ago = datetime.now() - relativedelta(months=3)

        query = """
        SELECT 
            EXTRACT(HOUR FROM tz_timestamp) as hour,
            EXTRACT(DOW FROM tz_timestamp) as day_of_week,
            DATE(tz_timestamp) as date,
            COUNT(*) as measurements_count,
            AVG(activity) as avg_activity
        FROM measurements 
        WHERE patient_id = %s 
            AND tz_timestamp >= %s
            AND quality_flag = 'ok'
        GROUP BY EXTRACT(HOUR FROM tz_timestamp), EXTRACT(DOW FROM tz_timestamp), DATE(tz_timestamp)
        """

        conn = psycopg2.connect(**self.db_config)
        patterns_df = pd.read_sql_query(query, conn, params=(patient_id, three_months_ago))
        conn.close()

        patterns = {}

        if not patterns_df.empty:
            # Heures les plus actives
            hourly_activity = patterns_df.groupby('hour')['avg_activity'].mean()
            patterns['most_active_hours'] = hourly_activity.nlargest(3).index.tolist()
            patterns['least_active_hours'] = hourly_activity.nsmallest(3).index.tolist()

            # Patterns hebdomadaires
            weekly_activity = patterns_df.groupby('day_of_week')['avg_activity'].mean()
            day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
            patterns['most_active_day'] = day_names[int(weekly_activity.idxmax())]
            patterns['least_active_day'] = day_names[int(weekly_activity.idxmin())]

            # Régularité du monitoring (jours avec données)
            daily_counts = patterns_df.groupby('date')['measurements_count'].sum()
            patterns['monitoring_regularity'] = {
                'days_with_data': len(daily_counts),
                'avg_measurements_per_day': float(daily_counts.mean()),
                'consistency_score': float(1 - (daily_counts.std() / daily_counts.mean())) if daily_counts.mean() > 0 else 0
            }

        return patterns

    async def _analyze_crisis_history(self, patient_id: str) -> Dict:
        """
        Analyse complète de l'historique des crises
        """
        query = """
        SELECT 
            a.created_at, a.alert_type, a.severity, a.message,
            als.statut, als.changed_at,
            EXTRACT(EPOCH FROM (als.changed_at - a.created_at))/60 as resolution_time_minutes
        FROM alerts a
        LEFT JOIN alert_statut_logs als ON a.alert_id = als.alert_id AND als.statut = 'resolved'
        WHERE a.patient_id = %s
        ORDER BY a.created_at DESC
        """

        conn = psycopg2.connect(**self.db_config)
        alerts_df = pd.read_sql_query(query, conn, params=(patient_id,))
        conn.close()

        crisis_analysis = {
            'total_alerts': len(alerts_df),
            'critical_alerts': 0,
            'crisis_frequency': {},
            'seasonal_patterns': {},
            'resolution_metrics': {}
        }

        if not alerts_df.empty:
            alerts_df['created_at'] = pd.to_datetime(alerts_df['created_at'])

            # Comptage par sévérité
            severity_counts = alerts_df['severity'].value_counts()
            crisis_analysis['critical_alerts'] = severity_counts.get('critical', 0)
            crisis_analysis['medium_alerts'] = severity_counts.get('medium', 0)
            crisis_analysis['low_alerts'] = severity_counts.get('low', 0)

            # Fréquence des crises (par mois)
            alerts_df['year_month'] = alerts_df['created_at'].dt.to_period('M')
            monthly_counts = alerts_df.groupby('year_month').size()
            crisis_analysis['crisis_frequency'] = {
                'avg_per_month': float(monthly_counts.mean()),
                'max_per_month': int(monthly_counts.max()),
                'trend': 'increasing' if monthly_counts.iloc[-1] > monthly_counts.mean() else 'stable'
            }

            # Patterns saisonniers
            alerts_df['month'] = alerts_df['created_at'].dt.month
            seasonal_counts = alerts_df.groupby('month').size()
            if len(seasonal_counts) >= 6:  # Au moins 6 mois de données
                peak_month = seasonal_counts.idxmax()
                crisis_analysis['seasonal_patterns'] = {
                    'peak_crisis_month': int(peak_month),
                    'seasonal_variation': float(seasonal_counts.std())
                }

            # Métriques de résolution
            resolved_alerts = alerts_df[alerts_df['resolution_time_minutes'].notna()]
            if not resolved_alerts.empty:
                crisis_analysis['resolution_metrics'] = {
                    'avg_resolution_time_minutes': float(resolved_alerts['resolution_time_minutes'].mean()),
                    'resolution_rate': len(resolved_alerts) / len(alerts_df) * 100,
                    'fast_resolution_rate': len(resolved_alerts[resolved_alerts['resolution_time_minutes'] < 30]) / len(resolved_alerts) * 100
                }

        return crisis_analysis

    async def _calculate_compliance_metrics(self, patient_id: str) -> Dict:
        """
        Calcule les métriques de compliance détaillées
        """
        # Compliance sur les 90 derniers jours
        ninety_days_ago = datetime.now() - timedelta(days=90)

        query = """
        SELECT 
            DATE(tz_timestamp) as date,
            COUNT(*) as measurements_count,
            COUNT(DISTINCT EXTRACT(HOUR FROM tz_timestamp)) as hours_covered,
            AVG(CASE WHEN quality_flag = 'ok' THEN 1 ELSE 0 END) as quality_rate
        FROM measurements 
        WHERE patient_id = %s 
            AND tz_timestamp >= %s
        GROUP BY DATE(tz_timestamp)
        ORDER BY date
        """

        conn = psycopg2.connect(**self.db_config)
        compliance_df = pd.read_sql_query(query, conn, params=(patient_id, ninety_days_ago))
        conn.close()

        compliance = {
            'monitoring_days': len(compliance_df),
            'total_possible_days': 90,
            'compliance_rate': len(compliance_df) / 90 * 100 if len(compliance_df) > 0 else 0
        }

        if not compliance_df.empty:
            # Analyse détaillée
            compliance['avg_measurements_per_day'] = float(compliance_df['measurements_count'].mean())
            compliance['avg_hours_covered_per_day'] = float(compliance_df['hours_covered'].mean())
            compliance['data_quality_rate'] = float(compliance_df['quality_rate'].mean() * 100)

            # Patterns de compliance
            compliance['consistency_score'] = float(1 - (compliance_df['measurements_count'].std() / compliance_df['measurements_count'].mean())) if compliance_df['measurements_count'].mean() > 0 else 0

            # Classification
            if compliance['compliance_rate'] >= 85:
                compliance['compliance_category'] = 'excellent'
            elif compliance['compliance_rate'] >= 70:
                compliance['compliance_category'] = 'good'
            elif compliance['compliance_rate'] >= 50:
                compliance['compliance_category'] = 'acceptable'
            else:
                compliance['compliance_category'] = 'poor'

        return compliance

    async def _calculate_risk_scores(self, patient_id: str, profile: Dict) -> Dict:
        """
        Calcule des scores de risque personnalisés
        """
        risk_scores = {}

        # Score de risque de crise (0-100)
        crisis_risk = 0

        # Facteurs génotype
        genotype = profile.get('demographics', {}).get('genotype', '')
        if genotype == 'SS':
            crisis_risk += 30
        elif genotype == 'SC':
            crisis_risk += 20
        elif genotype == 'AS':
            crisis_risk += 10

        # Facteurs physiologiques
        physio = profile.get('physiological_profile', {})
        spo2_mean = physio.get('spo2_mean', 100)
        if spo2_mean < 92:
            crisis_risk += 25
        elif spo2_mean < 95:
            crisis_risk += 15

        # Historique de crises
        crisis_history = profile.get('crisis_history', {})
        critical_alerts = crisis_history.get('critical_alerts', 0)
        if critical_alerts > 5:
            crisis_risk += 20
        elif critical_alerts > 2:
            crisis_risk += 10

        # Compliance
        compliance = profile.get('compliance_metrics', {})
        if compliance.get('compliance_rate', 100) < 70:
            crisis_risk += 15

        risk_scores['crisis_risk_score'] = min(crisis_risk, 100)

        # Classification du risque
        if crisis_risk >= 70:
            risk_scores['risk_category'] = 'high'
        elif crisis_risk >= 40:
            risk_scores['risk_category'] = 'medium'
        else:
            risk_scores['risk_category'] = 'low'

        return risk_scores

    async def _analyze_temporal_evolution(self, patient_id: str) -> Dict:
        """
        Analyse l'évolution temporelle sur 3, 6, 12 mois
        """
        periods = [
            ('3_months', relativedelta(months=3)),
            ('6_months', relativedelta(months=6)),
            ('12_months', relativedelta(months=12))
        ]

        evolution = {}

        for period_name, period_delta in periods:
            start_date = datetime.now() - period_delta

            query = """
            SELECT 
                AVG(spo2_pct) as avg_spo2,
                COUNT(*) FILTER (WHERE spo2_pct < 90) as hypoxemia_episodes,
                COUNT(DISTINCT DATE(tz_timestamp)) as monitoring_days
            FROM measurements 
            WHERE patient_id = %s 
                AND tz_timestamp >= %s
                AND quality_flag = 'ok'
            """

            conn = psycopg2.connect(**self.db_config)
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (patient_id, start_date))
                period_data = dict(cursor.fetchone() or {})
            conn.close()

            evolution[period_name] = period_data

        # Calcul des tendances
        if evolution.get('12_months', {}).get('avg_spo2') and evolution.get('3_months', {}).get('avg_spo2'):
            spo2_12m = evolution['12_months']['avg_spo2']
            spo2_3m = evolution['3_months']['avg_spo2']
            evolution['spo2_trend'] = 'improving' if spo2_3m > spo2_12m else 'declining' if spo2_3m < spo2_12m else 'stable'

        return evolution

    async def _generate_personalized_recommendations(self, profile: Dict) -> List[Dict]:
        """
        Génère des recommandations personnalisées basées sur le profil
        """
        recommendations = []

        # Recommandations basées sur le risque
        risk_category = profile.get('risk_scores', {}).get('risk_category', 'low')
        if risk_category == 'high':
            recommendations.append({
                'category': 'monitoring',
                'priority': 'high',
                'recommendation': 'Surveillance renforcée avec téléconsultations hebdomadaires',
                'rationale': 'Score de risque élevé nécessite suivi rapproché'
            })

        # Recommandations basées sur la compliance
        compliance_category = profile.get('compliance_metrics', {}).get('compliance_category', 'good')
        if compliance_category in ['acceptable', 'poor']:
            recommendations.append({
                'category': 'compliance',
                'priority': 'medium',
                'recommendation': 'Programme d\'accompagnement personnalisé pour améliorer l\'observance',
                'rationale': f'Compliance {compliance_category} nécessite support additionnel'
            })

        # Recommandations basées sur les patterns physiologiques
        spo2_baseline = profile.get('physiological_profile', {}).get('spo2_baseline_category', 'good')
        if spo2_baseline == 'concerning':
            recommendations.append({
                'category': 'medical',
                'priority': 'high',
                'recommendation': 'Évaluation médicale approfondie et ajustement thérapeutique',
                'rationale': 'SpO2 baseline préoccupant nécessite intervention'
            })

        return recommendations

    async def _analyze_patient_cohort(self, profiles: List[Dict]) -> Dict:
        """
        Analyse de cohorte sur l'ensemble des profils
        """
        if not profiles:
            return {}

        # Analyse par génotype
        genotype_stats = {}
        for genotype in ['SS', 'SC', 'AS']:
            genotype_profiles = [p for p in profiles if p.get('demographics', {}).get('genotype') == genotype]
            if genotype_profiles:
                avg_spo2 = np.mean([p.get('physiological_profile', {}).get('spo2_mean', 0) for p in genotype_profiles])
                avg_crises = np.mean([p.get('crisis_history', {}).get('critical_alerts', 0) for p in genotype_profiles])
                genotype_stats[genotype] = {
                    'patient_count': len(genotype_profiles),
                    'avg_spo2': avg_spo2,
                    'avg_critical_alerts': avg_crises
                }

        # Distribution des risques
        risk_distribution = {'high': 0, 'medium': 0, 'low': 0}
        for profile in profiles:
            risk_cat = profile.get('risk_scores', {}).get('risk_category', 'low')
            risk_distribution[risk_cat] += 1

        return {
            'total_patients': len(profiles),
            'genotype_analysis': genotype_stats,
            'risk_distribution': risk_distribution
        }

    async def _stratify_patient_risks(self, profiles: List[Dict]) -> Dict:
        """
        Stratification des risques pour la cohorte
        """
        high_risk_patients = [p for p in profiles if p.get('risk_scores', {}).get('risk_category') == 'high']

        stratification = {
            'high_risk_count': len(high_risk_patients),
            'high_risk_percentage': len(high_risk_patients) / len(profiles) * 100 if profiles else 0,
            'high_risk_patients': [p['patient_id'] for p in high_risk_patients]
        }

        return stratification

    async def _get_active_patients(self) -> List[str]:
        """
        Récupère la liste des patients actifs (avec données récentes)
        """
        thirty_days_ago = datetime.now() - timedelta(days=30)

        query = """
        SELECT DISTINCT patient_id 
        FROM measurements 
        WHERE tz_timestamp >= %s
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor() as cursor:
            cursor.execute(query, (thirty_days_ago,))
            patient_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return patient_ids

    async def _save_patient_profiles(self, profiles_report: Dict):
        """
        Sauvegarde les profils patients en base de données
        """
        try:
            for profile in profiles_report['profiles']:
                query = """
                INSERT INTO patient_comprehensive_profiles (
                    patient_id, profile_date,
                    risk_category, risk_score,
                    spo2_baseline, compliance_category,
                    crisis_count_6m, profile_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (patient_id, profile_date) DO UPDATE SET
                    risk_category = EXCLUDED.risk_category,
                    risk_score = EXCLUDED.risk_score,
                    spo2_baseline = EXCLUDED.spo2_baseline,
                    compliance_category = EXCLUDED.compliance_category,
                    crisis_count_6m = EXCLUDED.crisis_count_6m,
                    profile_data = EXCLUDED.profile_data
                """

                params = (
                    profile['patient_id'],
                    profile['profile_date'].date(),
                    profile.get('risk_scores', {}).get('risk_category'),
                    profile.get('risk_scores', {}).get('crisis_risk_score'),
                    profile.get('physiological_profile', {}).get('spo2_baseline_category'),
                    profile.get('compliance_metrics', {}).get('compliance_category'),
                    profile.get('crisis_history', {}).get('critical_alerts'),
                    json.dumps(profile, default=str)
                )

                conn = psycopg2.connect(**self.db_config)
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    conn.commit()
                conn.close()

            logger.info(f"✅ {len(profiles_report['profiles'])} profils patients sauvegardés")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde profils: {e}")

async def main():
    """
    Test du processeur de profils patients
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = PatientProfilesProcessor(db_config)
    profiles_report = await processor.generate_comprehensive_patient_profiles()

    print(f"👥 Profils patients générés:")
    print(f"   Total patients: {profiles_report['patients_processed']}")
    print(f"   Profils créés: {len(profiles_report['profiles'])}")
    if profiles_report['cohort_analytics']:
        print(f"   Patients haut risque: {profiles_report['risk_stratification']['high_risk_count']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
