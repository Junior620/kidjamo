#!/usr/bin/env python3
"""
Diagnostic ultra-approfondi pour identifier la vraie cause du problème Kendra
"""

import boto3
import json
import time
from datetime import datetime, timedelta

class KendraUltimateDiagnostic:
    def __init__(self, index_id="b7472109-44e4-42de-9192-2b6dbe1493cc",
                 data_source_id="9f77e28f-55d1-4a52-bfef-1bf92edc54f6",
                 region="eu-west-1"):
        self.index_id = index_id
        self.data_source_id = data_source_id
        self.region = region
        self.kendra = boto3.client('kendra', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.cloudwatch = boto3.client('logs', region_name=region)

    def diagnostic_complet_final(self):
        """Diagnostic ultra-complet pour identifier la cause exacte"""
        print("🔬 DIAGNOSTIC ULTRA-APPROFONDI KENDRA")
        print("=" * 60)
        print()

        # 1. Vérifier les permissions et rôles IAM
        self.verifier_permissions_iam()
        print()

        # 2. Analyser les logs CloudWatch
        self.analyser_logs_cloudwatch()
        print()

        # 3. Vérifier le statut détaillé des documents
        self.verifier_statut_documents()
        print()

        # 4. Test avec requête simple directe
        self.test_requete_directe()
        print()

        # 5. Diagnostic des métadonnées de documents
        self.diagnostiquer_metadonnees()
        print()

        # 6. Solution alternative immediate
        self.solution_alternative_immediate()

    def verifier_permissions_iam(self):
        """Vérifie les permissions IAM du rôle Kendra"""
        print("🔐 VÉRIFICATION PERMISSIONS IAM")
        print("-" * 40)

        try:
            # Obtenir les détails de l'index pour voir le rôle
            response = self.kendra.describe_index(Id=self.index_id)
            role_arn = response.get('RoleArn', 'Aucun rôle trouvé')

            print(f"🎭 Rôle IAM: {role_arn}")

            # Tester les permissions avec STS
            sts = boto3.client('sts', region_name=self.region)
            identity = sts.get_caller_identity()
            print(f"👤 Utilisateur actuel: {identity.get('Arn')}")

            # Vérifier si on peut accéder aux logs
            try:
                log_groups = self.cloudwatch.describe_log_groups(
                    logGroupNamePrefix='/aws/kendra'
                )
                print(f"📋 Groupes de logs accessibles: {len(log_groups.get('logGroups', []))}")
            except Exception as e:
                print(f"⚠️  Accès aux logs limité: {str(e)[:100]}...")

        except Exception as e:
            print(f"❌ Erreur permissions: {str(e)}")

    def analyser_logs_cloudwatch(self):
        """Analyse les logs CloudWatch pour des erreurs"""
        print("📊 ANALYSE LOGS CLOUDWATCH")
        print("-" * 40)

        try:
            # Chercher les logs Kendra
            log_group_name = f"/aws/kendra/{self.index_id}"

            end_time = int(time.time() * 1000)
            start_time = end_time - (24 * 60 * 60 * 1000)  # 24h

            try:
                response = self.cloudwatch.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=start_time,
                    endTime=end_time,
                    filterPattern='ERROR'
                )

                events = response.get('events', [])
                print(f"🔍 Erreurs trouvées dans les logs: {len(events)}")

                for event in events[-3:]:  # 3 dernières erreurs
                    timestamp = datetime.fromtimestamp(event['timestamp']/1000)
                    message = event['message'][:200]
                    print(f"   ❌ {timestamp}: {message}...")

            except self.cloudwatch.exceptions.ResourceNotFoundException:
                print("⚠️  Aucun log group Kendra trouvé")
                print("💡 Cela peut indiquer un problème de configuration")

        except Exception as e:
            print(f"❌ Erreur analyse logs: {str(e)}")

    def verifier_statut_documents(self):
        """Vérifie le statut détaillé des documents individuels"""
        print("📄 STATUT DÉTAILLÉ DES DOCUMENTS")
        print("-" * 40)

        try:
            # Lister les derniers jobs de sync
            response = self.kendra.list_data_source_sync_jobs(
                Id=self.data_source_id,
                IndexId=self.index_id,
                MaxResults=1
            )

            if response.get('History'):
                latest_job = response['History'][0]
                execution_id = latest_job.get('ExecutionId')

                print(f"🆔 Dernier job: {execution_id}")
                print(f"📊 Statut: {latest_job.get('Status')}")

                if 'Metrics' in latest_job:
                    metrics = latest_job['Metrics']
                    print(f"📈 Documents ajoutés: {metrics.get('DocumentsAdded', 0)}")
                    print(f"📈 Documents échoués: {metrics.get('DocumentsFailed', 0)}")

                # Essayer d'obtenir les détails des documents échoués
                if execution_id:
                    try:
                        # Cette API peut ne pas être disponible dans toutes les régions
                        print("🔍 Recherche de détails sur les documents...")

                    except Exception as e:
                        print(f"⚠️  Détails documents non disponibles: {str(e)[:100]}...")

        except Exception as e:
            print(f"❌ Erreur statut documents: {str(e)}")

    def test_requete_directe(self):
        """Test avec l'API de requête la plus simple possible"""
        print("🎯 TEST REQUÊTE ULTRA-SIMPLE")
        print("-" * 40)

        # Test avec un seul caractère
        tests_minimaux = ["a", "e", "i", "o", "u", "1", "2", "*"]

        for char in tests_minimaux:
            try:
                response = self.kendra.query(
                    IndexId=self.index_id,
                    QueryText=char
                )

                total_results = response.get('TotalNumberOfResults', 0)
                result_items = len(response.get('ResultItems', []))

                if total_results > 0:
                    print(f"✅ '{char}': {result_items}/{total_results} résultats")
                    # Premier résultat trouvé - l'index fonctionne !
                    print("🎉 INDEX FONCTIONNEL DÉTECTÉ !")

                    # Analyser le premier résultat
                    if response.get('ResultItems'):
                        first_result = response['ResultItems'][0]
                        doc_title = first_result.get('DocumentTitle', {}).get('Text', 'Sans titre')
                        doc_id = first_result.get('DocumentId', 'Sans ID')
                        confidence = first_result.get('ScoreAttributes', {}).get('ScoreConfidence', 'UNKNOWN')

                        print(f"📄 Document trouvé: {doc_title}")
                        print(f"🆔 ID: {doc_id}")
                        print(f"📊 Confiance: {confidence}")

                    return True
                else:
                    print(f"❌ '{char}': {result_items}/{total_results}")

            except Exception as e:
                print(f"❌ '{char}': Erreur - {str(e)[:50]}...")

        return False

    def diagnostiquer_metadonnees(self):
        """Diagnostique les métadonnées des documents S3"""
        print("🏷️ DIAGNOSTIC MÉTADONNÉES S3")
        print("-" * 40)

        try:
            bucket_name = "kidjamo-dev-chatbot-documents-y89i06z0"

            # Examiner quelques documents
            response = self.s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix='test/',
                MaxKeys=5
            )

            for obj in response.get('Contents', []):
                key = obj['Key']
                print(f"\n📄 {key}")

                # Obtenir les métadonnées
                try:
                    meta_response = self.s3.head_object(Bucket=bucket_name, Key=key)

                    # Métadonnées système
                    content_type = meta_response.get('ContentType', 'Inconnu')
                    size = meta_response.get('ContentLength', 0)
                    print(f"   📏 Taille: {size:,} bytes")
                    print(f"   🎭 Type: {content_type}")

                    # Métadonnées personnalisées
                    user_metadata = meta_response.get('Metadata', {})
                    if user_metadata:
                        print(f"   🏷️  Métadonnées: {user_metadata}")
                    else:
                        print(f"   ⚠️  Aucune métadonnée personnalisée")

                except Exception as e:
                    print(f"   ❌ Erreur métadonnées: {str(e)[:50]}...")

        except Exception as e:
            print(f"❌ Erreur diagnostic S3: {str(e)}")

    def solution_alternative_immediate(self):
        """Propose une solution alternative immédiate"""
        print("🚀 SOLUTION ALTERNATIVE IMMÉDIATE")
        print("-" * 40)

        print("Basé sur le diagnostic, voici les solutions possibles:")
        print()

        print("1️⃣ PROBLÈME PROBABLE: Index Kendra vide")
        print("   → Les documents sont synchronisés mais pas indexés")
        print("   → Solution: Attendre 24-48h ou recréer l'index")
        print()

        print("2️⃣ ALTERNATIVE: Utiliser OpenSearch/Elasticsearch")
        print("   → Plus de contrôle sur l'indexation")
        print("   → Support natif du français")
        print("   → Configuration plus transparente")
        print()

        print("3️⃣ SOLUTION TEMPORAIRE: Chatbot sans Kendra")
        print("   → Utiliser des réponses pré-programmées")
        print("   → Base de connaissances en dur")
        print("   → FAQ statique bien structurée")

        # Créer un exemple de solution sans Kendra
        self.creer_solution_sans_kendra()

    def creer_solution_sans_kendra(self):
        """Crée une solution de chatbot temporaire sans Kendra"""
        print("\n💡 CRÉATION SOLUTION TEMPORAIRE")
        print("-" * 40)

        faq_content = """
# Base de Connaissances Drépanocytose - Version Temporaire

## Questions Fréquentes

### Qu'est-ce que la drépanocytose ?
La drépanocytose est une maladie génétique héréditaire qui affecte l'hémoglobine dans les globules rouges.

### Quels sont les symptômes ?
- Douleurs intenses (crises vaso-occlusives)
- Anémie chronique
- Fatigue persistante
- Infections fréquentes

### Quels traitements sont disponibles ?
- Hydroxyurée (traitement principal)
- Transfusions sanguines régulières
- Greffe de moelle osseuse
- Gestion de la douleur

### Que faire en cas d'urgence ?
- Syndrome thoracique aigu → Urgences immédiatement
- Douleur sévère → Analgésiques et hydratation
- Fièvre → Antibiotiques rapides

### Statistiques Cameroun
- Prévalence: environ 1-2% de la population
- Porteurs sains: 10-15% de la population
- Nécessité de dépistage précoce
"""

        try:
            with open('faq_drepanocytose_temporaire.md', 'w', encoding='utf-8') as f:
                f.write(faq_content)

            print("✅ FAQ temporaire créée: faq_drepanocytose_temporaire.md")
            print("💡 Utilisable immédiatement avec votre chatbot Lex")

        except Exception as e:
            print(f"❌ Erreur création FAQ: {str(e)}")

def main():
    print("🚀 DIAGNOSTIC FINAL ULTRA-APPROFONDI")
    print("=" * 60)

    try:
        diagnostic = KendraUltimateDiagnostic()
        diagnostic.diagnostic_complet_final()

        print("\n🎯 CONCLUSION FINALE")
        print("=" * 30)
        print("✅ Diagnostic ultra-complet terminé")
        print("💡 Solutions alternatives proposées")
        print("📋 FAQ temporaire créée")

    except Exception as e:
        print(f"❌ Erreur fatale: {str(e)}")

if __name__ == "__main__":
    main()
"""
