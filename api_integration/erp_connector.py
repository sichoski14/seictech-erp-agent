import requests
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
import time

class ERPConnector:
    def __init__(self, config):
        self.base_url = config.ERP_API_URL
        self.api_key = config.ERP_API_KEY
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def fetch_inventory_data(self) -> pd.DataFrame:
        """Busca dados de inventário do ERP"""
        try:
            response = requests.get(
                f'{self.base_url}/inventory',
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return pd.DataFrame(response.json()['data'])
        except Exception as e:
            print(f"Error fetching inventory: {e}")
            return pd.DataFrame()
    
    def fetch_sales_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Busca dados de vendas do ERP"""
        try:
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            response = requests.get(
                f'{self.base_url}/sales',
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return pd.DataFrame(response.json()['data'])
        except Exception as e:
            print(f"Error fetching sales: {e}")
            return pd.DataFrame()
    
    def fetch_operational_data(self) -> pd.DataFrame:
        """Busca dados operacionais"""
        try:
            endpoints = ['operators', 'production', 'payments']
            data = {}
            
            for endpoint in endpoints:
                response = requests.get(
                    f'{self.base_url}/{endpoint}',
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                data[endpoint] = response.json()['data']
            
            return pd.DataFrame(data)
        except Exception as e:
            print(f"Error fetching operational data: {e}")
            return pd.DataFrame()
    
    def send_stock_update(self, product_id: str, quantity: int, location: str):
        """Envia atualização de estoque para o ERP"""
        payload = {
            'product_id': product_id,
            'quantity': quantity,
            'location': location,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/inventory/update',
                headers=self.headers,
                json=payload,
                timeout=30
            )
            return response.json()
        except Exception as e:
            print(f"Error updating stock: {e}")
            return None
    
    def sync_data_periodically(self, interval_seconds: int = 300):
        """Sincroniza dados periodicamente"""
        while True:
            print(f"[{datetime.now()}] Starting data synchronization...")
            
            # Sincroniza inventário
            inventory = self.fetch_inventory_data()
            
            # Sincroniza vendas (últimos 7 dias)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            sales = self.fetch_sales_data(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            print(f"Synced {len(inventory)} inventory items and {len(sales)} sales records")
            time.sleep(interval_seconds)