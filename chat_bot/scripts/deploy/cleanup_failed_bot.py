#!/usr/bin/env python3
"""
Script de nettoyage pour supprimer le bot Lex partiellement créé
"""

import boto3
import time

def cleanup_failed_bot():
    lex_v2 = boto3.client('lexv2-models', region_name='eu-west-1')

    # ID du bot qui a échoué (d'après votre sortie)
    failed_bot_id = '6SY0PMKTNI'

    print("🧹 NETTOYAGE DU BOT LEX ÉCHOUÉ")
    print("=" * 40)

    try:
        # Vérifier le statut du bot
        response = lex_v2.describe_bot(botId=failed_bot_id)
        bot_status = response['botStatus']
        bot_name = response['botName']

        print(f"🤖 Bot trouvé: {bot_name}")
        print(f"📊 Statut: {bot_status}")

        # Supprimer la locale si elle existe
        try:
            print("🗑️ Suppression de la locale française...")
            lex_v2.delete_bot_locale(
                botId=failed_bot_id,
                botVersion='DRAFT',
                localeId='fr_FR'
            )
            print("✅ Locale supprimée")
            time.sleep(10)
        except Exception as e:
            print(f"⚠️ Locale déjà supprimée ou inexistante: {str(e)}")

        # Supprimer le bot
        print("🗑️ Suppression du bot...")
        lex_v2.delete_bot(
            botId=failed_bot_id,
            skipResourceInUseCheck=True
        )

        print("✅ Bot supprimé avec succès")
        print("🔄 Vous pouvez maintenant relancer le déploiement")

    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {str(e)}")
        if "ResourceNotFoundException" in str(e):
            print("✅ Le bot n'existe plus - nettoyage inutile")
        else:
            print("⚠️ Vous pouvez essayer de continuer le déploiement")

if __name__ == "__main__":
    cleanup_failed_bot()
