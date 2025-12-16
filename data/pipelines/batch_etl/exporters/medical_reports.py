#!/usr/bin/env python3
"""
🏥 KIDJAMO - Exporteur Rapports Médicaux PDF
Génération automatique de rapports médicaux au format PDF
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedicalReportsExporter:
    """
    Exporteur pour générer des rapports médicaux PDF automatisés
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config

    async def generate_patient_medical_report(self, patient_id: str, timeframe_days: int = 30) -> str:
        """
        Génère un rapport médical PDF complet pour un patient
        """
        logger.info(f"📄 Génération rapport médical PDF pour patient {patient_id}")

        # Collecte des données
        patient_data = await self._collect_patient_report_data(patient_id, timeframe_days)

        # Génération du PDF
        filename = f"rapport_medical_{patient_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = f"../../evidence/medical_reports/{filename}"

        await self._create_pdf_report(patient_data, filepath)

        return filepath

    async def _collect_patient_report_data(self, patient_id: str, timeframe_days: int) -> Dict:
        """
        Collecte toutes les données nécessaires pour le rapport
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=timeframe_days)

        # Informations patient
        patient_info_query = """
        SELECT 
            u.first_name, u.last_name, u.gender,
            p.genotype, p.birth_date,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age
        FROM patients p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.patient_id = %s
        """

        # Données vitales période
        vitals_query = """
        SELECT 
            DATE(tz_timestamp) as date,
            AVG(spo2_pct) as avg_spo2,
            MIN(spo2_pct) as min_spo2,
            MAX(spo2_pct) as max_spo2,
            AVG(freq_card) as avg_hr,
            AVG(temp_corp) as avg_temp,
            MAX(temp_corp) as max_temp,
            COUNT(*) as measurements_count
        FROM measurements 
        WHERE patient_id = %s 
            AND DATE(tz_timestamp) BETWEEN %s AND %s
            AND quality_flag = 'ok'
        GROUP BY DATE(tz_timestamp)
        ORDER BY date
        """

        # Alertes période
        alerts_query = """
        SELECT 
            created_at, alert_type, severity, message,
            CASE WHEN EXISTS (
                SELECT 1 FROM alert_statut_logs 
                WHERE alert_id = a.alert_id AND statut = 'resolved'
            ) THEN 'Résolu' ELSE 'En cours' END as status
        FROM alerts a
        WHERE patient_id = %s 
            AND DATE(created_at) BETWEEN %s AND %s
        ORDER BY created_at DESC
        """

        # Traitements actuels
        treatments_query = """
        SELECT drug_name, treatment_start, treatment_end
        FROM treatments 
        WHERE patient_id = %s 
            AND (treatment_end IS NULL OR treatment_end >= %s)
        ORDER BY treatment_start DESC
        """

        conn = psycopg2.connect(**self.db_config)

        # Exécution des requêtes
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Info patient
            cursor.execute(patient_info_query, (patient_id,))
            patient_info = dict(cursor.fetchone() or {})

            # Données vitales
            cursor.execute(vitals_query, (patient_id, start_date, end_date))
            vitals_data = [dict(row) for row in cursor.fetchall()]

            # Alertes
            cursor.execute(alerts_query, (patient_id, start_date, end_date))
            alerts_data = [dict(row) for row in cursor.fetchall()]

            # Traitements
            cursor.execute(treatments_query, (patient_id, start_date))
            treatments_data = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'patient_info': patient_info,
            'vitals_data': vitals_data,
            'alerts_data': alerts_data,
            'treatments_data': treatments_data,
            'period': {'start': start_date, 'end': end_date}
        }

    async def _create_pdf_report(self, data: Dict, filepath: str):
        """
        Crée le rapport PDF avec mise en forme médicale
        """
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Configuration du document
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()

        # Styles personnalisés
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.HexColor('#2c5aa0')
        )

        story = []

        # En-tête du rapport
        story.append(Paragraph("🏥 RAPPORT MÉDICAL KIDJAMO", title_style))
        story.append(Spacer(1, 20))

        # Informations patient
        patient_info = data['patient_info']
        if patient_info:
            patient_table_data = [
                ['Patient:', f"{patient_info.get('first_name', '')} {patient_info.get('last_name', '')}"],
                ['Âge:', f"{patient_info.get('age', 'N/A')} ans"],
                ['Génotype:', patient_info.get('genotype', 'N/A')],
                ['Sexe:', patient_info.get('gender', 'N/A')],
                ['Période:', f"{data['period']['start']} → {data['period']['end']}"],
                ['Date génération:', datetime.now().strftime('%d/%m/%Y à %H:%M')]
            ]

            patient_table = Table(patient_table_data, colWidths=[2*inch, 4*inch])
            patient_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(patient_table)
            story.append(Spacer(1, 30))

        # Résumé des données vitales
        if data['vitals_data']:
            story.append(Paragraph("📊 RÉSUMÉ DES PARAMÈTRES VITAUX", styles['Heading2']))

            # Calculs statistiques
            vitals_df = pd.DataFrame(data['vitals_data'])

            summary_data = [
                ['Paramètre', 'Moyenne', 'Min', 'Max', 'Écart-type'],
                ['SpO2 (%)',
                 f"{vitals_df['avg_spo2'].mean():.1f}",
                 f"{vitals_df['min_spo2'].min():.1f}",
                 f"{vitals_df['max_spo2'].max():.1f}",
                 f"{vitals_df['avg_spo2'].std():.1f}"],
                ['Fréquence cardiaque (bpm)',
                 f"{vitals_df['avg_hr'].mean():.0f}",
                 f"{vitals_df['avg_hr'].min():.0f}",
                 f"{vitals_df['avg_hr'].max():.0f}",
                 f"{vitals_df['avg_hr'].std():.1f}"],
                ['Température (°C)',
                 f"{vitals_df['avg_temp'].mean():.1f}",
                 f"{vitals_df['avg_temp'].min():.1f}",
                 f"{vitals_df['max_temp'].max():.1f}",
                 f"{vitals_df['avg_temp'].std():.1f}"]
            ]

            summary_table = Table(summary_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(summary_table)
            story.append(Spacer(1, 20))

            # Graphique d'évolution SpO2
            chart_image = await self._create_spo2_chart(vitals_df)
            if chart_image:
                story.append(chart_image)
                story.append(Spacer(1, 20))

        # Alertes et incidents
        if data['alerts_data']:
            story.append(Paragraph("🚨 ALERTES ET INCIDENTS", styles['Heading2']))

            alerts_summary = f"Total: {len(data['alerts_data'])} alertes sur la période"
            critical_count = len([a for a in data['alerts_data'] if a['severity'] == 'critical'])
            if critical_count > 0:
                alerts_summary += f" (dont {critical_count} critiques)"

            story.append(Paragraph(alerts_summary, styles['Normal']))
            story.append(Spacer(1, 10))

            # Tableau des alertes récentes (5 dernières)
            recent_alerts = data['alerts_data'][:5]
            alerts_table_data = [['Date/Heure', 'Type', 'Sévérité', 'Statut']]

            for alert in recent_alerts:
                alerts_table_data.append([
                    alert['created_at'].strftime('%d/%m %H:%M'),
                    alert['alert_type'],
                    alert['severity'],
                    alert['status']
                ])

            alerts_table = Table(alerts_table_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1*inch])
            alerts_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(alerts_table)
            story.append(Spacer(1, 20))

        # Traitements actuels
        if data['treatments_data']:
            story.append(Paragraph("💊 TRAITEMENTS EN COURS", styles['Heading2']))

            treatments_table_data = [['Médicament', 'Début', 'Fin prévue']]

            for treatment in data['treatments_data']:
                end_date = treatment['treatment_end'].strftime('%d/%m/%Y') if treatment['treatment_end'] else 'En cours'
                treatments_table_data.append([
                    treatment['drug_name'],
                    treatment['treatment_start'].strftime('%d/%m/%Y'),
                    end_date
                ])

            treatments_table = Table(treatments_table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            treatments_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#388e3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(treatments_table)
            story.append(Spacer(1, 20))

        # Recommandations médicales
        story.append(Paragraph("💡 RECOMMANDATIONS", styles['Heading2']))
        recommendations = await self._generate_medical_recommendations(data)

        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", styles['Normal']))

        story.append(Spacer(1, 30))

        # Pied de page
        footer_text = """
        <i>Rapport généré automatiquement par le système Kidjamo de surveillance médicale continue.<br/>
        Ce document est confidentiel et destiné exclusivement à l'usage médical.</i>
        """
        story.append(Paragraph(footer_text, styles['Normal']))

        # Construction du PDF
        doc.build(story)
        logger.info(f"✅ Rapport PDF généré: {filepath}")

    async def _create_spo2_chart(self, vitals_df):
        """
        Crée un graphique d'évolution SpO2
        """
        try:
            plt.figure(figsize=(8, 4))
            plt.plot(vitals_df['date'], vitals_df['avg_spo2'], marker='o', linewidth=2)
            plt.axhline(y=95, color='orange', linestyle='--', alpha=0.7, label='Seuil surveillance')
            plt.axhline(y=90, color='red', linestyle='--', alpha=0.7, label='Seuil critique')

            plt.title('Évolution SpO2 moyenne quotidienne')
            plt.xlabel('Date')
            plt.ylabel('SpO2 (%)')
            plt.xticks(rotation=45)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            # Conversion en image pour PDF
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close()

            from reportlab.platypus import Image
            chart_image = Image(img_buffer, width=6*inch, height=3*inch)
            return chart_image

        except Exception as e:
            logger.error(f"Erreur génération graphique: {e}")
            return None

    async def _generate_medical_recommendations(self, data: Dict) -> List[str]:
        """
        Génère des recommandations médicales basées sur les données
        """
        recommendations = []

        if data['vitals_data']:
            vitals_df = pd.DataFrame(data['vitals_data'])
            avg_spo2 = vitals_df['avg_spo2'].mean()

            if avg_spo2 < 92:
                recommendations.append("⚠️ SpO2 moyenne préoccupante (<92%). Consultation urgente recommandée.")
            elif avg_spo2 < 95:
                recommendations.append("📋 SpO2 moyenne en zone de surveillance. Suivi renforcé conseillé.")

            # Variabilité SpO2
            spo2_std = vitals_df['avg_spo2'].std()
            if spo2_std > 3:
                recommendations.append("📊 Forte variabilité SpO2. Évaluer compliance et qualité du capteur.")

        # Recommandations basées sur les alertes
        if data['alerts_data']:
            critical_alerts = [a for a in data['alerts_data'] if a['severity'] == 'critical']
            if len(critical_alerts) > 3:
                recommendations.append("🚨 Nombre élevé d'alertes critiques. Révision du plan thérapeutique suggérée.")

        # Recommandations générales
        recommendations.extend([
            "💧 Maintenir une hydratation optimale, particulièrement par temps chaud",
            "🏃‍♂️ Activité physique modérée selon recommandations médicales",
            "📱 Vérifier régulièrement le bon fonctionnement du capteur IoT"
        ])

        return recommendations

async def main():
    """
    Test de l'exporteur de rapports médicaux
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    exporter = MedicalReportsExporter(db_config)

    # Test avec un patient exemple
    test_patient_id = "patient_001"
    filepath = await exporter.generate_patient_medical_report(test_patient_id, timeframe_days=30)

    print(f"📄 Rapport médical généré: {filepath}")

if __name__ == "__main__":
    import asyncio
    import pandas as pd
    asyncio.run(main())
