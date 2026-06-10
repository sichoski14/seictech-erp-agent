import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

class SalesAgent:
    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.model = None
        self.scaler = StandardScaler()
    
    def analyze_sales_performance(self) -> Dict[str, Any]:
        """Análise de performance de vendas"""
        query = """
            SELECT 
                DATE(sale_date) as date,
                SUM(total_amount) as daily_revenue,
                COUNT(*) as total_transactions,
                AVG(total_amount) as avg_ticket,
                COUNT(DISTINCT operator_id) as active_operators
            FROM sales
            WHERE sale_date >= DATE('now', '-30 days')
            GROUP BY DATE(sale_date)
            ORDER BY date
        """
        
        daily_sales = self.db.execute_query(query)
        
        # Métricas de performance
        metrics = {
            'total_revenue_30d': daily_sales['daily_revenue'].sum(),
            'avg_daily_revenue': daily_sales['daily_revenue'].mean(),
            'total_transactions_30d': daily_sales['total_transactions'].sum(),
            'avg_ticket': daily_sales['avg_ticket'].mean(),
            'growth_rate': self._calculate_growth_rate(daily_sales),
            'best_day': daily_sales.loc[daily_sales['daily_revenue'].idxmax()].to_dict(),
            'worst_day': daily_sales.loc[daily_sales['daily_revenue'].idxmin()].to_dict()
        }
        
        return metrics
    
    def analyze_product_turnover(self) -> pd.DataFrame:
        """Análise de giro de produtos"""
        query = """
            WITH product_sales AS (
                SELECT 
                    p.sku,
                    p.name,
                    p.category,
                    COUNT(s.id) as sales_count,
                    SUM(s.quantity) as total_sold,
                    SUM(s.total_amount) as total_revenue,
                    AVG(i.quantity) as avg_stock
                FROM products p
                LEFT JOIN sales s ON p.id = s.product_id 
                    AND s.sale_date >= DATE('now', '-90 days')
                LEFT JOIN inventory i ON p.id = i.product_id
                GROUP BY p.id
            )
            SELECT 
                *,
                CASE 
                    WHEN avg_stock > 0 THEN total_sold / avg_stock 
                    ELSE 0 
                END as turnover_rate,
                CASE 
                    WHEN total_sold > 0 THEN total_revenue / total_sold 
                    ELSE 0 
                END as avg_unit_revenue
            FROM product_sales
            ORDER BY turnover_rate DESC
        """
        
        turnover_data = self.db.execute_query(query)
        
        # Classificar produtos por giro
        turnover_data['classification'] = pd.cut(
            turnover_data['turnover_rate'],
            bins=[-float('inf'), 1, 3, float('inf')],
            labels=['BAIXO_GIRO', 'MEDIO_GIRO', 'ALTO_GIRO']
        )
        
        return turnover_data
    
    def predict_sales(self, days_ahead: int = 7) -> pd.DataFrame:
        """Previsão de vendas usando ML"""
        # Buscar histórico
        query = """
            SELECT 
                DATE(sale_date) as date,
                SUM(total_amount) as revenue,
                COUNT(*) as transactions
            FROM sales
            WHERE sale_date >= DATE('now', '-180 days')
            GROUP BY DATE(sale_date)
            ORDER BY date
        """
        
        historical_data = self.db.execute_query(query)
        
        if len(historical_data) < 30:
            return pd.DataFrame()
        
        # Preparar features
        historical_data['day_of_week'] = pd.to_datetime(historical_data['date']).dt.dayofweek
        historical_data['day_of_month'] = pd.to_datetime(historical_data['date']).dt.day
        historical_data['month'] = pd.to_datetime(historical_data['date']).dt.month
        
        # Criar lag features
        for lag in [1, 7, 14, 30]:
            historical_data[f'revenue_lag_{lag}'] = historical_data['revenue'].shift(lag)
            historical_data[f'transactions_lag_{lag}'] = historical_data['transactions'].shift(lag)
        
        # Remover NaN
        historical_data = historical_data.dropna()
        
        # Features e target
        feature_cols = ['day_of_week', 'day_of_month', 'month'] + \
                      [f'revenue_lag_{lag}' for lag in [1, 7, 14, 30]]
        
        X = historical_data[feature_cols]
        y = historical_data['revenue']
        
        # Treinar modelo
        model = LinearRegression()
        X_scaled = self.scaler.fit_transform(X)
        model.fit(X_scaled, y)
        
        # Prever próximos dias
        last_date = pd.to_datetime(historical_data['date'].iloc[-1])
        predictions = []
        
        for i in range(1, days_ahead + 1):
            pred_date = last_date + timedelta(days=i)
            
            features = {
                'day_of_week': pred_date.dayofweek,
                'day_of_month': pred_date.day,
                'month': pred_date.month
            }
            
            # Usar último valor conhecido para lags
            for lag in [1, 7, 14, 30]:
                features[f'revenue_lag_{lag}'] = historical_data['revenue'].iloc[-lag]
            
            X_pred = pd.DataFrame([features])
            X_pred_scaled = self.scaler.transform(X_pred)
            
            prediction = model.predict(X_pred_scaled)[0]
            
            predictions.append({
                'date': pred_date.strftime('%Y-%m-%d'),
                'predicted_revenue': max(0, prediction),
                'confidence': 'MEDIUM' if i <= 3 else 'LOW'
            })
        
        return pd.DataFrame(predictions)
    
    def _calculate_growth_rate(self, df: pd.DataFrame) -> float:
        """Calcula taxa de crescimento"""
        if len(df) >= 14:
            first_week = df.head(7)['daily_revenue'].mean()
            last_week = df.tail(7)['daily_revenue'].mean()
            return ((last_week - first_week) / first_week) * 100
        return 0
    
    def analyze_operator_performance(self) -> pd.DataFrame:
        """Análise de performance por operador"""
        query = """
            SELECT 
                operator_id,
                COUNT(*) as total_sales,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_ticket,
                COUNT(DISTINCT DATE(sale_date)) as active_days,
                SUM(total_amount) / COUNT(DISTINCT DATE(sale_date)) as revenue_per_day
            FROM sales
            WHERE sale_date >= DATE('now', '-30 days')
            GROUP BY operator_id
            ORDER BY total_revenue DESC
        """
        
        return self.db.execute_query(query)