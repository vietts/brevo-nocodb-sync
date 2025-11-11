#!/usr/bin/env python3

"""
Script di sincronizzazione Brevo <-> NocoDB
Importa i dati delle campagne da Brevo e li sincronizza in NocoDB
"""

import requests
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import time
import logging

# Carica configurazione da file
CONFIG_FILE = '/Users/francesconguyen/brevo-nocodb-config.json'
with open(CONFIG_FILE, 'r') as f:
    CONFIG = json.load(f)

# Sovrascrivi con variabili d'ambiente se disponibili
CONFIG['brevo']['api_key'] = os.getenv("BREVO_API_KEY", CONFIG['brevo']['fallback_api_key'])
CONFIG['nocodb']['api_key'] = os.getenv("NOCODB_API_KEY", CONFIG['nocodb']['fallback_api_key'])

# Configura il logger
LOG_FILE = '/tmp/brevo-nocodb-sync-executions.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BrevoClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = CONFIG['brevo']['api_url']
        self.headers = {
            'api-key': api_key,
            'Content-Type': 'application/json'
        }

    def get_email_campaigns(self) -> List[Dict]:
        """Recupera tutte le campagne email da Brevo con statistiche globali"""
        print("📧 Recuperando campagne da Brevo...")

        try:
            url = f"{self.base_url}/emailCampaigns"
            params = {"statistics": "globalStats"}
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            campaigns = response.json().get('campaigns', [])
            print(f"✅ Trovate {len(campaigns)} campagne")
            return campaigns
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore nel recupero campagne Brevo: {e}")
            raise

    def get_campaign_details(self, campaign_id: int) -> Optional[Dict]:
        """Ottiene i dettagli di una campagna specifica"""
        try:
            url = f"{self.base_url}/emailCampaigns/{campaign_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Errore nel recupero dettagli campagna {campaign_id}: {e}")
            return None


class NocODBClient:
    def __init__(self, api_key: str, table_url: str):
        self.api_key = api_key
        self.table_url = table_url
        # Usa Authorization: Bearer (xc-auth non funziona con questo token)
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def get_existing_campaign_ids(self) -> set:
        """Recupera gli ID delle campagne già sincronizzate"""
        print("📋 Recuperando IDs delle campagne già sincronizzate...")

        try:
            # Recupera tutti i record (con limite alto per essere sicuri)
            url = f"{self.table_url}?limit=1000"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                campaign_ids = {str(record.get('id_campagna')) for record in data.get('list', [])}
                print(f"✅ Trovate {len(campaign_ids)} campagne già sincronizzate")
                return campaign_ids
            else:
                print(f"⚠️  Non posso recuperare i record esistenti (status {response.status_code})")
                return set()
        except Exception as e:
            print(f"⚠️  Errore nel recupero record: {e}")
            return set()

    def get_existing_campaigns_dict(self) -> Dict:
        """Recupera tutti i record esistenti come dict con id_campagna come chiave"""
        print("📋 Recuperando campagne dal database...")

        try:
            # Recupera tutti i record (con limite alto per essere sicuri)
            url = f"{self.table_url}?limit=1000"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Crea un dict con id_campagna come chiave
                campaigns_dict = {
                    str(record.get('id_campagna')): record
                    for record in data.get('list', [])
                }
                print(f"✅ Trovate {len(campaigns_dict)} campagne nel database")
                return campaigns_dict
            else:
                print(f"⚠️  Non posso recuperare i record esistenti (status {response.status_code})")
                return {}
        except Exception as e:
            print(f"⚠️  Errore nel recupero record: {e}")
            return {}

    def verify_table(self) -> bool:
        """Verifica che la tabella sia accessibile"""
        print("🔍 Verificando accesso alla tabella NocoDB...")

        try:
            # Prova con il token nel header
            response = requests.get(self.table_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                print(f"✅ Tabella accessibile (via header)")
                return True
            elif response.status_code == 401:
                # Prova con token come query parameter
                print("⚠️  Token nel header non valido, provo con query parameter...")
                url_with_token = f"{self.table_url}?nc={self.api_key}"
                response = requests.get(url_with_token, timeout=10)

                if response.status_code == 200:
                    # Aggiorna l'URL per i prossimi inserimenti
                    self.table_url = url_with_token
                    print(f"✅ Tabella accessibile (via query parameter)")
                    return True
                else:
                    print(f"❌ Errore di accesso: {response.status_code}")
                    return False
            else:
                print(f"❌ Errore di accesso: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore nel verificare la tabella: {e}")
            return False

    def update_record(self, record_id, record_data: Dict) -> bool:
        """Aggiorna un record esistente in NocoDB"""
        try:
            # L'endpoint per update è: /tables/{table_id}/records/{record_id}
            # record_id è il valore del campo 'Id' di NocoDB
            url = f"{self.table_url}/{record_id}"
            response = requests.patch(url, headers=self.headers, json=record_data, timeout=10)

            if response.status_code in [200, 201]:
                return True
            else:
                print(f"  ⚠️  Errore nell'aggiornamento record {record_id}: {response.status_code} - {response.text[:100]}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Errore nell'aggiornamento record: {e}")
            return False

    def insert_records(self, records: List[Dict]) -> None:
        """Inserisce i record nella tabella"""
        print(f"💾 Inserendo {len(records)} campagne in NocoDB...")

        try:
            for idx, record in enumerate(records, 1):
                try:
                    # Invia il record così com'è (NocoDB accetta None per valori vuoti)
                    response = requests.post(self.table_url, headers=self.headers, json=record, timeout=10)

                    if response.status_code in [200, 201]:
                        print(f"  ✅ [{idx}/{len(records)}] {record.get('nome_campagna', 'N/A')} (NEW)")
                    elif response.status_code == 403:
                        # Prova senza i campi Currency e calcolati
                        simplified_record = {
                            'id_campagna': record.get('id_campagna'),
                            'nome_campagna': record.get('nome_campagna'),
                            'data_creazione': record.get('data_creazione'),
                            'data_invio': record.get('data_invio'),
                            'stato': record.get('stato'),
                            'num_contatti': record.get('num_contatti'),
                        }
                        response = requests.post(self.table_url, headers=self.headers, json=simplified_record, timeout=10)

                        if response.status_code in [200, 201]:
                            print(f"  ✅ [{idx}/{len(records)}] {record.get('nome_campagna', 'N/A')} (NEW - formato semplificato)")
                        else:
                            print(f"  ⚠️  [{idx}/{len(records)}] {record.get('nome_campagna', 'N/A')} - Errore: {response.status_code}")
                            # Debug: stampa il primo errore 403
                            if idx == 2:
                                print(f"     Debug response: {response.text[:200]}")
                    else:
                        print(f"  ⚠️  [{idx}/{len(records)}] {record.get('nome_campagna', 'N/A')} - Errore: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"  ❌ [{idx}/{len(records)}] Errore inserimento: {e}")

                time.sleep(0.2)  # Rate limiting

        except Exception as e:
            print(f"❌ Errore nell'inserimento dati: {e}")
            raise

    def sync_records(self, new_records: List[Dict], updates: List[tuple]) -> None:
        """Sincronizza i record: inserisce i nuovi e aggiorna gli esistenti"""
        # Inserisce i nuovi record
        if new_records:
            self.insert_records(new_records)

        # Aggiorna i record esistenti
        if updates:
            print(f"🔄 Aggiornando {len(updates)} campagne in NocoDB...")
            for idx, (record_id, record_data) in enumerate(updates, 1):
                try:
                    success = self.update_record(record_id, record_data)
                    if success:
                        print(f"  ✅ [{idx}/{len(updates)}] {record_data.get('nome_campagna', 'N/A')} (UPDATE)")
                    else:
                        print(f"  ⚠️  [{idx}/{len(updates)}] {record_data.get('nome_campagna', 'N/A')} - Errore nell'aggiornamento")
                except Exception as e:
                    print(f"  ❌ [{idx}/{len(updates)}] Errore aggiornamento: {e}")

                time.sleep(0.2)  # Rate limiting


def map_brevo_status(status: str) -> str:
    """Mappa lo stato da Brevo ai valori standard"""
    status_map = {
        'draft': 'Draft',
        'scheduled': 'Scheduled',
        'queued': 'Sending',
        'sending': 'Sending',
        'sent': 'Sent',
        'paused': 'Paused',
        'failed': 'Failed'
    }
    return status_map.get(status, status)


def transform_campaign_data(campaign: Dict) -> Dict:
    """Trasforma i dati della campagna Brevo nel formato NocoDB"""

    stats_root = campaign.get('statistics', {})
    global_stats = stats_root.get('globalStats', {}) or {}

    # Campi corretti da Brevo API
    delivered = int(global_stats.get('delivered', 0) or 0)
    unique_views = int(global_stats.get('uniqueViews', 0) or 0)
    unique_clicks = int(global_stats.get('uniqueClicks', 0) or 0)

    # Calcola tassi percentuali basati su delivered
    base = delivered if delivered > 0 else 1
    tasso_apertura_pct = round((unique_views / base) * 100, 2) if delivered > 0 else 0
    tasso_clic_pct = round((unique_clicks / base) * 100, 2) if delivered > 0 else 0

    # Estrai sender direttamente da Brevo (campo 'sender' della campagna)
    # Brevo ritorna il valore di sender come dict con i dettagli del mittente
    sender_field = campaign.get('sender')
    sender = None

    if sender_field:
        if isinstance(sender_field, dict):
            # Prova email, poi name, poi l'intero dict come string
            sender = sender_field.get('email') or sender_field.get('name') or sender_field.get('senderName') or str(sender_field)
        else:
            # È una stringa
            sender = str(sender_field)

    # Mappa al formato della tabella NocoDB
    return {
        'id_campagna': str(campaign.get('id', '')),
        'nome_campagna': campaign.get('name', 'N/A'),
        'data_creazione': campaign.get('createdAt'),
        'data_invio': campaign.get('scheduledAt'),
        'data_fine': None,
        'stato': map_brevo_status(campaign.get('status', 'unknown')),
        'num_contatti': delivered,
        'tasso_apertura_pct': tasso_apertura_pct,
        'tasso_clic_pct': tasso_clic_pct,
        'num_conversioni': None,
        'budget': None,
        'roi_pct': None,
        'note': campaign.get('subject', ''),
        'sender': sender,
        'url_campagna': f"https://app.brevo.com/campaigns/{campaign.get('id', '')}"
    }


def sync_brevo_to_nocodb():
    """Funzione principale di sincronizzazione"""
    logger.info("="*80)
    logger.info("🚀 Avviando sincronizzazione Brevo -> NocoDB")
    print("🚀 Avviando sincronizzazione Brevo -> NocoDB\n")

    try:
        # 1. Ottenere le campagne da Brevo
        brevo = BrevoClient(CONFIG['brevo']['api_key'])
        all_campaigns = brevo.get_email_campaigns()

        if not all_campaigns:
            logger.warning("⚠️  Nessuna campagna trovata in Brevo")
            print("⚠️  Nessuna campagna trovata in Brevo")
            return

        logger.info(f"✅ Trovate {len(all_campaigns)} campagne da Brevo")

        # 2. Connettere a NocoDB
        table_id = CONFIG['nocodb']['table_id']
        table_url = f"{CONFIG['nocodb']['api_url']}/tables/{table_id}/records"
        nocodb = NocODBClient(CONFIG['nocodb']['api_key'], table_url)

        # 3. Verificare accesso alla tabella
        if not nocodb.verify_table():
            logger.error("❌ Impossibile accedere alla tabella NocoDB")
            print("❌ Impossibile accedere alla tabella NocoDB")
            exit(1)

        # 4. Recuperare tutti i record esistenti dal database (come dict)
        existing_campaigns = nocodb.get_existing_campaigns_dict()

        # 5. Separare le campagne da Brevo in nuove e da aggiornare:
        #    - NUOVE: non presenti in existing_campaigns
        #    - AGGIORNAMENTO: presenti in existing_campaigns E status ≠ 'Sent'
        new_campaigns = []
        campaigns_to_update = []

        for campaign in all_campaigns:
            campaign_id = str(campaign.get('id'))
            if campaign_id not in existing_campaigns:
                # Campagna nuova
                new_campaigns.append(campaign)
            elif campaign.get('status') != 'sent':
                # Campagna esistente ma non in stato "Sent" → aggiornamento necessario
                campaigns_to_update.append((campaign_id, campaign))

        # Se nulla da fare, esci
        if not new_campaigns and not campaigns_to_update:
            logger.info(f"ℹ️  Nessuna campagna da sincronizzare")
            logger.info(f"📊 Tutte le {len(all_campaigns)} campagne sono già sincronizzate e in stato 'Sent'")
            print("\n✨ Nessuna campagna da sincronizzare")
            print(f"📊 Tutte le {len(all_campaigns)} campagne sono già sincronizzate e in stato 'Sent'")
            return

        # Log delle operazioni
        if new_campaigns:
            logger.info(f"📥 Nuove campagne da inserire: {len(new_campaigns)}")
            print(f"\n📥 Nuove campagne: {len(new_campaigns)}")

        if campaigns_to_update:
            logger.info(f"🔄 Campagne da aggiornare (non in stato 'Sent'): {len(campaigns_to_update)}")
            print(f"🔄 Campagne da aggiornare: {len(campaigns_to_update)}")

        total = len(new_campaigns) + len(campaigns_to_update)
        logger.info(f"📥 Totale operazioni: {total} su {len(all_campaigns)}")
        print(f"📥 Totale operazioni: {total} su {len(all_campaigns)}")

        # 6. Trasformare i dati e sincronizzare
        # Trasforma i nuovi record
        new_records = [transform_campaign_data(campaign) for campaign in new_campaigns]

        # Trasforma i record da aggiornare (mantenendo record_id)
        # Nota: NocoDB usa 'Id' (con I maiuscola) come campo identificativo
        updates = [
            (existing_campaigns[campaign_id]['Id'], transform_campaign_data(campaign))
            for campaign_id, campaign in campaigns_to_update
        ]

        # Sincronizza (insert + update)
        nocodb.sync_records(new_records, updates)

        logger.info(f"✨ Sincronizzazione completata con SUCCESSO")
        logger.info(f"📊 {len(new_campaigns)} nuove campagne sincronizzate")
        logger.info(f"🔄 {len(campaigns_to_update)} campagne aggiornate")
        logger.info(f"📈 Totale campagne nel database: {len(all_campaigns)}")
        logger.info("STATUS: ✅ OK")
        logger.info("="*80 + "\n")

        print("\n✨ Sincronizzazione completata!")
        print(f"📊 {len(new_campaigns)} nuove campagne sincronizzate")
        print(f"🔄 {len(campaigns_to_update)} campagne aggiornate")
        print(f"📈 Totale campagne nel database: {len(all_campaigns)}")

    except Exception as e:
        logger.error(f"❌ Sincronizzazione fallita: {e}")
        logger.error("STATUS: ❌ FALLITO")
        logger.error("="*80 + "\n")
        print(f"\n❌ Sincronizzazione fallita: {e}")
        exit(1)


if __name__ == '__main__':
    sync_brevo_to_nocodb()
