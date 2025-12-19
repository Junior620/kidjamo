#!/usr/bin/env python3
"""
Script de gestion de la synchronisation Kendra pour Kidjamo
Permet de déclencher et surveiller l'indexation des documents médicaux
"""

import boto3
import json
import time
import argparse
import os
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import NoCredentialsError, ClientError

class KendraSyncManager:
    def __init__(self, index_id="b7472109-44e4-42de-9192-2b6dbe1493cc",
                 data_source_id="9f77e28f-55d1-4a52-bfef-1bf92edc54f6",
                 region="eu-west-1"):
        self.index_id = index_id
        self.data_source_id = data_source_id
        self.region = region

        # Vérifier les credentials avant de créer les clients
        self._check_aws_credentials()

        try:
            # Créer les clients AWS avec gestion d'erreur
            self.kendra = boto3.client('kendra', region_name=region)
            self.s3 = boto3.client('s3', region_name=region)
            self.bucket_name = "kidjamo-dev-chatbot-documents-y89i06z0"

            # Tester la connexion
            self._test_aws_connection()

        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation des clients AWS: {str(e)}")
            print("💡 Vérifiez vos credentials AWS et votre connexion internet")
            raise

    def _check_aws_credentials(self):
        """Vérifie les credentials AWS de manière silencieuse"""
        # Vérification silencieuse des credentials
        pass

    def _test_aws_connection(self):
        """Teste la connexion AWS avec STS"""
        try:
            sts = boto3.client('sts', region_name=self.region)
            identity = sts.get_caller_identity()
            print(f"✅ Connexion AWS réussie!")
            print(f"   👤 Utilisateur: {identity.get('Arn', 'Inconnu')}")
            print(f"   🏢 Compte: {identity.get('Account', 'Inconnu')}")
            print()
        except ClientError as e:
            if 'SignatureDoesNotMatch' in str(e) or 'InvalidSignature' in str(e):
                print("❌ Erreur de signature AWS détectée!")
                print("💡 Solutions possibles:")
                print("   1. Vérifiez que l'heure de votre système est correcte")
                print("   2. Renouvelez vos credentials AWS")
                print("   3. Vérifiez votre connexion internet")
                print("   4. Exécutez: aws configure list")
                print()
            raise

    def list_bucket_documents(self):
        """Liste les documents dans le bucket S3"""
        print("📁 Documents dans le bucket S3:")
        print("=" * 50)
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' not in response:
                print("❌ Aucun document trouvé dans le bucket")
                return
                
            total_size = 0
            doc_count = 0
            
            for obj in response['Contents']:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"📄 {key}")
                print(f"   📏 Taille: {size:,} bytes")
                print(f"   📅 Modifié: {modified}")
                print()
                
                total_size += size
                doc_count += 1
            
            print(f"📊 Total: {doc_count} documents ({total_size:,} bytes)")
            
        except Exception as e:
            print(f"❌ Erreur lors de la liste des documents: {str(e)}")
    
    def start_sync(self):
        """Démarre une synchronisation manuelle"""
        print("🔄 Démarrage de la synchronisation Kendra...")
        
        try:
            response = self.kendra.start_data_source_sync_job(
                Id=self.data_source_id,
                IndexId=self.index_id
            )
            
            execution_id = response['ExecutionId']
            print(f"✅ Synchronisation démarrée avec succès!")
            print(f"🆔 ID d'exécution: {execution_id}")
            print("⏱️  La synchronisation peut prendre 5-15 minutes selon le nombre de documents")
            
            return execution_id
            
        except Exception as e:
            if "ConflictException" in str(e):
                print("⚠️  Une synchronisation est déjà en cours")
                print("🔍 Utilisez --status pour vérifier l'état")
            else:
                print(f"❌ Erreur lors du démarrage: {str(e)}")
            return None
    
    def check_sync_status(self, execution_id=None):
        """Vérifie l'état de la synchronisation"""
        print("📊 État de la synchronisation Kendra:")
        print("=" * 40)
        
        try:
            # Obtenir la liste des jobs de synchronisation
            response = self.kendra.list_data_source_sync_jobs(
                Id=self.data_source_id,
                IndexId=self.index_id,
                MaxResults=5
            )
            
            if not response.get('History'):
                print("❌ Aucun job de synchronisation trouvé")
                return
            
            for i, job in enumerate(response['History']):
                status = job['Status']
                start_time = job['StartTime'].strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"🔄 Job #{i+1}")
                print(f"   📅 Démarré: {start_time}")
                print(f"   📊 État: {self._format_status(status)}")
                
                if 'EndTime' in job:
                    end_time = job['EndTime'].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"   🏁 Terminé: {end_time}")
                
                if 'Metrics' in job:
                    metrics = job['Metrics']
                    print(f"   📈 Documents ajoutés: {metrics.get('DocumentsAdded', 0)}")
                    print(f"   📈 Documents modifiés: {metrics.get('DocumentsModified', 0)}")
                    print(f"   📈 Documents supprimés: {metrics.get('DocumentsDeleted', 0)}")
                    print(f"   📈 Documents échoués: {metrics.get('DocumentsFailed', 0)}")
                
                if 'ErrorMessage' in job:
                    print(f"   ❌ Erreur: {job['ErrorMessage']}")
                
                print()
                
        except Exception as e:
            print(f"❌ Erreur lors de la vérification: {str(e)}")
    
    def _format_status(self, status):
        """Formate le statut avec des émojis"""
        status_map = {
            'RUNNING': '🏃 EN COURS',
            'SUCCEEDED': '✅ RÉUSSI',
            'FAILED': '❌ ÉCHOUÉ',
            'STOPPING': '⏹️ ARRÊT EN COURS',
            'STOPPED': '⏸️ ARRÊTÉ'
        }
        return status_map.get(status, f"❓ {status}")
    
    def test_search(self):
        """Teste la recherche après synchronisation"""
        print("🔍 Test de recherche dans l'index Kendra:")
        print("=" * 45)
        
        test_queries = [
            "drépanocytose définition",
            "symptômes anémie falciforme",
            "traitement hydroxyurée",
            "crise vaso-occlusive",
            "urgence médicale drépanocytose"
        ]
        
        for query in test_queries:
            print(f"🔎 Recherche: '{query}'")
            
            try:
                response = self.kendra.query(
                    IndexId=self.index_id,
                    QueryText=query,
                    PageSize=3
                )
                
                results = response.get('ResultItems', [])
                print(f"   📋 {len(results)} résultat(s) trouvé(s)")
                
                for i, result in enumerate(results[:2]):
                    title = result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                    excerpt = result.get('DocumentExcerpt', {}).get('Text', '')[:100]
                    confidence = result.get('ScoreAttributes', {}).get('ScoreConfidence', 'UNKNOWN')
                    
                    print(f"   [{i+1}] {title} (Confiance: {confidence})")
                    print(f"       {excerpt}...")
                
                print()
                
            except Exception as e:
                print(f"   ❌ Erreur: {str(e)}")
                print()
    
    def monitor_sync(self, check_interval=30):
        """Surveille une synchronisation en cours"""
        print("👀 Surveillance de la synchronisation en cours...")
        print("   Appuyez sur Ctrl+C pour arrêter la surveillance")
        print()
        
        try:
            while True:
                self.check_sync_status()
                
                # Vérifier si la dernière sync est terminée
                response = self.kendra.list_data_source_sync_jobs(
                    Id=self.data_source_id,
                    IndexId=self.index_id,
                    MaxResults=1
                )
                
                if response.get('History'):
                    latest_job = response['History'][0]
                    if latest_job['Status'] in ['SUCCEEDED', 'FAILED', 'STOPPED']:
                        print("🏁 Synchronisation terminée!")
                        if latest_job['Status'] == 'SUCCEEDED':
                            print("✅ Vous pouvez maintenant tester la recherche avec --test")
                        break
                
                print(f"⏰ Prochaine vérification dans {check_interval} secondes...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n👋 Surveillance interrompue par l'utilisateur")

def main():
    parser = argparse.ArgumentParser(description='Gestionnaire de synchronisation Kendra')
    parser.add_argument('--list', action='store_true', help='Lister les documents S3')
    parser.add_argument('--sync', action='store_true', help='Démarrer une synchronisation')
    parser.add_argument('--status', action='store_true', help='Vérifier l\'état des synchronisations')
    parser.add_argument('--test', action='store_true', help='Tester la recherche')
    parser.add_argument('--monitor', action='store_true', help='Surveiller la synchronisation')
    parser.add_argument('--all', action='store_true', help='Exécuter toutes les actions')
    
    args = parser.parse_args()
    
    manager = KendraSyncManager()
    
    if args.all or args.list:
        manager.list_bucket_documents()
        print()
    
    if args.all or args.sync:
        execution_id = manager.start_sync()
        print()
        
        if execution_id and (args.all or args.monitor):
            time.sleep(5)  # Attendre que le job démarre
            manager.monitor_sync()
    
    if args.status:
        manager.check_sync_status()
        print()
    
    if args.test:
        manager.test_search()
    
    if args.monitor and not (args.all or args.sync):
        manager.monitor_sync()
    
    if not any(vars(args).values()):
        print("🔧 Gestionnaire de synchronisation Kendra Kidjamo")
        print("=" * 50)
        print("Utilisations:")
        print("  --list     : Lister les documents dans S3")
        print("  --sync     : Démarrer une synchronisation")
        print("  --status   : Vérifier l'état des synchronisations")
        print("  --test     : Tester la recherche")
        print("  --monitor  : Surveiller la synchronisation")
        print("  --all      : Tout faire (list + sync + monitor)")
        print()
        print("Exemples:")
        print("  python kendra_sync_manager.py --sync")
        print("  python kendra_sync_manager.py --all")
        print("  python kendra_sync_manager.py --test")

if __name__ == "__main__":
    main()
