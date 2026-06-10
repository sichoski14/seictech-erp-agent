import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StockAgent:
    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.analysis_results = {}
    
    def analyze_stock_health(self) -> Dict[str, Any]:
        """Analisa saúde do estoque por SKU"""
        query = """
            SELECT 
                p.sku,
                p.name,
                p.category,
                i.quantity,
                i.location_id,
                p.minimum_stock,
                p.maximum_stock,
                (i.quantity - COALESCE(s.daily_sales, 0)) as projected_stock
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            LEFT JOIN (
                SELECT 
                    product_id, 
                    AVG(daily_qty) as daily_sales
                FROM (
                    SELECT 
                        product_id,
                        DATE(sale_date) as sale_day,
                        SUM(quantity) as daily_qty
                    FROM sales
                    WHERE sale_date >= DATE('now', '-30 days')
                    GROUP BY product_id, DATE(sale_date)
                )
                GROUP BY product_id
            ) s ON p.id = s.product_id
        """
        
        stock_data = self.db.execute_query(query)
        
        # Calcular métricas
        stock_data['stock_status'] = stock_data.apply(
            lambda row: self._classify_stock_status(row), axis=1
        )
        
        stock_data['days_of_stock'] = np.where(
            stock_data['daily_sales'] > 0,
            stock_data['quantity'] / stock_data['daily_sales'],
            float('inf')
        )
        
        # Identificar produtos críticos
        critical = stock_data[stock_data['stock_status'] == 'CRITICAL']
        alert = stock_data[stock_data['stock_status'] == 'ALERT']
        
        return {
            'total_products': len(stock_data),
            'critical_products': critical.to_dict('records'),
            'alert_products': alert.to_dict('records'),
            'stock_by_category': self._group_by_category(stock_data),
            'stock_by_location': self._group_by_location(stock_data),
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_stock_status(self, row) -> str:
        """Classifica status do estoque"""
        if row['quantity'] <= row['minimum_stock']:
            return 'CRITICAL'
        elif row['quantity'] <= row['minimum_stock'] * 1.5:
            return 'ALERT'
        elif row['quantity'] >= row['maximum_stock']:
            return 'EXCESS'
        return 'NORMAL'
    
    def analyze_heatmap_data(self) -> pd.DataFrame:
        """Análise de mapa de calor por operador e horário"""
        query = """
            SELECT 
                operator_id,
                strftime('%H', sale_date) as hour,
                strftime('%w', sale_date) as day_of_week,
                COUNT(*) as transaction_count,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_ticket
            FROM sales
            WHERE sale_date >= DATE('now', '-30 days')
            GROUP BY operator_id, hour, day_of_week
            ORDER BY transaction_count DESC
        """
        
        heatmap_data = self.db.execute_query(query)
        
        # Criar matriz de calor
        pivot_table = heatmap_data.pivot_table(
            values='transaction_count',
            index='hour',
            columns='operator_id',
            aggfunc='sum',
            fill_value=0
        )
        
        return pivot_table
    
    def analyze_payment_methods(self) -> Dict[str, Any]:
        """Análise de formas de pagamento"""
        query = """
            SELECT 
                payment_method,
                COUNT(*) as total_transactions,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_ticket,
                strftime('%Y-%m', sale_date) as month
            FROM sales
            WHERE sale_date >= DATE('now', '-6 months')
            GROUP BY payment_method, month
            ORDER BY month, total_revenue DESC
        """
        
        payments_data = self.db.execute_query(query)
        
        # Tendências de pagamento
        trends = payments_data.pivot_table(
            values='total_revenue',
            index='month',
            columns='payment_method',
            aggfunc='sum',
            fill_value=0
        )
        
        return {
            'payment_distribution': payments_data.to_dict('records'),
            'monthly_trends': trends.to_dict(),
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_stock_recommendations(self) -> List[Dict[str, Any]]:
        """Gera recomendações de estoque"""
        stock_health = self.analyze_stock_health()
        recommendations = []
        
        for product in stock_health['critical_products']:
            if product['days_of_stock'] < 3:
                recommendations.append({
                    'sku': product['sku'],
                    'name': product['name'],
                    'action': 'URGENT_REORDER',
                    'suggested_quantity': int(product['minimum_stock'] * 2 - product['quantity']),
                    'priority': 'HIGH',
                    'estimated_cost': float(
                        product['cost_price'] * (product['minimum_stock'] * 2 - product['quantity'])
                    )
                })
        
        for product in stock_health['alert_products']:
            if product['stock_status'] == 'EXCESS':
                recommendations.append({
                    'sku': product['sku'],
                    'name': product['name'],
                    'action': 'REDISTRIBUTE',
                    'excess_quantity': int(product['quantity'] - product['maximum_stock']),
                    'priority': 'MEDIUM',
                    'current_location': product['location_id']
                })
        
        return recommendations
    
    def _group_by_category(self, df: pd.DataFrame) -> Dict:
        """Agrupa por categoria"""
        return df.groupby('category').agg({
            'quantity': 'sum',
            'daily_sales': 'sum'
        }).to_dict()
    
    def _group_by_location(self, df: pd.DataFrame) -> Dict:
        """Agrupa por localização"""
        return df.groupby('location_id').agg({
            'quantity': 'sum',
            'stock_status': lambda x: (x == 'CRITICAL').sum()
        }).to_dict()