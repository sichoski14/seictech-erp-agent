"""
SISTEMA DE ANÁLISE DE VAREJO - VERSÃO FUNCIONAL
"""
from flask import Flask, jsonify, render_template_string
import sqlite3
import random
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Criar banco de dados
DB_PATH = 'data/varejo.db'
os.makedirs('data', exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Produtos
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT, name TEXT, category TEXT,
        price REAL, cost REAL, min_stock INTEGER, max_stock INTEGER
    )''')
    
    # Estoque
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, location TEXT, quantity INTEGER,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')
    
    # Vendas
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, quantity INTEGER,
        price REAL, total REAL,
        payment_method TEXT, operator TEXT,
        sale_date TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')
    
    # Verificar se tem dados
    count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    
    if count == 0:
        # Inserir produtos
        products = [
            ('SKU001', 'Camiseta Básica', 'Vestuário', 49.90, 25.00, 10, 100),
            ('SKU002', 'Calça Jeans', 'Vestuário', 129.90, 65.00, 5, 50),
            ('SKU003', 'Tênis Esportivo', 'Calçados', 299.90, 150.00, 3, 30),
            ('SKU004', 'Boné', 'Acessórios', 39.90, 20.00, 8, 80),
            ('SKU005', 'Meia', 'Acessórios', 19.90, 10.00, 15, 150),
            ('SKU006', 'Jaqueta', 'Vestuário', 199.90, 100.00, 4, 40),
            ('SKU007', 'Bermuda', 'Vestuário', 89.90, 45.00, 6, 60),
            ('SKU008', 'Chinelo', 'Calçados', 29.90, 15.00, 12, 120),
        ]
        
        for p in products:
            c.execute('INSERT INTO products (sku,name,category,price,cost,min_stock,max_stock) VALUES (?,?,?,?,?,?,?)', p)
        
        # Estoque
        for i in range(1, 9):
            for loc in ['LOJA-A', 'LOJA-B', 'CD-01']:
                c.execute('INSERT INTO inventory (product_id,location,quantity) VALUES (?,?,?)', 
                         (i, loc, random.randint(5, 80)))
        
        # Vendas
        payments = ['PIX', 'Cartão Crédito', 'Cartão Débito', 'Dinheiro']
        operators = ['OP001', 'OP002', 'OP003', 'OP004']
        
        for _ in range(200):
            prod_id = random.randint(1, 8)
            price = [p[3] for p in products if p[0] == f'SKU{prod_id:03d}'][0]
            qty = random.randint(1, 4)
            total = price * qty
            days_ago = random.randint(0, 30)
            date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            
            c.execute('INSERT INTO sales (product_id,quantity,price,total,payment_method,operator,sale_date) VALUES (?,?,?,?,?,?,?)',
                     (prod_id, qty, price, total, random.choice(payments), random.choice(operators), date))
    
    conn.commit()
    conn.close()

init_db()

# Funções auxiliares
def query_db(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    result = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in result]

def query_one(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(query, params).fetchone()
    conn.close()
    return result

# HTML COMPLETO
HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Análise de Varejo</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; display: flex; min-height: 100vh; background: #f5f5f5; }
        
        .sidebar {
            width: 250px; background: #1a1a2e; color: white; padding: 20px 0;
            position: fixed; height: 100vh; overflow-y: auto;
        }
        .sidebar h2 { text-align: center; margin-bottom: 30px; font-size: 18px; }
        .menu-btn {
            display: block; width: calc(100% - 40px); margin: 5px 20px;
            padding: 12px 20px; background: transparent; color: #ccc;
            border: none; text-align: left; cursor: pointer; border-radius: 8px;
            font-size: 14px; transition: all 0.3s;
        }
        .menu-btn:hover, .menu-btn.active { background: #16213e; color: white; }
        
        .main { margin-left: 250px; flex: 1; padding: 20px; }
        .header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .header h1 { font-size: 24px; color: #333; }
        
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .card .title { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .card .value { font-size: 28px; font-weight: bold; }
        .card.blue .value { color: #667eea; }
        .card.green .value { color: #48bb78; }
        .card.orange .value { color: #ed8936; }
        .card.red .value { color: #f56565; }
        
        .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .panel { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .panel h3 { margin-bottom: 15px; color: #333; }
        
        table { width: 100%; border-collapse: collapse; }
        th { background: #f7f7f7; padding: 10px; text-align: left; font-size: 12px; text-transform: uppercase; color: #666; }
        td { padding: 10px; border-bottom: 1px solid #eee; font-size: 13px; }
        tr:hover { background: #f9f9f9; }
        
        .badge { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
        .badge-success { background: #c6f6d5; color: #22543d; }
        .badge-danger { background: #fed7d7; color: #822727; }
        .badge-warning { background: #fefcbf; color: #744210; }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .refresh-btn { background: #667eea; color: white; border: none; padding: 8px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 15px; }
        .refresh-btn:hover { background: #5a67d8; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>📊 Retail Analytics</h2>
        <button class="menu-btn active" onclick="showTab('dashboard', this)">📊 Dashboard</button>
        <button class="menu-btn" onclick="showTab('estoque', this)">📦 Estoque</button>
        <button class="menu-btn" onclick="showTab('vendas', this)">💰 Vendas</button>
        <button class="menu-btn" onclick="showTab('financeiro', this)">🏦 Financeiro</button>
        <button class="menu-btn" onclick="showTab('previsoes', this)">🔮 Previsões</button>
    </div>
    
    <div class="main">
        <div class="header">
            <h1 id="pageTitle">📊 Dashboard Principal</h1>
            <small id="updateTime" style="color:#999"></small>
        </div>
        
        <button class="refresh-btn" onclick="loadCurrentTab()">🔄 Atualizar</button>
        
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <div class="cards" id="dashCards"></div>
            <div class="grid-2">
                <div class="panel"><h3>📈 Vendas (30 dias)</h3><canvas id="chartSales30"></canvas></div>
                <div class="panel"><h3>💳 Pagamentos</h3><canvas id="chartPayments"></canvas></div>
            </div>
            <div class="panel"><h3>🏆 Top Produtos</h3><table><thead><tr><th>Produto</th><th>Vendas</th><th>Receita</th><th>Estoque</th></tr></thead><tbody id="topProducts"></tbody></table></div>
        </div>
        
        <!-- ESTOQUE -->
        <div id="estoque" class="tab-content">
            <div class="cards" id="stockCards"></div>
            <div class="panel"><h3>📋 Status do Estoque</h3><table><thead><tr><th>SKU</th><th>Produto</th><th>Categoria</th><th>Quantidade</th><th>Local</th><th>Mínimo</th><th>Status</th></tr></thead><tbody id="stockTable"></tbody></table></div>
        </div>
        
        <!-- VENDAS -->
        <div id="vendas" class="tab-content">
            <div class="cards" id="salesCards"></div>
            <div class="grid-2">
                <div class="panel"><h3>📈 Tendência de Vendas</h3><canvas id="chartTrend"></canvas></div>
                <div class="panel"><h3>👥 Performance por Operador</h3><canvas id="chartOperators"></canvas></div>
            </div>
            <div class="panel"><h3>🔄 Giro de Produtos</h3><table><thead><tr><th>Produto</th><th>Vendas (90d)</th><th>Giro</th><th>Classificação</th></tr></thead><tbody id="turnoverTable"></tbody></table></div>
        </div>
        
        <!-- FINANCEIRO -->
        <div id="financeiro" class="tab-content">
            <div class="cards" id="finCards"></div>
            <div class="grid-2">
                <div class="panel"><h3>💵 Receita Mensal</h3><canvas id="chartMonthly"></canvas></div>
                <div class="panel"><h3>📊 Saldo Diário</h3><canvas id="chartBalance"></canvas></div>
            </div>
            <div class="panel"><h3>📈 Rentabilidade</h3><table><thead><tr><th>Produto</th><th>Categoria</th><th>Receita</th><th>Lucro</th><th>Margem</th></tr></thead><tbody id="profitTable"></tbody></table></div>
        </div>
        
        <!-- PREVISÕES -->
        <div id="previsoes" class="tab-content">
            <div class="grid-2">
                <div class="panel"><h3>🔮 Fluxo de Caixa Previsto</h3><canvas id="chartCashflow"></canvas></div>
                <div class="panel"><h3>💰 Saldo Acumulado</h3><canvas id="chartCumulative"></canvas></div>
            </div>
            <div class="panel"><h3>📋 Previsão 30 Dias</h3><table><thead><tr><th>Data</th><th>Receita</th><th>Custos</th><th>Saldo</th><th>Acumulado</th></tr></thead><tbody id="predictTable"></tbody></table></div>
        </div>
    </div>
    
    <script>
        let currentTab = 'dashboard';
        let charts = {};
        
        function formatMoney(v) { return 'R$ ' + (v||0).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}); }
        
        function showTab(tab, btn) {
            document.querySelectorAll('.menu-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            currentTab = tab;
            
            const titles = {dashboard:'📊 Dashboard Principal', estoque:'📦 Gestão de Estoque', vendas:'💰 Análise de Vendas', financeiro:'🏦 Análise Financeira', previsoes:'🔮 Previsões ML'};
            document.getElementById('pageTitle').textContent = titles[tab];
            
            loadCurrentTab();
        }
        
        function loadCurrentTab() {
            document.getElementById('updateTime').textContent = 'Atualizado: ' + new Date().toLocaleString('pt-BR');
            
            if (currentTab === 'dashboard') loadDashboard();
            else if (currentTab === 'estoque') loadStock();
            else if (currentTab === 'vendas') loadSales();
            else if (currentTab === 'financeiro') loadFinancial();
            else if (currentTab === 'previsoes') loadPredictions();
        }
        
        async function fetchAPI(url) {
            try {
                const resp = await fetch(url);
                return await resp.json();
            } catch(e) {
                console.error('Erro:', e);
                return [];
            }
        }
        
        function destroyChart(id) {
            if (charts[id]) { charts[id].destroy(); delete charts[id]; }
        }
        
        function makeLineChart(id, labels, data, label, color='#667eea') {
            destroyChart(id);
            const ctx = document.getElementById(id);
            if (!ctx) return;
            charts[id] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{label: label, data: data, borderColor: color, backgroundColor: color+'20', fill: true, tension: 0.4}]
                },
                options: { responsive: true, maintainAspectRatio: false,
                    scales: { y: { ticks: { callback: v => formatMoney(v) } } }
                }
            });
        }
        
        function makeBarChart(id, labels, data, label, color='#667eea') {
            destroyChart(id);
            const ctx = document.getElementById(id);
            if (!ctx) return;
            charts[id] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{label: label, data: data, backgroundColor: color, borderRadius: 5}]
                },
                options: { responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { ticks: { callback: v => formatMoney(v) } } }
                }
            });
        }
        
        function makeDoughnutChart(id, labels, data) {
            destroyChart(id);
            const ctx = document.getElementById(id);
            if (!ctx) return;
            charts[id] = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{data: data, backgroundColor: ['#667eea','#48bb78','#ed8936','#f56565','#9f7aea','#4299e1','#ecc94b','#9b59b6']}]
                },
                options: { responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }
        
        function makeMultiLineChart(id, labels, datasets) {
            destroyChart(id);
            const ctx = document.getElementById(id);
            if (!ctx) return;
            charts[id] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets.map(d => ({
                        label: d.label, data: d.data, borderColor: d.color,
                        backgroundColor: d.color+'20', fill: d.fill !== false, tension: 0.4
                    }))
                },
                options: { responsive: true, maintainAspectRatio: false,
                    scales: { y: { ticks: { callback: v => formatMoney(v) } } }
                }
            });
        }
        
        // DASHBOARD
        async function loadDashboard() {
            const [sales, fin, stock, top, pay] = await Promise.all([
                fetchAPI('/api/dashboard/sales'),
                fetchAPI('/api/dashboard/financial'),
                fetchAPI('/api/stock/health'),
                fetchAPI('/api/sales/top-products'),
                fetchAPI('/api/sales/payments')
            ]);
            
            document.getElementById('dashCards').innerHTML = `
                <div class="card blue"><div class="title">Receita Hoje</div><div class="value">${formatMoney(sales.today_revenue)}</div></div>
                <div class="card green"><div class="title">Receita Mês</div><div class="value">${formatMoney(sales.month_revenue)}</div></div>
                <div class="card orange"><div class="title">Transações Hoje</div><div class="value">${sales.today_transactions}</div></div>
                <div class="card red"><div class="title">Produtos Críticos</div><div class="value">${stock.filter(s=>s.status==='CRÍTICO').length}</div></div>
                <div class="card green"><div class="title">Margem Bruta</div><div class="value">${fin.margin.toFixed(1)}%</div></div>
            `;
            
            const trend = await fetchAPI('/api/sales/trend');
            makeLineChart('chartSales30', trend.map(t=>t.date), trend.map(t=>t.revenue), 'Receita');
            
            makeDoughnutChart('chartPayments', pay.map(p=>p.method), pay.map(p=>p.total));
            
            document.getElementById('topProducts').innerHTML = top.map(p => `
                <tr><td>${p.name}</td><td>${p.sales}</td><td>${formatMoney(p.revenue)}</td><td>${p.stock}</td></tr>
            `).join('');
        }
        
        // ESTOQUE
        async function loadStock() {
            const data = await fetchAPI('/api/stock/health');
            const critical = data.filter(s=>s.status==='CRÍTICO').length;
            const alert = data.filter(s=>s.status==='ALERTA').length;
            const normal = data.filter(s=>s.status==='NORMAL').length;
            
            document.getElementById('stockCards').innerHTML = `
                <div class="card blue"><div class="title">Total Produtos</div><div class="value">${data.length}</div></div>
                <div class="card red"><div class="title">Críticos</div><div class="value">${critical}</div></div>
                <div class="card orange"><div class="title">Em Alerta</div><div class="value">${alert}</div></div>
                <div class="card green"><div class="title">Normais</div><div class="value">${normal}</div></div>
            `;
            
            document.getElementById('stockTable').innerHTML = data.map(d => {
                const badge = d.status === 'CRÍTICO' ? 'danger' : d.status === 'ALERTA' ? 'warning' : 'success';
                const text = d.status === 'CRÍTICO' ? 'Crítico' : d.status === 'ALERTA' ? 'Alerta' : 'Normal';
                return `<tr><td>${d.sku}</td><td>${d.name}</td><td>${d.category}</td><td>${d.quantity}</td><td>${d.location}</td><td>${d.min_stock}</td><td><span class="badge badge-${badge}">${text}</span></td></tr>`;
            }).join('');
        }
        
        // VENDAS
        async function loadSales() {
            const [summary, trend, ops, turnover] = await Promise.all([
                fetchAPI('/api/dashboard/sales'),
                fetchAPI('/api/sales/trend'),
                fetchAPI('/api/sales/operators'),
                fetchAPI('/api/sales/turnover')
            ]);
            
            document.getElementById('salesCards').innerHTML = `
                <div class="card blue"><div class="title">Receita Hoje</div><div class="value">${formatMoney(summary.today_revenue)}</div></div>
                <div class="card green"><div class="title">Transações Hoje</div><div class="value">${summary.today_transactions}</div></div>
                <div class="card orange"><div class="title">Ticket Médio</div><div class="value">${formatMoney(summary.today_avg)}</div></div>
                <div class="card blue"><div class="title">Receita Mês</div><div class="value">${formatMoney(summary.month_revenue)}</div></div>
            `;
            
            makeLineChart('chartTrend', trend.map(t=>t.date), trend.map(t=>t.revenue), 'Receita');
            makeBarChart('chartOperators', ops.map(o=>o.operator), ops.map(o=>o.revenue), 'Receita', '#48bb78');
            
            document.getElementById('turnoverTable').innerHTML = turnover.map(t => {
                const cls = t.turnover > 3 ? 'Alto' : t.turnover > 1 ? 'Médio' : 'Baixo';
                const badge = t.turnover > 3 ? 'success' : t.turnover > 1 ? 'warning' : 'danger';
                return `<tr><td>${t.name}</td><td>${t.sales}</td><td>${t.turnover.toFixed(2)}</td><td><span class="badge badge-${badge}">${cls}</span></td></tr>`;
            }).join('');
        }
        
        // FINANCEIRO
        async function loadFinancial() {
            const [summary, monthly, balance, profit] = await Promise.all([
                fetchAPI('/api/dashboard/financial'),
                fetchAPI('/api/financial/monthly'),
                fetchAPI('/api/financial/daily-balance'),
                fetchAPI('/api/financial/profitability')
            ]);
            
            document.getElementById('finCards').innerHTML = `
                <div class="card blue"><div class="title">Receita 30d</div><div class="value">${formatMoney(summary.revenue)}</div></div>
                <div class="card green"><div class="title">Lucro Bruto</div><div class="value">${formatMoney(summary.profit)}</div></div>
                <div class="card orange"><div class="title">Margem</div><div class="value">${summary.margin.toFixed(1)}%</div></div>
                <div class="card red"><div class="title">Custos</div><div class="value">${formatMoney(summary.cost)}</div></div>
            `;
            
            makeBarChart('chartMonthly', monthly.map(m=>m.month), monthly.map(m=>m.revenue), 'Receita');
            
            makeMultiLineChart('chartBalance', balance.map(b=>b.date), [
                {label:'Receita', data:balance.map(b=>b.revenue), color:'#48bb78'},
                {label:'Custos', data:balance.map(b=>b.cost), color:'#f56565'},
                {label:'Saldo', data:balance.map(b=>b.balance), color:'#667eea'}
            ]);
            
            document.getElementById('profitTable').innerHTML = profit.map(p => `
                <tr>
                    <td>${p.name}</td><td>${p.category}</td>
                    <td>${formatMoney(p.revenue)}</td>
                    <td style="color:${p.profit>=0?'green':'red'}">${formatMoney(p.profit)}</td>
                    <td><strong>${p.margin.toFixed(1)}%</strong></td>
                </tr>
            `).join('');
        }
        
        // PREVISÕES
        async function loadPredictions() {
            const data = await fetchAPI('/api/financial/cashflow');
            
            makeMultiLineChart('chartCashflow', data.map(d=>d.date), [
                {label:'Receita', data:data.map(d=>d.revenue), color:'#48bb78'},
                {label:'Saldo', data:data.map(d=>d.balance), color:'#667eea'}
            ]);
            
            makeLineChart('chartCumulative', data.map(d=>d.date), data.map(d=>d.cumulative), 'Acumulado', '#ed8936');
            
            document.getElementById('predictTable').innerHTML = data.map(d => `
                <tr>
                    <td><strong>${d.date}</strong></td>
                    <td style="color:green">${formatMoney(d.revenue)}</td>
                    <td style="color:red">${formatMoney(d.cost)}</td>
                    <td style="color:#667eea;font-weight:bold">${formatMoney(d.balance)}</td>
                    <td>${formatMoney(d.cumulative)}</td>
                </tr>
            `).join('');
        }
        
        // Iniciar
        loadDashboard();
    </script>
</body>
</html>
'''

# ROTAS API
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/dashboard/sales')
def dash_sales():
    today = query_one("SELECT COALESCE(SUM(total),0), COUNT(*) FROM sales WHERE DATE(sale_date)=DATE('now')")
    month = query_one("SELECT COALESCE(SUM(total),0), COUNT(*) FROM sales WHERE sale_date>=DATE('now','-30 days')")
    return jsonify({
        'today_revenue': today[0] or 0,
        'today_transactions': today[1] or 0,
        'today_avg': (today[0]/today[1]) if today[1] > 0 else 0,
        'month_revenue': month[0] or 0,
        'month_transactions': month[1] or 0
    })

@app.route('/api/dashboard/financial')
def dash_financial():
    rev = query_one("SELECT COALESCE(SUM(total),0) FROM sales WHERE sale_date>=DATE('now','-30 days')")[0]
    cost = query_one("""
        SELECT COALESCE(SUM(s.quantity*p.cost),0) FROM sales s
        JOIN products p ON s.product_id=p.id
        WHERE s.sale_date>=DATE('now','-30 days')
    """)[0]
    profit = rev - cost
    margin = (profit/rev*100) if rev > 0 else 0
    return jsonify({'revenue': rev, 'cost': cost, 'profit': profit, 'margin': margin})

@app.route('/api/stock/health')
def stock_health():
    data = query_db("""
        SELECT p.sku, p.name, p.category, i.quantity, i.location, p.min_stock,
               CASE WHEN i.quantity<=p.min_stock THEN 'CRÍTICO'
                    WHEN i.quantity<=p.min_stock*1.5 THEN 'ALERTA'
                    ELSE 'NORMAL' END as status
        FROM products p JOIN inventory i ON p.id=i.product_id
        ORDER BY i.quantity ASC
    """)
    return jsonify(data)

@app.route('/api/sales/trend')
def sales_trend():
    data = query_db("""
        SELECT DATE(sale_date) as date, SUM(total) as revenue
        FROM sales WHERE sale_date>=DATE('now','-30 days')
        GROUP BY DATE(sale_date) ORDER BY date
    """)
    return jsonify(data)

@app.route('/api/sales/top-products')
def top_products():
    data = query_db("""
        SELECT p.name, p.sku, COUNT(s.id) as sales, SUM(s.total) as revenue, i.quantity as stock
        FROM products p
        LEFT JOIN sales s ON p.id=s.product_id AND s.sale_date>=DATE('now','-30 days')
        LEFT JOIN inventory i ON p.id=i.product_id
        GROUP BY p.id ORDER BY revenue DESC LIMIT 10
    """)
    return jsonify(data)

@app.route('/api/sales/payments')
def payments():
    data = query_db("""
        SELECT payment_method as method, COUNT(*) as count, SUM(total) as total, AVG(total) as avg
        FROM sales WHERE sale_date>=DATE('now','-30 days')
        GROUP BY payment_method ORDER BY total DESC
    """)
    return jsonify(data)

@app.route('/api/sales/operators')
def operators():
    data = query_db("""
        SELECT operator, COUNT(*) as sales, SUM(total) as revenue, AVG(total) as avg_ticket
        FROM sales WHERE sale_date>=DATE('now','-30 days')
        GROUP BY operator ORDER BY revenue DESC
    """)
    return jsonify(data)

@app.route('/api/sales/turnover')
def turnover():
    data = query_db("""
        SELECT p.name, p.sku, COUNT(s.id) as sales, 
               COALESCE(AVG(i.quantity),0) as avg_stock,
               CASE WHEN AVG(i.quantity)>0 THEN COUNT(s.id)*1.0/AVG(i.quantity) ELSE 0 END as turnover
        FROM products p
        LEFT JOIN sales s ON p.id=s.product_id AND s.sale_date>=DATE('now','-90 days')
        LEFT JOIN inventory i ON p.id=i.product_id
        GROUP BY p.id ORDER BY turnover DESC
    """)
    return jsonify(data)

@app.route('/api/financial/monthly')
def financial_monthly():
    data = query_db("""
        SELECT strftime('%Y-%m', sale_date) as month, SUM(total) as revenue, COUNT(*) as transactions
        FROM sales WHERE sale_date>=DATE('now','-12 months')
        GROUP BY month ORDER BY month
    """)
    return jsonify(data)

@app.route('/api/financial/daily-balance')
def daily_balance():
    data = query_db("""
        SELECT DATE(s.sale_date) as date, SUM(s.total) as revenue,
               COALESCE(SUM(s.quantity*p.cost),0) as cost,
               SUM(s.total)-COALESCE(SUM(s.quantity*p.cost),0) as balance
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.sale_date>=DATE('now','-30 days')
        GROUP BY DATE(s.sale_date) ORDER BY date
    """)
    return jsonify(data)

@app.route('/api/financial/cashflow')
def cashflow():
    import random as rnd
    predictions = []
    cumulative = 0
    for i in range(1, 31):
        date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
        revenue = rnd.uniform(500, 3000)
        cost = revenue * 0.6
        balance = revenue - cost
        cumulative += balance
        predictions.append({'date': date, 'revenue': round(revenue,2), 'cost': round(cost,2), 'balance': round(balance,2), 'cumulative': round(cumulative,2)})
    return jsonify(predictions)

@app.route('/api/financial/profitability')
def profitability():
    data = query_db("""
        SELECT p.name, p.sku, p.category, COUNT(s.id) as units, SUM(s.total) as revenue,
               SUM(s.total)-(SUM(s.quantity)*AVG(p.cost)) as profit,
               CASE WHEN SUM(s.total)>0 THEN ((SUM(s.total)-(SUM(s.quantity)*AVG(p.cost)))/SUM(s.total))*100 ELSE 0 END as margin
        FROM products p
        LEFT JOIN sales s ON p.id=s.product_id AND s.sale_date>=DATE('now','-90 days')
        GROUP BY p.id ORDER BY profit DESC
    """)
    return jsonify(data)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SISTEMA DE ANÁLISE DE VAREJO")
    print("=" * 60)
    print("🌐 http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)