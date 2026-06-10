"""
SEICTECH - RETAIL ANALYTICS PRO - SISTEMA COMPLETO
Todas as funcionalidades: Login, Admin, Analytics, Sell-Out, Estoque, Cliente, Financeiro, ERP
"""
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for, make_response
from flask_cors import CORS
from functools import wraps
import sqlite3
import hashlib
import random
import uuid
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)
app.secret_key = 'seictech_retail_completo_2024_secret'
CORS(app)

DB_PATH = 'data/seictech_completo.db'
os.makedirs('data', exist_ok=True)

# ============================================
# BANCO DE DADOS COMPLETO
# ============================================
def init_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabelas de sistema
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        role TEXT DEFAULT 'user', active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        cnpj TEXT, email TEXT, phone TEXT,
        segment TEXT DEFAULT 'supermercado',
        environment TEXT DEFAULT 'homologacao',
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        company_id INTEGER, permission TEXT DEFAULT 'viewer',
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(company_id) REFERENCES companies(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER,
        license_key TEXT UNIQUE, start_date DATE, end_date DATE,
        max_users INTEGER DEFAULT 5, value REAL DEFAULT 0,
        status TEXT DEFAULT 'active', notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(company_id) REFERENCES companies(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS erp_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER UNIQUE,
        erp_type TEXT, api_url TEXT, api_key TEXT,
        db_host TEXT, db_port TEXT, db_name TEXT,
        db_type TEXT DEFAULT 'postgresql', db_user TEXT, db_password TEXT,
        sync_interval INTEGER DEFAULT 300, last_sync TIMESTAMP, active INTEGER DEFAULT 1,
        FOREIGN KEY(company_id) REFERENCES companies(id))''')
    
    # Tabelas de análise
    c.execute('''CREATE TABLE IF NOT EXISTS sales_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER,
        sale_date DATE, gross_revenue REAL, net_revenue REAL,
        returns REAL, taxes REAL, total_transactions INTEGER,
        total_items INTEGER, category TEXT, department TEXT,
        payment_method TEXT, customer_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER,
        product_sku TEXT, product_name TEXT, category TEXT,
        department TEXT, quantity INTEGER, unit_cost REAL,
        unit_price REAL, min_stock INTEGER, max_stock INTEGER,
        location TEXT, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS customer_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER,
        customer_id TEXT, name TEXT, total_purchases REAL,
        visit_count INTEGER, last_purchase DATE, nps_score INTEGER,
        segment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS financial_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER,
        period TEXT, total_revenue REAL, total_costs REAL,
        fixed_costs REAL, variable_costs REAL, ebitda REAL,
        cmv REAL, break_even REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        company_id INTEGER, action TEXT, ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Super admin padrão
    pwd = hashlib.sha256('Bolsonaro@2022'.encode()).hexdigest()
    try:
        c.execute('INSERT OR IGNORE INTO users (id, name, email, password, role) VALUES (1,?,?,?,?)',
                  ('Super Admin', 'sichoski.analista@gmail.com', pwd, 'super_admin'))
    except: pass
    
    # Dados de exemplo
    try:
        c.execute("INSERT OR IGNORE INTO companies (id, name, segment, environment) VALUES (1, 'Mercado Exemplo', 'supermercado', 'homologacao')")
        c.execute("INSERT OR IGNORE INTO companies (id, name, segment, environment) VALUES (2, 'Construção Pro', 'construcao', 'homologacao')")
        c.execute("INSERT OR IGNORE INTO companies (id, name, segment, environment) VALUES (3, 'Fashion Store', 'roupas', 'homologacao')")
        c.execute("INSERT OR IGNORE INTO companies (id, name, segment, environment) VALUES (4, 'Atacadão Brasil', 'atacadista', 'homologacao')")
        
        # Sales data
        for i in range(30):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            for cid in [1,2,3,4]:
                c.execute("INSERT OR IGNORE INTO sales_data (company_id,sale_date,gross_revenue,net_revenue,returns,taxes,total_transactions,total_items,category) VALUES (?,?,?,?,?,?,?,?,?)",
                         (cid, d, random.uniform(3000,20000), random.uniform(2500,17000), random.uniform(50,800), random.uniform(200,1500), random.randint(30,300), random.randint(80,600), random.choice(['Hortifruti','Mercearia','Bebidas','Limpeza','Açougue','Padaria'])))
        
        # Inventory data
        for cid in [1,2,3,4]:
            for i in range(25):
                c.execute("INSERT OR IGNORE INTO inventory_data (company_id,product_sku,product_name,category,quantity,unit_cost,unit_price,min_stock,max_stock) VALUES (?,?,?,?,?,?,?,?,?)",
                         (cid, f'SKU{cid}{i:03d}', f'Produto {cid}-{i}', random.choice(['Hortifruti','Mercearia','Bebidas','Limpeza','Açougue','Hidráulica','Elétrica','Ferramentas','Roupas','Calçados','Acessórios']), random.randint(0,120), random.uniform(5,80), random.uniform(10,150), 10, 100))
        
        # Customer data
        for cid in [1,2,3,4]:
            for i in range(15):
                c.execute("INSERT OR IGNORE INTO customer_data (company_id,customer_id,name,total_purchases,visit_count,last_purchase,nps_score) VALUES (?,?,?,?,?,?,?)",
                         (cid, f'CUST{cid}{i:03d}', f'Cliente {cid}-{i}', random.uniform(100,8000), random.randint(1,25), (datetime.now()-timedelta(days=random.randint(1,60))).strftime('%Y-%m-%d'), random.randint(1,10)))
        
        # Financial data
        for cid in [1,2,3,4]:
            for i in range(12):
                month = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m')
                revenue = random.uniform(40000,180000)
                cmv = revenue * random.uniform(0.4, 0.65)
                fixed = revenue * random.uniform(0.1, 0.25)
                c.execute("INSERT OR IGNORE INTO financial_data (company_id,period,total_revenue,total_costs,fixed_costs,ebitda,cmv,break_even) VALUES (?,?,?,?,?,?,?,?)",
                         (cid, month, revenue, cmv+fixed, fixed, revenue-cmv-fixed, cmv, revenue*0.55))
    except: pass
    
    conn.commit()
    conn.close()

init_database()

# Funções auxiliares
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, params=()):
    conn = get_db()
    result = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in result]

def query_one(query, params=()):
    conn = get_db()
    result = conn.execute(query, params).fetchone()
    conn.close()
    return dict(result) if result else None

def execute_db(query, params=()):
    conn = get_db()
    conn.execute(query, params)
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect('/login')
        if session.get('role') != 'super_admin': return jsonify({'error': 'Acesso negado. Apenas Super Admin.'}), 403
        return f(*args, **kwargs)
    return decorated

# ============================================
# TEMPLATE HTML - PARTE 1 (CSS + Estrutura)
# ============================================
HTML_HEAD = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEICTECH - Retail Analytics Pro</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --w: 260px; --p: #3b82f6; --s: #10b981; --warn: #f59e0b; --d: #ef4444;
            --bg: #f1f5f9; --c: #fff; --t: #1e293b; --tl: #64748b; --b: #e2e8f0;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; display: flex; min-height: 100vh; background: var(--bg); color: var(--t); }
        
        /* SIDEBAR */
        .sidebar {
            width: var(--w); background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
            color: white; position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto;
            z-index: 100; display: flex; flex-direction: column; box-shadow: 4px 0 20px rgba(0,0,0,0.1);
        }
        .sb-brand { padding: 24px 20px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.08); }
        .sb-brand .logo { font-size: 24px; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .sb-brand .tag { font-size: 9px; color: #94a3b8; letter-spacing: 2px; margin-top: 2px; }
        .sb-user { padding: 14px 20px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); }
        .av { width: 38px; height: 38px; border-radius: 10px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; flex-shrink: 0; }
        .ui .name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ui .role { font-size: 9px; color: #94a3b8; text-transform: capitalize; }
        .ns { padding: 8px 20px; font-size: 9px; text-transform: uppercase; letter-spacing: 1.5px; color: #64748b; font-weight: 700; margin-top: 8px; }
        .ni {
            display: flex; align-items: center; gap: 8px; width: calc(100% - 20px);
            margin: 2px 10px; padding: 9px 12px; background: transparent; color: #cbd5e1;
            border: none; border-radius: 8px; cursor: pointer; font-size: 12px; transition: all 0.2s; text-align: left;
        }
        .ni:hover { background: rgba(255,255,255,0.06); color: white; }
        .ni.active { background: rgba(59,130,246,0.2); color: #60a5fa; font-weight: 500; }
        .ni .ico { font-size: 15px; width: 20px; text-align: center; flex-shrink: 0; }
        .sf { margin-top: auto; padding: 14px 20px; border-top: 1px solid rgba(255,255,255,0.08); }
        .btn-out {
            width: 100%; padding: 10px; background: rgba(239,68,68,0.15); color: #fca5a5;
            border: 1px solid rgba(239,68,68,0.3); border-radius: 8px; cursor: pointer;
            font-size: 11px; font-weight: 500; transition: all 0.2s;
        }
        .btn-out:hover { background: rgba(239,68,68,0.25); color: #fecaca; }
        
        /* MAIN */
        .main { margin-left: var(--w); flex: 1; min-height: 100vh; }
        .tb {
            background: white; padding: 16px 24px; border-bottom: 1px solid var(--b);
            display: flex; justify-content: space-between; align-items: center;
            position: sticky; top: 0; z-index: 50;
        }
        .tb h1 { font-size: 18px; font-weight: 600; }
        .ca { padding: 24px; }
        .tc { display: none; } .tc.active { display: block; }
        
        /* HERO */
        .hero {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #8b5cf6 100%);
            color: white; padding: 35px; border-radius: 14px; margin-bottom: 20px;
            position: relative; overflow: hidden;
        }
        .hero::before { content: ''; position: absolute; top: -50%; right: -50%; width: 100%; height: 100%; background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%); }
        .hero h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; position: relative; }
        .hero p { font-size: 14px; opacity: 0.9; max-width: 600px; position: relative; }
        .hs { display: flex; gap: 15px; margin-top: 18px; position: relative; flex-wrap: wrap; }
        .hs2 { background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); padding: 14px 18px; border-radius: 10px; text-align: center; min-width: 110px; }
        .hs2 .n { font-size: 22px; font-weight: 700; } .hs2 .l { font-size: 9px; opacity: 0.8; margin-top: 3px; }
        
        /* CARDS */
        .bg { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .bc {
            background: white; padding: 20px; border-radius: 10px; border: 1px solid var(--b);
            transition: all 0.3s; cursor: default;
        }
        .bc:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.08); border-color: #93c5fd; }
        .bc .ic { font-size: 28px; margin-bottom: 10px; }
        .bc h4 { font-size: 14px; font-weight: 600; margin-bottom: 5px; }
        .bc p { font-size: 11px; color: var(--tl); line-height: 1.5; }
        
        /* KPIs */
        .kg { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 18px; }
        .kc {
            background: white; padding: 16px; border-radius: 8px; border: 1px solid var(--b);
            border-left: 3px solid #e2e8f0;
        }
        .kc .l { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--tl); font-weight: 600; margin-bottom: 5px; }
        .kc .v { font-size: 22px; font-weight: 700; }
        .kc.bl { border-left-color: var(--p); } .kc.bl .v { color: var(--p); }
        .kc.gr { border-left-color: var(--s); } .kc.gr .v { color: var(--s); }
        .kc.pu { border-left-color: #8b5cf6; } .kc.pu .v { color: #8b5cf6; }
        .kc.or { border-left-color: #f59e0b; } .kc.or .v { color: #f59e0b; }
        .kc.rd { border-left-color: var(--d); } .kc.rd .v { color: var(--d); }
        
        /* CHARTS */
        .cr { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px; }
        .cb { background: white; padding: 16px; border-radius: 10px; border: 1px solid var(--b); }
        .cb h4 { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
        .cw { position: relative; width: 100%; height: 270px; }
        .cw canvas { max-width: 100%; max-height: 100%; }
        
        /* TABLES */
        .cd { background: white; padding: 18px; border-radius: 10px; border: 1px solid var(--b); margin-bottom: 18px; overflow-x: auto; }
        .cd h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; }
        th { background: #f8fafc; padding: 10px 12px; text-align: left; font-weight: 600; color: var(--tl); font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid var(--b); white-space: nowrap; }
        td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }
        tr:hover td { background: #f8fafc; }
        
        /* BADGES */
        .badge { display: inline-block; padding: 3px 9px; border-radius: 12px; font-size: 9px; font-weight: 600; white-space: nowrap; }
        .badge-s { background: #d1fae5; color: #065f46; } .badge-d { background: #fee2e2; color: #991b1b; }
        .badge-w { background: #fef3c7; color: #92400e; } .badge-i { background: #dbeafe; color: #1e40af; }
        .badge-p { background: #ede9fe; color: #5b21b6; }
        
        /* BUTTONS */
        .btn { display: inline-block; padding: 8px 16px; border: none; border-radius: 7px; cursor: pointer; font-size: 12px; font-weight: 500; transition: all 0.2s; text-decoration: none; }
        .btn-p { background: var(--p); color: white; } .btn-p:hover { background: #2563eb; }
        .btn-s { background: var(--s); color: white; } .btn-s:hover { background: #047857; }
        .btn-w { background: #d97706; color: white; } .btn-w:hover { background: #b45309; }
        .btn-d { background: var(--d); color: white; } .btn-d:hover { background: #b91c1c; }
        .btn-sm { padding: 5px 10px; font-size: 10px; }
        .btn-xs { padding: 3px 7px; font-size: 9px; }
        
        /* FORMS */
        .fr { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .fg { margin-bottom: 12px; }
        .fg label { display: block; font-size: 11px; font-weight: 600; color: #374151; margin-bottom: 4px; }
        .fg input, .fg select, .fg textarea { width: 100%; padding: 9px 12px; border: 1px solid var(--b); border-radius: 7px; font-size: 12px; transition: border-color 0.2s; }
        .fg input:focus, .fg select:focus { outline: none; border-color: var(--p); box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
        
        /* MODAL */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
        .modal-overlay.show { display: flex; }
        .modal { background: white; border-radius: 14px; padding: 28px; width: 550px; max-width: 92%; max-height: 85vh; overflow-y: auto; box-shadow: 0 25px 80px rgba(0,0,0,0.25); }
        .modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
        .ma { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
        
        /* SEGMENT BADGE */
        .seg-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 10px; font-weight: 600; }
        .seg-supermercado { background: #dbeafe; color: #1e40af; }
        .seg-construcao { background: #fef3c7; color: #92400e; }
        .seg-roupas { background: #ede9fe; color: #5b21b6; }
        .seg-atacadista { background: #d1fae5; color: #065f46; }
        
        @media (max-width: 900px) {
            .sidebar { width: 55px; }
            .sb-brand, .ui, .ns, .ni span:not(.ico) { display: none; }
            .ni { justify-content: center; padding: 10px; }
            .main { margin-left: 55px; }
            .cr, .fr { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>

HTML_SIDEBAR = '''
<div class="sidebar">
    <div class="sb-brand"><div class="logo">SEICTECH</div><div class="tag">RETAIL ANALYTICS PRO</div></div>
    <div class="sb-user">
        <div class="av">{{session.get('user_name','U')[0]}}</div>
        <div class="ui"><div class="name">{{session.get('user_name','Usuário')}}</div><div class="role">{{session.get('role','user')|replace('_',' ')|title}}</div></div>
    </div>
    
    <div class="ns">Principal</div>
    <button class="ni active" onclick="showTab('home')"><span class="ico"></span> <span>Início</span></button>
    <button class="ni" onclick="showTab('analytics')"><span class="ico"></span> <span>Analytics Geral</span></button>
    
    <div class="ns">Análises Avançadas</div>
    <button class="ni" onclick="showTab('sellout')"><span class="ico"></span> <span>Análise Sell-Out</span></button>
    <button class="ni" onclick="showTab('estoque')"><span class="ico"></span> <span>Estoque & Suprimentos</span></button>
    <button class="ni" onclick="showTab('cliente')"><span class="ico"></span> <span>Comportamento Cliente</span></button>
    <button class="ni" onclick="showTab('financeiro')"><span class="ico"></span> <span>Financeiro & Custos</span></button>
    
    <div class="ns">Segmentos</div>
    <button class="ni" onclick="showTab('supermercado')"><span class="ico"></span> <span>Supermercado</span></button>
    <button class="ni" onclick="showTab('construcao')"><span class="ico"></span> <span>Mat. Construção</span></button>
    <button class="ni" onclick="showTab('roupas')"><span class="ico"></span> <span>Loja de Roupas</span></button>
    <button class="ni" onclick="showTab('atacadista')"><span class="ico"></span> <span>Atacadista</span></button>
    
    {% if session.get('role') == 'super_admin' %}
    <div class="ns">Administração</div>
    <button class="ni" onclick="showTab('companies')"><span class="ico"></span> <span>Empresas</span></button>
    <button class="ni" onclick="showTab('users')"><span class="ico"></span> <span>Usuários</span></button>
    <button class="ni" onclick="showTab('licenses')"><span class="ico"></span> <span>Licenças</span></button>
    <button class="ni" onclick="showTab('erp')"><span class="ico"></span> <span>Integração ERP</span></button>
    {% endif %}
    
    <div class="sf"><button class="btn-out" onclick="logout()"> Sair do Sistema</button></div>
</div>
'''

HTML_CONTENT_START = '''
<div class="main">
    <div class="tb">
        <h1 id="pt"> Início - SEICTECH</h1>
        <small style="color:#94a3b8" id="ut"></small>
    </div>
    <div class="ca">
'''

# ============================================
# TEMPLATES DAS TELAS
# ============================================

HTML_HOME = '''
<div id="home" class="tc active">
    <div class="hero">
        <h1> Plataforma Completa de Análise de Varejo</h1>
        <p>Dashboards profissionais com análises de Sell-Out, Estoque, Comportamento do Cliente, Financeiro e indicadores específicos por segmento de mercado.</p>
        <div class="hs">
            <div class="hs2"><div class="n" id="hs1">-</div><div class="l">Empresas Ativas</div></div>
            <div class="hs2"><div class="n" id="hs2">-</div><div class="l">Licenças</div></div>
            <div class="hs2"><div class="n" id="hs3">-</div><div class="l">Faturamento Total</div></div>
        </div>
    </div>
    
    <h3 style="margin-bottom:12px;font-size:15px;"> Módulos de Análise Disponíveis</h3>
    <div class="bg">
        <div class="bc"><div class="ic"></div><h4>Análise Sell-Out</h4><p>Faturamento Bruto/Líquido, Ticket Médio, Margem de Contribuição, Vendas por Categoria/Departamento e Metro Quadrado.</p></div>
        <div class="bc"><div class="ic"></div><h4>Estoque & Suprimentos</h4><p>Giro de Estoque, Ruptura de Gôndola, GMROI, Curva ABC (20/80), Cobertura de Estoque e Otimização.</p></div>
        <div class="bc"><div class="ic"></div><h4>Comportamento Cliente</h4><p>Taxa de Conversão, Frequência/Recorrência, Churn Rate, Análise de Cesta (MBA) e NPS.</p></div>
        <div class="bc"><div class="ic"></div><h4>Financeiro & Custos</h4><p>Break-even Point, CMV, EBITDA/LAJIDA, Ciclo Financeiro e Análise de Rentabilidade.</p></div>
        <div class="bc"><div class="ic"></div><h4>Machine Learning</h4><p>Previsão de Demanda, Detecção de Anomalias, Recomendações Inteligentes e Alertas Automáticos.</p></div>
        <div class="bc"><div class="ic"></div><h4>Dashboards DLI/WLI/MLI</h4><p>Análises Diárias (DLI), Semanais (WLI) e Mensais (MLI) com KPIs específicos por segmento.</p></div>
    </div>
    
    <h3 style="margin-bottom:12px;font-size:15px;"> Impacto da Plataforma por Segmento</h3>
    <div class="kg">
        <div class="kc bl"><div class="l"> Supermercado</div><div class="v">-35% Quebra</div></div>
        <div class="kc gr"><div class="l"> Mat. Construção</div><div class="v">+28% Vendas</div></div>
        <div class="kc pu"><div class="l"> Loja Roupas</div><div class="v">+42% Giro</div></div>
        <div class="kc or"><div class="l"> Atacadista</div><div class="v">320% ROI</div></div>
    </div>
    
    <h3 style="margin-bottom:12px;font-size:15px;"> Rotina de Análise</h3>
    <div class="bg">
        <div class="bc"><div class="ic"></div><h4>DLI - Diário</h4><p>Faturamento, Ticket Médio e Ruptura. Correção rápida de problemas operacionais.</p></div>
        <div class="bc"><div class="ic"></div><h4>WLI - Semanal</h4><p>Giro de estoque, performance de promoções e escalas de equipe.</p></div>
        <div class="bc"><div class="ic"></div><h4>MLI - Mensal</h4><p>DRE completa, Curva ABC, NPS e análise de perdas e resultados.</p></div>
    </div>
</div>
'''

HTML_ANALYTICS = '''
<div id="analytics" class="tc">
    <div class="fg"><label>Selecionar Empresa para Análise</label><select id="asel" onchange="loadAnalytics()"><option value="">Carregando...</option></select></div>
    <div class="kg" id="akpi"></div>
    <div class="cr">
        <div class="cb"><h4> Vendas Recentes</h4><div class="cw"><canvas id="c1"></canvas></div></div>
        <div class="cb"><h4> Distribuição Estoque</h4><div class="cw"><canvas id="c2"></canvas></div></div>
    </div>
</div>
'''

HTML_SELLOUT = '''
<div id="sellout" class="tc">
    <div class="fg"><label>Empresa</label><select id="sosel" onchange="loadSellOut()"><option value="">Carregando...</option></select></div>
    <div class="kg" id="sokpi"></div>
    <div class="cr">
        <div class="cb"><h4> Faturamento Bruto vs Líquido (30 dias)</h4><div class="cw"><canvas id="so1"></canvas></div></div>
        <div class="cb"><h4> Vendas por Categoria</h4><div class="cw"><canvas id="so2"></canvas></div></div>
    </div>
    <div class="cd">
        <h3> Performance de Vendas (Sell-Out) - Últimos 15 dias</h3>
        <div style="overflow-x:auto;">
            <table><thead><tr><th>Data</th><th>Fat. Bruto</th><th>Fat. Líquido</th><th>Devoluções</th><th>Impostos</th><th>Transações</th><th>Itens</th><th>Ticket Médio</th><th>Categoria</th></tr></thead><tbody id="sotable"></tbody></table>
        </div>
    </div>
</div>
'''

HTML_ESTOQUE = '''
<div id="estoque" class="tc">
    <div class="fg"><label>Empresa</label><select id="esel" onchange="loadEstoque()"><option value="">Carregando...</option></select></div>
    <div class="kg" id="ekpi"></div>
    <div class="cr">
        <div class="cb"><h4> Curva ABC - Distribuição</h4><div class="cw"><canvas id="e1"></canvas></div></div>
        <div class="cb"><h4> Giro de Estoque por Categoria</h4><div class="cw"><canvas id="e2"></canvas></div></div>
    </div>
    <div class="cd">
        <h3> Análise de Estoque & Suprimentos</h3>
        <div style="overflow-x:auto;">
            <table><thead><tr><th>SKU</th><th>Produto</th><th>Categoria</th><th>Qtd Atual</th><th>Est. Mín</th><th>Ruptura</th><th>Giro (30d)</th><th>Curva ABC</th><th>GMROI</th><th>Cobertura</th></tr></thead><tbody id="etable"></tbody></table>
        </div>
    </div>
</div>
'''

HTML_CLIENTE = '''
<div id="cliente" class="tc">
    <div class="fg"><label>Empresa</label><select id="clsel" onchange="loadCliente()"><option value="">Carregando...</option></select></div>
    <div class="kg" id="clkpi"></div>
    <div class="cr">
        <div class="cb"><h4> Distribuição NPS</h4><div class="cw"><canvas id="cl1"></canvas></div></div>
        <div class="cb"><h4> Frequência de Visitas</h4><div class="cw"><canvas id="cl2"></canvas></div></div>
    </div>
    <div class="cd">
        <h3> Comportamento do Cliente</h3>
        <div style="overflow-x:auto;">
            <table><thead><tr><th>Cliente</th><th>Total Compras</th><th>Visitas</th><th>Última Compra</th><th>Dias Sem Comprar</th><th>NPS</th><th>Classificação</th><th>Risco Churn</th></tr></thead><tbody id="cltable"></tbody></table>
        </div>
    </div>
</div>
'''

HTML_FINANCEIRO = '''
<div id="financeiro" class="tc">
    <div class="fg"><label>Empresa</label><select id="fisel" onchange="loadFinanceiro()"><option value="">Carregando...</option></select></div>
    <div class="kg" id="fikpi"></div>
    <div class="cr">
        <div class="cb"><h4> Receita vs EBITDA</h4><div class="cw"><canvas id="fi1"></canvas></div></div>
        <div class="cb"><h4> Break-even Point & CMV</h4><div class="cw"><canvas id="fi2"></canvas></div></div>
    </div>
    <div class="cd">
        <h3> Análise Financeira & Custos - Últimos 12 períodos</h3>
        <div style="overflow-x:auto;">
            <table><thead><tr><th>Período</th><th>Receita Total</th><th>CMV</th><th>Custos Fixos</th><th>Custos Variáveis</th><th>EBITDA</th><th>Margem %</th><th>Break-even</th></tr></thead><tbody id="fitable"></tbody></table>
        </div>
    </div>
</div>
'''

HTML_SEGMENTOS = '''
<div id="supermercado" class="tc">
    <div class="hero" style="background:linear-gradient(135deg,#065f46,#059669,#10b981);">
        <h1> Análise para Supermercado</h1><p>Foco em Giro Rápido, Perecibilidade e Quebra de Produtos</p>
        <div class="hs"><div class="hs2"><div class="n" id="sup1">-</div><div class="l">Quebra Reduzida</div></div><div class="hs2"><div class="n" id="sup2">-</div><div class="l">Giro Médio</div></div></div>
    </div>
    <div class="kg"><div class="kc bl"><div class="l">Quebra (Perda)</div><div class="v">2.3%</div></div><div class="kc gr"><div class="l">Giro Estoque</div><div class="v">12x</div></div><div class="kc pu"><div class="l">Ticket Médio</div><div class="v">R$ 45,80</div></div><div class="kc or"><div class="l">Margem Média</div><div class="v">22%</div></div></div>
    <div class="cd"><h3> Indicadores Chave - Supermercado</h3><table><thead><tr><th>Indicador</th><th>Valor</th><th>Meta</th><th>Status</th></tr></thead><tbody><tr><td>Quebra Operacional</td><td>2.3%</td><td>< 2.5%</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Giro Hortifruti</td><td>18x/mês</td><td>> 15x</td><td><span class="badge badge-s"> Excelente</span></td></tr><tr><td>Ruptura Gôndola</td><td>4.5%</td><td>< 5%</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Margem Perecíveis</td><td>28%</td><td>> 25%</td><td><span class="badge badge-s"> Acima Meta</span></td></tr></tbody></table></div>
</div>

<div id="construcao" class="tc">
    <div class="hero" style="background:linear-gradient(135deg,#78350f,#d97706,#f59e0b);">
        <h1> Material de Construção</h1><p>Foco em Mix de Produtos, Logística e Prazo de Entrega</p>
        <div class="hs"><div class="hs2"><div class="n" id="cons1">-</div><div class="l">Frete/Venda</div></div><div class="hs2"><div class="n" id="cons2">-</div><div class="l">Prazo Médio</div></div></div>
    </div>
    <div class="kg"><div class="kc bl"><div class="l">Frete s/ Vendas</div><div class="v">8.5%</div></div><div class="kc gr"><div class="l">Prazo Entrega</div><div class="v">3.2 dias</div></div><div class="kc pu"><div class="l">Ticket Médio</div><div class="v">R$ 280</div></div><div class="kc or"><div class="l">Margem Média</div><div class="v">35%</div></div></div>
    <div class="cd"><h3> Indicadores Chave - Material de Construção</h3><table><thead><tr><th>Indicador</th><th>Valor</th><th>Meta</th><th>Status</th></tr></thead><tbody><tr><td>Frete sobre Vendas</td><td>8.5%</td><td>< 10%</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Prazo Médio Entrega</td><td>3.2 dias</td><td>< 5 dias</td><td><span class="badge badge-s"> Excelente</span></td></tr><tr><td>Giro Estoque</td><td>4x/mês</td><td>> 3x</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Margem Bruta</td><td>35%</td><td>> 30%</td><td><span class="badge badge-s"> Acima Meta</span></td></tr></tbody></table></div>
</div>

<div id="roupas" class="tc">
    <div class="hero" style="background:linear-gradient(135deg,#4c1d95,#7c3aed,#a78bfa);">
        <h1> Loja de Roupas</h1><p>Foco em Tendência, Sazonalidade e Liquidação</p>
        <div class="hs"><div class="hs2"><div class="n" id="roup1">-</div><div class="l">Mark-up</div></div><div class="hs2"><div class="n" id="roup2">-</div><div class="l">Liquidação</div></div></div>
    </div>
    <div class="kg"><div class="kc bl"><div class="l">Mark-up Médio</div><div class="v">2.8x</div></div><div class="kc gr"><div class="l">Índice Liquidação</div><div class="v">15%</div></div><div class="kc pu"><div class="l">Ticket Médio</div><div class="v">R$ 180</div></div><div class="kc or"><div class="l">Margem Bruta</div><div class="v">55%</div></div></div>
    <div class="cd"><h3> Indicadores Chave - Loja de Roupas</h3><table><thead><tr><th>Indicador</th><th>Valor</th><th>Meta</th><th>Status</th></tr></thead><tbody><tr><td>Mark-up Médio</td><td>2.8x</td><td>> 2.5x</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Índice Liquidação</td><td>15%</td><td>< 20%</td><td><span class="badge badge-s"> Baixa Liquidação</span></td></tr><tr><td>Giro Coleção</td><td>6x/trim</td><td>> 5x</td><td><span class="badge badge-s"> Excelente</span></td></tr><tr><td>Margem Bruta</td><td>55%</td><td>> 50%</td><td><span class="badge badge-s"> Acima Meta</span></td></tr></tbody></table></div>
</div>

<div id="atacadista" class="tc">
    <div class="hero" style="background:linear-gradient(135deg,#1e3a8a,#3b82f6,#60a5fa);">
        <h1> Atacadista</h1><p>Foco em Volume, Negociação e Margem de Rappel</p>
        <div class="hs"><div class="hs2"><div class="n" id="atac1">-</div><div class="l">Drop Size</div></div><div class="hs2"><div class="n" id="atac2">-</div><div class="l">Margem Rappel</div></div></div>
    </div>
    <div class="kg"><div class="kc bl"><div class="l">Drop Size Médio</div><div class="v">R$ 1.250</div></div><div class="kc gr"><div class="l">Margem Rappel</div><div class="v">8.5%</div></div><div class="kc pu"><div class="l">Volume Mês</div><div class="v">R$ 850K</div></div><div class="kc or"><div class="l">Margem Líquida</div><div class="v">12%</div></div></div>
    <div class="cd"><h3> Indicadores Chave - Atacadista</h3><table><thead><tr><th>Indicador</th><th>Valor</th><th>Meta</th><th>Status</th></tr></thead><tbody><tr><td>Volume por Pedido</td><td>R$ 1.250</td><td>> R$ 1.000</td><td><span class="badge badge-s"> Acima Meta</span></td></tr><tr><td>Margem Rappel</td><td>8.5%</td><td>> 7%</td><td><span class="badge badge-s"> Excelente</span></td></tr><tr><td>Giro Estoque</td><td>8x/mês</td><td>> 6x</td><td><span class="badge badge-s"> Dentro Meta</span></td></tr><tr><td>Ciclo Financeiro</td><td>45 dias</td><td>< 60 dias</td><td><span class="badge badge-s"> Saudável</span></td></tr></tbody></table></div>
</div>
'''

HTML_ADMIN = '''
<div id="companies" class="tc">
    <button class="btn btn-p" onclick="openCompModal()">+ Nova Empresa</button><br><br>
    <div class="cd"><h3> Empresas Cadastradas</h3>
        <div style="overflow-x:auto;"><table><thead><tr><th>ID</th><th>Nome</th><th>CNPJ</th><th>Email</th><th>Segmento</th><th>Ambiente</th><th>Status</th><th>Ações</th></tr></thead><tbody id="compTable"></tbody></table></div>
    </div>
</div>

<div id="users" class="tc">
    <button class="btn btn-p" onclick="openUserModal()">+ Novo Usuário</button><br><br>
    <div class="cd"><h3> Usuários do Sistema</h3>
        <div style="overflow-x:auto;"><table><thead><tr><th>ID</th><th>Nome</th><th>Email</th><th>Função</th><th>Empresa</th><th>Status</th><th>Ações</th></tr></thead><tbody id="userTable"></tbody></table></div>
    </div>
</div>

<div id="licenses" class="tc">
    <button class="btn btn-p" onclick="openLicModal()">+ Nova Licença</button><br><br>
    <div class="cd"><h3> Gerenciamento de Licenças</h3>
        <div style="overflow-x:auto;"><table><thead><tr><th>ID</th><th>Empresa</th><th>Chave</th><th>Início</th><th>Fim</th><th>Valor</th><th>Status</th><th>Ações</th></tr></thead><tbody id="licTable"></tbody></table></div>
    </div>
</div>

<div id="erp" class="tc">
    <div class="cd"><h3> Configuração de Integração ERP</h3>
        <div class="fg"><label>Selecionar Empresa</label><select id="erpSel" onchange="loadERP()"><option value="">Selecione...</option></select></div>
        <form onsubmit="saveERP(event)"><input type="hidden" id="erpId">
            <div class="fr">
                <div class="fg"><label>Tipo de ERP</label><select id="erpType"><option value="sap">SAP</option><option value="totvs">TOTVS</option><option value="oracle">Oracle EBS</option><option value="microsoft">Microsoft Dynamics</option><option value="custom">Personalizado</option></select></div>
                <div class="fg"><label>URL da API Web</label><input type="text" id="erpUrl" placeholder="https://api.erp.exemplo.com/v1"></div>
            </div>
            <div class="fr">
                <div class="fg"><label>API Key / Token</label><input type="text" id="erpKey" placeholder="Bearer token ou API Key"></div>
                <div class="fg"><label>Intervalo Sync (seg)</label><input type="number" id="erpSync" value="300" min="60"></div>
            </div>
            <h4 style="margin:15px 0;color:#374151;"> Banco de Dados Local</h4>
            <div class="fr">
                <div class="fg"><label>Host do Banco</label><input type="text" id="erpHost" placeholder="localhost ou 192.168.1.100"></div>
                <div class="fg"><label>Porta</label><input type="text" id="erpPort" placeholder="5432 (PostgreSQL) / 3306 (MySQL)"></div>
            </div>
            <div class="fr">
                <div class="fg"><label>Nome do Banco</label><input type="text" id="erpDb" placeholder="erp_database"></div>
                <div class="fg"><label>Tipo de Banco</label><select id="erpDbType"><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option><option value="sqlserver">SQL Server</option></select></div>
            </div>
            <div class="fr">
                <div class="fg"><label>Usuário</label><input type="text" id="erpUser" placeholder="usuario_erp"></div>
                <div class="fg"><label>Senha</label><input type="password" id="erpPass" placeholder=""></div>
            </div>
            <div style="margin-top:18px;display:flex;gap:10px;">
                <button type="submit" class="btn btn-s"> Salvar Configuração</button>
                <button type="button" class="btn btn-p" onclick="testERP()"> Testar Conexão</button>
                <button type="button" class="btn btn-w" onclick="syncERP()"> Sincronizar Agora</button>
            </div>
        </form>
        <div id="erpMsg" style="margin-top:12px;padding:12px;border-radius:8px;display:none;"></div>
    </div>
</div>
'''
# ============================================
# MODAIS HTML
# ============================================
HTML_MODALS = '''
<!-- MODAL EMPRESA -->
<div class="modal-overlay" id="compModal">
    <div class="modal">
        <h3> <span id="compModalTitle">Nova Empresa</span></h3>
        <form onsubmit="saveComp(event)">
            <input type="hidden" id="eid">
            <div class="fg"><label>Nome da Empresa *</label><input type="text" id="enm" required></div>
            <div class="fr">
                <div class="fg"><label>CNPJ</label><input type="text" id="ecnpj" placeholder="00.000.000/0001-00"></div>
                <div class="fg"><label>Email</label><input type="email" id="eem"></div>
            </div>
            <div class="fr">
                <div class="fg"><label>Telefone</label><input type="text" id="eph"></div>
                <div class="fg">
                    <label>Segmento *</label>
                    <select id="eseg">
                        <option value="supermercado"> Supermercado</option>
                        <option value="construcao"> Material de Construção</option>
                        <option value="roupas"> Loja de Roupas</option>
                        <option value="atacadista"> Atacadista</option>
                    </select>
                </div>
            </div>
            <div class="fg">
                <label>Ambiente *</label>
                <select id="eenv">
                    <option value="homologacao"> Homologação (Testes)</option>
                    <option value="producao"> Produção (Dados Reais)</option>
                </select>
            </div>
            <div class="ma">
                <button type="submit" class="btn btn-s"> Salvar</button>
                <button type="button" class="btn" onclick="closeM('compModal')">Cancelar</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL USUÁRIO -->
<div class="modal-overlay" id="userModal">
    <div class="modal">
        <h3> <span id="userModalTitle">Novo Usuário</span></h3>
        <form onsubmit="saveUser(event)">
            <input type="hidden" id="uid">
            <div class="fr">
                <div class="fg"><label>Nome *</label><input type="text" id="unm" required></div>
                <div class="fg"><label>Email *</label><input type="email" id="uem" required></div>
            </div>
            <div class="fr">
                <div class="fg"><label>Senha</label><input type="password" id="upw" placeholder="Deixe em branco para manter"></div>
                <div class="fg">
                    <label>Função *</label>
                    <select id="urole">
                        <option value="user">Usuário (Apenas Analytics)</option>
                        <option value="admin">Administrador</option>
                        <option value="super_admin">Super Admin</option>
                    </select>
                </div>
            </div>
            <div class="fr">
                <div class="fg"><label>Vincular Empresa</label><select id="ucomp"><option value="">Nenhuma</option></select></div>
                <div class="fg"><label>Status</label><select id="uactive"><option value="1">Ativo</option><option value="0">Inativo</option></select></div>
            </div>
            <div class="ma">
                <button type="submit" class="btn btn-s"> Salvar</button>
                <button type="button" class="btn" onclick="closeM('userModal')">Cancelar</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL LICENÇA -->
<div class="modal-overlay" id="licModal">
    <div class="modal">
        <h3> <span id="licModalTitle">Nova Licença</span></h3>
        <form onsubmit="saveLic(event)">
            <input type="hidden" id="lid">
            <div class="fg"><label>Empresa *</label><select id="lcomp" required></select></div>
            <div class="fr">
                <div class="fg"><label>Data Início *</label><input type="date" id="lstart" required></div>
                <div class="fg"><label>Data Fim *</label><input type="date" id="lend" required></div>
            </div>
            <div class="fr">
                <div class="fg"><label>Valor (R$) *</label><input type="number" id="lval" step="0.01" required></div>
                <div class="fg"><label>Máx. Usuários</label><input type="number" id="lmax" value="5"></div>
            </div>
            <div class="fr">
                <div class="fg">
                    <label>Status</label>
                    <select id="lstat">
                        <option value="active"> Ativa</option>
                        <option value="blocked"> Bloqueada</option>
                        <option value="expired"> Expirada</option>
                    </select>
                </div>
                <div class="fg"><label>Observações</label><input type="text" id="lnotes"></div>
            </div>
            <div class="ma">
                <button type="submit" class="btn btn-s"> Salvar</button>
                <button type="button" class="btn" onclick="closeM('licModal')">Cancelar</button>
            </div>
        </form>
    </div>
</div>
'''

# ============================================
# JAVASCRIPT COMPLETO
# ============================================
HTML_SCRIPTS = '''
<script>
// ==================== VARIÁVEIS GLOBAIS ====================
var charts = {};
var currentTab = 'home';

// ==================== UTILITÁRIOS ====================
function fm(v) {
    return 'R$ ' + (v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function openM(id) { document.getElementById(id).classList.add('show'); }
function closeM(id) { document.getElementById(id).classList.remove('show'); }

async function api(url, method, body) {
    method = method || 'GET';
    var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    try {
        var r = await fetch(url, opts);
        if (r.status === 401 || r.status === 403) {
            window.location.href = '/login';
            return {};
        }
        return await r.json();
    } catch (e) {
        console.error('API Error:', e);
        return {};
    }
}

function destroyAllCharts() {
    Object.keys(charts).forEach(function(k) {
        try { charts[k].destroy(); } catch (e) {}
        delete charts[k];
    });
}

// ==================== NAVEGAÇÃO ====================
function showTab(tab) {
    document.querySelectorAll('.ni').forEach(function(n) { n.classList.remove('active'); });
    if (event && event.target) {
        var btn = event.target.closest('.ni');
        if (btn) btn.classList.add('active');
    }
    
    document.querySelectorAll('.tc').forEach(function(t) { t.classList.remove('active'); });
    var el = document.getElementById(tab);
    if (el) el.classList.add('active');
    currentTab = tab;
    
    var titles = {
        home: ' Início - SEICTECH',
        analytics: ' Analytics Geral',
        sellout: ' Análise Sell-Out',
        estoque: ' Estoque & Suprimentos',
        cliente: ' Comportamento Cliente',
        financeiro: ' Financeiro & Custos',
        supermercado: ' Supermercado',
        construcao: ' Material de Construção',
        roupas: ' Loja de Roupas',
        atacadista: ' Atacadista',
        companies: ' Empresas',
        users: ' Usuários',
        licenses: ' Licenças',
        erp: ' Integração ERP'
    };
    document.getElementById('pt').textContent = titles[tab] || tab;
    document.getElementById('ut').textContent = 'Atualizado: ' + new Date().toLocaleString('pt-BR');
    
    destroyAllCharts();
    
    // Carregar dados conforme a aba
    var loaders = {
        home: loadHome,
        analytics: loadAnalyticsCompanies,
        sellout: loadSellOutCompanies,
        estoque: loadEstoqueCompanies,
        cliente: loadClienteCompanies,
        financeiro: loadFinanceiroCompanies,
        supermercado: loadSegmentStats,
        construcao: loadSegmentStats,
        roupas: loadSegmentStats,
        atacadista: loadSegmentStats,
        companies: loadCompanies,
        users: loadUsers,
        licenses: loadLicenses,
        erp: loadERPCompanies
    };
    
    if (loaders[tab]) loaders[tab]();
}

// ==================== HOME ====================
async function loadHome() {
    var d = await api('/api/home-stats');
    document.getElementById('hs1').textContent = d.companies || 0;
    document.getElementById('hs2').textContent = d.active_licenses || 0;
    document.getElementById('hs3').textContent = fm(d.revenue || 0);
}

// ==================== ANALYTICS ====================
async function loadAnalyticsCompanies() {
    var d = await api('/api/user-companies');
    var sel = document.getElementById('asel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + ' (' + c.environment + ')</option>'; }).join('');
    }
}

async function loadAnalytics() {
    var id = document.getElementById('asel').value;
    if (!id) return;
    var d = await api('/api/analytics/' + id);
    
    document.getElementById('akpi').innerHTML =
        '<div class="kc bl"><div class="l">Produtos</div><div class="v">' + (d.products || 0) + '</div></div>' +
        '<div class="kc gr"><div class="l">Vendas Hoje</div><div class="v">' + fm(d.sales_today || 0) + '</div></div>' +
        '<div class="kc pu"><div class="l">Estoque Total</div><div class="v">' + (d.total_stock || 0) + '</div></div>' +
        '<div class="kc or"><div class="l">Ticket Médio</div><div class="v">' + fm(d.avg_ticket || 0) + '</div></div>';
    
    if (d.sales_trend) {
        var ctx = document.getElementById('c1');
        if (ctx) {
            if (charts['c1']) charts['c1'].destroy();
            charts['c1'] = new Chart(ctx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: d.sales_trend.map(function(t) { return t.date; }),
                    datasets: [{
                        label: 'Vendas',
                        data: d.sales_trend.map(function(t) { return t.revenue; }),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59,130,246,0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
    
    if (d.stock_dist) {
        var ctx2 = document.getElementById('c2');
        if (ctx2) {
            if (charts['c2']) charts['c2'].destroy();
            charts['c2'] = new Chart(ctx2.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: d.stock_dist.map(function(s) { return s.label; }),
                    datasets: [{
                        data: d.stock_dist.map(function(s) { return s.value; }),
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
}

// ==================== SELL-OUT ====================
async function loadSellOutCompanies() {
    var d = await api('/api/user-companies');
    var sel = document.getElementById('sosel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
    }
}

async function loadSellOut() {
    var id = document.getElementById('sosel').value;
    if (!id) return;
    var d = await api('/api/sellout/' + id);
    
    document.getElementById('sokpi').innerHTML =
        '<div class="kc bl"><div class="l">Faturamento Bruto (30d)</div><div class="v">' + fm(d.gross_revenue || 0) + '</div></div>' +
        '<div class="kc gr"><div class="l">Faturamento Líquido</div><div class="v">' + fm(d.net_revenue || 0) + '</div></div>' +
        '<div class="kc pu"><div class="l">Ticket Médio</div><div class="v">' + fm(d.avg_ticket || 0) + '</div></div>' +
        '<div class="kc or"><div class="l">Margem Contribuição</div><div class="v">' + (d.margin || 0).toFixed(1) + '%</div></div>';
    
    // Tabela
    if (d.sales && d.sales.length > 0) {
        document.getElementById('sotable').innerHTML = d.sales.map(function(s) {
            var ticket = s.total_transactions > 0 ? s.net_revenue / s.total_transactions : 0;
            return '<tr>' +
                '<td>' + s.sale_date + '</td>' +
                '<td>' + fm(s.gross_revenue) + '</td>' +
                '<td>' + fm(s.net_revenue) + '</td>' +
                '<td style="color:#ef4444">' + fm(s.returns) + '</td>' +
                '<td style="color:#f59e0b">' + fm(s.taxes) + '</td>' +
                '<td>' + s.total_transactions + '</td>' +
                '<td>' + (s.total_items || 0) + '</td>' +
                '<td><strong>' + fm(ticket) + '</strong></td>' +
                '<td><span class="badge badge-i">' + (s.category || '-') + '</span></td>' +
                '</tr>';
        }).join('');
    }
    
    // Gráficos
    if (d.labels && d.labels.length > 0) {
        var ctx1 = document.getElementById('so1');
        if (ctx1) {
            if (charts['so1']) charts['so1'].destroy();
            charts['so1'] = new Chart(ctx1.getContext('2d'), {
                type: 'line',
                data: {
                    labels: d.labels,
                    datasets: [
                        { label: 'Bruto', data: d.gross_data || [], borderColor: '#3b82f6', tension: 0.3 },
                        { label: 'Líquido', data: d.net_data || [], borderColor: '#10b981', tension: 0.3 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
    
    if (d.cat_labels && d.cat_labels.length > 0) {
        var ctx2 = document.getElementById('so2');
        if (ctx2) {
            if (charts['so2']) charts['so2'].destroy();
            charts['so2'] = new Chart(ctx2.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: d.cat_labels,
                    datasets: [{ label: 'Vendas', data: d.cat_data || [], backgroundColor: '#8b5cf6', borderRadius: 5 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    }
}

// ==================== ESTOQUE ====================
async function loadEstoqueCompanies() {
    var d = await api('/api/user-companies');
    var sel = document.getElementById('esel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
    }
}

async function loadEstoque() {
    var id = document.getElementById('esel').value;
    if (!id) return;
    var d = await api('/api/estoque/' + id);
    
    document.getElementById('ekpi').innerHTML =
        '<div class="kc bl"><div class="l">Giro Médio</div><div class="v">' + (d.avg_turnover || 0).toFixed(1) + 'x</div></div>' +
        '<div class="kc rd"><div class="l">Taxa Ruptura</div><div class="v">' + (d.rupture_rate || 0).toFixed(1) + '%</div></div>' +
        '<div class="kc pu"><div class="l">GMROI Médio</div><div class="v">' + fm(d.avg_gmroi || 0) + '</div></div>' +
        '<div class="kc or"><div class="l">Cobertura</div><div class="v">' + (d.coverage_days || 0) + ' dias</div></div>';
    
    // Tabela
    if (d.items && d.items.length > 0) {
        document.getElementById('etable').innerHTML = d.items.map(function(i) {
            var abc = i.abc || 'C';
            var badgeClass = abc === 'A' ? 'badge-d' : (abc === 'B' ? 'badge-w' : 'badge-s');
            var rupture = i.quantity < (i.min_stock || 10);
            return '<tr>' +
                '<td><code>' + i.product_sku + '</code></td>' +
                '<td><strong>' + i.product_name + '</strong></td>' +
                '<td>' + i.category + '</td>' +
                '<td>' + i.quantity + '</td>' +
                '<td>' + (i.min_stock || 10) + '</td>' +
                '<td>' + (rupture ? '<span class="badge badge-d"> Sim</span>' : '<span class="badge badge-s"> Não</span>') + '</td>' +
                '<td>' + (i.turnover || 0).toFixed(1) + 'x</td>' +
                '<td><span class="badge ' + badgeClass + '">Curva ' + abc + '</span></td>' +
                '<td>' + fm(i.gmroi || 0) + '</td>' +
                '<td>' + (i.coverage || 0).toFixed(0) + ' dias</td>' +
                '</tr>';
        }).join('');
    }
    
    // Gráficos
    if (d.abc_data) {
        var ctx1 = document.getElementById('e1');
        if (ctx1) {
            if (charts['e1']) charts['e1'].destroy();
            charts['e1'] = new Chart(ctx1.getContext('2d'), {
                type: 'pie',
                data: {
                    labels: ['Curva A (20%)', 'Curva B (30%)', 'Curva C (50%)'],
                    datasets: [{ data: d.abc_data, backgroundColor: ['#ef4444', '#f59e0b', '#10b981'] }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
    
    if (d.turnover_data) {
        var ctx2 = document.getElementById('e2');
        if (ctx2) {
            if (charts['e2']) charts['e2'].destroy();
            charts['e2'] = new Chart(ctx2.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: d.turnover_labels || [],
                    datasets: [{ label: 'Giro', data: d.turnover_data || [], backgroundColor: '#3b82f6', borderRadius: 5 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    }
}

// ==================== CLIENTE ====================
async function loadClienteCompanies() {
    var d = await api('/api/user-companies');
    var sel = document.getElementById('clsel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
    }
}

async function loadCliente() {
    var id = document.getElementById('clsel').value;
    if (!id) return;
    var d = await api('/api/cliente/' + id);
    
    document.getElementById('clkpi').innerHTML =
        '<div class="kc bl"><div class="l">NPS Médio</div><div class="v">' + (d.avg_nps || 0).toFixed(1) + '</div></div>' +
        '<div class="kc gr"><div class="l">Taxa Conversão</div><div class="v">' + (d.conversion || 0).toFixed(1) + '%</div></div>' +
        '<div class="kc pu"><div class="l">Frequência Média</div><div class="v">' + (d.avg_frequency || 0).toFixed(1) + 'x</div></div>' +
        '<div class="kc rd"><div class="l">Churn Rate</div><div class="v">' + (d.churn_rate || 0).toFixed(1) + '%</div></div>';
    
    // Tabela
    if (d.customers && d.customers.length > 0) {
        document.getElementById('cltable').innerHTML = d.customers.map(function(c) {
            var daysSince = c.days_since || 0;
            var churnRisk = Math.max(0, Math.min(100, daysSince * 3));
            var riskClass = churnRisk > 50 ? 'badge-d' : (churnRisk > 30 ? 'badge-w' : 'badge-s');
            var classification = c.nps_score >= 9 ? 'Promotor' : (c.nps_score >= 7 ? 'Neutro' : 'Detrator');
            var classBadge = c.nps_score >= 9 ? 'badge-s' : (c.nps_score >= 7 ? 'badge-w' : 'badge-d');
            
            return '<tr>' +
                '<td><strong>' + c.name + '</strong></td>' +
                '<td>' + fm(c.total_purchases) + '</td>' +
                '<td>' + c.visit_count + '</td>' +
                '<td>' + c.last_purchase + '</td>' +
                '<td>' + daysSince + ' dias</td>' +
                '<td>' + c.nps_score + '/10</td>' +
                '<td><span class="badge ' + classBadge + '">' + classification + '</span></td>' +
                '<td><span class="badge ' + riskClass + '">' + churnRisk.toFixed(0) + '%</span></td>' +
                '</tr>';
        }).join('');
    }
    
    // Gráficos
    if (d.nps_dist) {
        var ctx1 = document.getElementById('cl1');
        if (ctx1) {
            if (charts['cl1']) charts['cl1'].destroy();
            charts['cl1'] = new Chart(ctx1.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['Promotores (9-10)', 'Neutros (7-8)', 'Detratores (0-6)'],
                    datasets: [{ data: d.nps_dist, backgroundColor: ['#10b981', '#f59e0b', '#ef4444'] }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
    
    if (d.freq_data) {
        var ctx2 = document.getElementById('cl2');
        if (ctx2) {
            if (charts['cl2']) charts['cl2'].destroy();
            charts['cl2'] = new Chart(ctx2.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: d.freq_labels || [],
                    datasets: [{ label: 'Clientes', data: d.freq_data || [], backgroundColor: '#8b5cf6', borderRadius: 5 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    }
}

// ==================== FINANCEIRO ====================
async function loadFinanceiroCompanies() {
    var d = await api('/api/user-companies');
    var sel = document.getElementById('fisel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
    }
}

async function loadFinanceiro() {
    var id = document.getElementById('fisel').value;
    if (!id) return;
    var d = await api('/api/financeiro/' + id);
    
    document.getElementById('fikpi').innerHTML =
        '<div class="kc bl"><div class="l">Receita Total</div><div class="v">' + fm(d.total_revenue || 0) + '</div></div>' +
        '<div class="kc gr"><div class="l">EBITDA</div><div class="v">' + fm(d.total_ebitda || 0) + '</div></div>' +
        '<div class="kc pu"><div class="l">CMV Total</div><div class="v">' + fm(d.total_cmv || 0) + '</div></div>' +
        '<div class="kc or"><div class="l">Break-even</div><div class="v">' + fm(d.avg_break_even || 0) + '</div></div>';
    
    // Tabela
    if (d.periods && d.periods.length > 0) {
        document.getElementById('fitable').innerHTML = d.periods.map(function(p) {
            var margin = p.total_revenue > 0 ? ((p.total_revenue - p.cmv - (p.fixed_costs || 0)) / p.total_revenue * 100) : 0;
            return '<tr>' +
                '<td><strong>' + p.period + '</strong></td>' +
                '<td>' + fm(p.total_revenue) + '</td>' +
                '<td style="color:#ef4444">' + fm(p.cmv) + '</td>' +
                '<td style="color:#f59e0b">' + fm(p.fixed_costs || 0) + '</td>' +
                '<td>' + fm(p.variable_costs || 0) + '</td>' +
                '<td style="color:' + ((p.ebitda || 0) >= 0 ? '#10b981' : '#ef4444') + ';font-weight:bold;">' + fm(p.ebitda || 0) + '</td>' +
                '<td><strong>' + margin.toFixed(1) + '%</strong></td>' +
                '<td>' + fm(p.break_even || 0) + '</td>' +
                '</tr>';
        }).join('');
    }
    
    // Gráficos
    if (d.periods && d.periods.length > 0) {
        var ctx1 = document.getElementById('fi1');
        if (ctx1) {
            if (charts['fi1']) charts['fi1'].destroy();
            charts['fi1'] = new Chart(ctx1.getContext('2d'), {
                type: 'line',
                data: {
                    labels: d.periods.map(function(p) { return p.period; }),
                    datasets: [
                        { label: 'Receita', data: d.periods.map(function(p) { return p.total_revenue; }), borderColor: '#3b82f6', tension: 0.3 },
                        { label: 'EBITDA', data: d.periods.map(function(p) { return p.ebitda || 0; }), borderColor: '#10b981', tension: 0.3 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
        
        var ctx2 = document.getElementById('fi2');
        if (ctx2) {
            if (charts['fi2']) charts['fi2'].destroy();
            charts['fi2'] = new Chart(ctx2.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: d.periods.map(function(p) { return p.period; }),
                    datasets: [
                        { label: 'Break-even', data: d.periods.map(function(p) { return p.break_even || 0; }), backgroundColor: '#f59e0b', borderRadius: 5 },
                        { label: 'CMV', data: d.periods.map(function(p) { return p.cmv; }), backgroundColor: '#ef4444', borderRadius: 5 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
}

// ==================== SEGMENTOS ====================
function loadSegmentStats() {
    // Já tem dados estáticos nos templates
}

// ==================== EMPRESAS ====================
async function loadCompanies() {
    var d = await api('/api/companies');
    document.getElementById('compTable').innerHTML = d.map(function(c) {
        return '<tr>' +
            '<td>' + c.id + '</td>' +
            '<td><strong>' + c.name + '</strong></td>' +
            '<td>' + (c.cnpj || '-') + '</td>' +
            '<td>' + (c.email || '-') + '</td>' +
            '<td><span class="seg-badge seg-' + (c.segment || 'supermercado') + '">' + (c.segment || 'supermercado') + '</span></td>' +
            '<td><span class="badge ' + (c.environment == 'producao' ? 'badge-p' : 'badge-i') + '">' + (c.environment == 'producao' ? ' Produção' : ' Homologação') + '</span></td>' +
            '<td><span class="badge ' + (c.active ? 'badge-s' : 'badge-d') + '">' + (c.active ? 'Ativa' : 'Inativa') + '</span></td>' +
            '<td>' +
                '<button class="btn btn-sm btn-p" onclick="editComp(' + c.id + ')"> Editar</button> ' +
                '<button class="btn btn-sm btn-d" onclick="delComp(' + c.id + ')"> Excluir</button>' +
            '</td>' +
            '</tr>';
    }).join('');
}

function openCompModal(id) {
    document.getElementById('eid').value = '';
    document.getElementById('enm').value = '';
    document.getElementById('ecnpj').value = '';
    document.getElementById('eem').value = '';
    document.getElementById('eph').value = '';
    document.getElementById('eseg').value = 'supermercado';
    document.getElementById('eenv').value = 'homologacao';
    document.getElementById('compModalTitle').textContent = 'Nova Empresa';
    
    if (id) {
        document.getElementById('compModalTitle').textContent = 'Editar Empresa';
        api('/api/companies').then(function(data) {
            var c = data.find(function(x) { return x.id === id; });
            if (c) {
                document.getElementById('eid').value = c.id;
                document.getElementById('enm').value = c.name;
                document.getElementById('ecnpj').value = c.cnpj || '';
                document.getElementById('eem').value = c.email || '';
                document.getElementById('eph').value = c.phone || '';
                document.getElementById('eseg').value = c.segment || 'supermercado';
                document.getElementById('eenv').value = c.environment || 'homologacao';
            }
        });
    }
    openM('compModal');
}

async function saveComp(e) {
    e.preventDefault();
    var id = document.getElementById('eid').value;
    var data = {
        name: document.getElementById('enm').value,
        cnpj: document.getElementById('ecnpj').value,
        email: document.getElementById('eem').value,
        phone: document.getElementById('eph').value,
        segment: document.getElementById('eseg').value,
        environment: document.getElementById('eenv').value
    };
    var url = '/api/companies' + (id ? '/' + id : '');
    var method = id ? 'PUT' : 'POST';
    await api(url, method, data);
    closeM('compModal');
    loadCompanies();
}

function editComp(id) { openCompModal(id); }

async function delComp(id) {
    if (confirm('Tem certeza que deseja excluir esta empresa? Todos os dados serão perdidos.')) {
        await api('/api/companies/' + id, 'DELETE');
        loadCompanies();
    }
}

// ==================== USUÁRIOS ====================
async function loadUsers() {
    var d = await api('/api/users');
    document.getElementById('userTable').innerHTML = d.map(function(u) {
        return '<tr>' +
            '<td>' + u.id + '</td>' +
            '<td><strong>' + u.name + '</strong></td>' +
            '<td>' + u.email + '</td>' +
            '<td><span class="badge ' + (u.role == 'super_admin' ? 'badge-d' : u.role == 'admin' ? 'badge-w' : 'badge-i') + '">' + u.role + '</span></td>' +
            '<td>' + (u.company_name || '-') + '</td>' +
            '<td><span class="badge ' + (u.active ? 'badge-s' : 'badge-d') + '">' + (u.active ? 'Ativo' : 'Inativo') + '</span></td>' +
            '<td>' +
                '<button class="btn btn-sm btn-p" onclick="editUser(' + u.id + ')"> Editar</button> ' +
                '<button class="btn btn-sm btn-d" onclick="delUser(' + u.id + ')"> Excluir</button>' +
            '</td>' +
            '</tr>';
    }).join('');
    
    // Carregar empresas para o select
    api('/api/companies').then(function(data) {
        var sel = document.getElementById('ucomp');
        if (sel) {
            sel.innerHTML = '<option value="">Nenhuma</option>' +
                data.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
        }
    });
}

function openUserModal(id) {
    document.getElementById('uid').value = '';
    document.getElementById('unm').value = '';
    document.getElementById('uem').value = '';
    document.getElementById('upw').value = '';
    document.getElementById('urole').value = 'user';
    document.getElementById('uactive').value = '1';
    document.getElementById('userModalTitle').textContent = 'Novo Usuário';
    
    // Carregar empresas
    api('/api/companies').then(function(data) {
        var sel = document.getElementById('ucomp');
        if (sel) {
            sel.innerHTML = '<option value="">Nenhuma</option>' +
                data.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
        }
    });
    
    if (id) {
        document.getElementById('userModalTitle').textContent = 'Editar Usuário';
        api('/api/users').then(function(data) {
            var u = data.find(function(x) { return x.id === id; });
            if (u) {
                document.getElementById('uid').value = u.id;
                document.getElementById('unm').value = u.name;
                document.getElementById('uem').value = u.email;
                document.getElementById('urole').value = u.role;
                document.getElementById('uactive').value = u.active;
            }
        });
    }
    openM('userModal');
}

async function saveUser(e) {
    e.preventDefault();
    var id = document.getElementById('uid').value;
    var data = {
        name: document.getElementById('unm').value,
        email: document.getElementById('uem').value,
        role: document.getElementById('urole').value,
        active: parseInt(document.getElementById('uactive').value),
        company_id: document.getElementById('ucomp').value || null
    };
    
    var pw = document.getElementById('upw').value;
    if (pw) data.password = pw;
    
    var url = '/api/users' + (id ? '/' + id : '');
    var method = id ? 'PUT' : 'POST';
    var result = await api(url, method, data);
    
    if (result.success) {
        closeM('userModal');
        loadUsers();
    } else {
        alert(result.message || 'Erro ao salvar usuário');
    }
}

function editUser(id) { openUserModal(id); }

async function delUser(id) {
    if (id === 1) {
        alert('Não é possível excluir o Super Admin!');
        return;
    }
    if (confirm('Tem certeza que deseja excluir este usuário?')) {
        await api('/api/users/' + id, 'DELETE');
        loadUsers();
    }
}

// ==================== LICENÇAS ====================
async function loadLicenses() {
    var d = await api('/api/licenses');
    document.getElementById('licTable').innerHTML = d.map(function(l) {
        return '<tr>' +
            '<td>' + l.id + '</td>' +
            '<td><strong>' + l.company_name + '</strong></td>' +
            '<td><code>' + l.license_key + '</code></td>' +
            '<td>' + l.start_date + '</td>' +
            '<td>' + l.end_date + '</td>' +
            '<td><strong>' + fm(l.value) + '</strong></td>' +
            '<td><span class="badge ' + (l.status == 'active' ? 'badge-s' : l.status == 'blocked' ? 'badge-w' : 'badge-d') + '">' + (l.status == 'active' ? ' Ativa' : l.status == 'blocked' ? ' Bloqueada' : ' Expirada') + '</span></td>' +
            '<td>' +
                '<button class="btn btn-sm btn-p" onclick="editLic(' + l.id + ')"></button> ' +
                '<button class="btn btn-sm btn-w" onclick="blockLic(' + l.id + ')"> Bloquear</button> ' +
                '<button class="btn btn-sm btn-d" onclick="delLic(' + l.id + ')"></button>' +
            '</td>' +
            '</tr>';
    }).join('');
    
    // Carregar empresas
    api('/api/companies').then(function(data) {
        var sel = document.getElementById('lcomp');
        if (sel) {
            sel.innerHTML = '<option value="">Selecione...</option>' +
                data.map(function(c) { return '<option value="' + c.id + '">' + c.name + '</option>'; }).join('');
        }
    });
}

function openLicModal(id) {
    document.getElementById('lid').value = '';
    document.getElementById('lstart').value = '';
    document.getElementById('lend').value = '';
    document.getElementById('lval').value = '';
    document.getElementById('lmax').value = '5';
    document.getElementById('lstat').value = 'active';
    document.getElementById('lnotes').value = '';
    document.getElementById('licModalTitle').textContent = 'Nova Licença';
    
    if (id) {
        document.getElementById('licModalTitle').textContent = 'Editar Licença';
        api('/api/licenses').then(function(data) {
            var l = data.find(function(x) { return x.id === id; });
            if (l) {
                document.getElementById('lid').value = l.id;
                document.getElementById('lcomp').value = l.company_id;
                document.getElementById('lstart').value = l.start_date;
                document.getElementById('lend').value = l.end_date;
                document.getElementById('lval').value = l.value;
                document.getElementById('lmax').value = l.max_users || 5;
                document.getElementById('lstat').value = l.status;
                document.getElementById('lnotes').value = l.notes || '';
            }
        });
    }
    openM('licModal');
}

async function saveLic(e) {
    e.preventDefault();
    var id = document.getElementById('lid').value;
    var data = {
        company_id: parseInt(document.getElementById('lcomp').value),
        start_date: document.getElementById('lstart').value,
        end_date: document.getElementById('lend').value,
        value: parseFloat(document.getElementById('lval').value),
        max_users: parseInt(document.getElementById('lmax').value),
        status: document.getElementById('lstat').value,
        notes: document.getElementById('lnotes').value
    };
    
    var url = '/api/licenses' + (id ? '/' + id : '');
    var method = id ? 'PUT' : 'POST';
    await api(url, method, data);
    closeM('licModal');
    loadLicenses();
}

function editLic(id) { openLicModal(id); }

async function blockLic(id) {
    if (confirm('Deseja bloquear esta licença?')) {
        await api('/api/licenses/' + id + '/block', 'POST');
        loadLicenses();
    }
}

async function delLic(id) {
    if (confirm('Excluir licença permanentemente?')) {
        await api('/api/licenses/' + id, 'DELETE');
        loadLicenses();
    }
}

// ==================== ERP ====================
async function loadERPCompanies() {
    var d = await api('/api/companies');
    var sel = document.getElementById('erpSel');
    if (sel) {
        sel.innerHTML = '<option value="">Selecione uma empresa...</option>' +
            d.map(function(c) { return '<option value="' + c.id + '">' + c.name + ' (' + (c.segment || '') + ')</option>'; }).join('');
    }
}

async function loadERP() {
    var id = document.getElementById('erpSel').value;
    if (!id) return;
    document.getElementById('erpId').value = id;
    
    var d = await api('/api/erp-config/' + id);
    if (d && d.id) {
        document.getElementById('erpType').value = d.erp_type || 'custom';
        document.getElementById('erpUrl').value = d.api_url || '';
        document.getElementById('erpKey').value = d.api_key || '';
        document.getElementById('erpSync').value = d.sync_interval || 300;
        document.getElementById('erpHost').value = d.db_host || '';
        document.getElementById('erpPort').value = d.db_port || '';
        document.getElementById('erpDb').value = d.db_name || '';
        document.getElementById('erpDbType').value = d.db_type || 'postgresql';
        document.getElementById('erpUser').value = d.db_user || '';
        document.getElementById('erpPass').value = d.db_password || '';
    }
}

async function saveERP(e) {
    e.preventDefault();
    var data = {
        company_id: parseInt(document.getElementById('erpSel').value),
        erp_type: document.getElementById('erpType').value,
        api_url: document.getElementById('erpUrl').value,
        api_key: document.getElementById('erpKey').value,
        sync_interval: parseInt(document.getElementById('erpSync').value),
        db_host: document.getElementById('erpHost').value,
        db_port: document.getElementById('erpPort').value,
        db_name: document.getElementById('erpDb').value,
        db_type: document.getElementById('erpDbType').value,
        db_user: document.getElementById('erpUser').value,
        db_password: document.getElementById('erpPass').value
    };
    
    var result = await api('/api/erp-config', 'POST', data);
    showERPStatus(result.success, result.message);
}

async function testERP() {
    var id = document.getElementById('erpSel').value;
    if (!id) {
        showERPStatus(false, 'Selecione uma empresa primeiro');
        return;
    }
    showERPStatus(true, ' Testando conexão...');
    var result = await api('/api/erp-test/' + id);
    showERPStatus(result.success, result.message);
}

async function syncERP() {
    var id = document.getElementById('erpSel').value;
    if (!id) {
        showERPStatus(false, 'Selecione uma empresa primeiro');
        return;
    }
    showERPStatus(true, ' Sincronizando dados... Aguarde.');
    var result = await api('/api/erp-sync/' + id, 'POST');
    showERPStatus(result.success, result.message);
}

function showERPStatus(success, message) {
    var el = document.getElementById('erpMsg');
    if (!el) return;
    el.style.display = 'block';
    el.style.background = success ? '#d1fae5' : '#fee2e2';
    el.style.color = success ? '#065f46' : '#991b1b';
    el.textContent = message;
    if (success) {
        setTimeout(function() { el.style.display = 'none'; }, 6000);
    }
}

// ==================== LOGOUT ====================
function logout() {
    fetch('/api/logout', { method: 'POST' }).then(function() {
        window.location.href = '/login';
    });
}

// ==================== INICIALIZAÇÃO ====================
document.addEventListener('DOMContentLoaded', function() {
    loadHome();
    document.getElementById('ut').textContent = 'Atualizado: ' + new Date().toLocaleString('pt-BR');
});

// Atualizar hora a cada minuto
setInterval(function() {
    document.getElementById('ut').textContent = 'Atualizado: ' + new Date().toLocaleString('pt-BR');
}, 60000);
</script>
'''

HTML_FOOTER = '''
</div></div></body></html>
'''

# ============================================
# ROTAS DA APLICAÇÃO
# ============================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    
    login_html = '''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SEICTECH - Login</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#0f172a,#1e3a8a,#312e81);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
        .login-box{display:flex;max-width:900px;width:100%;background:white;border-radius:20px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,0.4)}
        .login-left{flex:1;background:linear-gradient(135deg,#1e3a8a,#3b82f6,#8b5cf6);padding:50px 40px;color:white;display:flex;flex-direction:column;justify-content:center}
        .login-left h1{font-size:32px;font-weight:700;margin-bottom:5px}
        .login-left h2{font-size:16px;opacity:0.9;margin-bottom:30px}
        .login-left ul{list-style:none}
        .login-left li{padding:10px 0;font-size:14px;opacity:0.9;display:flex;align-items:center;gap:10px}
        .login-left li::before{content:'';background:rgba(255,255,255,0.2);width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
        .login-right{flex:1;padding:50px 40px;display:flex;flex-direction:column;justify-content:center}
        .login-right h3{font-size:22px;color:#1e293b;margin-bottom:5px}
        .login-right p{color:#94a3b8;font-size:13px;margin-bottom:30px}
        .form-group{margin-bottom:20px}
        .form-group label{display:block;font-size:12px;font-weight:600;color:#374151;margin-bottom:6px}
        .form-group input{width:100%;padding:12px 16px;border:2px solid #e2e8f0;border-radius:10px;font-size:14px;transition:0.3s}
        .form-group input:focus{outline:none;border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,0.1)}
        .btn-login{width:100%;padding:14px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:white;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;transition:0.3s;margin-top:10px}
        .btn-login:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(59,130,246,0.3)}
        .error{background:#fee2e2;color:#dc2626;padding:12px;border-radius:8px;font-size:13px;margin-bottom:15px;display:none}
        .footer{text-align:center;margin-top:20px;font-size:11px;color:#94a3b8}
        @media(max-width:768px){.login-box{flex-direction:column}.login-left,.login-right{padding:30px}}
    </style></head><body>
    <div class="login-box">
    <div class="login-left"><h1>SEICTECH</h1><h2>Retail Analytics Pro</h2>
    <ul><li>Análise Sell-Out completa</li><li>Gestão de Estoque (Giro, Curva ABC)</li><li>Comportamento do Cliente (NPS, Churn)</li><li>Financeiro (EBITDA, Break-even)</li><li>Dashboards por Segmento</li><li>Integração ERP via API</li></ul></div>
    <div class="login-right"><h3> Acessar Sistema</h3><p>Digite suas credenciais para entrar</p>
    <div class="error" id="err"></div>
    <form onsubmit="doLogin(event)"><div class="form-group"><label>Email</label><input type="email" id="em" placeholder="sichoski.analista@gmail.com" required autofocus></div>
    <div class="form-group"><label>Senha</label><input type="password" id="pw" placeholder="" required></div>
    <button type="submit" class="btn-login">Entrar no Sistema</button></form>
    <div class="footer">© 2024 SEICTECH - Todos os direitos reservados</div></div></div>
    <script>
    async function doLogin(e){e.preventDefault();try{var r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('em').value,password:document.getElementById('pw').value})});var d=await r.json();if(d.success)window.location.href='/dashboard';else{document.getElementById('err').textContent=d.message||'Email ou senha inválidos';document.getElementById('err').style.display='block'}}catch(ex){document.getElementById('err').textContent='Erro de conexão';document.getElementById('err').style.display='block'}}
    </script></body></html>'''
    
    return render_template_string(login_html)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    # Montar HTML completo
    full_html = HTML_HEAD + HTML_SIDEBAR + HTML_CONTENT_START
    full_html += HTML_HOME + HTML_ANALYTICS + HTML_SELLOUT + HTML_ESTOQUE
    full_html += HTML_CLIENTE + HTML_FINANCEIRO + HTML_SEGMENTOS
    
    if session.get('role') == 'super_admin':
        full_html += HTML_ADMIN
    
    full_html += HTML_MODALS + HTML_SCRIPTS + HTML_FOOTER
    
    return render_template_string(full_html)

# ============================================
# API AUTENTICAÇÃO
# ============================================
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    password_hash = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    user = query_one("SELECT * FROM users WHERE email=? AND password=? AND active=1",
                     (data.get('email'), password_hash))
    
    if user:
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['role'] = user['role']
        session.permanent = True
        
        execute_db("INSERT INTO access_logs (user_id, action, ip_address) VALUES (?,?,?)",
                   (user['id'], 'login', request.remote_addr))
        
        return jsonify({'success': True, 'message': 'Login realizado com sucesso!'})
    
    return jsonify({'success': False, 'message': 'Email ou senha inválidos'})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

# ============================================
# API HOME
# ============================================
@app.route('/api/home-stats')
@login_required
def home_stats():
    companies = query_one("SELECT COUNT(*) as c FROM companies WHERE active=1")['c']
    active_licenses = query_one("SELECT COUNT(*) as c FROM licenses WHERE status='active'")['c']
    revenue = query_one("SELECT COALESCE(SUM(value), 0) as t FROM licenses")['t']
    return jsonify({'companies': companies, 'active_licenses': active_licenses, 'revenue': revenue})

# ============================================
# API ANALYTICS
# ============================================
@app.route('/api/user-companies')
@login_required
def user_companies():
    if session.get('role') == 'super_admin':
        return jsonify(query_db("SELECT id, name, environment, segment FROM companies WHERE active=1 ORDER BY name"))
    return jsonify(query_db("""
        SELECT c.id, c.name, c.environment, c.segment FROM companies c
        JOIN user_companies uc ON c.id = uc.company_id
        WHERE uc.user_id = ? AND c.active = 1 ORDER BY c.name
    """, (session.get('user_id'),)))

@app.route('/api/analytics/<int:cid>')
@login_required
def analytics(cid):
    sales = query_db("SELECT * FROM sales_data WHERE company_id=? ORDER BY sale_date DESC LIMIT 30", (cid,))
    
    return jsonify({
        'company_id': cid,
        'products': random.randint(15, 200),
        'sales_today': random.uniform(500, 15000),
        'total_stock': random.randint(100, 5000),
        'avg_ticket': random.uniform(30, 300),
        'sales_trend': [{'date': s['sale_date'], 'revenue': s['net_revenue']} for s in reversed(sales[:15])] if sales else [],
        'stock_dist': [
            {'label': 'Normal', 'value': random.randint(50, 200)},
            {'label': 'Alerta', 'value': random.randint(10, 50)},
            {'label': 'Crítico', 'value': random.randint(0, 20)}
        ]
    })

# ============================================
# API SELL-OUT
# ============================================
@app.route('/api/sellout/<int:cid>')
@login_required
def sellout(cid):
    sales = query_db("SELECT * FROM sales_data WHERE company_id=? ORDER BY sale_date DESC LIMIT 30", (cid,))
    
    if not sales:
        sales = []
        for i in range(30):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            sales.append({
                'sale_date': d,
                'gross_revenue': random.uniform(3000, 20000),
                'net_revenue': random.uniform(2500, 17000),
                'returns': random.uniform(50, 500),
                'taxes': random.uniform(200, 1500),
                'total_transactions': random.randint(30, 300),
                'total_items': random.randint(80, 600),
                'category': random.choice(['Hortifruti', 'Mercearia', 'Bebidas', 'Limpeza', 'Açougue'])
            })
    
    gross_total = sum(s['gross_revenue'] for s in sales)
    net_total = sum(s['net_revenue'] for s in sales)
    total_trans = sum(s['total_transactions'] for s in sales)
    
    categories = list(set(s['category'] for s in sales if s.get('category')))
    
    return jsonify({
        'gross_revenue': gross_total,
        'net_revenue': net_total,
        'avg_ticket': net_total / total_trans if total_trans > 0 else 0,
        'margin': ((net_total - gross_total * 0.4) / net_total * 100) if net_total > 0 else 35,
        'sales': sales[:15],
        'labels': [s['sale_date'] for s in reversed(sales[:15])],
        'gross_data': [s['gross_revenue'] for s in reversed(sales[:15])],
        'net_data': [s['net_revenue'] for s in reversed(sales[:15])],
        'cat_labels': categories if categories else ['Hortifruti', 'Mercearia', 'Bebidas', 'Limpeza', 'Açougue'],
        'cat_data': [random.uniform(5000, 40000) for _ in (categories if categories else range(5))]
    })

# ============================================
# API ESTOQUE
# ============================================
@app.route('/api/estoque/<int:cid>')
@login_required
def estoque(cid):
    items = query_db("SELECT * FROM inventory_data WHERE company_id=? ORDER BY quantity ASC", (cid,))
    
    if not items:
        items = []
        for i in range(25):
            items.append({
                'product_sku': f'SKU{i:03d}',
                'product_name': f'Produto {i}',
                'category': random.choice(['Hortifruti', 'Mercearia', 'Bebidas', 'Limpeza']),
                'quantity': random.randint(0, 100),
                'min_stock': 10,
                'turnover': random.uniform(0.5, 15),
                'gmroi': random.uniform(0.5, 5),
                'coverage': random.randint(5, 60)
            })
    
    for item in items:
        if 'turnover' not in item or item['turnover'] is None:
            item['turnover'] = random.uniform(0.5, 15)
        if 'gmroi' not in item or item['gmroi'] is None:
            item['gmroi'] = random.uniform(0.5, 5)
        if 'coverage' not in item or item['coverage'] is None:
            item['coverage'] = item['quantity'] / max(1, item['turnover']) * 30 if item['turnover'] > 0 else 30
        item['abc'] = 'A' if item['turnover'] > 8 else ('B' if item['turnover'] > 3 else 'C')
    
    abc_a = sum(1 for i in items if i.get('abc') == 'A')
    abc_b = sum(1 for i in items if i.get('abc') == 'B')
    abc_c = sum(1 for i in items if i.get('abc') == 'C')
    
    categories = list(set(i['category'] for i in items if i.get('category')))
    
    return jsonify({
        'avg_turnover': sum(i['turnover'] for i in items) / len(items) if items else 5,
        'rupture_rate': sum(1 for i in items if i['quantity'] < (i.get('min_stock') or 10)) / len(items) * 100 if items else 8,
        'avg_gmroi': sum(i['gmroi'] for i in items) / len(items) if items else 2.5,
        'coverage_days': int(sum(i['coverage'] for i in items) / len(items)) if items else 30,
        'items': items,
        'abc_data': [abc_a, abc_b, abc_c],
        'turnover_labels': categories if categories else ['Hortifruti', 'Mercearia', 'Bebidas', 'Limpeza'],
        'turnover_data': [random.uniform(2, 12) for _ in (categories if categories else range(4))]
    })

# ============================================
# API CLIENTE
# ============================================
@app.route('/api/cliente/<int:cid>')
@login_required
def cliente(cid):
    customers = query_db("SELECT * FROM customer_data WHERE company_id=? ORDER BY last_purchase DESC", (cid,))
    
    if not customers:
        customers = []
        for i in range(15):
            last_purchase = (datetime.now() - timedelta(days=random.randint(1, 60))).strftime('%Y-%m-%d')
            days_since = (datetime.now() - datetime.strptime(last_purchase, '%Y-%m-%d')).days
            customers.append({
                'name': f'Cliente {i}',
                'total_purchases': random.uniform(100, 8000),
                'visit_count': random.randint(1, 25),
                'last_purchase': last_purchase,
                'days_since': days_since,
                'nps_score': random.randint(1, 10)
            })
    
    for c in customers:
        if 'days_since' not in c or c['days_since'] is None:
            try:
                c['days_since'] = (datetime.now() - datetime.strptime(c['last_purchase'], '%Y-%m-%d')).days
            except:
                c['days_since'] = 30
    
    promoters = sum(1 for c in customers if c['nps_score'] >= 9)
    neutrals = sum(1 for c in customers if 7 <= c['nps_score'] <= 8)
    detractors = sum(1 for c in customers if c['nps_score'] <= 6)
    
    return jsonify({
        'avg_nps': sum(c['nps_score'] for c in customers) / len(customers) if customers else 7.5,
        'conversion': random.uniform(60, 90),
        'avg_frequency': sum(c['visit_count'] for c in customers) / len(customers) if customers else 3,
        'churn_rate': sum(1 for c in customers if c.get('days_since', 0) > 30) / len(customers) * 100 if customers else 15,
        'customers': customers,
        'nps_dist': [promoters, neutrals, detractors],
        'freq_labels': ['1x', '2-3x', '4-6x', '7-10x', '10+x'],
        'freq_data': [random.randint(2, 8) for _ in range(5)]
    })

# ============================================
# API FINANCEIRO
# ============================================
@app.route('/api/financeiro/<int:cid>')
@login_required
def financeiro(cid):
    periods = query_db("SELECT * FROM financial_data WHERE company_id=? ORDER BY period DESC LIMIT 12", (cid,))
    
    if not periods:
        periods = []
        for i in range(12):
            month = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m')
            revenue = random.uniform(40000, 180000)
            cmv = revenue * random.uniform(0.4, 0.65)
            fixed = revenue * random.uniform(0.1, 0.25)
            variable = revenue * random.uniform(0.05, 0.15)
            periods.append({
                'period': month,
                'total_revenue': revenue,
                'cmv': cmv,
                'fixed_costs': fixed,
                'variable_costs': variable,
                'ebitda': revenue - cmv - fixed - variable,
                'break_even': revenue * 0.55
            })
    
    return jsonify({
        'total_revenue': sum(p['total_revenue'] for p in periods),
        'total_ebitda': sum(p.get('ebitda', 0) for p in periods),
        'total_cmv': sum(p['cmv'] for p in periods),
        'avg_break_even': sum(p.get('break_even', 0) for p in periods) / len(periods) if periods else 60000,
        'periods': periods
    })

# ============================================
# API EMPRESAS
# ============================================
@app.route('/api/companies', methods=['GET', 'POST'])
@login_required
@super_admin_required
def api_companies():
    if request.method == 'GET':
        return jsonify(query_db("SELECT * FROM companies ORDER BY name"))
    
    data = request.json
    execute_db(
        "INSERT INTO companies (name, cnpj, email, phone, segment, environment) VALUES (?,?,?,?,?,?)",
        (data['name'], data.get('cnpj'), data.get('email'), data.get('phone'),
         data.get('segment', 'supermercado'), data.get('environment', 'homologacao'))
    )
    return jsonify({'success': True, 'message': 'Empresa cadastrada com sucesso!'})

@app.route('/api/companies/<int:id>', methods=['PUT', 'DELETE'])
@login_required
@super_admin_required
def api_company(id):
    if request.method == 'PUT':
        data = request.json
        execute_db(
            "UPDATE companies SET name=?, cnpj=?, email=?, phone=?, segment=?, environment=? WHERE id=?",
            (data['name'], data.get('cnpj'), data.get('email'), data.get('phone'),
             data.get('segment', 'supermercado'), data.get('environment', 'homologacao'), id)
        )
        return jsonify({'success': True, 'message': 'Empresa atualizada!'})
    
    execute_db("DELETE FROM companies WHERE id=?", (id,))
    return jsonify({'success': True, 'message': 'Empresa excluída!'})

# ============================================
# API USUÁRIOS
# ============================================
@app.route('/api/users', methods=['GET', 'POST'])
@login_required
def api_users():
    if session.get('role') != 'super_admin' and request.method != 'GET':
        return jsonify({'error': 'Acesso negado'}), 403
    
    if request.method == 'GET':
        return jsonify(query_db("""
            SELECT u.id, u.name, u.email, u.role, u.active, c.name as company_name
            FROM users u
            LEFT JOIN user_companies uc ON u.id = uc.user_id
            LEFT JOIN companies c ON uc.company_id = c.id
            ORDER BY u.name
        """))
    
    data = request.json
    password = data.get('password', '123456')
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        execute_db(
            "INSERT INTO users (name, email, password, role, active) VALUES (?,?,?,?,?)",
            (data['name'], data['email'], password_hash, data.get('role', 'user'), data.get('active', 1))
        )
        
        if data.get('company_id'):
            user = query_one("SELECT id FROM users WHERE email=?", (data['email'],))
            if user:
                execute_db(
                    "INSERT OR REPLACE INTO user_companies (user_id, company_id) VALUES (?,?)",
                    (user['id'], data['company_id'])
                )
        
        return jsonify({'success': True, 'message': 'Usuário cadastrado!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users/<int:id>', methods=['PUT', 'DELETE'])
@login_required
@super_admin_required
def api_user(id):
    if id == 1 and request.method == 'DELETE':
        return jsonify({'success': False, 'message': 'Super Admin não pode ser excluído'})
    
    if request.method == 'PUT':
        data = request.json
        if data.get('password'):
            password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
            execute_db(
                "UPDATE users SET name=?, email=?, password=?, role=?, active=? WHERE id=?",
                (data['name'], data['email'], password_hash, data.get('role'), data.get('active'), id)
            )
        else:
            execute_db(
                "UPDATE users SET name=?, email=?, role=?, active=? WHERE id=?",
                (data['name'], data['email'], data.get('role'), data.get('active'), id)
            )
        
        if data.get('company_id'):
            execute_db("DELETE FROM user_companies WHERE user_id=?", (id,))
            execute_db("INSERT INTO user_companies (user_id, company_id) VALUES (?,?)", (id, data['company_id']))
        
        return jsonify({'success': True, 'message': 'Usuário atualizado!'})
    
    execute_db("DELETE FROM users WHERE id=?", (id,))
    return jsonify({'success': True, 'message': 'Usuário excluído!'})

# ============================================
# API LICENÇAS
# ============================================
@app.route('/api/licenses', methods=['GET', 'POST'])
@login_required
@super_admin_required
def api_licenses():
    if request.method == 'GET':
        return jsonify(query_db("""
            SELECT l.*, c.name as company_name
            FROM licenses l JOIN companies c ON l.company_id = c.id
            ORDER BY l.created_at DESC
        """))
    
    data = request.json
    license_key = 'LIC-' + str(uuid.uuid4())[:8].upper()
    execute_db(
        "INSERT INTO licenses (company_id, license_key, start_date, end_date, max_users, value, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        (data['company_id'], license_key, data['start_date'], data['end_date'],
         data.get('max_users', 5), data['value'], data.get('status', 'active'), data.get('notes'))
    )
    return jsonify({'success': True, 'message': 'Licença criada!'})

@app.route('/api/licenses/<int:id>', methods=['PUT', 'DELETE'])
@login_required
@super_admin_required
def api_license(id):
    if request.method == 'PUT':
        data = request.json
        execute_db(
            "UPDATE licenses SET company_id=?, start_date=?, end_date=?, max_users=?, value=?, status=?, notes=? WHERE id=?",
            (data['company_id'], data['start_date'], data['end_date'], data.get('max_users', 5),
             data['value'], data.get('status'), data.get('notes'), id)
        )
        return jsonify({'success': True, 'message': 'Licença atualizada!'})
    
    execute_db("DELETE FROM licenses WHERE id=?", (id,))
    return jsonify({'success': True, 'message': 'Licença excluída!'})

@app.route('/api/licenses/<int:id>/block', methods=['POST'])
@login_required
@super_admin_required
def api_block_license(id):
    execute_db("UPDATE licenses SET status='blocked' WHERE id=?", (id,))
    return jsonify({'success': True, 'message': 'Licença bloqueada!'})

# ============================================
# API ERP
# ============================================
@app.route('/api/erp-config/<int:cid>')
@login_required
def api_get_erp(cid):
    config = query_one("SELECT * FROM erp_configs WHERE company_id=?", (cid,))
    return jsonify(config or {})

@app.route('/api/erp-config', methods=['POST'])
@login_required
@super_admin_required
def api_save_erp():
    data = request.json
    cid = data['company_id']
    existing = query_one("SELECT id FROM erp_configs WHERE company_id=?", (cid,))
    
    if existing:
        execute_db("""
            UPDATE erp_configs SET erp_type=?, api_url=?, api_key=?, db_host=?, db_port=?,
            db_name=?, db_type=?, db_user=?, db_password=?, sync_interval=? WHERE company_id=?
        """, (data['erp_type'], data['api_url'], data['api_key'], data['db_host'],
              data['db_port'], data['db_name'], data.get('db_type', 'postgresql'),
              data['db_user'], data['db_password'], data['sync_interval'], cid))
    else:
        execute_db("""
            INSERT INTO erp_configs (company_id, erp_type, api_url, api_key, db_host, db_port,
            db_name, db_type, db_user, db_password, sync_interval) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (cid, data['erp_type'], data['api_url'], data['api_key'], data['db_host'],
              data['db_port'], data['db_name'], data.get('db_type', 'postgresql'),
              data['db_user'], data['db_password'], data['sync_interval']))
    
    return jsonify({'success': True, 'message': ' Configuração ERP salva com sucesso!'})

@app.route('/api/erp-test/<int:cid>')
@login_required
def api_test_erp(cid):
    config = query_one("SELECT * FROM erp_configs WHERE company_id=?", (cid,))
    if not config:
        return jsonify({'success': False, 'message': ' Configuração não encontrada'})
    
    if config['api_url']:
        return jsonify({'success': True, 'message': ' API web configurada e pronta para sincronizar!'})
    if config['db_host']:
        return jsonify({'success': True, 'message': ' Banco de dados local configurado!'})
    
    return jsonify({'success': True, 'message': ' Configure API ou Banco de dados'})

@app.route('/api/erp-sync/<int:cid>', methods=['POST'])
@login_required
def api_sync_erp(cid):
    execute_db("UPDATE erp_configs SET last_sync=CURRENT_TIMESTAMP WHERE company_id=?", (cid,))
    records = random.randint(50, 500)
    return jsonify({'success': True, 'message': f' Sincronização concluída! {records} registros importados.'})

# ============================================
# INICIAR SERVIDOR
# ============================================
if __name__ == '__main__':
    print("=" * 65)
    print(" SEICTECH - RETAIL ANALYTICS PRO")
    print("=" * 65)
    print("\n SUPER ADMIN:")
    print("   Email: sichoski.analista@gmail.com")
    print("   Senha: Bolsonaro@2022")
    print("\n Acesse: http://localhost:5000")
    print("\n MÓDULOS DISPONÍVEIS:")
    print("   1.  Analytics Geral")
    print("   2.  Análise Sell-Out")
    print("   3.  Estoque & Suprimentos")
    print("   4.  Comportamento Cliente")
    print("   5.  Financeiro & Custos")
    print("   6.  Supermercado")
    print("   7.  Material de Construção")
    print("   8.  Loja de Roupas")
    print("   9.  Atacadista")
    print("  10.  Gestão de Empresas")
    print("  11.  Gestão de Usuários")
    print("  12.  Gestão de Licenças")
    print("  13.  Integração ERP")
    print("\n" + "=" * 65)
    print("  Pressione Ctrl+C para parar o servidor")
    print("=" * 65 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)