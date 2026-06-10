import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sklearn.ensemble import RandomForestRegressor

class FinancialAgent:
    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
    
    def analyze_financial_health(self) -> Dict[str, Any]:
        """Análise financeira completa"""
        # Receitas
        revenue = self._get_revenue_analysis()
        
        # Custos
        costs = self._get_cost_analysis()
        
        # Margens
        margins = self._calculate_margins()
        
        # Fluxo de caixa
        cash_flow = self._analyze_cashflow()
        
        return {
            'revenue': revenue,
            'costs': costs,
            'margins': margins,
            'cashflow': cash_flow,
            'timestamp': datetime.now().isoformat()
        }
    
    def predict_cashflow(self, days_ahead: int = 30) -> pd.DataFrame:
        """Previsão de fluxo de caixa"""
        query = """
            SELECT 
                DATE(sale_date) as date,
                SUM(total_amount) as daily_revenue,
                COUNT(*) as transactions
            FROM sales
            WHERE sale_date >= DATE('now', '-180 days')
            GROUP BY DATE(sale_date)
            ORDER BY date
        """
        
        historical = self.db.execute_query(query)
        
        if len(historical) < 60:
            return pd.DataFrame()
        
        # Calcular métricas móveis
        historical['revenue_ma7'] = historical['daily_revenue'].rolling(7).mean()
        historical['revenue_ma30'] = historical['daily_revenue'].rolling(30).mean()
        historical['revenue_std7'] = historical['daily_revenue'].rolling(7).std()
        
        # Preparar features para ML
        historical['day_of_week'] = pd.to_datetime(historical['date']).dt.dayofweek
        historical['month'] = pd.to_datetime(historical['date']).dt.month
        historical['day'] = pd.to_datetime(historical['date']).dt.day
        
        historical = historical.dropna()
        
        # Features
        feature_cols = ['day_of_week', 'month', 'day', 'revenue_ma7', 'revenue_ma30', 'revenue_std7']
        X = historical[feature_cols]
        y = historical['daily_revenue']
        
        # Treinar modelo
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # Previsões
        last_row = historical.iloc[-1]
        predictions = []
        
        current_date = datetime.strptime(last_row['date'], '%Y-%m-%d')
        
        for i in range(1, days_ahead + 1):
            pred_date = current_date + timedelta(days=i)
            
            features = {
                'day_of_week': pred_date.weekday(),
                'month': pred_date.month,
                'day': pred_date.day,
                'revenue_ma7': last_row['revenue_ma7'],
                'revenue_ma30': last_row['revenue_ma30'],
                'revenue_std7': last_row['revenue_std7']
            }
            
            X_pred = pd.DataFrame([features])
            predicted_revenue = model.predict(X_pred)[0]
            
            # Estimar custos (60% da receita como base)
            estimated_costs = predicted_revenue * 0.6
            
            predictions.append({
                'date': pred_date.strftime('%Y-%m-%d'),
                'predicted_revenue': max(0, predicted_revenue),
                'estimated_costs': max(0, estimated_costs),
                'projected_balance': max(0, predicted_revenue - estimated_costs)
            })
        
        return pd.DataFrame(predictions)
    
    def analyze_profitability(self) -> Dict[str, Any]:
        """Análise de rentabilidade por produto/categoria"""
        query = """
            WITH product_profitability AS (
                SELECT 
                    p.sku,
                    p.name,
                    p.category,
                    SUM(s.quantity) as total_units_sold,
                    SUM(s.total_amount) as total_revenue,
                    AVG(p.cost_price) as avg_cost,
                    AVG(p.unit_price) as avg_price,
                    SUM(s.total_amount) - (SUM(s.quantity) * AVG(p.cost_price)) as gross_profit,
                    CASE 
                        WHEN SUM(s.total_amount) > 0 
                        THEN (SUM(s.total_amount) - (SUM(s.quantity) * AVG(p.cost_price))) / SUM(s.total_amount) * 100
                        ELSE 0 
                    END as margin_percentage
                FROM products p
                INNER JOIN sales s ON p.id = s.product_id
                WHERE s.sale_date >= DATE('now', '-90 days')
                GROUP BY p.id
            )
            SELECT * FROM product_profitability
            ORDER BY gross_profit DESC
        """
        
        return self.db.execute_query(query).to_dict('records')
    
    def _get_revenue_analysis(self) -> Dict:
        """Análise detalhada de receitas"""
        query = """
            SELECT 
                strftime('%Y-%m', sale_date) as month,
                SUM(total_amount) as revenue,
                COUNT(*) as transactions,
                SUM(quantity) as units_sold
            FROM sales
            WHERE sale_date >= DATE('now', '-12 months')
            GROUP BY strftime('%Y-%m', sale_date)
            ORDER BY month
        """
        
        revenue_data = self.db.execute_query(query)
        
        return {
            'monthly_data': revenue_data.to_dict('records'),
            'total_revenue_12m': revenue_data['revenue'].sum(),
            'avg_monthly_revenue': revenue_data['revenue'].mean(),
            'growth_trend': self._calculate_trend(revenue_data['revenue'])
        }
    
    def _get_cost_analysis(self) -> Dict:
        """Análise de custos"""
        query = """
            SELECT 
                strftime('%Y-%m', s.sale_date) as month,
                SUM(s.quantity * p.cost_price) as total_cost,
                COUNT(DISTINCT p.supplier_id) as active_suppliers
            FROM sales s
            INNER JOIN products p ON s.product_id = p.id
            WHERE s.sale_date >= DATE('now', '-12 months')
            GROUP BY strftime('%Y-%m', s.sale_date)
            ORDER BY month
        """
        
        return self.db.execute_query(query).to_dict('records')
    
    def _calculate_margins(self) -> Dict:
        """Calcula margens detalhadas"""
        query = """
            SELECT 
                SUM(s.total_amount) as total_revenue,
                SUM(s.quantity * p.cost_price) as total_cost,
                SUM(s.total_amount) - SUM(s.quantity * p.cost_price) as gross_profit,
                (SUM(s.total_amount) - SUM(s.quantity * p.cost_price)) / SUM(s.total_amount) * 100 as gross_margin
            FROM sales s
            INNER JOIN products p ON s.product_id = p.id
            WHERE s.sale_date >= DATE('now', '-30 days')
        """
        
        return self.db.execute_query(query).iloc[0].to_dict()
    
    def _analyze_cashflow(self) -> Dict:
        """Análise de fluxo de caixa"""
        query = """
            SELECT 
                DATE(sale_date) as date,
                SUM(total_amount) as inflows,
                0 as outflows
            FROM sales
            WHERE sale_date >= DATE('now', '-90 days')
            GROUP BY DATE(sale_date)
            ORDER BY date
        """
        
        cashflow = self.db.execute_query(query)
        
        # Estimar saídas (compras de estoque, etc.)
        cashflow['outflows'] = cashflow['inflows'] * 0.7  # Simplificação
        cashflow['net_cashflow'] = cashflow['inflows'] - cashflow['outflows']
        cashflow['cumulative_cashflow'] = cashflow['net_cashflow'].cumsum()
        
        return cashflow.to_dict('records')
    
    def _calculate_trend(self, series: pd.Series) -> str:
        """Calcula tendência"""
        if len(series) > 2:
            recent_avg = series.tail(3).mean()
            previous_avg = series.head(3).mean()
            
            if recent_avg > previous_avg * 1.1:
                return 'CRESCIMENTO'
            elif recent_avg < previous_avg * 0.9:
                return 'QUEDA'
            else:
                return 'ESTÁVEL'
        return 'INSUFICIENTE'