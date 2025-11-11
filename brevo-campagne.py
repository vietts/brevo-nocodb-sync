#!/usr/bin/env python3

"""
Script per generare CSV delle campagne Brevo
Sincronizza i dati da Brevo a un file CSV o direttamente a NocoDB
"""

import os
import json
import requests
import csv
from datetime import datetime

# Carica configurazione
CONFIG_FILE = '/Users/francesconguyen/brevo-nocodb-config.json'
with open(CONFIG_FILE, 'r') as f:
    CONFIG = json.load(f)

# Configurazione
BREVO_API_KEY = os.getenv("BREVO_API_KEY", CONFIG['brevo']['fallback_api_key'])
BREVO_API_URL = CONFIG['brevo']['api_url']
CSV_OUTPUT = CONFIG['csv']['output_file']


class BrevoClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BREVO_API_URL
        self.headers = {
            'api-key': api_key,
            'Content-Type': 'application/json'
        }

    def get_email_campaigns(self):
        """Recupera tutte le campagne email da Brevo (con globalStats)"""
        print("📧 Recuperando campagne da Brevo...")

        try:
            url = f"{self.base_url}/emailCampaigns"
            # parametro statistics obbligatorio per avere i globalStats
            params = {"statistics": "globalStats"}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            campaigns = data.get('campaigns', [])
            print(f"✅ Trovate {len(campaigns)} campagne")
            return campaigns
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore nel recupero campagne Brevo: {e}")
            raise

    def get_campaign_details(self, campaign_id: int):
        """Recupera i dettagli completi di una campagna"""
        try:
            url = f"{self.base_url}/emailCampaigns/{campaign_id}"
            params = {"statistics": "globalStats"}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Errore nel recupero dettagli campagna {campaign_id}: {e}")
            return None


def map_brevo_status(status: str) -> str:
    """Mappa lo stato da Brevo ai valori standard"""
    status_map = {
        'draft': 'Draft',
        'scheduled': 'Scheduled',
        'queued': 'Sending',
        'sending': 'Sending',
        'sent': 'Sent',
        'paused': 'Paused',
        'failed': 'Failed',
        'inProcess': 'Sending',
        'archive': 'Archived',
        'suspended': 'Suspended',
    }
    return status_map.get(status, status)


def generate_csv():
    """Genera CSV delle campagne Brevo"""
    print("🚀 Generando CSV delle campagne Brevo\n")

    try:
        # 1. Recupera le campagne
        brevo = BrevoClient(BREVO_API_KEY)
        campaigns = brevo.get_email_campaigns()

        if not campaigns:
            print("⚠️  Nessuna campagna trovata")
            return

        # 2. Prepara i dati
        csv_file = CSV_OUTPUT
        fieldnames = CONFIG['csv']['fieldnames']

        with open(csv_file, 'w', newline='', encoding='utf-8') as f:

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for campaign in campaigns:
                # --- STATISTICHE ---
                stats_root = campaign.get('statistics', {})
                global_stats = stats_root.get('globalStats', {}) or {}

                # Campi corretti da Brevo API
                sent = int(global_stats.get('sent', 0) or 0)
                delivered = int(global_stats.get('delivered', 0) or 0)
                unique_views = int(global_stats.get('uniqueViews', 0) or 0)
                unique_clicks = int(global_stats.get('uniqueClicks', 0) or 0)
                soft_bounces = int(global_stats.get('softBounces', 0) or 0)
                hard_bounces = int(global_stats.get('hardBounces', 0) or 0)
                unsubscriptions = int(global_stats.get('unsubscriptions', 0) or 0)
                complaints = int(global_stats.get('complaints', 0) or 0)

                # Calcola tassi percentuali basati su delivered
                base = delivered if delivered > 0 else 1
                tasso_apertura_pct = round((unique_views / base) * 100, 2) if delivered > 0 else 0
                tasso_clic_pct = round((unique_clicks / base) * 100, 2) if delivered > 0 else 0

                # --- DATE ---
                created_at = campaign.get('createdAt', '')
                # scheduledAt è la data di invio pianificata
                data_invio = campaign.get('scheduledAt', '')

                row = {
                    'id_campagna': campaign.get('id', ''),
                    'nome_campagna': campaign.get('name', ''),
                    'data_creazione': created_at,
                    'data_invio': data_invio,
                    'stato': map_brevo_status(campaign.get('status', '')),
                    'sent': sent,
                    'delivered': delivered,
                    'unique_views': unique_views,
                    'unique_clicks': unique_clicks,
                    'tasso_apertura_pct': tasso_apertura_pct,
                    'tasso_clic_pct': tasso_clic_pct,
                    'soft_bounces': soft_bounces,
                    'hard_bounces': hard_bounces,
                    'unsubscriptions': unsubscriptions,
                    'complaints': complaints,
                    'note': campaign.get('subject', ''),
                    'url_campagna': f"https://app.brevo.com/campaigns/{campaign.get('id', '')}"
                }

                writer.writerow(row)

        print(f"✅ CSV generato con successo: {csv_file}")
        print(f"📊 {len(campaigns)} righe scritte")
        print(f"\n📁 File pronto per l'importazione in NocoDB")

    except Exception as e:
        print(f"❌ Errore: {e}")
        exit(1)


if __name__ == '__main__':
    generate_csv()
