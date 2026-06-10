import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
import json
from typing import Dict, Any, List

class ReportGenerator:
    def __init__(self, config, db_manager):
        self.config = config
        self.db = db_manager
    
    def generate_daily_report(self) -> Dict[str, Any]:
        """Gera relatório diário executivo"""
        # Dados de vendas do dia
        sales_query = """
            SELECT 
                COUNT(*) as total_transactions,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_ticket,
                COUNT(DISTINCT operator_id) as active_operators
            FROM sales
            WHERE DATE(sale_date) = DATE('now')
        """
        
        daily_sales = self.db.execute_query(sales_query).iloc[0].to_dict()
        
        # Top produtos
        top_products_query = """
            SELECT 
                p.name,
                SUM(s.quantity) as units_sold,
                SUM(s.total_amount) as revenue
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE DATE(s.sale_date) = DATE('now')
            GROUP BY p.id
            ORDER BY revenue DESC
            LIMIT 10
        """
        
        top_products = self.db.execute_query(top_products_query).to_dict('records')
        
        # Alertas de estoque
        stock_alerts_query = """
            SELECT 
                p.sku,
                p.name,
                i.quantity,
                p.minimum_stock
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            WHERE i.quantity <= p.minimum_stock
            ORDER BY i.quantity ASC
            LIMIT 20
        """
        
        stock_alerts = self.db.execute_query(stock_alerts_query).to_dict('records')
        
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'sales_summary': daily_sales,
            'top_products': top_products,
            'stock_alerts': stock_alerts,
            'generated_at': datetime.now().isoformat()
        }
    
    def generate_html_report(self, data: Dict[str, Any]) -> str:
        """Gera relatório em HTML formatado"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; }}
                .section {{ margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .alert {{ color: red; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Relatório Diário de Análise de Varejo</h1>
                <p>Data: {data['date']}</p>
            </div>
            
            <div class="section">
                <h2>Resumo de Vendas</h2>
                <table>
                    <tr>
                        <th>Métrica</th>
                        <th>Valor</th>
                    </tr>
                    <tr>
                        <td>Total de Transações</td>
                        <td>{data['sales_summary']['total_transactions']}</td>
                    </tr>
                    <tr>
                        <td>Receita Total</td>
                        <td>R$ {data['sales_summary']['total_revenue']:,.2f}</td>
                    </tr>
                    <tr>
                        <td>Ticket Médio</td>
                        <td>R$ {data['sales_summary']['avg_ticket']:,.2f}</td>
                    </tr>
                    <tr>
                        <td>Operadores Ativos</td>
                        <td>{data['sales_summary']['active_operators']}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>Top 10 Produtos</h2>
                <table>
                    <tr>
                        <th>Produto</th>
                        <th>Unidades Vendidas</th>
                        <th>Receita</th>
                    </tr>
        """
        
        for product in data['top_products']:
            html += f"""
                    <tr>
                        <td>{product['name']}</td>
                        <td>{product['units_sold']}</td>
                        <td>R$ {product['revenue']:,.2f}</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
            
            <div class="section">
                <h2>Alertas de Estoque</h2>
                <table>
                    <tr>
                        <th>SKU</th>
                        <th>Produto</th>
                        <th>Estoque Atual</th>
                        <th>Estoque Mínimo</th>
                        <th>Status</th>
                    </tr>
        """
        
        for alert in data['stock_alerts']:
            html += f"""
                    <tr>
                        <td>{alert['sku']}</td>
                        <td>{alert['name']}</td>
                        <td class="alert">{alert['quantity']}</td>
                        <td>{alert['minimum_stock']}</td>
                        <td class="alert">CRÍTICO</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
            
            <div class="section">
                <p>Relatório gerado automaticamente pelo Sistema de Análise Avançada de Varejo</p>
                <p>Data/Hora: """ + data['generated_at'] + """</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_report_email(self, report_data: Dict, recipients: List[str]):
        """Envia relatório por e-mail"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Relatório de Análise - {report_data['date']}"
            msg['From'] = self.config.SMTP_USER
            msg['To'] = ', '.join(recipients)
            
            # HTML content
            html_content = self.generate_html_report(report_data)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Anexar dados em JSON
            json_attachment = MIMEApplication(
                json.dumps(report_data, indent=2, default=str),
                'json'
            )
            json_attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=f'report_{report_data["date"]}.json'
            )
            msg.attach(json_attachment)
            
            # Enviar e-mail
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USER, self.config.SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"Report sent successfully to {recipients}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False