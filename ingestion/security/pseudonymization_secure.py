import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
from cryptography.fernet import Fernet
import base64

# Chargement sécurisé des variables d'environnement
from dotenv import load_dotenv
load_dotenv()

class SecurePseudonymizer:
    """
    Gestionnaire sécurisé pour la pseudonymisation et le chiffrement des données patients.
    Remplace le salt hardcodé par une gestion sécurisée via .env.
    """

    def __init__(self, config_path: str = None):
        # ✅ CORRECTION CRITIQUE: Éliminer le salt hardcodé
        self.salt = os.getenv('PSEUDONYMIZATION_SALT')
        if not self.salt:
            raise ValueError("PSEUDONYMIZATION_SALT non défini dans .env")

        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY non définie dans .env")

        # Initialiser le chiffrement
        self.cipher = Fernet(self.encryption_key.encode())

        # Configuration de rotation des clés
        self.rotation_interval_hours = int(os.getenv('KEY_ROTATION_INTERVAL_HOURS', '24'))
        self.last_rotation = self._load_last_rotation()

        # Audit trail
        self.audit_log_path = os.getenv('EVIDENCE_PATH', 'evidence') + '/security_audit.log'
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)

    def _load_last_rotation(self) -> datetime:
        """Charge la date de dernière rotation des clés."""
        rotation_file = 'evidence/last_key_rotation.json'
        if os.path.exists(rotation_file):
            with open(rotation_file, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data['last_rotation'])
        return datetime.now() - timedelta(hours=self.rotation_interval_hours + 1)

    def _save_rotation_timestamp(self):
        """Sauvegarde la date de rotation des clés."""
        rotation_file = 'evidence/last_key_rotation.json'
        with open(rotation_file, 'w') as f:
            json.dump({
                'last_rotation': datetime.now().isoformat(),
                'rotation_interval_hours': self.rotation_interval_hours
            }, f)

    def _log_security_event(self, event_type: str, details: Dict):
        """Log des événements de sécurité."""
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'details': details
        }

        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def hash_patient_id(self, patient_id: str) -> str:
        """
        ✅ SÉCURISÉ: Hache l'ID patient avec salt depuis .env
        """
        if not patient_id:
            raise ValueError("patient_id ne peut pas être vide")

        # Hachage HMAC-SHA256 sécurisé
        hasher = hmac.new(
            self.salt.encode('utf-8'),
            patient_id.encode('utf-8'),
            hashlib.sha256
        )

        hashed_id = hasher.hexdigest()

        # Log de l'opération (sans données sensibles)
        self._log_security_event('patient_id_hashed', {
            'original_length': len(patient_id),
            'hash_prefix': hashed_id[:8] + '...',
            'algorithm': 'HMAC-SHA256'
        })

        return hashed_id

# ✅ INSTANCE GLOBALE SÉCURISÉE (remplace l'ancienne)
try:
    secure_pseudonymizer = SecurePseudonymizer()

    # Interface de compatibilité avec l'ancien code
    def hash_patient_id(patient_id: str) -> str:
        """Interface compatible pour les anciens appels."""
        return secure_pseudonymizer.hash_patient_id(patient_id)

except Exception as e:
    print(f"ERREUR: Impossible d'initialiser la sécurité - {e}")
    print("Vérifiez que le fichier .env contient PSEUDONYMIZATION_SALT et ENCRYPTION_KEY")
    raise
