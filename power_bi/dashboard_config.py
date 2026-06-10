import requests
import json
from typing import Dict, Any, List
from datetime import datetime

class PowerBIDashboard:
    def __init__(self, config):
        self.config = config
        self.api_url = "https://api.powerbi.com/v1.0/myorg"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._get_token()}'
        }
    
    def _get_token(self):
        """Obtém token de autenticação"""
        # Implementar autenticação Azure AD
        return "your_power_bi_token"
    
    def create_dashboard_dataset(self):
        """Cria dataset no Power BI"""
        dataset_schema = {
            "name": "Retail Analytics Dashboard",
            "tables": [
                {
                    "name": "InventoryAnalysis",
                    "columns": [
                        {"name": "SKU", "dataType": "string"},
                        {"name": "ProductName", "dataType": "string"},
                        {"name": "Quantity", "dataType": "int64"},
                        {"name": "StockStatus", "dataType": "string"},
                        {"name": "Location", "dataType": "string"},
                        {"name": "Timestamp", "dataType": "DateTime"}
                    ]
                },
                {
                    "name": "SalesPerformance",
                    "columns": [
                        {"name": "Date", "dataType": "DateTime"},
                        {"name": "Revenue", "dataType": "double"},
                        {"name": "Transactions", "dataType": "int64"},
                        {"name": "AvgTicket", "dataType": "double"},
                        {"name": "ActiveOperators", "dataType": "int64"}
                    ]
                },
                {
                    "name": "FinancialMetrics",
                    "columns": [
                        {"name": "MetricName", "dataType": "string"},
                        {"name": "MetricValue", "dataType": "double"},
                        {"name": "Date", "dataType": "DateTime"}
                    ]
                },
                {
                    "name": "Predictions",
                    "columns": [
                        {"name": "Date", "dataType": "DateTime"},
                        {"name": "PredictedRevenue", "dataType": "double"},
                        {"name": "Confidence", "dataType": "string"},
                        {"name": "ProductSKU", "dataType": "string"}
                    ]
                }
            ]
        }
        
        response = requests.post(
            f"{self.api_url}/datasets",
            headers=self.headers,
            json=dataset_schema
        )
        
        return response.json()
    
    def push_data(self, data: Dict[str, Any]):
        """Envia dados para o Power BI"""
        # Preparar dados de inventário
        inventory_rows = []
        if 'stock_health' in data:
            for product in data['stock_health'].get('critical_products', []):
                inventory_rows.append({
                    "SKU": product.get('sku'),
                    "ProductName": product.get('name'),
                    "Quantity": product.get('quantity', 0),
                    "StockStatus": "CRITICAL",
                    "Location": product.get('location_id', ''),
                    "Timestamp": datetime.now().isoformat()
                })
        
        # Preparar dados de vendas
        sales_rows = []
        if 'sales_summary' in data:
            sales_rows.append({
                "Date": datetime.now().strftime('%Y-%m-%d'),
                "Revenue": data['sales_summary'].get('total_revenue_30d', 0),
                "Transactions": data['sales_summary'].get('total_transactions_30d', 0),
                "AvgTicket": data['sales_summary'].get('avg_ticket', 0),
                "ActiveOperators": 0
            })
        
        # Enviar para Power BI
        datasets = {
            "InventoryAnalysis": inventory_rows,
            "SalesPerformance": sales_rows,
            "FinancialMetrics": [],
            "Predictions": []
        }
        
        for table_name, rows in datasets.items():
            if rows:
                payload = {"rows": rows}
                response = requests.post(
                    f"{self.api_url}/datasets/{self.config.POWER_BI_DATASET_ID}/tables/{table_name}/rows",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    print(f"✅ Dados enviados para {table_name}")
                else:
                    print(f"❌ Erro ao enviar para {table_name}: {response.text}")