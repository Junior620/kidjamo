# =====================================================
# SIMULATEUR MASSIF - PARTIE 3 : LOGIQUE PRINCIPALE
# =====================================================

# =====================================================
# GÉNÉRATEUR DE PROFILS PATIENTS
# =====================================================

class PatientGenerator:
    """Générateur de profils patients réalistes avec diversité médicale"""

    def __init__(self):
        self.used_names = set()
        self.french_first_names = [
            "Gabriel", "Raphaël", "Léo", "Louis", "Lucas", "Adam", "Arthur", "Hugo", "Jules", "Maël",
            "Emma", "Jade", "Louise", "Alice", "Chloé", "Lina", "Rose", "Anna", "Mila", "Léa",
            "Ibrahim", "Mohamed", "Youssef", "Omar", "Hassan", "Aminata", "Fatou", "Aïssatou", "Mariam", "Khadija",
            "Jean-Baptiste", "Marie-Claire", "Pierre-Louis", "Anne-Sophie", "François", "Catherine", "Nicolas", "Isabelle"
        ]

        self.french_last_names = [
            "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
            "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
            "Morel", "Girard", "André", "Lefevre", "Mercier", "Dupont", "Lambert", "Bonnet", "François", "Martinez",
            "Diallo", "Traore", "Kone", "Coulibaly", "Ouattara", "Camara", "Toure", "Keita", "Sankare", "Sidibe"
        ]

    def generate_patient_batch(self, count: int) -> List[PatientProfile]:
        """Génère un lot de patients avec diversité réaliste"""
        patients = []

        for i in range(count):
            patient = self._generate_single_patient(i)
            patients.append(patient)

        logger.info(f"✅ Généré {len(patients)} profils patients diversifiés")
        return patients

    def _generate_single_patient(self, index: int) -> PatientProfile:
        """Génère un profil patient individuel"""

        # Identifiants uniques
        patient_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())

        # Nom unique
        first_name, last_name = self._generate_unique_name()

        # Caractéristiques démographiques
        age = random.randint(5, 65)  # Large gamme d'âges
        gender = random.choice(['M', 'F'])

        # Distribution réaliste des génotypes drépanocytaires
        genotype = self._select_genotype_weighted()
        genotype_info = GENOTYPES[genotype]

        # Morphologie selon âge et genre
        if age < 18:
            weight_kg = round(random.uniform(15 + age * 2, 25 + age * 2.5), 1)
            height_cm = round(random.uniform(80 + age * 4, 100 + age * 4.5), 1)
        else:
            if gender == 'M':
                weight_kg = round(random.uniform(60, 95), 1)
                height_cm = round(random.uniform(165, 190), 1)
            else:
                weight_kg = round(random.uniform(45, 80), 1)
                height_cm = round(random.uniform(155, 175), 1)

        # Paramètres physiologiques de base selon âge et génotype
        if age < 12:
            base_hr_min, base_hr_max = 80, 120
            base_rr_min, base_rr_max = 20, 30
        elif age < 18:
            base_hr_min, base_hr_max = 70, 100
            base_rr_min, base_rr_max = 16, 24
        else:
            base_hr_min, base_hr_max = 60, 90
            base_rr_min, base_rr_max = 12, 20

        base_heart_rate = random.randint(base_hr_min, base_hr_max)
        base_respiratory_rate = random.randint(base_rr_min, base_rr_max)
        base_spo2_range = genotype_info["base_spo2_range"]
        base_temperature = round(random.uniform(36.2, 37.1), 1)
        base_hydration = round(random.uniform(65, 85), 1)

        # État médical initial
        is_in_crisis = random.random() < (genotype_info["crisis_frequency"] / 10)  # Probabilité réduite au démarrage
        pain_level = random.randint(0, 3) if not is_in_crisis else random.randint(4, 8)
        infection_risk = genotype_info["infection_risk"]

        patient = PatientProfile(
            patient_id=patient_id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            age=age,
            gender=gender,
            genotype=genotype,
            weight_kg=weight_kg,
            height_cm=height_cm,
            device_id=device_id,
            base_heart_rate=base_heart_rate,
            base_spo2_range=base_spo2_range,
            base_temperature=base_temperature,
            base_respiratory_rate=base_respiratory_rate,
            base_hydration=base_hydration,
            is_in_crisis=is_in_crisis,
            crisis_start_time=datetime.now() if is_in_crisis else None,
            pain_level=pain_level,
            infection_risk_factor=infection_risk
        )

        logger.debug(f"👤 Patient généré: {first_name} {last_name}, {age}ans, {genotype}, {'En crise' if is_in_crisis else 'Stable'}")
        return patient

    def _generate_unique_name(self) -> Tuple[str, str]:
        """Génère un nom unique non déjà utilisé"""
        max_attempts = 100

        for _ in range(max_attempts):
            first_name = random.choice(self.french_first_names)
            last_name = random.choice(self.french_last_names)
            full_name = f"{first_name} {last_name}"

            if full_name not in self.used_names:
                self.used_names.add(full_name)
                return first_name, last_name

        # Fallback avec suffixe numérique
        first_name = random.choice(self.french_first_names)
        last_name = random.choice(self.french_last_names)
        suffix = len(self.used_names)
        full_name = f"{first_name} {last_name}-{suffix}"
        self.used_names.add(full_name)

        return first_name, f"{last_name}-{suffix}"

    def _select_genotype_weighted(self) -> str:
        """Sélection pondérée des génotypes selon prévalence réelle"""
        # Distribution réaliste en population drépanocytaire
        weights = {
            "SS": 0.45,   # Forme la plus sévère - 45%
            "SC": 0.30,   # Forme intermédiaire - 30%
            "AS": 0.20,   # Porteurs sains - 20%
            "Sβ0": 0.05   # Forme rare - 5%
        }

        genotypes = list(weights.keys())
        probabilities = list(weights.values())

        return random.choices(genotypes, weights=probabilities)[0]

# =====================================================
# SIMULATEUR DE MESURES PHYSIOLOGIQUES
# =====================================================

class PhysiologicalSimulator:
    """Simulateur de mesures physiologiques avec cycles circadiens et pathologies"""

    def __init__(self):
        self.noise_generators = {}
        self.circadian_cache = {}

    def generate_measurement(self, patient: PatientProfile, timestamp: datetime) -> MeasurementRecord:
        """Génère une mesure physiologique complète pour un patient"""

        # Facteurs temporels et environnementaux
        circadian_factor = self._calculate_circadian_factor(timestamp)
        ambient_temp = self._calculate_ambient_temperature(timestamp)
        activity_level = self._calculate_activity_level(patient, timestamp)

        # Variables physiologiques principales
        heart_rate = self._simulate_heart_rate(patient, circadian_factor, activity_level)
        spo2 = self._simulate_spo2(patient, circadian_factor, activity_level)
        temperature = self._simulate_body_temperature(patient, circadian_factor, ambient_temp)
        respiratory_rate = self._simulate_respiratory_rate(patient, circadian_factor, activity_level)
        hydration = self._simulate_hydration(patient, circadian_factor, ambient_temp)

        # Variables contextuelles
        pain_scale = self._simulate_pain(patient, circadian_factor)
        battery_percent = self._simulate_battery_level(patient, timestamp)
        signal_quality = self._simulate_signal_quality(patient, activity_level)
        heat_index = self._calculate_heat_index(temperature, ambient_temp)

        # Qualité des données
        quality_flag = self._assess_data_quality(signal_quality, battery_percent, activity_level)

        measurement = MeasurementRecord(
            measurement_id=None,
            patient_id=patient.patient_id,
            device_id=patient.device_id,
            recorded_at=timestamp,
            received_at=timestamp + timedelta(seconds=random.uniform(0.1, 2.0)),
            heart_rate_bpm=heart_rate,
            respiratory_rate_min=respiratory_rate,
            spo2_percent=spo2,
            temperature_celsius=temperature,
            ambient_temp_celsius=ambient_temp,
            hydration_percent=hydration,
            activity_level=activity_level,
            heat_index_celsius=heat_index,
            pain_scale=pain_scale,
            battery_percent=battery_percent,
            signal_quality=signal_quality,
            quality_flag=quality_flag
        )

        # Mise à jour état patient
        patient.last_measurement_time = timestamp

        return measurement

    def _calculate_circadian_factor(self, timestamp: datetime) -> float:
        """Calcule facteur circadien (0.8-1.2) selon heure de la journée"""
        hour = timestamp.hour + timestamp.minute / 60.0

        # Minimum vers 4h du matin, maximum vers 16h
        # Fonction sinusoïdale décalée
        phase = (hour - 4) * 2 * math.pi / 24
        circadian_raw = 0.5 * math.sin(phase) + 0.5

        # Normalisation 0.8 à 1.2
        return 0.8 + 0.4 * circadian_raw

    def _calculate_ambient_temperature(self, timestamp: datetime) -> float:
        """Calcule température ambiante avec variation journalière"""
        hour = timestamp.hour + timestamp.minute / 60.0

        # Base saisonnière (simulation été tropical)
        base_temp = 28.0

        # Variation journalière (-4°C à +8°C)
        daily_variation = 6 * math.sin((hour - 6) * 2 * math.pi / 24)

        # Bruit aléatoire
        noise = random.uniform(-1.5, 1.5)

        ambient = base_temp + daily_variation + noise
        return round(max(22.0, min(42.0, ambient)), 1)

    def _calculate_activity_level(self, patient: PatientProfile, timestamp: datetime) -> int:
        """Calcule niveau d'activité (0-10) selon heure et état patient"""
        hour = timestamp.hour

        # Pattern d'activité normale
        if 6 <= hour <= 8:  # Réveil
            base_activity = 3
        elif 9 <= hour <= 11:  # Matinée active
            base_activity = 5
        elif 12 <= hour <= 14:  # Déjeuner/repos
            base_activity = 2
        elif 15 <= hour <= 18:  # Après-midi
            base_activity = 4
        elif 19 <= hour <= 21:  # Soirée
            base_activity = 3
        else:  # Nuit
            base_activity = 1

        # Modifications selon état patient
        if patient.is_in_crisis:
            base_activity = max(0, base_activity - 3)

        if patient.pain_level >= 6:
            base_activity = max(0, base_activity - 2)

        # Variation aléatoire
        activity = base_activity + random.randint(-1, 2)
        return max(0, min(10, activity))

    def _simulate_heart_rate(self, patient: PatientProfile, circadian_factor: float, activity_level: int) -> int:
        """Simule fréquence cardiaque avec facteurs physiologiques"""
        base_hr = patient.base_heart_rate

        # Facteur circadien
        hr = base_hr * circadian_factor

        # Facteur activité
        activity_factor = 1.0 + (activity_level * 0.1)
        hr *= activity_factor

        # Facteur douleur
        if patient.pain_level >= 6:
            hr *= 1.2
        elif patient.pain_level >= 3:
            hr *= 1.1

        # Facteur crise drépanocytaire
        if patient.is_in_crisis:
            hr *= 1.3

        # Facteur température corporelle (si fièvre)
        if hasattr(patient, '_current_temp') and patient._current_temp > 38.0:
            fever_factor = 1.0 + (patient._current_temp - 37.0) * 0.1
            hr *= fever_factor

        # Bruit physiologique
        noise = random.uniform(-5, 5)
        hr += noise

        # Limites physiologiques
        if patient.age < 18:
            hr = max(60, min(200, hr))
        else:
            hr = max(40, min(180, hr))

        return int(round(hr))

    def _simulate_spo2(self, patient: PatientProfile, circadian_factor: float, activity_level: int) -> float:
        """Simule SpO2 avec facteurs pathologiques"""
        min_spo2, max_spo2 = patient.base_spo2_range
        base_spo2 = random.uniform(min_spo2, max_spo2)

        # Facteur circadien léger
        spo2 = base_spo2 * (0.98 + 0.02 * circadian_factor)

        # Facteur activité (légère baisse si activité intense)
        if activity_level >= 7:
            spo2 *= 0.98
        elif activity_level >= 5:
            spo2 *= 0.99

        # Facteur crise drépanocytaire (impact majeur)
        if patient.is_in_crisis:
            crisis_severity = random.uniform(0.85, 0.95)
            spo2 *= crisis_severity

        # Facteur douleur (stress respiratoire)
        if patient.pain_level >= 7:
            spo2 *= 0.97

        # Simulation désaturation sporadique (génotype SS)
        if patient.genotype == "SS" and random.random() < 0.05:
            spo2 *= random.uniform(0.90, 0.96)

        # Bruit de mesure
        noise = random.uniform(-0.5, 0.5)
        spo2 += noise

        # Limites physiologiques
        spo2 = max(70.0, min(100.0, spo2))

        return round(spo2, 1)

    def _simulate_body_temperature(self, patient: PatientProfile, circadian_factor: float, ambient_temp: float) -> float:
        """Simule température corporelle avec cycles et pathologies"""
        base_temp = patient.base_temperature

        # Facteur circadien (température plus basse le matin)
        temp = base_temp + (circadian_factor - 1.0) * 0.3

        # Facteur crise drépanocytaire (risque infectieux)
        if patient.is_in_crisis:
            if random.random() < 0.3:  # 30% chance fièvre en crise
                fever_intensity = random.uniform(1.0, 2.5)
                temp += fever_intensity

        # Simulation infection (selon facteur risque génotype)
        infection_risk = patient.infection_risk_factor
        if random.random() < (infection_risk * 0.01):  # Probabilité quotidienne ajustée
            fever_intensity = random.uniform(0.8, 3.0)
            temp += fever_intensity

        # Facteur température ambiante (légère influence)
        if ambient_temp > 35.0:
            temp += (ambient_temp - 35.0) * 0.05

        # Bruit physiologique
        noise = random.uniform(-0.2, 0.2)
        temp += noise

        # Cache pour usage dans autres simulations
        patient._current_temp = temp

        # Limites physiologiques
        temp = max(33.0, min(42.0, temp))

        return round(temp, 1)

    def _simulate_respiratory_rate(self, patient: PatientProfile, circadian_factor: float, activity_level: int) -> int:
        """Simule fréquence respiratoire"""
        base_rr = patient.base_respiratory_rate

        # Facteur circadien léger
        rr = base_rr * (0.95 + 0.1 * circadian_factor)

        # Facteur activité
        activity_factor = 1.0 + (activity_level * 0.05)
        rr *= activity_factor

        # Facteur douleur/stress
        if patient.pain_level >= 6:
            rr *= 1.2
        elif patient.pain_level >= 3:
            rr *= 1.1

        # Facteur crise (détresse respiratoire)
        if patient.is_in_crisis:
            rr *= 1.25

        # Facteur température (tachypnée si fièvre)
        if hasattr(patient, '_current_temp') and patient._current_temp > 38.0:
            fever_factor = 1.0 + (patient._current_temp - 37.0) * 0.08
            rr *= fever_factor

        # Bruit physiologique
        noise = random.uniform(-2, 2)
        rr += noise

        # Limites physiologiques
        if patient.age < 18:
            rr = max(10, min(50, rr))
        else:
            rr = max(8, min(40, rr))

        return int(round(rr))

    def _simulate_hydration(self, patient: PatientProfile, circadian_factor: float, ambient_temp: float) -> float:
        """Simule niveau d'hydratation"""
        base_hydration = patient.base_hydration

        # Dégradation progressive dans la journée
        hour = datetime.now().hour
        dehydration_factor = 1.0 - (hour * 0.01)  # -1% par heure

        hydration = base_hydration * dehydration_factor

        # Facteur température ambiante
        if ambient_temp > 32.0:
            heat_dehydration = (ambient_temp - 32.0) * 0.5
            hydration -= heat_dehydration

        # Facteur crise (déshydratation accélérée)
        if patient.is_in_crisis:
            hydration *= 0.85

        # Facteur fièvre
        if hasattr(patient, '_current_temp') and patient._current_temp > 38.0:
            fever_dehydration = (patient._current_temp - 37.0) * 2.0
            hydration -= fever_dehydration

        # Récupération nocturne partielle
        if 22 <= hour or hour <= 6:
            hydration += 2.0

        # Bruit de mesure
        noise = random.uniform(-2, 2)
        hydration += noise

        # Limites physiologiques
        hydration = max(20.0, min(100.0, hydration))

        return round(hydration, 1)

    def _simulate_pain(self, patient: PatientProfile, circadian_factor: float) -> int:
        """Simule échelle de douleur"""
        base_pain = patient.pain_level

        # Facteur circadien (douleur plus intense la nuit)
        if circadian_factor < 0.9:  # Nuit/petit matin
            pain_modifier = random.randint(0, 2)
        else:
            pain_modifier = random.randint(-1, 1)

        # Évolution de la crise
        if patient.is_in_crisis:
            # Crise peut s'intensifier ou diminuer lentement
            if random.random() < 0.1:  # 10% chance évolution
                evolution = random.choice([-1, -1, 0, 1, 2])  # Biais vers amélioration
                base_pain = max(0, min(10, base_pain + evolution))
                patient.pain_level = base_pain

        current_pain = base_pain + pain_modifier

        # Limites échelle
        return max(0, min(10, current_pain))

    def _simulate_battery_level(self, patient: PatientProfile, timestamp: datetime) -> int:
        """Simule niveau batterie dispositif"""
        # Dégradation réaliste batterie IoT
        hours_since_start = (timestamp - patient.created_at).total_seconds() / 3600

        # Dégradation 2-4% par heure selon utilisation
        usage_factor = random.uniform(2.0, 4.0)
        battery_loss = hours_since_start * usage_factor

        initial_battery = random.randint(85, 100)  # Charge initiale
        current_battery = initial_battery - battery_loss

        # Simulation rechargement périodique
        if current_battery < 20:
            if random.random() < 0.3:  # 30% chance rechargement
                current_battery = random.randint(80, 100)

        return max(0, min(100, int(current_battery)))

    def _simulate_signal_quality(self, patient: PatientProfile, activity_level: int) -> int:
        """Simule qualité signal capteur"""
        base_quality = random.randint(75, 95)

        # Dégradation selon activité
        activity_penalty = activity_level * 3
        quality = base_quality - activity_penalty

        # Facteur mouvement/positionnement
        if activity_level >= 7:
            movement_noise = random.randint(-15, -5)
            quality += movement_noise

        # Facteur environnemental aléatoire
        environmental_factor = random.randint(-10, 5)
        quality += environmental_factor

        return max(10, min(100, quality))

    def _calculate_heat_index(self, body_temp: float, ambient_temp: float) -> float:
        """Calcule index de chaleur corporelle"""
        # Formule simplifiée index de chaleur
        temp_diff = body_temp - 37.0
        ambient_factor = max(0, ambient_temp - 25.0) * 0.1

        heat_index = body_temp + ambient_factor + (temp_diff * 0.5)

        return round(heat_index, 1)

    def _assess_data_quality(self, signal_quality: int, battery_level: int, activity_level: int) -> str:
        """Évalue qualité globale des données"""
        if signal_quality < 30 or battery_level < 5:
            return 'poor'
        elif signal_quality < 50 or battery_level < 15 or activity_level >= 8:
            return 'fair'
        elif signal_quality < 70 or activity_level >= 6:
            return 'good'
        else:
            return 'ok'

# =====================================================
# SUITE DANS LE PROCHAIN FICHIER...
# =====================================================
