# =====================================================
# SUITE DU SIMULATEUR MASSIF - PARTIE 2
# =====================================================

# =====================================================
# GESTIONNAIRE BASE DE DONNÉES
# =====================================================

class DatabaseManager:
    """Gestionnaire optimisé pour insertion batch haute performance"""

    def __init__(self):
        self.connection = None
        self.measurement_buffer = []
        self.alert_buffer = []
        self.patient_buffer = []
        self.buffer_size = 1000  # Taille batch pour performance
        self.last_flush_time = datetime.now()
        self._connect()

    def _connect(self):
        """Connexion PostgreSQL avec configuration optimisée"""
        try:
            self.connection = psycopg2.connect(**DB_CONFIG)
            self.connection.autocommit = False
            logger.info("✅ Connexion PostgreSQL établie")
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            self.connection = None

    def _ensure_connection(self):
        """Vérification et reconnexion si nécessaire"""
        if not self.connection or self.connection.closed:
            self._connect()

    def add_patient(self, patient: PatientProfile):
        """Ajout patient au buffer"""
        self.patient_buffer.append(patient.to_db_record())

        # Flush immédiat pour les patients (nombre limité)
        if len(self.patient_buffer) >= 10:
            self.flush_patients()

    def add_measurement(self, measurement: MeasurementRecord):
        """Ajout mesure au buffer avec flush automatique"""
        self.measurement_buffer.append(measurement.to_db_record())

        # Flush automatique si buffer plein ou timeout
        current_time = datetime.now()
        if (len(self.measurement_buffer) >= self.buffer_size or
            (current_time - self.last_flush_time).seconds >= 30):
            self.flush_measurements()

    def add_alert(self, alert: AlertRecord):
        """Ajout alerte au buffer avec flush prioritaire"""
        self.alert_buffer.append(alert.to_db_record())

        # Flush immédiat pour alertes critiques
        if alert.severity == 'critical' or len(self.alert_buffer) >= 50:
            self.flush_alerts()

    def flush_patients(self):
        """Flush buffer patients vers PostgreSQL"""
        if not self.patient_buffer or not self.connection:
            return

        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            # Insertion users d'abord
            user_query = """
                INSERT INTO users (user_id, role, first_name, last_name, gender, 
                                 email, password_hash, phone, city, country, 
                                 is_active, created_at, updated_at)
                VALUES (%(user_id)s, 'patient', %(first_name)s, %(last_name)s, %(gender)s,
                        %(email)s, 'simulation_hash', %(phone)s, 'Simulation City', 'France',
                        true, %(created_at)s, %(updated_at)s)
                ON CONFLICT (user_id) DO NOTHING
            """

            users_data = []
            for patient in self.patient_buffer:
                # Génération données user depuis patient
                birth_date = patient['birth_date']
                age = (datetime.now().date() - birth_date).days // 365

                user_data = {
                    'user_id': patient['user_id'],
                    'first_name': f"Patient_{patient['patient_id'][:8]}",
                    'last_name': f"Sim_{age}ans",
                    'gender': random.choice(['M', 'F']),
                    'email': f"patient_{patient['patient_id'][:8]}@kidjamo-sim.com",
                    'phone': f"+237695{random.randint(100000, 999999)}",
                    'created_at': patient['created_at'],
                    'updated_at': patient['updated_at']
                }
                users_data.append(user_data)

            execute_batch(cursor, user_query, users_data, page_size=100)

            # Insertion patients
            patient_query = """
                INSERT INTO patients (patient_id, user_id, genotype, birth_date, 
                                    weight_kg, height_cm, current_device_id, 
                                    medical_notes, created_at, updated_at)
                VALUES (%(patient_id)s, %(user_id)s, %(genotype)s, %(birth_date)s,
                        %(weight_kg)s, %(height_cm)s, %(current_device_id)s,
                        %(medical_notes)s, %(created_at)s, %(updated_at)s)
                ON CONFLICT (patient_id) DO NOTHING
            """

            execute_batch(cursor, patient_query, self.patient_buffer, page_size=100)
            self.connection.commit()

            logger.info(f"💾 Flush {len(self.patient_buffer)} patients vers DB")
            self.patient_buffer.clear()

        except Exception as e:
            logger.error(f"❌ Erreur flush patients: {e}")
            if self.connection:
                self.connection.rollback()

    def flush_measurements(self):
        """Flush buffer mesures vers PostgreSQL avec performance optimisée"""
        if not self.measurement_buffer or not self.connection:
            return

        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            query = """
                INSERT INTO measurements (
                    patient_id, device_id, message_id, recorded_at, received_at,
                    heart_rate_bpm, respiratory_rate_min, spo2_percent, 
                    temperature_celsius, ambient_temp_celsius, hydration_percent,
                    activity_level, heat_index_celsius, pain_scale, 
                    battery_percent, signal_quality, quality_flag, 
                    data_source, is_validated
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """

            execute_batch(cursor, query, self.measurement_buffer, page_size=1000)
            self.connection.commit()

            logger.info(f"💾 Flush {len(self.measurement_buffer)} mesures vers DB")
            self.measurement_buffer.clear()
            self.last_flush_time = datetime.now()

        except Exception as e:
            logger.error(f"❌ Erreur flush mesures: {e}")
            if self.connection:
                self.connection.rollback()

    def flush_alerts(self):
        """Flush buffer alertes vers PostgreSQL"""
        if not self.alert_buffer or not self.connection:
            return

        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            query = """
                INSERT INTO alerts (
                    patient_id, alert_type, severity, title, message,
                    vitals_snapshot, trigger_conditions, suggested_actions,
                    created_at, first_seen_at, resolved_at, auto_resolved,
                    ack_deadline, escalation_level, created_by_system,
                    related_measurement_id, correlation_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
            """

            execute_batch(cursor, query, self.alert_buffer, page_size=100)
            self.connection.commit()

            logger.info(f"🚨 Flush {len(self.alert_buffer)} alertes vers DB")
            self.alert_buffer.clear()

        except Exception as e:
            logger.error(f"❌ Erreur flush alertes: {e}")
            if self.connection:
                self.connection.rollback()

    def flush_all(self):
        """Flush tous les buffers"""
        self.flush_patients()
        self.flush_measurements()
        self.flush_alerts()

    def close(self):
        """Fermeture propre avec flush final"""
        self.flush_all()
        if self.connection:
            self.connection.close()

# =====================================================
# MOTEUR DE DÉTECTION D'ALERTES
# =====================================================

class AlertEngine:
    """Moteur de détection d'alertes médicales avec logique clinique avancée"""

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
        self.alert_history = {}  # Cache pour éviter spam alertes
        self.cooldown_period = 300  # 5 min entre alertes similaires

    def analyze_measurement(self, measurement: MeasurementRecord, patient: PatientProfile) -> List[AlertRecord]:
        """Analyse une mesure et génère les alertes appropriées"""
        alerts = []
        current_time = measurement.recorded_at

        # Snapshot des signes vitaux pour contexte
        vitals_snapshot = {
            'spo2': measurement.spo2_percent,
            'heart_rate': measurement.heart_rate_bpm,
            'temperature': measurement.temperature_celsius,
            'respiratory_rate': measurement.respiratory_rate_min,
            'hydration': measurement.hydration_percent,
            'pain': measurement.pain_scale,
            'battery': measurement.battery_percent,
            'signal_quality': measurement.signal_quality,
            'activity': measurement.activity_level
        }

        # 1. Alertes SpO2 critiques (priorité maximale)
        spo2_alerts = self._check_spo2_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(spo2_alerts)

        # 2. Alertes température/fièvre
        temp_alerts = self._check_temperature_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(temp_alerts)

        # 3. Alertes rythme cardiaque
        hr_alerts = self._check_heart_rate_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(hr_alerts)

        # 4. Alertes respiratoires
        resp_alerts = self._check_respiratory_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(resp_alerts)

        # 5. Alertes déshydratation
        hydration_alerts = self._check_hydration_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(hydration_alerts)

        # 6. Alertes douleur sévère
        pain_alerts = self._check_pain_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(pain_alerts)

        # 7. Alertes techniques (batterie, signal)
        tech_alerts = self._check_technical_alerts(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(tech_alerts)

        # 8. Combinaisons multi-paramètres (crise drépanocytaire)
        crisis_alerts = self._check_crisis_patterns(measurement, patient, vitals_snapshot, current_time)
        alerts.extend(crisis_alerts)

        return alerts

    def _check_spo2_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                          vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes SpO2 avec seuils adaptés au génotype"""
        alerts = []
        spo2 = measurement.spo2_percent

        # Seuils selon génotype
        if patient.genotype == "SS":
            critical_threshold = MEDICAL_THRESHOLDS["spo2_critical_ss"]
        else:
            critical_threshold = MEDICAL_THRESHOLDS["spo2_critical_general"]

        # SpO2 critique
        if spo2 < critical_threshold:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="spo2_critical",
                severity="critical",
                title=f"SpO2 CRITIQUE: {spo2}%",
                message=f"SpO2 dangereusement basse ({spo2}%) - Intervention immédiate requise",
                vitals_snapshot=vitals,
                trigger_conditions=[f"SpO2 {spo2}% < seuil critique {critical_threshold}%"],
                suggested_actions=[
                    "Administrer oxygène immédiatement",
                    "Contacter équipe médicale d'urgence",
                    "Positionner patient en position semi-assise",
                    "Surveiller signes de détresse respiratoire"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=5)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # SpO2 basse (surveillance)
        elif spo2 < MEDICAL_THRESHOLDS["spo2_low"]:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="spo2_low",
                severity="alert",
                title=f"SpO2 Basse: {spo2}%",
                message=f"SpO2 sous la normale ({spo2}%) - Surveillance renforcée recommandée",
                vitals_snapshot=vitals,
                trigger_conditions=[f"SpO2 {spo2}% < {MEDICAL_THRESHOLDS['spo2_low']}%"],
                suggested_actions=[
                    "Surveiller évolution SpO2",
                    "Vérifier positionnement capteur",
                    "Encourager respiration profonde",
                    "Préparer oxygène si dégradation"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=15)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_temperature_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                                 vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes température corporelle"""
        alerts = []
        temp = measurement.temperature_celsius

        # Fièvre élevée (critique)
        if temp >= MEDICAL_THRESHOLDS["temperature_high_fever"]:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="fever_high",
                severity="critical",
                title=f"FIÈVRE ÉLEVÉE: {temp}°C",
                message=f"Température très élevée ({temp}°C) - Risque complications",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Température {temp}°C ≥ {MEDICAL_THRESHOLDS['temperature_high_fever']}°C"],
                suggested_actions=[
                    "Administrer antipyrétique selon protocole",
                    "Refroidissement physique (linge humide)",
                    "Surveillance neurologique",
                    "Contacter médecin urgence",
                    "Rechercher foyer infectieux"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=10)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Fièvre modérée
        elif temp >= MEDICAL_THRESHOLDS["temperature_fever"]:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="fever",
                severity="alert",
                title=f"Fièvre Détectée: {temp}°C",
                message=f"Élévation température ({temp}°C) - Surveillance nécessaire",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Température {temp}°C ≥ {MEDICAL_THRESHOLDS['temperature_fever']}°C"],
                suggested_actions=[
                    "Surveiller évolution température",
                    "Encourager hydratation",
                    "Mesures confort (vêtements légers)",
                    "Préparer antipyrétique si progression"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=30)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Hypothermie
        elif temp < 35.0:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="hypothermia",
                severity="alert",
                title=f"Hypothermie: {temp}°C",
                message=f"Température corporelle basse ({temp}°C)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Température {temp}°C < 35.0°C"],
                suggested_actions=[
                    "Réchauffement progressif",
                    "Surveillance cardiaque",
                    "Couvertures chauffantes",
                    "Évaluation état général"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=20)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_heart_rate_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                                vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes rythme cardiaque selon âge"""
        alerts = []
        hr = measurement.heart_rate_bpm

        # Seuils selon âge
        if patient.age < 18:
            tachy_threshold = MEDICAL_THRESHOLDS["heart_rate_tachycardia_child"]
            brady_threshold = 60
        else:
            tachy_threshold = MEDICAL_THRESHOLDS["heart_rate_tachycardia_adult"]
            brady_threshold = MEDICAL_THRESHOLDS["heart_rate_bradycardia"]

        # Tachycardie
        if hr > tachy_threshold:
            severity = "critical" if hr > tachy_threshold + 30 else "alert"
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="tachycardia",
                severity=severity,
                title=f"Tachycardie: {hr} bpm",
                message=f"Fréquence cardiaque élevée ({hr} bpm)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"FC {hr} bpm > {tachy_threshold} bpm"],
                suggested_actions=[
                    "Évaluer tolérance hémodynamique",
                    "Rechercher cause (fièvre, douleur, stress)",
                    "Surveillance électrocardiographique",
                    "Mesures de refroidissement si fièvre"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=15 if severity == "alert" else 5)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Bradycardie
        elif hr < brady_threshold:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="bradycardia",
                severity="alert",
                title=f"Bradycardie: {hr} bpm",
                message=f"Fréquence cardiaque basse ({hr} bpm)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"FC {hr} bpm < {brady_threshold} bpm"],
                suggested_actions=[
                    "Évaluer état neurologique",
                    "Vérifier capteur et placement",
                    "Surveillance pression artérielle",
                    "Rechercher signes d'intolérance"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=20)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_respiratory_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                                 vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes fréquence respiratoire"""
        alerts = []
        rr = measurement.respiratory_rate_min

        # Seuils selon âge
        if patient.age < 18:
            tachy_threshold = MEDICAL_THRESHOLDS["respiratory_rate_high_child"]
            brady_threshold = 12
        else:
            tachy_threshold = MEDICAL_THRESHOLDS["respiratory_rate_high_adult"]
            brady_threshold = 8

        # Tachypnée
        if rr > tachy_threshold:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="tachypnea",
                severity="alert",
                title=f"Tachypnée: {rr}/min",
                message=f"Fréquence respiratoire élevée ({rr}/min)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"FR {rr}/min > {tachy_threshold}/min"],
                suggested_actions=[
                    "Évaluer détresse respiratoire",
                    "Rechercher cause (fièvre, douleur, anxiété)",
                    "Surveiller SpO2 en continu",
                    "Considérer oxygénothérapie"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=15)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Bradypnée
        elif rr < brady_threshold:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="bradypnea",
                severity="alert",
                title=f"Bradypnée: {rr}/min",
                message=f"Fréquence respiratoire basse ({rr}/min)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"FR {rr}/min < {brady_threshold}/min"],
                suggested_actions=[
                    "Évaluer état de conscience",
                    "Vérifier perméabilité voies aériennes",
                    "Surveillance neurologique",
                    "Préparer ventilation assistée si nécessaire"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=10)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_hydration_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                               vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes déshydratation"""
        alerts = []
        hydration = measurement.hydration_percent

        # Déshydratation critique
        if hydration < MEDICAL_THRESHOLDS["dehydration_threshold"]:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="dehydration_critical",
                severity="critical",
                title=f"Déshydratation Sévère: {hydration}%",
                message=f"Niveau d'hydratation critique ({hydration}%)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Hydratation {hydration}% < {MEDICAL_THRESHOLDS['dehydration_threshold']}%"],
                suggested_actions=[
                    "Réhydratation orale immédiate",
                    "Évaluer tolérance digestive",
                    "Considérer réhydratation IV",
                    "Surveiller signes choc hypovolémique",
                    "Rechercher cause de la déshydratation"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=10)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Déshydratation modérée
        elif hydration < 55:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="dehydration_moderate",
                severity="alert",
                title=f"Déshydratation: {hydration}%",
                message=f"Niveau d'hydratation bas ({hydration}%)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Hydratation {hydration}% < 55%"],
                suggested_actions=[
                    "Encourager apports hydriques",
                    "Surveillance diurèse",
                    "Évaluer signes cliniques déshydratation",
                    "Adapter apports selon activité/température"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=30)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_pain_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                          vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes douleur"""
        alerts = []
        pain = measurement.pain_scale

        # Douleur sévère
        if pain >= MEDICAL_THRESHOLDS["pain_severe"]:
            severity = "critical" if pain >= 9 else "alert"
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="pain_severe",
                severity=severity,
                title=f"Douleur Sévère: {pain}/10",
                message=f"Score de douleur élevé ({pain}/10) - Intervention requise",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Douleur {pain}/10 ≥ {MEDICAL_THRESHOLDS['pain_severe']}/10"],
                suggested_actions=[
                    "Évaluer localisation et caractère douleur",
                    "Administrer antalgiques selon protocole",
                    "Rechercher signes de crise drépanocytaire",
                    "Mesures non-médicamenteuses (position, froid/chaud)",
                    "Réévaluer efficacité traitement"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=15 if severity == "alert" else 5)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_technical_alerts(self, measurement: MeasurementRecord, patient: PatientProfile,
                               vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Vérification alertes techniques (batterie, signal)"""
        alerts = []

        # Batterie critique
        if measurement.battery_percent <= MEDICAL_THRESHOLDS["battery_critical"]:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="battery_critical",
                severity="warn",
                title=f"Batterie Critique: {measurement.battery_percent}%",
                message=f"Niveau batterie faible ({measurement.battery_percent}%) - Recharge requise",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Batterie {measurement.battery_percent}% ≤ {MEDICAL_THRESHOLDS['battery_critical']}%"],
                suggested_actions=[
                    "Recharger dispositif immédiatement",
                    "Vérifier connexions et câbles",
                    "Préparer dispositif de secours",
                    "Notifier patient/famille"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=60)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        # Signal faible
        if measurement.signal_quality < 50:
            alert = AlertRecord(
                alert_id=None,
                patient_id=patient.patient_id,
                alert_type="signal_poor",
                severity="warn",
                title=f"Signal Faible: {measurement.signal_quality}%",
                message=f"Qualité signal dégradée ({measurement.signal_quality}%)",
                vitals_snapshot=vitals,
                trigger_conditions=[f"Qualité signal {measurement.signal_quality}% < 50%"],
                suggested_actions=[
                    "Vérifier placement capteurs",
                    "Nettoyer surfaces de contact",
                    "Repositionner dispositif",
                    "Vérifier interférences environnementales"
                ],
                created_at=timestamp,
                ack_deadline=timestamp + timedelta(minutes=45)
            )

            if self._should_trigger_alert(alert, patient):
                alerts.append(alert)

        return alerts

    def _check_crisis_patterns(self, measurement: MeasurementRecord, patient: PatientProfile,
                              vitals: Dict, timestamp: datetime) -> List[AlertRecord]:
        """Détection patterns multi-paramètres suggérant crise drépanocytaire"""
        alerts = []

        # Combinaison critique pour drépanocytose SS/SC
        if patient.genotype in ["SS", "SC", "Sβ0"]:
            crisis_indicators = 0
            conditions = []

            # SpO2 basse
            if measurement.spo2_percent < 92:
                crisis_indicators += 2
                conditions.append(f"SpO2 {measurement.spo2_percent}% < 92%")

            # Douleur élevée
            if measurement.pain_scale >= 6:
                crisis_indicators += 2
                conditions.append(f"Douleur {measurement.pain_scale}/10 ≥ 6/10")

            # Fièvre
            if measurement.temperature_celsius >= 38.0:
                crisis_indicators += 1
                conditions.append(f"Fièvre {measurement.temperature_celsius}°C")

            # Tachycardie
            if measurement.heart_rate_bpm > (120 if patient.age >= 18 else 140):
                crisis_indicators += 1
                conditions.append(f"Tachycardie {measurement.heart_rate_bpm} bpm")

            # Déshydratation
            if measurement.hydration_percent < 50:
                crisis_indicators += 1
                conditions.append(f"Déshydratation {measurement.hydration_percent}%")

            # Score de crise ≥ 3 = alerte combinée
            if crisis_indicators >= 3:
                alert = AlertRecord(
                    alert_id=None,
                    patient_id=patient.patient_id,
                    alert_type="sickle_crisis_suspected",
                    severity="critical",
                    title="🚨 CRISE DRÉPANOCYTAIRE SUSPECTÉE",
                    message=f"Combinaison de signes évocateurs de crise (score: {crisis_indicators}/6)",
                    vitals_snapshot=vitals,
                    trigger_conditions=conditions,
                    suggested_actions=[
                        "Prise en charge URGENTE crise drépanocytaire",
                        "Antalgie morphinique si besoin",
                        "Hydratation IV immédiate",
                        "Oxygénothérapie si SpO2 < 95%",
                        "Rechercher facteur déclenchant",
                        "Contact hématologie/urgences",
                        "Surveillance neurologique",
                        "Prévention complications"
                    ],
                    created_at=timestamp,
                    ack_deadline=timestamp + timedelta(minutes=3),
                    escalation_level=1
                )

                if self._should_trigger_alert(alert, patient):
                    alerts.append(alert)

        return alerts

    def _should_trigger_alert(self, alert: AlertRecord, patient: PatientProfile) -> bool:
        """Détermine si une alerte doit être déclenchée (évite spam)"""
        alert_key = f"{patient.patient_id}_{alert.alert_type}"
        current_time = alert.created_at

        # Vérifier historique récent
        if alert_key in self.alert_history:
            last_alert_time = self.alert_history[alert_key]
            time_since_last = (current_time - last_alert_time).total_seconds()

            # Cooldown en cours
            if time_since_last < self.cooldown_period:
                return False

            # Cooldown réduit pour alertes critiques
            if alert.severity == "critical" and time_since_last < 60:
                return False

        # Enregistrer cette alerte
        self.alert_history[alert_key] = current_time

        # Nettoyer historique ancien (garde seulement dernière heure)
        cutoff_time = current_time - timedelta(hours=1)
        self.alert_history = {
            k: v for k, v in self.alert_history.items()
            if v > cutoff_time
        }

        return True

# =====================================================
# SUITE DANS LE PROCHAIN FICHIER...
# =====================================================
