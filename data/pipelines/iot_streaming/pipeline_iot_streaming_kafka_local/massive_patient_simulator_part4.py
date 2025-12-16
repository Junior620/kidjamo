# =====================================================
# SIMULATEUR MASSIF - PARTIE 4 : CONTRÔLEUR PRINCIPAL
# =====================================================

# =====================================================
# WORKER DE SIMULATION PATIENT
# =====================================================

class PatientSimulationWorker:
    """Worker thread pour simulation individuelle d'un patient"""

    def __init__(self, patient: PatientProfile, db_manager: DatabaseManager,
                 alert_engine: AlertEngine, notification_service: NotificationService,
                 physiological_simulator: PhysiologicalSimulator):
        self.patient = patient
        self.db_manager = db_manager
        self.alert_engine = alert_engine
        self.notification_service = notification_service
        self.physiological_simulator = physiological_simulator
        self.running = False
        self.thread = None
        self.measurement_count = 0
        self.alert_count = 0
        self.last_measurement_time = None

    def start(self):
        """Démarre la simulation du patient"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.thread.start()
            logger.info(f"🟢 Simulation démarrée pour {self.patient.first_name} {self.patient.last_name}")

    def stop(self):
        """Arrête la simulation du patient"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info(f"🔴 Simulation arrêtée pour {self.patient.first_name} {self.patient.last_name}")

    def _simulation_loop(self):
        """Boucle principale de simulation pour ce patient"""
        try:
            while self.running:
                start_time = time.time()

                # Génération mesure
                timestamp = datetime.now()
                measurement = self.physiological_simulator.generate_measurement(self.patient, timestamp)

                # Sauvegarde en base
                self.db_manager.add_measurement(measurement)
                self.measurement_count += 1
                self.last_measurement_time = timestamp

                # Analyse alertes
                alerts = self.alert_engine.analyze_measurement(measurement, self.patient)

                if alerts:
                    for alert in alerts:
                        # Sauvegarde alerte
                        self.db_manager.add_alert(alert)
                        self.alert_count += 1

                        # Notification asynchrone
                        asyncio.run_coroutine_threadsafe(
                            self.notification_service.send_alert_notification(alert, self.patient),
                            asyncio.new_event_loop()
                        )

                        logger.warning(f"🚨 {alert.severity.upper()}: {alert.title} - {self.patient.first_name} {self.patient.last_name}")

                # Mise à jour évolution patient
                self._update_patient_evolution()

                # Logging périodique
                if self.measurement_count % 100 == 0:
                    logger.info(f"📊 {self.patient.first_name} {self.patient.last_name}: {self.measurement_count} mesures, {self.alert_count} alertes")

                # Respect timing 5 secondes
                elapsed = time.time() - start_time
                sleep_time = max(0, 5.0 - elapsed)
                time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"❌ Erreur simulation {self.patient.first_name} {self.patient.last_name}: {e}")
            self.running = False

    def _update_patient_evolution(self):
        """Met à jour l'évolution de l'état du patient"""
        # Évolution crise drépanocytaire
        if self.patient.is_in_crisis:
            crisis_duration = (datetime.now() - self.patient.crisis_start_time).total_seconds() / 3600

            # Crise dure généralement 4-72h
            if crisis_duration > random.uniform(4, 72):
                if random.random() < 0.1:  # 10% chance résolution par cycle
                    self.patient.is_in_crisis = False
                    self.patient.crisis_start_time = None
                    self.patient.pain_level = random.randint(0, 3)
                    logger.info(f"✅ Résolution crise pour {self.patient.first_name} {self.patient.last_name}")

        else:
            # Déclenchement nouvelle crise selon génotype
            genotype_info = GENOTYPES[self.patient.genotype]
            crisis_probability = genotype_info["crisis_frequency"] / (24 * 720)  # Probabilité par cycle 5sec

            if random.random() < crisis_probability:
                self.patient.is_in_crisis = True
                self.patient.crisis_start_time = datetime.now()
                self.patient.pain_level = random.randint(5, 9)
                logger.warning(f"⚠️  Début crise pour {self.patient.first_name} {self.patient.last_name}")

    def get_status(self) -> Dict:
        """Retourne le statut actuel du worker"""
        return {
            'patient_id': self.patient.patient_id,
            'patient_name': f"{self.patient.first_name} {self.patient.last_name}",
            'genotype': self.patient.genotype,
            'age': self.patient.age,
            'running': self.running,
            'measurement_count': self.measurement_count,
            'alert_count': self.alert_count,
            'last_measurement': self.last_measurement_time.isoformat() if self.last_measurement_time else None,
            'in_crisis': self.patient.is_in_crisis,
            'pain_level': self.patient.pain_level
        }

# =====================================================
# CONTRÔLEUR PRINCIPAL DE SIMULATION
# =====================================================

class MassivePatientSimulationController:
    """Contrôleur principal pour simulation massive de 50+ patients"""

    def __init__(self, patient_count: int = 50):
        self.patient_count = patient_count
        self.patients = []
        self.workers = []
        self.running = False
        self.start_time = None
        self.stats = {
            'total_measurements': 0,
            'total_alerts': 0,
            'patients_in_crisis': 0,
            'critical_alerts': 0,
            'uptime_hours': 0
        }

        # Initialisation services
        logger.info("🔧 Initialisation services...")
        self.notification_service = NotificationService()
        self.db_manager = DatabaseManager()
        self.alert_engine = AlertEngine(self.notification_service)
        self.patient_generator = PatientGenerator()
        self.physiological_simulator = PhysiologicalSimulator()

        # Monitoring thread
        self.monitoring_thread = None
        self.metrics_collection_interval = 60  # 1 minute

    def initialize_patients(self):
        """Initialise le lot de patients et les insère en base"""
        logger.info(f"👥 Génération de {self.patient_count} patients...")

        # Génération patients
        self.patients = self.patient_generator.generate_patient_batch(self.patient_count)

        # Insertion en base
        logger.info("💾 Insertion patients en base de données...")
        for patient in self.patients:
            self.db_manager.add_patient(patient)

        # Flush immédiat
        self.db_manager.flush_patients()

        logger.info(f"✅ {len(self.patients)} patients initialisés et sauvegardés")

        # Affichage répartition
        self._display_patient_distribution()

    def _display_patient_distribution(self):
        """Affiche la répartition des patients générés"""
        genotype_counts = {}
        age_groups = {'0-12': 0, '13-17': 0, '18-35': 0, '36-50': 0, '51+': 0}
        gender_counts = {'M': 0, 'F': 0}
        crisis_count = 0

        for patient in self.patients:
            # Génotypes
            genotype_counts[patient.genotype] = genotype_counts.get(patient.genotype, 0) + 1

            # Groupes d'âge
            if patient.age <= 12:
                age_groups['0-12'] += 1
            elif patient.age <= 17:
                age_groups['13-17'] += 1
            elif patient.age <= 35:
                age_groups['18-35'] += 1
            elif patient.age <= 50:
                age_groups['36-50'] += 1
            else:
                age_groups['51+'] += 1

            # Genre
            gender_counts[patient.gender] += 1

            # Crises en cours
            if patient.is_in_crisis:
                crisis_count += 1

        logger.info("📊 RÉPARTITION DES PATIENTS GÉNÉRÉS:")
        logger.info(f"   Génotypes: {genotype_counts}")
        logger.info(f"   Âges: {age_groups}")
        logger.info(f"   Genre: {gender_counts}")
        logger.info(f"   En crise au démarrage: {crisis_count}/{len(self.patients)}")

    def start_simulation(self):
        """Démarre la simulation massive"""
        if self.running:
            logger.warning("⚠️  Simulation déjà en cours")
            return

        if not self.patients:
            logger.error("❌ Aucun patient initialisé. Appelez initialize_patients() d'abord")
            return

        logger.info(f"🚀 DÉMARRAGE SIMULATION MASSIVE - {len(self.patients)} PATIENTS")
        logger.info("   ⏱️  Fréquence: mesure toutes les 5 secondes")
        logger.info("   ⏱️  Durée prévue: 24h continues")
        logger.info("   📊 Données attendues: ~17,280 mesures/patient sur 24h")

        self.running = True
        self.start_time = datetime.now()

        # Création workers pour chaque patient
        logger.info("🔧 Création workers de simulation...")
        for patient in self.patients:
            worker = PatientSimulationWorker(
                patient=patient,
                db_manager=self.db_manager,
                alert_engine=self.alert_engine,
                notification_service=self.notification_service,
                physiological_simulator=self.physiological_simulator
            )
            self.workers.append(worker)

        # Démarrage échelonné pour éviter pic initial
        logger.info("▶️  Démarrage échelonné des workers...")
        for i, worker in enumerate(self.workers):
            worker.start()
            if i % 10 == 9:  # Pause tous les 10 workers
                time.sleep(1)

        # Démarrage monitoring
        self._start_monitoring()

        logger.info("✅ SIMULATION DÉMARRÉE AVEC SUCCÈS")
        logger.info("   🛑 Arrêt: Ctrl+C ou appel stop_simulation()")
        logger.info("   📊 Monitoring: logs toutes les minutes")

    def stop_simulation(self):
        """Arrête la simulation"""
        if not self.running:
            logger.warning("⚠️  Simulation non active")
            return

        logger.info("🛑 ARRÊT EN COURS...")
        self.running = False

        # Arrêt monitoring
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)

        # Arrêt workers
        logger.info("🔧 Arrêt des workers...")
        for worker in self.workers:
            worker.stop()

        # Flush final base de données
        logger.info("💾 Flush final base de données...")
        self.db_manager.flush_all()
        self.db_manager.close()

        # Statistiques finales
        self._display_final_stats()

        logger.info("✅ SIMULATION ARRÊTÉE")

    def _start_monitoring(self):
        """Démarre le thread de monitoring"""
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def _monitoring_loop(self):
        """Boucle de monitoring et statistiques"""
        while self.running:
            try:
                time.sleep(self.metrics_collection_interval)
                self._collect_and_display_metrics()
            except Exception as e:
                logger.error(f"❌ Erreur monitoring: {e}")

    def _collect_and_display_metrics(self):
        """Collecte et affiche les métriques en temps réel"""
        if not self.running:
            return

        # Calcul statistiques
        total_measurements = sum(w.measurement_count for w in self.workers)
        total_alerts = sum(w.alert_count for w in self.workers)
        active_workers = sum(1 for w in self.workers if w.running)
        patients_in_crisis = sum(1 for w in self.workers if w.patient.is_in_crisis)

        # Uptime
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600

        # Taux de mesures
        measurement_rate = total_measurements / uptime if uptime > 0 else 0
        expected_rate = len(self.patients) * 720  # 720 mesures/patient/heure (toutes les 5sec)
        efficiency = (measurement_rate / expected_rate * 100) if expected_rate > 0 else 0

        # Mise à jour stats
        self.stats.update({
            'total_measurements': total_measurements,
            'total_alerts': total_alerts,
            'patients_in_crisis': patients_in_crisis,
            'uptime_hours': round(uptime, 1),
            'active_workers': active_workers,
            'measurement_rate': round(measurement_rate, 1),
            'efficiency_percent': round(efficiency, 1)
        })

        # Affichage
        logger.info("📊 MÉTRIQUES TEMPS RÉEL:")
        logger.info(f"   ⏱️  Uptime: {self.stats['uptime_hours']}h")
        logger.info(f"   👥 Workers actifs: {active_workers}/{len(self.workers)}")
        logger.info(f"   📈 Mesures totales: {total_measurements:,}")
        logger.info(f"   🚨 Alertes totales: {total_alerts}")
        logger.info(f"   ⚡ Taux mesures: {measurement_rate:.1f}/h (attendu: {expected_rate:.0f}/h)")
        logger.info(f"   📊 Efficacité: {efficiency:.1f}%")
        logger.info(f"   🔥 Patients en crise: {patients_in_crisis}/{len(self.patients)}")

        # Alertes si problèmes
        if efficiency < 90:
            logger.warning(f"⚠️  Efficacité faible: {efficiency:.1f}% - Vérifier performances")

        if active_workers < len(self.workers):
            failed_workers = len(self.workers) - active_workers
            logger.warning(f"⚠️  {failed_workers} workers arrêtés - Vérifier erreurs")

    def _display_final_stats(self):
        """Affiche les statistiques finales"""
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        total_measurements = sum(w.measurement_count for w in self.workers)
        total_alerts = sum(w.alert_count for w in self.workers)

        logger.info("📊 STATISTIQUES FINALES:")
        logger.info(f"   ⏱️  Durée totale: {uptime:.2f}h")
        logger.info(f"   👥 Patients simulés: {len(self.patients)}")
        logger.info(f"   📈 Mesures générées: {total_measurements:,}")
        logger.info(f"   🚨 Alertes déclenchées: {total_alerts}")
        logger.info(f"   📊 Moyenne mesures/patient: {total_measurements/len(self.patients):.0f}")
        logger.info(f"   📊 Moyenne alertes/patient: {total_alerts/len(self.patients):.1f}")

        # Détail par type d'alerte si possible
        # (nécessiterait tracking plus détaillé par type)

    def get_patient_status(self) -> List[Dict]:
        """Retourne le statut de tous les patients"""
        return [worker.get_status() for worker in self.workers]

    def get_system_metrics(self) -> Dict:
        """Retourne les métriques système"""
        return self.stats.copy()

    def force_crisis_simulation(self, patient_count: int = 5):
        """Force déclenchement de crises pour tests"""
        available_patients = [w.patient for w in self.workers if not w.patient.is_in_crisis]

        if len(available_patients) < patient_count:
            patient_count = len(available_patients)

        selected_patients = random.sample(available_patients, patient_count)

        for patient in selected_patients:
            patient.is_in_crisis = True
            patient.crisis_start_time = datetime.now()
            patient.pain_level = random.randint(6, 9)
            logger.info(f"🔥 Crise forcée: {patient.first_name} {patient.last_name}")

        logger.info(f"⚡ {patient_count} crises déclenchées pour test")

# =====================================================
# INTERFACE LIGNE DE COMMANDE
# =====================================================

def main():
    """Interface principale du simulateur"""
    import signal
    import sys

    # Configuration par défaut
    DEFAULT_PATIENT_COUNT = 50

    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description='Simulateur Massif IoT Patients - KIDJAMO')
    parser.add_argument('--patients', '-p', type=int, default=DEFAULT_PATIENT_COUNT,
                        help=f'Nombre de patients à simuler (défaut: {DEFAULT_PATIENT_COUNT})')
    parser.add_argument('--duration', '-d', type=int, default=24,
                        help='Durée simulation en heures (défaut: 24h)')
    parser.add_argument('--test-crisis', action='store_true',
                        help='Déclencher quelques crises au démarrage pour test')
    parser.add_argument('--db-host', default='localhost',
                        help='Host PostgreSQL (défaut: localhost)')
    parser.add_argument('--db-port', default='5432',
                        help='Port PostgreSQL (défaut: 5432)')
    parser.add_argument('--db-name', default='kidjamo',
                        help='Nom base de données (défaut: kidjamo)')
    args = parser.parse_args()

    # Override configuration DB si spécifiée
    if args.db_host != 'localhost':
        DB_CONFIG['host'] = args.db_host
    if args.db_port != '5432':
        DB_CONFIG['port'] = args.db_port
    if args.db_name != 'kidjamo':
        DB_CONFIG['database'] = args.db_name

    print("🏥 SIMULATEUR MASSIF IoT PATIENTS - KIDJAMO")
    print("=" * 50)
    print(f"📊 Configuration:")
    print(f"   👥 Patients: {args.patients}")
    print(f"   ⏱️  Durée: {args.duration}h")
    print(f"   💾 Base: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"   📱 SMS: {'✅' if TWILIO_CONFIG['account_sid'] else '❌'}")
    print(f"   📧 Email: {'✅' if EMAIL_CONFIG['username'] else '❌'}")
    print()

    # Initialisation contrôleur
    controller = MassivePatientSimulationController(patient_count=args.patients)

    # Gestionnaire signal pour arrêt propre
    def signal_handler(sig, frame):
        print("\n🛑 Signal d'arrêt reçu (Ctrl+C)")
        controller.stop_simulation()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialisation patients
        controller.initialize_patients()

        # Test crise si demandé
        if args.test_crisis:
            print("🔥 Déclenchement crises de test...")
            controller.force_crisis_simulation(3)

        # Démarrage simulation
        controller.start_simulation()

        # Boucle principale (attente)
        if args.duration > 0:
            duration_seconds = args.duration * 3600
            print(f"⏱️  Simulation programmée pour {args.duration}h. Arrêt automatique prévu.")
            time.sleep(duration_seconds)
            print("⏰ Durée atteinte - Arrêt automatique")
            controller.stop_simulation()
        else:
            # Mode infini
            print("♾️  Mode simulation infinie. Arrêt: Ctrl+C")
            while True:
                time.sleep(60)

    except KeyboardInterrupt:
        print("\n🛑 Interruption clavier")
        controller.stop_simulation()

    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        controller.stop_simulation()
        raise

# =====================================================
# SCRIPT D'EXEMPLES ET TESTS
# =====================================================

def run_quick_test():
    """Test rapide avec 5 patients pendant 10 minutes"""
    print("🧪 TEST RAPIDE - 5 patients, 10 minutes")

    controller = MassivePatientSimulationController(patient_count=5)

    try:
        controller.initialize_patients()
        controller.force_crisis_simulation(1)  # 1 crise pour test alertes
        controller.start_simulation()

        # Attendre 10 minutes
        time.sleep(600)

        controller.stop_simulation()

    except KeyboardInterrupt:
        print("🛑 Test interrompu")
        controller.stop_simulation()

def run_stress_test():
    """Test stress avec 100 patients"""
    print("💪 TEST STRESS - 100 patients")

    controller = MassivePatientSimulationController(patient_count=100)

    try:
        controller.initialize_patients()
        controller.start_simulation()

        # Surveillance 1h
        time.sleep(3600)

        controller.stop_simulation()

    except KeyboardInterrupt:
        print("🛑 Test stress interrompu")
        controller.stop_simulation()

if __name__ == "__main__":
    main()
