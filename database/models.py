import sqlite3
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabela de Produtos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100),
                    supplier_id VARCHAR(50),
                    unit_price DECIMAL(10,2),
                    cost_price DECIMAL(10,2),
                    minimum_stock INTEGER,
                    maximum_stock INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela de Estoque
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    location_id VARCHAR(50),
                    quantity INTEGER,
                    reserved_quantity INTEGER,
                    available_quantity INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # Tabela de Vendas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    quantity INTEGER,
                    unit_price DECIMAL(10,2),
                    total_amount DECIMAL(10,2),
                    payment_method VARCHAR(50),
                    operator_id VARCHAR(50),
                    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # Tabela de Movimentações de Estoque
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    quantity INTEGER,
                    movement_type VARCHAR(50),
                    reason VARCHAR(255),
                    movement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # Tabela de Previsões
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    predicted_demand INTEGER,
                    confidence_score DECIMAL(5,2),
                    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            conn.commit()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        with self.get_connection() as conn:
            if params:
                return pd.read_sql_query(query, conn, params=params)
            return pd.read_sql_query(query, conn)