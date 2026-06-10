import sqlite3
import pandas as pd
from datetime import datetime
import webbrowser
import os

def generate_html_report():
    """Gera relatório HTML e abre no navegador"""
    
    conn = sqlite3.connect('data/retail_analytics.db')
    
    # Dados
    products = pd.read_sql_query("""
        SELECT p.name, p.sku, p.category, i.quantity, p.unit_price
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
    """, conn)
    
    sales = pd.read_sql_query("""
        SELECT DATE(sale_date) as date, COUNT(*) as transactions,
               SUM(total_amount) as revenue
        FROM sales
        GROUP BY DATE(sale_date)
        ORDER BY date DESC
        LIMIT 30
    """, conn)
    
    # Criar HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Análise</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background: #4CAF50; color: white; }}
            .header {{ background: #4CAF50; color: white; padding: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Relatório de Análise de Varejo</h1>
            <p>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
        <h2>📦 Produtos em Estoque</h2>
        {products.to_html(classes='table', index=False)}
        
        <h2>💰 Vendas Recentes</h2>
        {sales.to_html(classes='table', index=False)}
        
        <footer>
            <p>Sistema Avançado de Análise de Varejo © 2024</p>
        </footer>
    </body>
    </html>
    """
    
    # Salvar e abrir
    report_path = 'reports/relatorio.html'
    os.makedirs('reports', exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    webbrowser.open(f'file://{os.path.abspath(report_path)}')
    print(f"✅ Relatório gerado: {report_path}")

if __name__ == '__main__':
    generate_html_report()