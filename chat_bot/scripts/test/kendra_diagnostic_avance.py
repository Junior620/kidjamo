#!/usr/bin/env python3
"""
Diagnostic avancé pour l'index Kendra - Identification des problèmes d'indexation
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

class KendraDiagnosticAvance:
    def __init__(self, index_id="b7472109-44e4-42de-9192-2b6dbe1493cc", region="eu-west-1"):
        self.index_id = index_id
        self.region = region
        self.kendra = boto3.client('kendra', region_name=region)

    def diagnostic_complet(self):
        """Effectue un diagnostic complet de l'index Kendra"""
        print("🔧 DIAGNOSTIC AVANCÉ KENDRA")
        print("=" * 50)
        print()

        # 1. État de l'index
        self.verifier_etat_index()
        print()

        # 2. Statistiques de l'index
        self.obtenir_statistiques_index()
        print()

        # 3. Configuration de l'index
        self.verifier_configuration_index()
        print()

        # 4. Test de recherche avec différentes stratégies
        self.test_recherche_avance()
        print()

        # 5. Suggestions de résolution
        self.suggestions_resolution()

    def verifier_etat_index(self):
        """Vérifie l'état détaillé de l'index"""
        print("📊 ÉTAT DE L'INDEX")
        print("-" * 30)

        try:
            response = self.kendra.describe_index(Id=self.index_id)

            status = response.get('Status', 'UNKNOWN')
            print(f"📈 État: {self._format_status(status)}")

            if 'CreatedAt' in response:
                created = response['CreatedAt'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"📅 Créé le: {created}")

            if 'UpdatedAt' in response:
                updated = response['UpdatedAt'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"🔄 Mis à jour: {updated}")

            if 'DocumentMetadataConfigurations' in response:
                metadata_count = len(response['DocumentMetadataConfigurations'])
                print(f"🏷️ Configurations de métadonnées: {metadata_count}")

            if 'ErrorMessage' in response:
                print(f"❌ Erreur: {response['ErrorMessage']}")

        except Exception as e:
            print(f"❌ Erreur lors de la vérification de l'index: {str(e)}")

    def obtenir_statistiques_index(self):
        """Obtient les statistiques détaillées de l'index"""
        print("📈 STATISTIQUES DE L'INDEX")
        print("-" * 30)

        try:
            # Obtenir les statistiques depuis une semaine
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=7)

            response = self.kendra.get_snapshots(
                IndexId=self.index_id,
                Interval='THIS_WEEK',
                MaxResults=10
            )

            if 'SnapshotsData' in response and response['SnapshotsData']:
                latest_snapshot = response['SnapshotsData'][0]

                if 'SnapshotsDataHeader' in latest_snapshot:
                    headers = latest_snapshot['SnapshotsDataHeader']
                    values = latest_snapshot['SnapshotsDataBody'][0] if latest_snapshot['SnapshotsDataBody'] else []

                    stats = dict(zip(headers, values))

                    print(f"📄 Documents indexés: {stats.get('DOCS_INDEXED', 'N/A')}")
                    print(f"🔍 Requêtes totales: {stats.get('QUERIES_COUNT', 'N/A')}")
                    print(f"📊 Questions-réponses: {stats.get('QUERY_DOC_COUNT', 'N/A')}")

            else:
                print("❌ Aucune statistique disponible")

        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des statistiques: {str(e)}")

    def verifier_configuration_index(self):
        """Vérifie la configuration de l'index"""
        print("⚙️ CONFIGURATION DE L'INDEX")
        print("-" * 30)

        try:
            response = self.kendra.describe_index(Id=self.index_id)

            # Vérifier l'édition
            edition = response.get('Edition', 'UNKNOWN')
            print(f"🏷️ Édition: {edition}")

            # Vérifier les capacités
            if 'CapacityUnits' in response:
                storage = response['CapacityUnits'].get('StorageCapacityUnits', 0)
                query = response['CapacityUnits'].get('QueryCapacityUnits', 0)
                print(f"💾 Capacité de stockage: {storage}")
                print(f"🔍 Capacité de requête: {query}")

            # Vérifier les sources de données
            data_sources = self.kendra.list_data_sources(IndexId=self.index_id)
            print(f"📁 Sources de données configurées: {len(data_sources.get('SummaryItems', []))}")

            for ds in data_sources.get('SummaryItems', []):
                name = ds.get('Name', 'Sans nom')
                status = ds.get('Status', 'UNKNOWN')
                ds_type = ds.get('Type', 'UNKNOWN')
                print(f"   - {name} ({ds_type}): {self._format_status(status)}")

        except Exception as e:
            print(f"❌ Erreur lors de la vérification de la configuration: {str(e)}")

    def test_recherche_avance(self):
        """Test de recherche avec différentes stratégies"""
        print("🔍 TESTS DE RECHERCHE AVANCÉS")
        print("-" * 30)

        # Tests avec différents types de requêtes
        test_cases = [
            {
                "nom": "Recherche simple",
                "requete": "drépanocytose",
                "type": "simple"
            },
            {
                "nom": "Recherche avec guillemets",
                "requete": '"anémie falciforme"',
                "type": "exact"
            },
            {
                "nom": "Recherche booléenne",
                "requete": "drépanocytose AND traitement",
                "type": "boolean"
            },
            {
                "nom": "Recherche par synonyme",
                "requete": "maladie génétique sang",
                "type": "synonyme"
            },
            {
                "nom": "Recherche en anglais",
                "requete": "sickle cell disease",
                "type": "anglais"
            }
        ]

        for test in test_cases:
            print(f"\n🔎 {test['nom']}: '{test['requete']}'")
            self._executer_recherche(test['requete'], test['type'])

    def _executer_recherche(self, query, search_type):
        """Exécute une recherche avec diagnostic détaillé"""
        try:
            # Configuration de base
            search_params = {
                'IndexId': self.index_id,
                'QueryText': query,
                'PageSize': 5
            }

            # Ajouter des attributs selon le type de recherche
            if search_type == "exact":
                search_params['QueryResultTypeFilter'] = 'DOCUMENT'
            elif search_type == "boolean":
                search_params['AttributeFilter'] = {
                    'AndAllFilters': []
                }

            response = self.kendra.query(**search_params)

            results = response.get('ResultItems', [])
            total_results = response.get('TotalNumberOfResults', 0)

            print(f"   📊 Résultats trouvés: {len(results)} (Total: {total_results})")

            if results:
                for i, result in enumerate(results[:2]):
                    title = result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                    doc_id = result.get('DocumentId', 'ID inconnu')
                    score = result.get('ScoreAttributes', {})
                    confidence = score.get('ScoreConfidence', 'UNKNOWN')

                    print(f"   [{i+1}] {title[:50]}...")
                    print(f"       ID: {doc_id}")
                    print(f"       Confiance: {confidence}")

                    if 'DocumentExcerpt' in result:
                        excerpt = result['DocumentExcerpt'].get('Text', '')[:80]
                        print(f"       Extrait: {excerpt}...")
            else:
                print("   ❌ Aucun résultat")

                # Diagnostic pour les résultats vides
                print("   🔧 Diagnostic:")
                print("      - Vérifiez que les documents contiennent les termes recherchés")
                print("      - Les documents sont peut-être dans une langue non supportée")
                print("      - L'indexation peut ne pas être complète")

        except Exception as e:
            print(f"   ❌ Erreur: {str(e)}")

    def suggestions_resolution(self):
        """Fournit des suggestions pour résoudre les problèmes"""
        print("💡 SUGGESTIONS DE RÉSOLUTION")
        print("-" * 30)

        suggestions = [
            "🔄 Relancer une synchronisation complète avec suppression/re-ajout",
            "📝 Vérifier que les documents PDF ne sont pas protégés par mot de passe",
            "🌐 Vérifier la détection de langue (français vs anglais)",
            "⏰ Attendre 24-48h pour l'indexation complète des gros documents",
            "🏷️ Ajouter des métadonnées explicites aux documents",
            "📊 Vérifier les logs CloudWatch pour des erreurs d'indexation",
            "🔧 Tester avec des documents plus simples (TXT, MD) en premier",
            "📑 Vérifier que les PDF ne sont pas des images scannées (OCR requis)"
        ]

        for suggestion in suggestions:
            print(f"   {suggestion}")

        print("\n🎯 ACTIONS RECOMMANDÉES IMMÉDIATES:")
        print("   1. Exécuter: python kendra_diagnostic_avance.py --force-reindex")
        print("   2. Tester avec un document simple (guide_drepanocytose_simple.md)")
        print("   3. Vérifier les logs CloudWatch pour cette région")

    def _format_status(self, status):
        """Formate le statut avec des émojis"""
        status_map = {
            'ACTIVE': '✅ ACTIF',
            'CREATING': '🔄 CRÉATION',
            'UPDATING': '🔄 MISE À JOUR',
            'DELETING': '🗑️ SUPPRESSION',
            'FAILED': '❌ ÉCHEC',
            'RUNNING': '🏃 EN COURS',
            'SUCCEEDED': '✅ RÉUSSI',
            'STOPPING': '⏹️ ARRÊT',
            'STOPPED': '⏸️ ARRÊTÉ'
        }
        return status_map.get(status, f"❓ {status}")

def main():
    print("🚀 Lancement du diagnostic avancé Kendra...")
    print()

    try:
        diagnostic = KendraDiagnosticAvance()
        diagnostic.diagnostic_complet()

    except Exception as e:
        print(f"❌ Erreur fatale: {str(e)}")
        print("💡 Vérifiez vos credentials AWS et votre connexion")

if __name__ == "__main__":
    main()
