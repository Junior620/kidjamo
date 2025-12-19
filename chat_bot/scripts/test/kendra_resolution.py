#!/usr/bin/env python3
"""
Script de résolution des problèmes d'indexation Kendra
Test avec document simple et réindexation forcée
"""

import boto3
import json
import time
import os
from datetime import datetime

class KendraResolution:
    def __init__(self, index_id="b7472109-44e4-42de-9192-2b6dbe1493cc",
                 data_source_id="9f77e28f-55d1-4a52-bfef-1bf92edc54f6",
                 region="eu-west-1"):
        self.index_id = index_id
        self.data_source_id = data_source_id
        self.region = region
        self.kendra = boto3.client('kendra', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.bucket_name = "kidjamo-dev-chatbot-documents-y89i06z0"

    def creer_document_test_simple(self):
        """Crée un document de test simple et explicite"""
        print("📝 CRÉATION D'UN DOCUMENT DE TEST SIMPLE")
        print("=" * 50)

        # Contenu de test très explicite
        contenu_test = """# Test Drépanocytose - Document de Diagnostic Kendra

## Qu'est-ce que la drépanocytose ?

La drépanocytose est une maladie génétique héréditaire qui affecte les globules rouges.
Elle est également appelée anémie falciforme.

## Symptômes principaux

Les symptômes de la drépanocytose incluent :
- Douleurs intenses (crises vaso-occlusives)
- Anémie chronique
- Fatigue persistante
- Infections fréquentes

## Traitements disponibles

Les traitements pour la drépanocytose comprennent :
- Hydroxyurée (traitement principal)
- Transfusions sanguines régulières
- Greffe de moelle osseuse
- Gestion de la douleur

## Urgences médicales

Les urgences liées à la drépanocytose :
- Syndrome thoracique aigu
- Accident vasculaire cérébral
- Séquestration splénique
- Crise douleur sévère

## Prévention et surveillance

- Dépistage précoce de la drépanocytose
- Prévention des infections par vaccination
- Surveillance médicale régulière
- Éducation thérapeutique du patient

## Contexte Cameroun et Afrique

La drépanocytose affecte particulièrement l'Afrique et le Cameroun.
Les statistiques montrent une prévalence élevée.
L'OMS (WHO) publie régulièrement des rapports sur cette maladie.

---
Document de test créé le: {date}
Mots-clés: drépanocytose, anémie falciforme, maladie génétique, hydroxyurée, Cameroun, Afrique
""".format(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # Sauvegarder localement
        with open('test_drepanocytose_diagnostic.md', 'w', encoding='utf-8') as f:
            f.write(contenu_test)

        print("✅ Document test créé localement: test_drepanocytose_diagnostic.md")

        # Uploader vers S3
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key='test/test_drepanocytose_diagnostic.md',
                Body=contenu_test.encode('utf-8'),
                ContentType='text/markdown',
                Metadata={
                    'titre': 'Document Test Drepanocytose',
                    'langue': 'francais',
                    'type': 'medical',
                    'test': 'diagnostic_kendra'
                }
            )
            print("✅ Document uploadé vers S3: test/test_drepanocytose_diagnostic.md")
            return True

        except Exception as e:
            print(f"❌ Erreur upload S3: {str(e)}")
            return False

    def forcer_reindexation_complete(self):
        """Force une réindexation complète avec nettoyage"""
        print("\n🔄 RÉINDEXATION FORCÉE COMPLÈTE")
        print("=" * 50)

        try:
            # Démarrer une nouvelle synchronisation
            print("🚀 Démarrage d'une nouvelle synchronisation...")
            response = self.kendra.start_data_source_sync_job(
                Id=self.data_source_id,
                IndexId=self.index_id
            )

            execution_id = response['ExecutionId']
            print(f"✅ Synchronisation démarrée: {execution_id}")
            print("⏱️  Attente de 2 minutes avant les tests...")

            return execution_id

        except Exception as e:
            if "ConflictException" in str(e):
                print("⚠️  Une synchronisation est déjà en cours")
                print("📊 Récupération de l'ID de la synchronisation actuelle...")

                # Obtenir le job en cours
                response = self.kendra.list_data_source_sync_jobs(
                    Id=self.data_source_id,
                    IndexId=self.index_id,
                    MaxResults=1
                )

                if response.get('History'):
                    latest_job = response['History'][0]
                    if latest_job['Status'] == 'RUNNING':
                        return latest_job['ExecutionId']

                return None
            else:
                print(f"❌ Erreur: {str(e)}")
                return None

    def test_recherche_immediate(self):
        """Test de recherche immédiat avec termes simples"""
        print("\n🔍 TESTS DE RECHERCHE IMMÉDIATS")
        print("=" * 50)

        # Tests très simples d'abord
        tests_simples = [
            "test",
            "drépanocytose",
            "maladie",
            "anémie",
            "diagnostic",
            "traitement"
        ]

        resultats_positifs = 0

        for terme in tests_simples:
            print(f"\n🔎 Test: '{terme}'")

            try:
                response = self.kendra.query(
                    IndexId=self.index_id,
                    QueryText=terme,
                    PageSize=3
                )

                results = response.get('ResultItems', [])
                print(f"   📊 {len(results)} résultat(s)")

                if results:
                    resultats_positifs += 1
                    for i, result in enumerate(results[:1]):
                        title = result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                        confidence = result.get('ScoreAttributes', {}).get('ScoreConfidence', 'UNKNOWN')
                        print(f"   ✅ [{i+1}] {title[:60]}... (Confiance: {confidence})")
                else:
                    print("   ❌ Aucun résultat")

            except Exception as e:
                print(f"   ❌ Erreur: {str(e)}")

        print(f"\n📈 Résumé: {resultats_positifs}/{len(tests_simples)} recherches avec résultats")
        return resultats_positifs > 0

    def surveiller_indexation(self, execution_id, max_minutes=10):
        """Surveille l'indexation en temps réel"""
        print(f"\n👀 SURVEILLANCE DE L'INDEXATION")
        print("=" * 50)
        print(f"🆔 Job ID: {execution_id}")
        print("⏰ Vérification toutes les 30 secondes...")
        print("💡 Appuyez sur Ctrl+C pour arrêter")

        start_time = time.time()

        try:
            while True:
                elapsed = (time.time() - start_time) / 60

                if elapsed > max_minutes:
                    print(f"\n⏰ Temps limite atteint ({max_minutes} minutes)")
                    break

                # Vérifier le statut
                response = self.kendra.list_data_source_sync_jobs(
                    Id=self.data_source_id,
                    IndexId=self.index_id,
                    MaxResults=1
                )

                if response.get('History'):
                    job = response['History'][0]
                    status = job['Status']

                    print(f"\r⏱️  {elapsed:.1f}min - État: {self._format_status(status)}", end="", flush=True)

                    if status in ['SUCCEEDED', 'FAILED', 'STOPPED']:
                        print(f"\n🏁 Synchronisation terminée: {status}")

                        if status == 'SUCCEEDED' and 'Metrics' in job:
                            metrics = job['Metrics']
                            print(f"📈 Documents traités: {metrics.get('DocumentsAdded', 0)} ajoutés")

                        break

                time.sleep(30)

        except KeyboardInterrupt:
            print("\n👋 Surveillance interrompue")

    def _format_status(self, status):
        """Formate le statut"""
        status_map = {
            'RUNNING': '🏃 EN COURS',
            'SUCCEEDED': '✅ RÉUSSI',
            'FAILED': '❌ ÉCHOUÉ',
            'STOPPING': '⏹️ ARRÊT',
            'STOPPED': '⏸️ ARRÊTÉ'
        }
        return status_map.get(status, status)

    def resolution_complete(self):
        """Processus de résolution complet"""
        print("🔧 PROCESSUS DE RÉSOLUTION COMPLET KENDRA")
        print("=" * 60)
        print()

        # Étape 1: Créer document test
        if not self.creer_document_test_simple():
            print("❌ Impossible de créer le document test")
            return

        # Étape 2: Test de recherche avant réindexation
        print("\n📊 Tests avant réindexation:")
        resultats_avant = self.test_recherche_immediate()

        # Étape 3: Forcer réindexation
        execution_id = self.forcer_reindexation_complete()

        if execution_id:
            # Étape 4: Surveiller
            self.surveiller_indexation(execution_id)

            # Étape 5: Tests après réindexation
            print("\n📊 Tests après réindexation:")
            resultats_apres = self.test_recherche_immediate()

            # Résumé
            print("\n🎯 RÉSUMÉ DE LA RÉSOLUTION")
            print("=" * 40)
            print(f"🔍 Recherches fonctionnelles avant: {'✅' if resultats_avant else '❌'}")
            print(f"🔍 Recherches fonctionnelles après: {'✅' if resultats_apres else '❌'}")

            if resultats_apres:
                print("\n✅ PROBLÈME RÉSOLU!")
                print("🎉 Votre index Kendra fonctionne maintenant correctement")
            else:
                print("\n⚠️  PROBLÈME PERSISTANT")
                print("💡 Actions supplémentaires recommandées:")
                print("   1. Vérifier les logs CloudWatch")
                print("   2. Attendre 24h pour l'indexation complète")
                print("   3. Contacter le support AWS si nécessaire")

def main():
    print("🚀 DÉMARRAGE DE LA RÉSOLUTION KENDRA")
    print("=" * 50)

    try:
        resolver = KendraResolution()
        resolver.resolution_complete()

    except Exception as e:
        print(f"❌ Erreur fatale: {str(e)}")

if __name__ == "__main__":
    main()
