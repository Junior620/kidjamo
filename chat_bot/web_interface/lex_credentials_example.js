/*
 * Configuration Lex pour environnement de production
 * Remplacez ce fichier par vos vraies credentials dans un environnement sécurisé
 */

// Option 1: Utilisation avec Cognito Identity Pool (RECOMMANDÉ pour production)
const LEX_PRODUCTION_CONFIG = {
    region: 'eu-west-1',
    botId: 'HPYX4OKHYE',
    botAliasId: 'AS7DAYY4IY',
    localeId: 'fr_FR',

    // ID du pool d'identité Cognito (à créer)
    identityPoolId: 'eu-west-1:your-cognito-identity-pool-id',

    // Configuration optionnelle pour l'authentification
    userPoolId: 'eu-west-1_yourUserPool',
    userPoolWebClientId: 'your-client-id'
};

// Option 2: Credentials temporaires (pour test uniquement)
const LEX_TEST_CONFIG = {
    region: 'eu-west-1',
    botId: 'HPYX4OKHYE',
    botAliasId: 'AS7DAYY4IY',
    localeId: 'fr_FR',

    // ⚠️ NE JAMAIS utiliser en production
    accessKeyId: 'VOTRE_ACCESS_KEY_TEMPORAIRE',
    secretAccessKey: 'VOTRE_SECRET_KEY_TEMPORAIRE',
    sessionToken: 'VOTRE_SESSION_TOKEN_TEMPORAIRE'
};

// Instructions pour activer Lex en production :
/*
1. Créer un Cognito Identity Pool dans AWS Console
2. Configurer les permissions IAM pour lexv2:RecognizeText
3. Remplacer LEX_CONFIG dans votre HTML avec LEX_PRODUCTION_CONFIG
4. Tester la connexion

Commandes AWS CLI pour créer l'Identity Pool :

aws cognito-identity create-identity-pool \
    --identity-pool-name "kidjamo-chatbot-users" \
    --allow-unauthenticated-identities \
    --region eu-west-1

aws iam create-role \
    --role-name "kidjamo-cognito-unauthenticated" \
    --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
    --role-name "kidjamo-cognito-unauthenticated" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonLexRunBotsOnly"
*/
