"""
SISTEMA FINANCEIRO AVANÇADO - MÓDULO COMPLETO
Análise financeira, previsão de caixa, margens e rentabilidade
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import json
import os

app = Flask(__name__)
DB_PATH = 'data/retail_analytics.db'

class FinancialAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path
        
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_financial_summary(self):
        """Resumo financeiro completo"""
        with self.get_connection() as conn:
            # Receita total (30 dias)
            revenue_30d = conn.execute("""
                SELECT COALESCE(SUM(total_amount), 0)
                FROM sales
                WHERE sale_date >= DATE('now', '-30 days')
            """).fetchone()[0]
            
            # Receita hoje
            revenue_today = conn.execute("""
                SELECT COALESCE(SUM(total_amount), 0)
                FROM sales
                WHERE DATE(sale_date) = DATE('now')
            """).fetchone()[0]
            
            # Custo total (30 dias)
            cost_30d = conn.execute("""
                SELECT COALESCE(SUM(s.quantity * p.cost_price), 0)
                FROM sales s
                JOIN products p ON s.product_id = p.id
                WHERE s.sale_date >= DATE('now', '-30 days')
            """).fetchone()[0]
            
            # Lucro bruto
            gross_profit = revenue_30d - cost_30d
            
            # Margem bruta
            gross_margin = (gross_profit / revenue_30d * 100) if revenue_30d > 0 else 0
            
            # Ticket médio
            avg_ticket = conn.execute("""
                SELECT COALESCE(AVG(total_amount), 0)
                FROM sales
                WHERE sale_date >= DATE('now', '-30 days')
            """).fetchone()[0]
            
            # Total de transações
            total_transactions = conn.execute("""
                SELECT COUNT(*)
                FROM sales
                WHERE sale_date >= DATE('now', '-30 days')
            """).fetchone()[0]
            
            return {
                'revenue_30d': revenue_30d,
                'revenue_today': revenue_today,
                'cost_30d': cost_30d,
                'gross_profit': gross_profit,
                'gross_margin': round(gross_margin, 2),
                'avg_ticket': avg_ticket,
                'total_transactions': total_transactions
            }
    
    def get_monthly_revenue(self):
        """Receita mensal dos últimos 12 meses"""
        with self.get_connection() as conn:
            monthly = conn.execute("""
                SELECT 
                    strftime('%Y-%m', sale_date) as month,
                    SUM(total_amount) as revenue,
                    COUNT(*) as transactions
                FROM sales
                WHERE sale_date >= DATE('now', '-12 months')
                GROUP BY strftime('%Y-%m', sale_date)
                ORDER BY month
            """).fetchall()
            
            return [{'month': m[0], 'revenue': m[1], 'transactions': m[2]} for m in monthly]
    
    def get_profitability_by_product(self):
        """Rentabilidade por produto"""
        with self.get_connection() as conn:
            products = conn.execute("""
                SELECT 
                    p.name,
                    p.sku,
                    p.category,
                    COUNT(s.id) as units_sold,
                    SUM(s.quantity) as total_quantity,
                    SUM(s.total_amount) as total_revenue,
                    AVG(p.cost_price) as avg_cost,
                    SUM(s.total_amount) - (SUM(s.quantity) * AVG(p.cost_price)) as gross_profit,
                    CASE 
                        WHEN SUM(s.total_amount) > 0 
                        THEN ((SUM(s.total_amount) - (SUM(s.quantity) * AVG(p.cost_price))) / SUM(s.total_amount)) * 100
                        ELSE 0 
                    END as margin_pct
                FROM products p
                LEFT JOIN sales s ON p.id = s.product_id 
                    AND s.sale_date >= DATE('now', '-90 days')
                GROUP BY p.id
                ORDER BY gross_profit DESC
            """).fetchall()
            
            return [{
                'name': p[0],
                'sku': p[1],
                'category': p[2],
                'units_sold': p[3] or 0,
                'total_quantity': p[4] or 0,
                'total_revenue': p[5] or 0,
                'avg_cost': p[6] or 0,
                'gross_profit': p[7] or 0,
                'margin_pct': round(p[8], 2) if p[8] else 0
            } for p in products]
    
    def get_cashflow_prediction(self, days_ahead=30):
        """Previsão de fluxo de caixa usando ML"""
        with self.get_connection() as conn:
            # Buscar histórico
            historical = conn.execute("""
                SELECT 
                    DATE(sale_date) as date,
                    SUM(total_amount) as daily_revenue,
                    COUNT(*) as transactions
                FROM sales
                WHERE sale_date >= DATE('now', '-180 days')
                GROUP BY DATE(sale_date)
                ORDER BY date
            """).fetchall()
            
            if len(historical) < 30:
                # Gerar dados sintéticos para previsão
                return self._generate_synthetic_prediction(days_ahead)
            
            # Converter para DataFrame
            df = pd.DataFrame(historical, columns=['date', 'revenue', 'transactions'])
            df['date'] = pd.to_datetime(df['date'])
            
            # Features
            df['day_of_week'] = df['date'].dt.dayofweek
            df['day_of_month'] = df['date'].dt.day
            df['month'] = df['date'].dt.month
            df['week_of_year'] = df['date'].dt.isocalendar().week
            
            # Lags
            for lag in [1, 7, 14, 30]:
                df[f'revenue_lag_{lag}'] = df['revenue'].shift(lag)
            
            # Médias móveis
            df['ma_7'] = df['revenue'].rolling(7).mean()
            df['ma_30'] = df['revenue'].rolling(30).mean()
            
            # Remover NaN
            df = df.dropna()
            
            if len(df) < 10:
                return self._generate_synthetic_prediction(days_ahead)
            
            # Treinar modelo
            features = ['day_of_week', 'day_of_month', 'month', 'week_of_year',
                       'revenue_lag_1', 'revenue_lag_7', 'ma_7', 'ma_30']
            
            X = df[features].fillna(0)
            y = df['revenue']
            
            model = LinearRegression()
            scaler = StandardScaler()
            
            X_scaled = scaler.fit_transform(X)
            model.fit(X_scaled, y)
            
            # Prever próximos dias
            predictions = []
            last_row = df.iloc[-1]
            current_date = df['date'].max()
            
            for i in range(1, days_ahead + 1):
                pred_date = current_date + timedelta(days=i)
                
                features_dict = {
                    'day_of_week': pred_date.dayofweek,
                    'day_of_month': pred_date.day,
                    'month': pred_date.month,
                    'week_of_year': pred_date.isocalendar().week,
                    'revenue_lag_1': last_row['revenue'],
                    'revenue_lag_7': df['revenue'].iloc[-7] if len(df) >= 7 else last_row['revenue'],
                    'ma_7': df['revenue'].tail(7).mean(),
                    'ma_30': df['revenue'].tail(30).mean() if len(df) >= 30 else df['revenue'].mean()
                }
                
                X_pred = pd.DataFrame([features_dict])
                X_pred_scaled = scaler.transform(X_pred)
                
                predicted_revenue = max(0, model.predict(X_pred_scaled)[0])
                
                # Estimar custos (60% da receita)
                estimated_costs = predicted_revenue * 0.6
                
                predictions.append({
                    'date': pred_date.strftime('%Y-%m-%d'),
                    'predicted_revenue': round(predicted_revenue, 2),
                    'estimated_costs': round(estimated_costs, 2),
                    'projected_balance': round(predicted_revenue - estimated_costs, 2),
                    'cumulative_balance': 0  # Será calculado depois
                })
            
            # Calcular saldo acumulado
            cumulative = 0
            for p in predictions:
                cumulative += p['projected_balance']
                p['cumulative_balance'] = round(cumulative, 2)
            
            return predictions
    
    def _generate_synthetic_prediction(self, days=30):
        """Gera previsão sintética quando não há dados suficientes"""
        predictions = []
        base_revenue = 1000
        trend = 1.02  # 2% de crescimento
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i+1)
            
            # Simular sazonalidade
            day_factor = 1.0
            if date.weekday() >= 5:  # Fim de semana
                day_factor = 1.3
            elif date.weekday() == 0:  # Segunda
                day_factor = 0.8
            
            # Simular período do mês
            if date.day <= 5:  # Início do mês
                day_factor *= 1.2
            elif date.day >= 25:  # Final do mês
                day_factor *= 0.9
            
            revenue = base_revenue * (trend ** i) * day_factor
            costs = revenue * 0.6
            
            predictions.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_revenue': round(revenue, 2),
                'estimated_costs': round(costs, 2),
                'projected_balance': round(revenue - costs, 2),
                'cumulative_balance': round((revenue - costs) * (i + 1), 2)
            })
        
        return predictions
    
    def get_expense_analysis(self):
        """Análise de despesas e custos"""
        with self.get_connection() as conn:
            # Custos por categoria
            costs_by_category = conn.execute("""
                SELECT 
                    p.category,
                    SUM(s.quantity * p.cost_price) as total_cost,
                    SUM(s.total_amount) as total_revenue,
                    COUNT(s.id) as transactions
                FROM sales s
                JOIN products p ON s.product_id = p.id
                WHERE s.sale_date >= DATE('now', '-30 days')
                GROUP BY p.category
            """).fetchall()
            
            return [{
                'category': c[0] or 'Sem categoria',
                'total_cost': c[1] or 0,
                'total_revenue': c[2] or 0,
                'transactions': c[3] or 0,
                'profit': (c[2] or 0) - (c[1] or 0)
            } for c in costs_by_category]
    
    def get_payment_methods_analysis(self):
        """Análise detalhada por forma de pagamento"""
        with self.get_connection() as conn:
            payments = conn.execute("""
                SELECT 
                    payment_method,
                    COUNT(*) as total_transactions,
                    SUM(total_amount) as total_amount,
                    AVG(total_amount) as avg_ticket,
                    MIN(total_amount) as min_ticket,
                    MAX(total_amount) as max_ticket
                FROM sales
                WHERE sale_date >= DATE('now', '-30 days')
                GROUP BY payment_method
                ORDER BY total_amount DESC
            """).fetchall()
            
            return [{
                'method': p[0],
                'transactions': p[1],
                'total_amount': p[2],
                'avg_ticket': round(p[3], 2) if p[3] else 0,
                'min_ticket': p[4] or 0,
                'max_ticket': p[5] or 0
            } for p in payments]
    
    def get_daily_balance(self, days=30):
        """Saldo diário (receitas - custos)"""
        with self.get_connection() as conn:
            balance = conn.execute("""
                SELECT 
                    DATE(s.sale_date) as date,
                    SUM(s.total_amount) as revenue,
                    SUM(s.quantity * p.cost_price) as cost,
                    SUM(s.total_amount) - SUM(s.quantity * p.cost_price) as balance
                FROM sales s
                JOIN products p ON s.product_id = p.id
                WHERE s.sale_date >= DATE('now', ?)
                GROUP BY DATE(s.sale_date)
                ORDER BY date
            """, (f'-{days} days',)).fetchall()
            
            return [{
                'date': b[0],
                'revenue': b[1] or 0,
                'cost': b[2] or 0,
                'balance': b[3] or 0
            } for b in balance]

# Instanciar analisador
analyzer = FinancialAnalyzer(DB_PATH)

# Template HTML do módulo financeiro
FINANCIAL_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Financeira - Sistema de Varejo</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #333;
        }
        .header {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            color: white;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 20px rgba(0,0,0,0.2);
        }
        .header h1 { font-size: 32px; margin-bottom: 5px; }
        .header p { opacity: 0.9; }
        .container { max-width: 1500px; margin: 0 auto; padding: 20px; }
        
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .kpi-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
            position: relative;
            overflow: hidden;
        }
        .kpi-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        .kpi-card .icon {
            font-size: 40px;
            margin-bottom: 10px;
        }
        .kpi-card .label {
            color: #666;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        .kpi-card .value {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .kpi-card .trend {
            font-size: 14px;
        }
        .kpi-card .trend.positive { color: #48bb78; }
        .kpi-card .trend.negative { color: #f56565; }
        
        .kpi-card.revenue { border-left: 4px solid #667eea; }
        .kpi-card.revenue .value { color: #667eea; }
        .kpi-card.profit { border-left: 4px solid #48bb78; }
        .kpi-card.profit .value { color: #48bb78; }
        .kpi-card.margin { border-left: 4px solid #ed8936; }
        .kpi-card.margin .value { color: #ed8936; }
        .kpi-card.ticket { border-left: 4px solid #9f7aea; }
        .kpi-card.ticket .value { color: #9f7aea; }
        
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .chart-card h3 {
            margin-bottom: 20px;
            color: #2d3748;
            font-size: 18px;
        }
        .chart-card canvas { max-height: 350px; }
        
        .table-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            overflow-x: auto;
        }
        .table-card h3 {
            margin-bottom: 20px;
            color: #2d3748;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #f7fafc;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        td {
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
        }
        tr:hover td { background: #f7fafc; }
        
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-high { background: #c6f6d5; color: #22543d; }
        .badge-medium { background: #fefcbf; color: #744210; }
        .badge-low { background: #fed7d7; color: #822727; }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .progress-fill.positive { background: linear-gradient(90deg, #48bb78, #38a169); }
        .progress-fill.negative { background: linear-gradient(90deg, #f56565, #e53e3e); }
        
        .refresh-btn {
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            padding: 12px 25px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #667eea;
            color: white;
        }
        
        .tab-nav {
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .tab-btn {
            padding: 12px 25px;
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
            backdrop-filter: blur(10px);
        }
        .tab-btn:hover, .tab-btn.active {
            background: white;
            color: #667eea;
        }
        
        @media (max-width: 768px) {
            .chart-grid {
                grid-template-columns: 1fr;
            }
            .kpi-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏦 Análise Financeira Avançada</h1>
        <p>Previsão de Caixa | Margens | Rentabilidade | ML Predictions</p>
        <p id="update-time" style="margin-top: 10px; font-size: 12px;"></p>
    </div>
    
    <div class="container">
        <button class="refresh-btn" onclick="loadAllData()">🔄 Atualizar Dados Financeiros</button>
        
        <div class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('overview')">📊 Visão Geral</button>
            <button class="tab-btn" onclick="switchTab('cashflow')">💵 Fluxo de Caixa</button>
            <button class="tab-btn" onclick="switchTab('profitability')">📈 Rentabilidade</button>
            <button class="tab-btn" onclick="switchTab('payments')">💳 Pagamentos</button>
        </div>
        
        <!-- VISÃO GERAL -->
        <div id="overview" class="tab-content">
            <div class="kpi-grid">
                <div class="kpi-card revenue">
                    <div class="icon">💰</div>
                    <div class="label">Receita Total (30 dias)</div>
                    <div class="value" id="revenue-30d">R$ 0</div>
                    <div class="trend positive" id="revenue-trend"></div>
                </div>
                <div class="kpi-card profit">
                    <div class="icon">📈</div>
                    <div class="label">Lucro Bruto (30 dias)</div>
                    <div class="value" id="gross-profit">R$ 0</div>
                </div>
                <div class="kpi-card margin">
                    <div class="icon">🎯</div>
                    <div class="label">Margem Bruta</div>
                    <div class="value" id="gross-margin">0%</div>
                </div>
                <div class="kpi-card ticket">
                    <div class="icon">🎫</div>
                    <div class="label">Ticket Médio</div>
                    <div class="value" id="avg-ticket">R$ 0</div>
                </div>
            </div>
            
            <div class="chart-grid">
                <div class="chart-card">
                    <h3>📊 Receita Mensal (12 meses)</h3>
                    <canvas id="monthlyRevenueChart"></canvas>
                </div>
                <div class="chart-card">
                    <h3>💵 Saldo Diário (30 dias)</h3>
                    <canvas id="dailyBalanceChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- FLUXO DE CAIXA -->
        <div id="cashflow" class="tab-content" style="display:none;">
            <div class="chart-card" style="margin-bottom:20px;">
                <h3>🔮 Previsão de Fluxo de Caixa - Próximos 30 Dias (Machine Learning)</h3>
                <canvas id="cashflowPredictionChart"></canvas>
            </div>
            
            <div class="table-card">
                <h3>📋 Detalhamento da Previsão</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Data</th>
                            <th>Receita Prevista</th>
                            <th>Custos Estimados</th>
                            <th>Saldo Projetado</th>
                            <th>Saldo Acumulado</th>
                        </tr>
                    </thead>
                    <tbody id="cashflow-table-body"></tbody>
                </table>
            </div>
        </div>
        
        <!-- RENTABILIDADE -->
        <div id="profitability" class="tab-content" style="display:none;">
            <div class="chart-grid">
                <div class="chart-card">
                    <h3>🏆 Top Produtos por Lucratividade</h3>
                    <canvas id="profitabilityChart"></canvas>
                </div>
                <div class="chart-card">
                    <h3>📦 Custos por Categoria</h3>
                    <canvas id="costCategoryChart"></canvas>
                </div>
            </div>
            
            <div class="table-card">
                <h3>📋 Rentabilidade por Produto</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Produto</th>
                            <th>Categoria</th>
                            <th>Unidades Vendidas</th>
                            <th>Receita Total</th>
                            <th>Lucro Bruto</th>
                            <th>Margem</th>
                            <th>Performance</th>
                        </tr>
                    </thead>
                    <tbody id="profitability-table-body"></tbody>
                </table>
            </div>
        </div>
        
        <!-- PAGAMENTOS -->
        <div id="payments" class="tab-content" style="display:none;">
            <div class="chart-grid">
                <div class="chart-card">
                    <h3>💳 Distribuição por Forma de Pagamento</h3>
                    <canvas id="paymentDistributionChart"></canvas>
                </div>
                <div class="chart-card">
                    <h3>🎫 Ticket Médio por Método</h3>
                    <canvas id="ticketByMethodChart"></canvas>
                </div>
            </div>
            
            <div class="table-card">
                <h3>📋 Detalhamento por Método de Pagamento</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Método</th>
                            <th>Transações</th>
                            <th>Valor Total</th>
                            <th>Ticket Médio</th>
                            <th>Ticket Mínimo</th>
                            <th>Ticket Máximo</th>
                            <th>Participação</th>
                        </tr>
                    </thead>
                    <tbody id="payment-table-body"></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        let monthlyRevenueChart, dailyBalanceChart, cashflowPredictionChart;
        let profitabilityChart, costCategoryChart, paymentDistributionChart, ticketByMethodChart;
        
        function switchTab(tabName) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
            
            document.querySelector(`[onclick="switchTab('${tabName}')"]`).classList.add('active');
            document.getElementById(tabName).style.display = 'block';
            
            if (tabName === 'overview') updateCharts();
            if (tabName === 'cashflow') loadCashflowData();
            if (tabName === 'profitability') loadProfitabilityData();
            if (tabName === 'payments') loadPaymentsData();
        }
        
        function formatCurrency(value) {
            return new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL'
            }).format(value || 0);
        }
        
        async function loadAllData() {
            await loadSummary();
            updateCharts();
        }
        
        async function loadSummary() {
            try {
                const response = await fetch('/api/financial/summary');
                const data = await response.json();
                
                document.getElementById('revenue-30d').textContent = formatCurrency(data.revenue_30d);
                document.getElementById('gross-profit').textContent = formatCurrency(data.gross_profit);
                document.getElementById('gross-margin').textContent = data.gross_margin.toFixed(1) + '%';
                document.getElementById('avg-ticket').textContent = formatCurrency(data.avg_ticket);
                
                // Trend
                const trend = data.revenue_today > (data.revenue_30d / 30) ? '↑ Acima da média' : '↓ Abaixo da média';
                const trendClass = data.revenue_today > (data.revenue_30d / 30) ? 'positive' : 'negative';
                document.getElementById('revenue-trend').textContent = trend;
                document.getElementById('revenue-trend').className = 'trend ' + trendClass;
                
            } catch (error) {
                console.error('Erro ao carregar resumo:', error);
            }
        }
        
        async function updateCharts() {
            await loadMonthlyRevenue();
            await loadDailyBalance();
        }
        
        async function loadMonthlyRevenue() {
            try {
                const response = await fetch('/api/financial/monthly-revenue');
                const data = await response.json();
                
                const ctx = document.getElementById('monthlyRevenueChart').getContext('2d');
                if (monthlyRevenueChart) monthlyRevenueChart.destroy();
                
                monthlyRevenueChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.map(d => d.month),
                        datasets: [{
                            label: 'Receita Mensal',
                            data: data.map(d => d.revenue),
                            backgroundColor: 'rgba(102, 126, 234, 0.8)',
                            borderColor: '#667eea',
                            borderWidth: 1,
                            borderRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: v => 'R$ ' + v.toLocaleString('pt-BR')
                                }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Erro ao carregar receita mensal:', error);
            }
        }
        
        async function loadDailyBalance() {
            try {
                const response = await fetch('/api/financial/daily-balance');
                const data = await response.json();
                
                const ctx = document.getElementById('dailyBalanceChart').getContext('2d');
                if (dailyBalanceChart) dailyBalanceChart.destroy();
                
                dailyBalanceChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.map(d => d.date),
                        datasets: [
                            {
                                label: 'Receita',
                                data: data.map(d => d.revenue),
                                borderColor: '#48bb78',
                                backgroundColor: 'rgba(72, 187, 120, 0.1)',
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'Custos',
                                data: data.map(d => d.cost),
                                borderColor: '#f56565',
                                backgroundColor: 'rgba(245, 101, 101, 0.1)',
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'Saldo',
                                data: data.map(d => d.balance),
                                borderColor: '#667eea',
                                borderWidth: 2,
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                ticks: {
                                    callback: v => 'R$ ' + v.toLocaleString('pt-BR')
                                }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Erro ao carregar saldo diário:', error);
            }
        }
        
        async function loadCashflowData() {
            try {
                const response = await fetch('/api/financial/cashflow-prediction');
                const data = await response.json();
                
                // Gráfico
                const ctx = document.getElementById('cashflowPredictionChart').getContext('2d');
                if (cashflowPredictionChart) cashflowPredictionChart.destroy();
                
                cashflowPredictionChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.map(d => d.date),
                        datasets: [
                            {
                                label: 'Receita Prevista',
                                data: data.map(d => d.predicted_revenue),
                                borderColor: '#48bb78',
                                backgroundColor: 'rgba(72, 187, 120, 0.1)',
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'Saldo Projetado',
                                data: data.map(d => d.projected_balance),
                                borderColor: '#667eea',
                                borderWidth: 2,
                                tension: 0.4
                            },
                            {
                                label: 'Saldo Acumulado',
                                data: data.map(d => d.cumulative_balance),
                                borderColor: '#ed8936',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                ticks: {
                                    callback: v => 'R$ ' + v.toLocaleString('pt-BR')
                                }
                            }
                        }
                    }
                });
                
                // Tabela
                const tbody = document.getElementById('cashflow-table-body');
                tbody.innerHTML = data.map(d => `
                    <tr>
                        <td><strong>${d.date}</strong></td>
                        <td style="color: #48bb78;">${formatCurrency(d.predicted_revenue)}</td>
                        <td style="color: #f56565;">${formatCurrency(d.estimated_costs)}</td>
                        <td style="color: #667eea; font-weight: bold;">${formatCurrency(d.projected_balance)}</td>
                        <td>${formatCurrency(d.cumulative_balance)}</td>
                    </tr>
                `).join('');
                
            } catch (error) {
                console.error('Erro ao carregar previsão:', error);
            }
        }
        
        async function loadProfitabilityData() {
            try {
                const response = await fetch('/api/financial/profitability');
                const data = await response.json();
                
                // Gráfico de produtos
                const ctx1 = document.getElementById('profitabilityChart').getContext('2d');
                if (profitabilityChart) profitabilityChart.destroy();
                
                const top10 = data.slice(0, 10);
                
                profitabilityChart = new Chart(ctx1, {
                    type: 'bar',
                    data: {
                        labels: top10.map(d => d.name),
                        datasets: [{
                            label: 'Lucro Bruto',
                            data: top10.map(d => d.gross_profit),
                            backgroundColor: top10.map(d => 
                                d.margin_pct > 40 ? 'rgba(72, 187, 120, 0.8)' :
                                d.margin_pct > 20 ? 'rgba(237, 137, 54, 0.8)' :
                                'rgba(245, 101, 101, 0.8)'
                            )
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: {
                                ticks: {
                                    callback: v => 'R$ ' + v.toLocaleString('pt-BR')
                                }
                            }
                        }
                    }
                });
                
                // Gráfico de categorias
                const categories = {};
                data.forEach(d => {
                    if (!categories[d.category]) {
                        categories[d.category] = { cost: 0, revenue: 0 };
                    }
                    categories[d.category].cost += d.total_revenue - d.gross_profit;
                    categories[d.category].revenue += d.total_revenue;
                });
                
                const ctx2 = document.getElementById('costCategoryChart').getContext('2d');
                if (costCategoryChart) costCategoryChart.destroy();
                
                costCategoryChart = new Chart(ctx2, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(categories),
                        datasets: [{
                            data: Object.values(categories).map(c => c.revenue),
                            backgroundColor: ['#667eea', '#48bb78', '#ed8936', '#f56565', '#9f7aea']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
                
                // Tabela
                const tbody = document.getElementById('profitability-table-body');
                tbody.innerHTML = data.map(d => {
                    const performance = d.margin_pct > 40 ? 'high' : d.margin_pct > 20 ? 'medium' : 'low';
                    const performanceText = performance === 'high' ? 'Excelente' : 
                                           performance === 'medium' ? 'Regular' : 'Baixa';
                    
                    return `
                        <tr>
                            <td><strong>${d.name}</strong></td>
                            <td>${d.category}</td>
                            <td>${d.units_sold}</td>
                            <td>${formatCurrency(d.total_revenue)}</td>
                            <td style="color: ${d.gross_profit >= 0 ? '#48bb78' : '#f56565'}; font-weight: bold;">
                                ${formatCurrency(d.gross_profit)}
                            </td>
                            <td>
                                <strong>${d.margin_pct.toFixed(1)}%</strong>
                                <div class="progress-bar">
                                    <div class="progress-fill ${d.margin_pct > 20 ? 'positive' : 'negative'}" 
                                         style="width: ${Math.min(d.margin_pct, 100)}%"></div>
                                </div>
                            </td>
                            <td><span class="badge badge-${performance}">${performanceText}</span></td>
                        </tr>
                    `;
                }).join('');
                
            } catch (error) {
                console.error('Erro ao carregar rentabilidade:', error);
            }
        }
        
        async function loadPaymentsData() {
            try {
                const response = await fetch('/api/financial/payments');
                const data = await response.json();
                
                // Distribuição
                const ctx1 = document.getElementById('paymentDistributionChart').getContext('2d');
                if (paymentDistributionChart) paymentDistributionChart.destroy();
                
                paymentDistributionChart = new Chart(ctx1, {
                    type: 'pie',
                    data: {
                        labels: data.map(d => d.method),
                        datasets: [{
                            data: data.map(d => d.total_amount),
                            backgroundColor: ['#667eea', '#48bb78', '#ed8936', '#f56565', '#9f7aea']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        return formatCurrency(ctx.raw);
                                    }
                                }
                            }
                        }
                    }
                });
                
                // Ticket por método
                const ctx2 = document.getElementById('ticketByMethodChart').getContext('2d');
                if (ticketByMethodChart) ticketByMethodChart.destroy();
                
                ticketByMethodChart = new Chart(ctx2, {
                    type: 'bar',
                    data: {
                        labels: data.map(d => d.method),
                        datasets: [{
                            label: 'Ticket Médio',
                            data: data.map(d => d.avg_ticket),
                            backgroundColor: '#667eea',
                            borderRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: {
                                ticks: {
                                    callback: v => 'R$ ' + v.toLocaleString('pt-BR')
                                }
                            }
                        }
                    }
                });
                
                // Tabela
                const totalAmount = data.reduce((sum, d) => sum + d.total_amount, 0);
                const tbody = document.getElementById('payment-table-body');
                tbody.innerHTML = data.map(d => {
                    const percentage = ((d.total_amount / totalAmount) * 100).toFixed(1);
                    return `
                        <tr>
                            <td><strong>${d.method}</strong></td>
                            <td>${d.transactions}</td>
                            <td>${formatCurrency(d.total_amount)}</td>
                            <td>${formatCurrency(d.avg_ticket)}</td>
                            <td>${formatCurrency(d.min_ticket)}</td>
                            <td>${formatCurrency(d.max_ticket)}</td>
                            <td>
                                <strong>${percentage}%</strong>
                                <div class="progress-bar">
                                    <div class="progress-fill positive" style="width: ${percentage}%"></div>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
                
            } catch (error) {
                console.error('Erro ao carregar pagamentos:', error);
            }
        }
        
        // Inicializar
        loadAllData();
        document.getElementById('update-time').textContent = 
            'Última atualização: ' + new Date().toLocaleString('pt-BR');
    </script>
</body>
</html>
'''

# Rotas da API Financeira
@app.route('/api/financial/summary')
def financial_summary():
    return jsonify(analyzer.get_financial_summary())

@app.route('/api/financial/monthly-revenue')
def monthly_revenue():
    return jsonify(analyzer.get_monthly_revenue())

@app.route('/api/financial/daily-balance')
def daily_balance():
    return jsonify(analyzer.get_daily_balance())

@app.route('/api/financial/cashflow-prediction')
def cashflow_prediction():
    return jsonify(analyzer.get_cashflow_prediction(30))

@app.route('/api/financial/profitability')
def profitability():
    return jsonify(analyzer.get_profitability_by_product())

@app.route('/api/financial/payments')
def payments_analysis():
    return jsonify(analyzer.get_payment_methods_analysis())

@app.route('/api/financial/expenses')
def expenses_analysis():
    return jsonify(analyzer.get_expense_analysis())

@app.route('/')
def index():
    return render_template_string(FINANCIAL_HTML)

if __name__ == '__main__':
    print("=" * 60)
    print("🏦 MÓDULO FINANCEIRO - SISTEMA DE VAREJO")
    print("=" * 60)
    print("\n📊 Acesse o painel financeiro:")
    print("   👉 http://localhost:5000")
    print("\n📈 Funcionalidades disponíveis:")
    print("   💰 Visão Geral Financeira")
    print("   💵 Fluxo de Caixa com ML")
    print("   📈 Rentabilidade por Produto")
    print("   💳 Análise de Pagamentos")
    print("\n⚠️  Pressione Ctrl+C para parar")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)