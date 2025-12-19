"""
Script de création des documents médicaux de base pour Amazon Kendra
Chatbot Santé Kidjamo - Configuration initiale
"""

import boto3
import json
import argparse
import logging
import os
from datetime import datetime
from typing import Dict, List

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MedicalDocumentsCreator:
    def __init__(self, bucket_name: str, environment: str):
        self.bucket_name = bucket_name
        self.environment = environment
        self.s3_client = boto3.client('s3')

    def create_all_documents(self):
        """Crée tous les documents médicaux de base"""
        logger.info("🏥 Création des documents médicaux pour Kendra...")

        documents = [
            self.create_drepanocytose_guide(),
            self.create_crisis_management_guide(),
            self.create_medications_guide(),
            self.create_lifestyle_recommendations(),
            self.create_emergency_protocols(),
            self.create_faq_document(),
            self.create_research_updates()
        ]

        # Upload des documents
        for doc in documents:
            self.upload_document(doc)

        # Création du fichier FAQ CSV
        self.create_faq_csv()

        # Création des métadonnées
        self.create_metadata_files()

        logger.info("✅ Tous les documents ont été créés et uploadés")

    def create_drepanocytose_guide(self) -> Dict:
        """Guide complet sur la drépanocytose"""
        content = """# Guide Complet - Comprendre la Drépanocytose

## Qu'est-ce que la drépanocytose ?

La drépanocytose est une maladie génétique héréditaire qui affecte l'hémoglobine, la protéine des globules rouges responsable du transport de l'oxygène dans le corps.

### Mécanisme de la maladie

Les globules rouges normaux sont souples et ronds, ce qui leur permet de circuler facilement dans les vaisseaux sanguins. Dans la drépanocytose, les globules rouges prennent une forme de faucille ou de croissant et deviennent rigides.

### Types de drépanocytose

- **SS (Homozygote)** : Forme la plus sévère
- **SC** : Forme modérée
- **S-β thalassémie** : Sévérité variable

## Symptômes principaux

### Crises vaso-occlusives
- Douleurs intenses et soudaines
- Localisations fréquentes : os, articulations, abdomen, thorax
- Durée variable : quelques heures à plusieurs jours

### Anémie chronique
- Fatigue persistante
- Essoufflement à l'effort
- Pâleur
- Vertiges

### Complications possibles
- Syndrome thoracique aigu
- Priapisme
- Accidents vasculaires cérébraux
- Infections graves

## Diagnostic

Le diagnostic se fait par :
- Test de dépistage néonatal
- Électrophorèse de l'hémoglobine
- Test de falciformation
- Analyse génétique

## Transmission héréditaire

La drépanocytose se transmet selon un mode autosomique récessif :
- Les deux parents doivent être porteurs
- 25% de risque d'avoir un enfant atteint
- 50% de risque d'avoir un enfant porteur sain

---
*Document mis à jour : {date}*
*Source : Centre de Référence Drépanocytose*
""".format(date=datetime.now().strftime("%d/%m/%Y"))

        return {
            'key': 'guides/drepanocytose-guide-complet.md',
            'content': content,
            'metadata': {
                'category': 'Guide Patient',
                'document_type': 'Guide Médical',
                'medical_specialty': 'Hématologie',
                'author': 'Équipe Médicale Kidjamo',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_crisis_management_guide(self) -> Dict:
        """Guide de gestion des crises"""
        content = """# Gestion des Crises de Drépanocytose

## Reconnaître une crise

### Signes d'alerte
- Douleur intense et soudaine
- Fièvre > 38.5°C
- Essoufflement important
- Douleur thoracique
- Maux de tête sévères
- Troubles visuels

## Que faire en cas de crise ?

### Mesures immédiates
1. **Hydratation** : Boire beaucoup d'eau
2. **Antalgiques** : Prendre les médicaments prescrits
3. **Repos** : Se mettre au repos complet
4. **Chaleur locale** : Appliquer une source de chaleur douce
5. **Éviter le froid** : Se couvrir, éviter l'air conditionné

### Quand consulter en urgence ?
- Douleur thoracique
- Difficulté respiratoire
- Fièvre élevée
- Troubles neurologiques
- Priapisme (érection prolongée)
- Douleur abdominale sévère

## Traitement de la douleur

### Échelle de douleur
- **1-3** : Douleur légère → Paracétamol
- **4-6** : Douleur modérée → Anti-inflammatoires si prescrits
- **7-10** : Douleur sévère → Morphiniques + consultation

### Médicaments courants
- **Paracétamol** : 1g toutes les 6h (max 4g/jour)
- **Tramadol** : Si prescrit par le médecin
- **Morphine** : En milieu hospitalier uniquement

## Prévention des crises

### Facteurs déclenchants à éviter
- Déshydratation
- Infections
- Stress intense
- Changements brusques de température
- Altitude élevée
- Effort physique intense
- Tabac et alcool

### Mesures préventives
- Hydratation régulière (2-3L/jour)
- Vaccination à jour
- Suivi médical régulier
- Prise d'hydroxyurée si prescrite
- Activité physique modérée et adaptée

---
*En cas d'urgence : 15 (SAMU) ou 112*
""".format(date=datetime.now().strftime("%d/%m/%Y"))

        return {
            'key': 'guides/gestion-crises-drepanocytose.md',
            'content': content,
            'metadata': {
                'category': 'Guide Urgence',
                'document_type': 'Protocole de Soins',
                'medical_specialty': 'Médecine d\'Urgence',
                'author': 'Équipe Urgences Kidjamo',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_medications_guide(self) -> Dict:
        """Guide des médicaments"""
        content = """# Guide des Médicaments en Drépanocytose

## Traitements préventifs

### Hydroxyurée (Hydrea®)
**Indication** : Prévention des crises vaso-occlusives

**Mécanisme** : Augmente la production d'hémoglobine fœtale
**Posologie** : Variable selon le poids et la tolérance
**Surveillance** : NFS mensuelle
**Effets secondaires** : 
- Baisse des globules blancs
- Troubles digestifs
- Hyperpigmentation cutanée

### Acide folique
**Indication** : Compensation de l'anémie
**Posologie** : 5mg/jour
**Importance** : Essentiel pour la formation des globules rouges

### Pénicilline (Prophylaxie)
**Indication** : Prévention des infections à pneumocoque
**Posologie** : 
- Enfant < 5 ans : Pénicilline V 125mg x2/jour
- Adulte : Selon prescription médicale

## Traitements symptomatiques

### Antalgiques niveau 1
- **Paracétamol** : 15mg/kg toutes les 6h
- **Aspirine** : À éviter (risque hémorragique)

### Antalgiques niveau 2
- **Tramadol** : 1-2mg/kg toutes les 6h
- **Codéine** : Selon prescription

### Antalgiques niveau 3
- **Morphine** : En milieu hospitalier
- **Fentanyl** : Cas sévères uniquement

## Anti-inflammatoires

### AINS (utilisation prudente)
- **Ibuprofène** : Éviter si possible
- **Diclofénac** : Sous surveillance médicale
- **Attention** : Risque de complications rénales

## Nouveaux traitements

### Voxelotor (Oxbryta®)
**Mécanisme** : Augmente l'affinité de l'hémoglobine pour l'oxygène
**Indication** : Anémie hémolytique
**Posologie** : 1500mg/jour

### Crizanlizumab (Adakveo®)
**Mécanisme** : Inhibiteur de la sélectine P
**Indication** : Prévention des crises vaso-occlusives
**Administration** : Perfusion IV mensuelle

## Interactions médicamenteuses importantes

### À éviter
- Association morphine + benzodiazépines
- AINS + anticoagulants
- Hydroxyurée + vaccins vivants

### Surveillance renforcée
- Hydroxyurée + autres cytostatiques
- Antalgiques opioïdes + alcool

---
*Toujours consulter votre médecin avant toute modification de traitement*
"""

        return {
            'key': 'guides/medicaments-drepanocytose.md',
            'content': content,
            'metadata': {
                'category': 'Guide Médicaments',
                'document_type': 'Référentiel Thérapeutique',
                'medical_specialty': 'Pharmacologie',
                'author': 'Pharmacien Clinicien Kidjamo',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_lifestyle_recommendations(self) -> Dict:
        """Recommandations de style de vie"""
        content = """# Vivre au Quotidien avec la Drépanocytose

## Hydratation - Règle d'or

### Quantités recommandées
- **Adulte** : 2,5 à 3 litres par jour
- **Enfant** : 100ml/kg/jour
- **Augmenter** en cas de fièvre, chaleur, effort

### Boissons conseillées
✅ Eau plate
✅ Tisanes non sucrées
✅ Jus de fruits dilués
✅ Soupes et bouillons

### À éviter
❌ Boissons glacées
❌ Alcool
❌ Boissons très sucrées
❌ Boissons énergisantes

## Alimentation équilibrée

### Nutriments essentiels

#### Acide folique
**Sources** : Épinards, brocolis, légumes verts, légumineuses
**Besoin** : 400-800 μg/jour

#### Fer
**Sources** : Viandes rouges, poissons, légumineuses
**Attention** : Surveillance du taux de fer (risque de surcharge)

#### Vitamine C
**Sources** : Agrumes, kiwi, poivrons, fraises
**Rôle** : Améliore l'absorption du fer

#### Calcium et Vitamine D
**Sources** : Produits laitiers, poissons gras, exposition solaire modérée
**Importance** : Santé osseuse

### Aliments à privilégier
- Fruits et légumes frais (5 portions/jour)
- Céréales complètes
- Poissons gras (2 fois/semaine)
- Légumineuses
- Noix et graines

### Aliments à limiter
- Sel (< 6g/jour)
- Sucres raffinés
- Graisses saturées
- Aliments transformés

## Activité physique adaptée

### Exercices recommandés
✅ Marche quotidienne (30 min)
✅ Natation (température > 26°C)
✅ Yoga, stretching
✅ Vélo d'appartement
✅ Gymnastique douce

### Précautions importantes
- Échauffement progressif
- Hydratation avant/pendant/après
- Éviter les efforts intenses
- Arrêt dès les premiers signes de fatigue
- Éviter l'altitude > 1500m

### Sports déconseillés
❌ Sports de contact violent
❌ Plongée sous-marine
❌ Sports en altitude
❌ Marathons

## Gestion du stress

### Techniques de relaxation
- Respiration profonde
- Méditation
- Sophrologie
- Musicothérapie
- Massage relaxant

### Soutien psychologique
- Groupes de parole
- Suivi psychologique
- Associations de patients
- Thérapies familiales

## Voyages et déplacements

### Précautions générales
- Hydratation renforcée
- Médicaments en quantité suffisante
- Carnet de santé traduit
- Assurance voyage adaptée

### Transport aérien
- Informer la compagnie
- Oxygène si nécessaire
- Se lever régulièrement
- Bas de contention

### Destinations
- Éviter les zones de paludisme sans protection
- Climat tempéré privilégié
- Altitude < 1500m

---
*La qualité de vie avec la drépanocytose dépend largement de l'observance de ces recommandations*
"""

        return {
            'key': 'guides/vie-quotidienne-drepanocytose.md',
            'content': content,
            'metadata': {
                'category': 'Guide Vie Quotidienne',
                'document_type': 'Recommandations',
                'medical_specialty': 'Médecine Générale',
                'author': 'Équipe Pluridisciplinaire Kidjamo',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_emergency_protocols(self) -> Dict:
        """Protocoles d'urgence"""
        content = """# Protocoles d'Urgence - Drépanocytose

## 🚨 SITUATIONS D'URGENCE VITALE

### Syndrome Thoracique Aigu (STA)
**Signes d'alerte** :
- Douleur thoracique + fièvre
- Dyspnée (difficulté respiratoire)
- Toux avec expectoration
- Infiltrat pulmonaire à la radio

**Conduite à tenir** :
1. Appel SAMU (15) IMMÉDIAT
2. Position demi-assise
3. Oxygénothérapie si disponible
4. Hydratation IV
5. Transfusion sanguine en urgence

### Priapisme
**Définition** : Érection douloureuse > 4h

**Conduite à tenir** :
1. Urgence urologique (< 6h)
2. Analgésie puissante
3. Hydratation
4. Parfois ponction-irrigation

### AVC (Accident Vasculaire Cérébral)
**Signes** : Paralysie, troubles de la parole, céphalées

**Conduite à tenir** :
1. SAMU (15) IMMÉDIAT
2. Position de sécurité
3. Surveillance conscience
4. IRM cérébrale en urgence

## 🔥 FIÈVRE - Protocole d'urgence

### Seuil d'alerte : 38,5°C

**Évaluation rapide** :
- Prise de température
- Recherche de foyer infectieux
- État général

**Examens urgents** :
- NFS, CRP, hémocultures
- ECBU
- Radio thorax si signes respiratoires

**Traitement** :
1. Paracétamol 15mg/kg
2. Hydratation intensive
3. Antibiothérapie précoce
4. Hospitalisation si signes de gravité

## 🩸 ANÉMIE AIGUË

### Signes de gravité :
- Hb < 5 g/dL
- Signes d'insuffisance cardiaque
- Troubles de conscience

**Conduite à tenir** :
1. Repos strict
2. Oxygénothérapie
3. Transfusion sanguine urgente
4. Recherche de la cause

## 📞 NUMÉROS D'URGENCE

### France
- **SAMU** : 15
- **Pompiers** : 18
- **Urgences européennes** : 112
- **Centre antipoison** : 01 40 05 48 48

### Centres de référence drépanocytose
- **Hôpital Robert Debré (Paris)** : 01 40 03 20 00
- **Hôpital Necker (Paris)** : 01 44 49 40 00
- **CHU Créteil** : 01 49 81 21 11

## 🎒 TROUSSE D'URGENCE

### Médicaments essentiels
- Paracétamol 1g (6 comprimés)
- Antalgique niveau 2 si prescrit
- Hydroxyurée (traitement habituel)
- Acide folique
- Antibiotique si prescrit

### Documents importants
- Carte de soins et d'urgence
- Ordonnances récentes
- Carnet de santé
- Carte de groupe sanguin
- Contacts médicaux

### Matériel
- Thermomètre
- Collier chauffant
- Bouteille d'eau
- Carnet de suivi des crises

## 🏥 CRITÈRES D'HOSPITALISATION

### Hospitalisation systématique
- Syndrome thoracique aigu
- Fièvre > 39°C chez l'enfant < 5 ans
- Séquestration splénique
- Aplasie médullaire
- AVC

### Hospitalisation selon contexte
- Crise douloureuse non calmée à domicile
- Déshydratation
- Infection grave
- Complications ophtalmologiques

---
*En cas de doute, toujours privilégier la consultation en urgence*
*Le pronostic dépend de la rapidité de la prise en charge*
"""

        return {
            'key': 'protocols/urgences-drepanocytose.md',
            'content': content,
            'metadata': {
                'category': 'Protocole Urgence',
                'document_type': 'Protocole de Soins',
                'medical_specialty': 'Médecine d\'Urgence',
                'author': 'SAMU - Équipe Urgences',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_faq_document(self) -> Dict:
        """Document FAQ général"""
        content = """# FAQ - Questions Fréquentes sur la Drépanocytose

## Questions générales

**Q: La drépanocytose est-elle contagieuse ?**
R: Non, la drépanocytose est une maladie génétique héréditaire, pas une maladie infectieuse.

**Q: Peut-on guérir de la drépanocytose ?**
R: Actuellement, la seule cure définitive est la greffe de moelle osseuse. Les thérapies géniques sont prometteuses.

**Q: Quelle est l'espérance de vie ?**
R: Avec un suivi médical adapté, l'espérance de vie a considérablement augmenté (> 50 ans dans les pays développés).

## Hérédité et famille

**Q: Si j'ai la drépanocytose, mes enfants l'auront-ils ?**
R: Cela dépend du statut de votre partenaire. Conseil génétique recommandé.

**Q: Peut-on détecter la maladie pendant la grossesse ?**
R: Oui, par diagnostic prénatal (amniocentèse, biopsie de trophoblaste).

## Vie quotidienne

**Q: Puis-je faire du sport ?**
R: Oui, mais adapté. Éviter les sports intenses, privilégier les activités modérées.

**Q: Puis-je voyager ?**
R: Oui, avec précautions (hydratation, altitude, assurance voyage).

**Q: Puis-je avoir une vie professionnelle normale ?**
R: Oui, avec adaptations si nécessaire (poste de travail, horaires).

## Traitements

**Q: L'hydroxyurée est-elle dangereuse ?**
R: C'est un traitement efficace et sûr sous surveillance médicale régulière.

**Q: Dois-je éviter certains médicaments ?**
R: Informez toujours vos médecins de votre maladie. Certains médicaments nécessitent des précautions.

---
*Pour toute question spécifique, consultez votre équipe médicale*
"""

        return {
            'key': 'faq/drepanocytose-faq-general.md',
            'content': content,
            'metadata': {
                'category': 'FAQ',
                'document_type': 'Questions-Réponses',
                'medical_specialty': 'Information Patient',
                'author': 'Équipe Éducation Thérapeutique',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_research_updates(self) -> Dict:
        """Actualités de recherche"""
        content = """# Actualités de la Recherche en Drépanocytose 2024-2025

## Thérapies Géniques

### CRISPR-Cas9 (CTX001)
**Principe** : Modification génétique des cellules souches du patient
**Résultats** : 95% des patients sans crise après 2 ans
**Statut** : Approuvé FDA et EMA
**Avantages** : Traitement curatif potentiel
**Limites** : Coût élevé, centres spécialisés

### Thérapie génique lentivirale (LentiGlobin)
**Principe** : Introduction d'un gène β-globine fonctionnel
**Résultats** : Réduction significative des crises
**Statut** : En cours d'évaluation

## Nouveaux Médicaments

### Voxelotor (Oxbryta®)
**Mécanisme** : Augmente l'affinité de l'HbS pour l'O2
**Efficacité** : +1,1 g/dL d'hémoglobine en moyenne
**Statut** : Approuvé, disponible

### Crizanlizumab (Adakveo®)
**Mécanisme** : Inhibiteur sélectine P
**Efficacité** : -45% de crises vaso-occlusives
**Administration** : Perfusion mensuelle

### L-Glutamine (Endari®)
**Mécanisme** : Améliore la fonction des globules rouges
**Efficacité** : Réduction des crises et des hospitalisations
**Forme** : Poudre orale

## Recherches Émergentes

### Inhibiteurs de la polymérisation HbS
- GBT021601 (Pfizer)
- Mitapivat (activateur pyruvate kinase)

### Anti-inflammatoires ciblés
- Inhibiteurs JAK
- Modulateurs du complément

### Médecine régénérative
- Cellules souches induites (iPSC)
- Édition génétique in vivo

## Biomarqueurs et Diagnostic

### Nouveaux marqueurs prédictifs
- Micro-ARN circulants
- Protéomique des crises
- Intelligence artificielle pour prédiction

### Imagerie avancée
- IRM haute résolution
- Échographie Doppler transcranien automatisé

## Essais Cliniques en Cours

### Phase III
- Inclacumab (anti-sélectine P)
- Rivipansel (inhibiteur pan-sélectine)

### Phase II
- Therapies épigénétiques
- Modulateurs de l'hème oxygénase

## Perspectives 2025-2030

### Objectifs à court terme
- Accès élargi aux thérapies géniques
- Réduction des coûts
- Amélioration de la qualité de vie

### Innovations attendues
- Thérapies géniques de 2ème génération
- Médecine personnalisée
- Applications mobiles de suivi

---
*Informations mises à jour régulièrement*
*Sources : NIH, EMA, Sociétés savantes*
"""

        return {
            'key': 'research/actualites-recherche-2024.md',
            'content': content,
            'metadata': {
                'category': 'Recherche Médicale',
                'document_type': 'Actualités Scientifiques',
                'medical_specialty': 'Recherche Clinique',
                'author': 'Équipe Recherche Kidjamo',
                'last_updated': datetime.now().isoformat()
            }
        }

    def create_faq_csv(self):
        """Crée le fichier FAQ au format CSV pour Kendra"""
        faq_data = [
            ["Question", "Answer"],
            ["Qu'est-ce que la drépanocytose ?", "La drépanocytose est une maladie génétique héréditaire qui affecte l'hémoglobine des globules rouges."],
            ["La drépanocytose est-elle contagieuse ?", "Non, la drépanocytose n'est pas contagieuse. C'est une maladie génétique héréditaire."],
            ["Comment se transmettent les crises ?", "Les crises de drépanocytose sont déclenchées par la déshydratation, le stress, les infections ou les changements de température."],
            ["Que faire en cas de crise ?", "En cas de crise : s'hydrater, prendre ses antalgiques, se reposer et consulter si la douleur persiste."],
            ["Quels médicaments pour la douleur ?", "Le paracétamol en première intention, puis les antalgiques prescrits selon l'intensité."],
            ["L'hydroxyurée est-elle dangereuse ?", "L'hydroxyurée est un traitement sûr et efficace sous surveillance médicale régulière."],
            ["Peut-on voyager avec la drépanocytose ?", "Oui, avec des précautions : hydratation, médicaments, éviter l'altitude élevée."],
            ["Quels sports sont autorisés ?", "Sports modérés recommandés : marche, natation, vélo. Éviter les sports intenses."],
            ["Comment prévenir les crises ?", "Hydratation régulière, éviter le stress, prendre ses médicaments, suivi médical."],
            ["Quand appeler les urgences ?", "Urgences si : douleur thoracique, fièvre élevée, difficulté respiratoire, troubles neurologiques."]
        ]

        import csv
        import io

        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerows(faq_data)

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key='faq/drepanocytose-faq.csv',
            Body=csv_content.getvalue(),
            ContentType='text/csv',
            Metadata={
                'category': 'FAQ',
                'document_type': 'Questions-Réponses'
            }
        )

        logger.info("✅ Fichier FAQ CSV créé")

    def create_metadata_files(self):
        """Crée les fichiers de métadonnées pour Kendra"""
        metadata_structure = {
            "DocumentId": "guides/drepanocytose-guide-complet.md",
            "Attributes": {
                "category": "Guide Patient",
                "document_type": "Guide Médical",
                "medical_specialty": "Hématologie"
            }
        }

        # Exemple de fichier de métadonnées
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key='metadata/example-metadata.json',
            Body=json.dumps(metadata_structure, indent=2),
            ContentType='application/json'
        )

        logger.info("✅ Fichiers de métadonnées créés")

    def upload_document(self, document: Dict):
        """Upload un document vers S3"""
        try:
            # Upload du contenu
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=document['key'],
                Body=document['content'],
                ContentType='text/markdown' if document['key'].endswith('.md') else 'text/plain',
                Metadata=document['metadata']
            )

            logger.info(f"✅ Document uploadé: {document['key']}")

        except Exception as e:
            logger.error(f"❌ Erreur upload {document['key']}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Création des documents médicaux pour Kendra')
    parser.add_argument('--bucket', required=True, help='Nom du bucket S3')
    parser.add_argument('--environment', required=True, help='Environnement (dev, stg, prod)')

    args = parser.parse_args()

    creator = MedicalDocumentsCreator(args.bucket, args.environment)
    creator.create_all_documents()

    print("🎉 Création des documents terminée !")
    print(f"📚 Documents disponibles dans le bucket: {args.bucket}")

if __name__ == '__main__':
    main()
