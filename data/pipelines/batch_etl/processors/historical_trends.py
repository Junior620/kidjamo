#!/usr/bin/env python3
"""
🏥 KIDJAMO - Processeur Tendances Historiques
Calcul et analyse des tendances historiques des paramètres vitaux
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistoricalTrendsProcessor:
    """
    Processeur pour analyser les tendances historiques des données médicales
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config

    async def calculate_patient_trends(self, patient_id: str, timeframe_days: int = 90) -> Dict:
        """
        Calcule les tendances pour un patient sur une période donnée
        """
        logger.info(f"📈 Calcul tendances patient {patient_id} sur {timeframe_days} jours")

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=timeframe_days)

        # Récupération des données historiques
        historical_data = await self._get_patient_historical_data(patient_id, start_date, end_date)

        if not historical_data:
            return {'patient_id': patient_id, 'status': 'NO_DATA'}

        trends = {
            'patient_id': patient_id,
            'timeframe_days': timeframe_days,
            'analysis_date': datetime.now(),
            'status': 'SUCCESS'
        }

        # Tendances SpO2
        trends['spo2_trends'] = await self._calculate_spo2_trends(historical_data)

        # Tendances fréquence cardiaque
        trends['heart_rate_trends'] = await self._calculate_heart_rate_trends(historical_data)

        # Tendances température
        trends['temperature_trends'] = await self._calculate_temperature_trends(historical_data)

        # Patterns d'activité
        trends['activity_patterns'] = await self._analyze_activity_patterns(historical_data)

        # Détection de changements significatifs
        trends['significant_changes'] = await self._detect_significant_changes(historical_data)

        # Prédictions à court terme
        trends['short_term_predictions'] = await self._generate_short_term_predictions(historical_data)

        # Sauvegarde dans la base
        await self._save_trends_to_db(trends)

        return trends

    async def _get_patient_historical_data(self, patient_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Récupère les données historiques d'un patient
        """
        query = """
        SELECT 
            tz_timestamp as timestamp,
            spo2_pct,
            freq_card as heart_rate,
            temp_corp as temperature,
            temp_abiante as ambient_temp,
            pct_hydratation as hydration,
            activity,
            heat_index,
            quality_flag
        FROM measurements 
        WHERE patient_id = %s 
            AND DATE(tz_timestamp) BETWEEN %s AND %s
            AND quality_flag = 'ok'  -- Données valides uniquement
        ORDER BY tz_timestamp
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn, params=(patient_id, start_date, end_date))
        conn.close()

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        return df

    async def _calculate_spo2_trends(self, data: pd.DataFrame) -> Dict:
        """
        Calcule les tendances SpO2 avec analyses statistiques avancées
        """
        if 'spo2_pct' not in data.columns or data['spo2_pct'].isna().all():
            return {'status': 'NO_SPO2_DATA'}

        spo2_data = data['spo2_pct'].dropna()

        # Statistiques de base
        stats_basic = {
            'mean': float(spo2_data.mean()),
            'std': float(spo2_data.std()),
            'min': float(spo2_data.min()),
            'max': float(spo2_data.max()),
            'median': float(spo2_data.median()),
            'q25': float(spo2_data.quantile(0.25)),
            'q75': float(spo2_data.quantile(0.75))
        }

        # Tendance linéaire
        if len(spo2_data) >= 10:
            x = np.arange(len(spo2_data)).reshape(-1, 1)
            y = spo2_data.values

            model = LinearRegression().fit(x, y)
            trend_slope = float(model.coef_[0])
            trend_r2 = float(model.score(x, y))

            # Classification de la tendance
            if abs(trend_slope) < 0.01:
                trend_classification = 'stable'
            elif trend_slope > 0.01:
                trend_classification = 'improving'
            else:
                trend_classification = 'declining'
        else:
            trend_slope = 0
            trend_r2 = 0
            trend_classification = 'insufficient_data'

        # Détection d'anomalies (valeurs < 90%)
        critical_episodes = spo2_data[spo2_data < 90]

        # Variabilité (coefficient de variation)
        cv = stats_basic['std'] / stats_basic['mean'] if stats_basic['mean'] > 0 else 0

        # Analyse par périodes (jour/nuit si données suffisantes)
        time_patterns = {}
        if len(spo2_data) >= 100:  # Au moins 100 mesures
            data_with_hour = spo2_data.to_frame()
            data_with_hour['hour'] = data_with_hour.index.hour

            # Moyennes par tranche horaire
            day_hours = data_with_hour[data_with_hour['hour'].between(6, 18)]
            night_hours = data_with_hour[data_with_hour['hour'].between(19, 5)]

            if not day_hours.empty and not night_hours.empty:
                time_patterns = {
                    'day_mean': float(day_hours['spo2_pct'].mean()),
                    'night_mean': float(night_hours['spo2_pct'].mean()),
                    'day_night_diff': float(day_hours['spo2_pct'].mean() - night_hours['spo2_pct'].mean())
                }

        return {
            'status': 'SUCCESS',
            'basic_stats': stats_basic,
            'trend_slope': trend_slope,
            'trend_r2': trend_r2,
            'trend_classification': trend_classification,
            'critical_episodes_count': len(critical_episodes),
            'critical_episodes_percentage': len(critical_episodes) / len(spo2_data) * 100,
            'coefficient_variation': cv,
            'time_patterns': time_patterns,
            'data_points': len(spo2_data)
        }

    async def _calculate_heart_rate_trends(self, data: pd.DataFrame) -> Dict:
        """
        Calcule les tendances de fréquence cardiaque
        """
        if 'heart_rate' not in data.columns or data['heart_rate'].isna().all():
            return {'status': 'NO_HEART_RATE_DATA'}

        hr_data = data['heart_rate'].dropna()

        # Statistiques de base
        stats_basic = {
            'mean': float(hr_data.mean()),
            'std': float(hr_data.std()),
            'min': float(hr_data.min()),
            'max': float(hr_data.max()),
            'resting_hr_estimate': float(hr_data.quantile(0.1))  # 10e percentile comme FC repos
        }

        # Détection d'épisodes anormaux
        # Tachycardie (> 100 bpm) et bradycardie (< 60 bpm)
        tachycardia_episodes = hr_data[hr_data > 100]
        bradycardia_episodes = hr_data[hr_data < 60]

        # Variabilité de la fréquence cardiaque (HRV proxy)
        if len(hr_data) >= 50:
            hr_diff = np.diff(hr_data.values)
            rmssd = np.sqrt(np.mean(hr_diff**2))  # Root Mean Square of Successive Differences
        else:
            rmssd = 0

        return {
            'status': 'SUCCESS',
            'basic_stats': stats_basic,
            'tachycardia_episodes': len(tachycardia_episodes),
            'bradycardia_episodes': len(bradycardia_episodes),
            'hrv_rmssd': float(rmssd),
            'data_points': len(hr_data)
        }

    async def _calculate_temperature_trends(self, data: pd.DataFrame) -> Dict:
        """
        Calcule les tendances de température corporelle
        """
        if 'temperature' not in data.columns or data['temperature'].isna().all():
            return {'status': 'NO_TEMPERATURE_DATA'}

        temp_data = data['temperature'].dropna()

        # Statistiques de base
        stats_basic = {
            'mean': float(temp_data.mean()),
            'std': float(temp_data.std()),
            'min': float(temp_data.min()),
            'max': float(temp_data.max())
        }

        # Détection d'épisodes fébriles (> 38°C)
        fever_episodes = temp_data[temp_data > 38.0]

        # Hypothermie (< 36°C)
        hypothermia_episodes = temp_data[temp_data < 36.0]

        # Corrélation avec température ambiante si disponible
        ambient_correlation = 0
        if 'ambient_temp' in data.columns and not data['ambient_temp'].isna().all():
            valid_pairs = data[['temperature', 'ambient_temp']].dropna()
            if len(valid_pairs) >= 20:
                ambient_correlation = float(valid_pairs['temperature'].corr(valid_pairs['ambient_temp']))

        return {
            'status': 'SUCCESS',
            'basic_stats': stats_basic,
            'fever_episodes': len(fever_episodes),
            'hypothermia_episodes': len(hypothermia_episodes),
            'ambient_correlation': ambient_correlation,
            'data_points': len(temp_data)
        }

    async def _analyze_activity_patterns(self, data: pd.DataFrame) -> Dict:
        """
        Analyse les patterns d'activité physique
        """
        if 'activity' not in data.columns or data['activity'].isna().all():
            return {'status': 'NO_ACTIVITY_DATA'}

        activity_data = data['activity'].dropna()

        # Classification des niveaux d'activité
        low_activity = activity_data[activity_data <= 2]
        moderate_activity = activity_data[(activity_data > 2) & (activity_data <= 6)]
        high_activity = activity_data[activity_data > 6]

        # Patterns temporels
        time_patterns = {}
        if len(activity_data) >= 100:
            data_with_time = activity_data.to_frame()
            data_with_time['hour'] = data_with_time.index.hour
            data_with_time['day_of_week'] = data_with_time.index.dayofweek

            # Moyennes par heure
            hourly_avg = data_with_time.groupby('hour')['activity'].mean()
            most_active_hour = int(hourly_avg.idxmax())
            least_active_hour = int(hourly_avg.idxmin())

            # Différence weekend vs semaine
            weekday_avg = data_with_time[data_with_time['day_of_week'] < 5]['activity'].mean()
            weekend_avg = data_with_time[data_with_time['day_of_week'] >= 5]['activity'].mean()

            time_patterns = {
                'most_active_hour': most_active_hour,
                'least_active_hour': least_active_hour,
                'weekday_avg': float(weekday_avg),
                'weekend_avg': float(weekend_avg)
            }

        return {
            'status': 'SUCCESS',
            'activity_distribution': {
                'low_percentage': len(low_activity) / len(activity_data) * 100,
                'moderate_percentage': len(moderate_activity) / len(activity_data) * 100,
                'high_percentage': len(high_activity) / len(activity_data) * 100
            },
            'average_activity': float(activity_data.mean()),
            'time_patterns': time_patterns,
            'data_points': len(activity_data)
        }

    async def _detect_significant_changes(self, data: pd.DataFrame) -> Dict:
        """
        Détecte les changements significatifs dans les tendances
        """
        changes = {}

        # Comparaison première moitié vs deuxième moitié de la période
        if len(data) >= 20:
            mid_point = len(data) // 2
            first_half = data.iloc[:mid_point]
            second_half = data.iloc[mid_point:]

            # Changements SpO2
            if 'spo2_pct' in data.columns:
                spo2_first = first_half['spo2_pct'].dropna().mean()
                spo2_second = second_half['spo2_pct'].dropna().mean()

                if not (pd.isna(spo2_first) or pd.isna(spo2_second)):
                    spo2_change = spo2_second - spo2_first
                    changes['spo2_change'] = {
                        'absolute_change': float(spo2_change),
                        'percentage_change': float(spo2_change / spo2_first * 100),
                        'significance': 'significant' if abs(spo2_change) > 2 else 'minor'
                    }

            # Changements fréquence cardiaque
            if 'heart_rate' in data.columns:
                hr_first = first_half['heart_rate'].dropna().mean()
                hr_second = second_half['heart_rate'].dropna().mean()

                if not (pd.isna(hr_first) or pd.isna(hr_second)):
                    hr_change = hr_second - hr_first
                    changes['heart_rate_change'] = {
                        'absolute_change': float(hr_change),
                        'significance': 'significant' if abs(hr_change) > 10 else 'minor'
                    }

        return changes

    async def _generate_short_term_predictions(self, data: pd.DataFrame) -> Dict:
        """
        Génère des prédictions à court terme (7 jours)
        """
        predictions = {}

        # Prédiction SpO2 moyenne des 7 prochains jours
        if 'spo2_pct' in data.columns and len(data) >= 30:
            spo2_recent = data['spo2_pct'].dropna().tail(30)  # 30 dernières mesures valides

            if len(spo2_recent) >= 10:
                # Modèle de régression simple
                x = np.arange(len(spo2_recent)).reshape(-1, 1)
                y = spo2_recent.values

                model = LinearRegression().fit(x, y)

                # Prédiction pour 7 jours (estimation basée sur tendance récente)
                future_x = np.array([[len(spo2_recent) + 7]])
                predicted_spo2 = model.predict(future_x)[0]

                # Intervalle de confiance simple (basé sur std récente)
                recent_std = float(spo2_recent.std())

                predictions['spo2_7days'] = {
                    'predicted_value': float(predicted_spo2),
                    'confidence_interval_lower': float(predicted_spo2 - recent_std),
                    'confidence_interval_upper': float(predicted_spo2 + recent_std),
                    'trend_direction': 'improving' if model.coef_[0] > 0 else 'declining' if model.coef_[0] < 0 else 'stable'
                }

        return predictions

    async def _save_trends_to_db(self, trends: Dict):
        """
        Sauvegarde les tendances calculées en base de données
        """
        try:
            query = """
            INSERT INTO patient_historical_trends (
                patient_id, analysis_date, timeframe_days,
                spo2_mean, spo2_trend_slope, spo2_trend_classification,
                heart_rate_mean, temperature_mean,
                critical_episodes_count, trends_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (patient_id, analysis_date) DO UPDATE SET
                spo2_mean = EXCLUDED.spo2_mean,
                spo2_trend_slope = EXCLUDED.spo2_trend_slope,
                spo2_trend_classification = EXCLUDED.spo2_trend_classification,
                heart_rate_mean = EXCLUDED.heart_rate_mean,
                temperature_mean = EXCLUDED.temperature_mean,
                critical_episodes_count = EXCLUDED.critical_episodes_count,
                trends_data = EXCLUDED.trends_data
            """

            # Extraction des valeurs clés
            spo2_trends = trends.get('spo2_trends', {})
            hr_trends = trends.get('heart_rate_trends', {})
            temp_trends = trends.get('temperature_trends', {})

            params = (
                trends['patient_id'],
                trends['analysis_date'],
                trends['timeframe_days'],
                spo2_trends.get('basic_stats', {}).get('mean'),
                spo2_trends.get('trend_slope'),
                spo2_trends.get('trend_classification'),
                hr_trends.get('basic_stats', {}).get('mean'),
                temp_trends.get('basic_stats', {}).get('mean'),
                spo2_trends.get('critical_episodes_count'),
                json.dumps(trends)  # Stockage complet en JSON
            )

            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            conn.close()

            logger.info(f"✅ Tendances sauvegardées pour patient {trends['patient_id']}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde tendances: {e}")

async def main():
    """
    Test du processeur de tendances historiques
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = HistoricalTrendsProcessor(db_config)

    # Test avec un patient exemple (à adapter)
    test_patient_id = "patient_001"
    trends = await processor.calculate_patient_trends(test_patient_id, timeframe_days=30)

    print(f"📊 Résultats analyse tendances:")
    print(f"   Patient: {trends['patient_id']}")
    print(f"   Statut: {trends['status']}")
    if trends['status'] == 'SUCCESS':
        print(f"   SpO2 moyen: {trends['spo2_trends']['basic_stats']['mean']:.1f}%")
        print(f"   Tendance: {trends['spo2_trends']['trend_classification']}")

if __name__ == "__main__":
    import asyncio
    import json
    asyncio.run(main())
