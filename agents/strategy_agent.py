import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime

class StrategyAgent:
    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
    
    def generate_complete_strategy(self) -> Dict[str, Any]:
        """Gera estratégia completa de negócio"""
        return {
            'stock_strategy': self.generate_stock_strategy(),
            'pricing_strategy': self.generate_pricing_strategy(),
            'distribution_strategy': self.generate_distribution_strategy(),
            'marketing_strategy': self.generate_marketing_strategy(),
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_stock_strategy(self) -> List[Dict]:
        """Estratégia de estoque inteligente"""
        query = """
            WITH product_metrics AS (
                SELECT 
                    p.*,
                    i.quantity as current_stock,
                    AVG(s.daily_sales) as avg_daily_demand,
                    MAX(s.daily_sales) as max_daily_demand,
                    AVG(s.daily_sales) * 1.96 * SQRT(
                        AVG(s.daily_sales * s.daily_sales) - AVG(s.daily_sales) * AVG(s.daily_sales)
                    ) as safety_stock
                FROM products p
                LEFT JOIN inventory i ON p.id = i.product_id
                LEFT JOIN (
                    SELECT 
                        product_id,
                        DATE(sale_date) as sale_day,
                        SUM(quantity) as daily_sales
                    FROM sales
                    WHERE sale_date >= DATE('now', '-60 days')
                    GROUP BY product_id, DATE(sale_date)
                ) s ON p.id = s.product_id
                GROUP BY p.id
            )
            SELECT 
                sku,
                name,
                current_stock,
                avg_daily_demand,
                safety_stock,
                CASE 
                    WHEN current_stock < safety_stock THEN safety_stock * 1.5 - current_stock
                    ELSE 0
                END as suggested_order,
                CASE 
                    WHEN current_stock > max_daily_demand * 15 THEN 'REDUCE_STOCK'
                    WHEN current_stock < safety_stock THEN 'REORDER'
                    ELSE 'MAINTAIN'
                END as action
            FROM product_metrics
            ORDER BY suggested_order DESC
        """
        
        return self.db.execute_query(query).to_dict('records')
    
    def generate_distribution_strategy(self) -> List[Dict]:
        """Estratégia de distribuição de estoque entre locais"""
        query = """
            WITH location_performance AS (
                SELECT 
                    i.location_id,
                    COUNT(DISTINCT p.id) as product_count,
                    SUM(i.quantity) as total_stock,
                    SUM(COALESCE(s.total_sales, 0)) as location_demand,
                    SUM(i.quantity) / NULLIF(SUM(COALESCE(s.total_sales, 0)), 0) as stock_sales_ratio
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                LEFT JOIN (
                    SELECT 
                        product_id,
                        SUM(quantity) as total_sales
                    FROM sales
                    WHERE sale_date >= DATE('now', '-30 days')
                    GROUP BY product_id
                ) s ON p.id = s.product_id
                GROUP BY i.location_id
            )
            SELECT 
                *,
                CASE 
                    WHEN stock_sales_ratio > 2 THEN 'EXCESS_INVENTORY'
                    WHEN stock_sales_ratio < 0.5 THEN 'LOW_INVENTORY'
                    ELSE 'BALANCED'
                END as status,
                CASE 
                    WHEN stock_sales_ratio > 2 THEN total_stock - (location_demand * 1.5)
                    ELSE 0
                END as excess_to_redistribute
            FROM location_performance
            ORDER BY stock_sales_ratio DESC
        """
        
        return self.db.execute_query(query).to_dict('records')
    
    def generate_pricing_strategy(self) -> List[Dict]:
        """Estratégia de precificação dinâmica"""
        query = """
            WITH price_elasticity AS (
                SELECT 
                    p.sku,
                    p.name,
                    p.category,
                    AVG(p.unit_price) as current_price,
                    AVG(p.cost_price) as cost,
                    COUNT(DISTINCT s.id) as sales_volume,
                    CASE 
                        WHEN AVG(p.unit_price) > 0 
                        THEN (AVG(p.unit_price) - AVG(p.cost_price)) / AVG(p.unit_price) * 100
                        ELSE 0
                    END as current_margin,
                    CASE 
                        WHEN COUNT(DISTINCT s.id) > 100 THEN 'HIGH_VOLUME'
                        WHEN COUNT(DISTINCT s.id) > 30 THEN 'MEDIUM_VOLUME'
                        ELSE 'LOW_VOLUME'
                    END as volume_category
                FROM products p
                LEFT JOIN sales s ON p.id = s.product_id 
                    AND s.sale_date >= DATE('now', '-90 days')
                GROUP BY p.id
            )
            SELECT 
                *,
                CASE 
                    WHEN current_margin < 20 AND volume_category = 'HIGH_VOLUME' 
                        THEN current_price * 1.10
                    WHEN current_margin > 50 AND volume_category = 'LOW_VOLUME'
                        THEN current_price * 0.90
                    ELSE current_price
                END as suggested_price,
                CASE 
                    WHEN current_margin < 20 THEN 'INCREASE'
                    WHEN current_margin > 50 THEN 'DECREASE'
                    ELSE 'MAINTAIN'
                END as pricing_action
            FROM price_elasticity
        """
        
        return self.db.execute_query(query).to_dict('records')
    
    def generate_marketing_strategy(self) -> Dict:
        """Gera estratégias de marketing baseadas em dados"""
        # Produtos para promoção (alto estoque, baixo giro)
        query_promotion = """
            SELECT 
                p.sku,
                p.name,
                i.quantity as current_stock,
                COUNT(s.id) as recent_sales
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            LEFT JOIN sales s ON p.id = s.product_id 
                AND s.sale_date >= DATE('now', '-30 days')
            GROUP BY p.id
            HAVING current_stock > 50 AND recent_sales < 10
            ORDER BY current_stock DESC
            LIMIT 20
        """
        
        # Produtos para cross-selling
        query_cross_sell = """
            WITH product_pairs AS (
                SELECT 
                    s1.product_id as product_a,
                    s2.product_id as product_b,
                    COUNT(*) as pair_count
                FROM sales s1
                JOIN sales s2 ON s1.id != s2.id 
                    AND DATE(s1.sale_date) = DATE(s2.sale_date)
                WHERE s1.sale_date >= DATE('now', '-90 days')
                GROUP BY product_a, product_b
                HAVING pair_count > 5
                ORDER BY pair_count DESC
            )
            SELECT 
                p1.name as product_name,
                p2.name as paired_product,
                pp.pair_count as frequency
            FROM product_pairs pp
            JOIN products p1 ON pp.product_a = p1.id
            JOIN products p2 ON pp.product_b = p2.id
            LIMIT 50
        """
        
        promo_products = self.db.execute_query(query_promotion).to_dict('records')
        cross_sell = self.db.execute_query(query_cross_sell).to_dict('records')
        
        return {
            'promotion_candidates': promo_products,
            'cross_sell_opportunities': cross_sell,
            'strategies': [
                {
                    'type': 'PROMOTION',
                    'action': 'Create bundle offers for high-stock items',
                    'target_products': [p['sku'] for p in promo_products[:5]]
                },
                {
                    'type': 'CROSS_SELL',
                    'action': 'Implement recommendation system',
                    'pairs': cross_sell[:10]
                }
            ]
        }