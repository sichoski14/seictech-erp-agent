import threading
import time
from datetime import datetime, timedelta
import schedule
import json
from typing import Dict, Any

# Importar todos os módulos
from config import Config
from database.models import DatabaseManager
from api_integration.erp_connector import ERPConnector
from agents.stock_agent import StockAgent
from agents.sales_agent import SalesAgent
from agents.financial_agent import FinancialAgent
from agents.strategy_agent import StrategyAgent
from reports.email_sender import ReportGenerator
from power_bi.dashboard_config import PowerBIDashboard

class RetailAnalyticsSystem:
    def __init__(self):
        print("=" * 60)
        print("INICIANDO SISTEMA AVANÇADO DE ANÁLISE DE VAREJO")
        print("=" * 60)
        
        # Inicializar componentes
        self.config = Config()
        self.db = DatabaseManager(self.config.DATABASE_PATH)
        self.erp = ERPConnector(self.config)
        
        # Inicializar agentes
        self.stock_agent = StockAgent(self.db, self.config)
        self.sales_agent = SalesAgent(self.db, self.config)
        self.financial_agent = FinancialAgent(self.db, self.config)
        self.strategy_agent = StrategyAgent(self.db, self.config)
        
        # Inicializar relatórios
        self.report_generator = ReportGenerator(self.config, self.db)
        
        # Inicializar Power BI
        self.power_bi = PowerBIDashboard(self.config)
        
        print("✅ Todos os módulos inicializados com sucesso!")
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Executa análise completa do sistema"""
        print(f"\n[{datetime.now()}] INICIANDO ANÁLISE COMPLETA...")
        
        analysis_results = {
            'timestamp': datetime.now().isoformat(),
            'stock_analysis': self.stock_agent.analyze_stock_health(),
            'heatmap_analysis': self.stock_agent.analyze_heatmap_data().to_dict(),
            'payment_analysis': self.stock_agent.analyze_payment_methods(),
            'stock_recommendations': self.stock_agent.generate_stock_recommendations(),
            'sales_performance': self.sales_agent.analyze_sales_performance(),
            'product_turnover': self.sales_agent.analyze_product_turnover().to_dict('records'),
            'sales_prediction': self.sales_agent.predict_sales(7).to_dict('records'),
            'operator_performance': self.sales_agent.analyze_operator_performance().to_dict('records'),
            'financial_health': self.financial_agent.analyze_financial_health(),
            'cashflow_prediction': self.financial_agent.predict_cashflow(30).to_dict('records'),
            'profitability': self.financial_agent.analyze_profitability(),
            'complete_strategy': self.strategy_agent.generate_complete_strategy()
        }
        
        print("✅ Análise completa finalizada!")
        return analysis_results
    
    def sync_erp_data(self):
        """Sincroniza dados com ERP"""
        print(f"[{datetime.now()}] Sincronizando dados com ERP...")
        
        try:
            # Buscar dados do ERP
            inventory_data = self.erp.fetch_inventory_data()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            sales_data = self.erp.fetch_sales_data(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            # Atualizar banco de dados local
            if not inventory_data.empty:
                with self.db.get_connection() as conn:
                    inventory_data.to_sql('inventory', conn, if_exists='replace', index=False)
                print(f"✅ {len(inventory_data)} registros de inventário atualizados")
            
            if not sales_data.empty:
                with self.db.get_connection() as conn:
                    sales_data.to_sql('sales', conn, if_exists='append', index=False)
                print(f"✅ {len(sales_data)} registros de vendas importados")
            
        except Exception as e:
            print(f"❌ Erro na sincronização: {e}")
    
    def send_scheduled_reports(self):
        """Envia relatórios programados"""
        print(f"[{datetime.now()}] Gerando relatórios diários...")
        
        try:
            # Gerar relatório
            report_data = self.report_generator.generate_daily_report()
            
            # Lista de destinatários
            recipients = [
                'gerente@empresa.com',
                'financeiro@empresa.com',
                'operacoes@empresa.com'
            ]
            
            # Enviar e-mail
            self.report_generator.send_report_email(report_data, recipients)
            
        except Exception as e:
            print(f"❌ Erro ao enviar relatórios: {e}")
    
    def update_power_bi(self):
        """Atualiza dashboards do Power BI"""
        print(f"[{datetime.now()}] Atualizando Power BI...")
        
        try:
            # Preparar dados para o dashboard
            dashboard_data = {
                'stock_health': self.stock_agent.analyze_stock_health(),
                'sales_summary': self.sales_agent.analyze_sales_performance(),
                'financial_overview': self.financial_agent.analyze_financial_health()
            }
            
            # Enviar para Power BI
            self.power_bi.push_data(dashboard_data)
            print("✅ Power BI atualizado!")
            
        except Exception as e:
            print(f"❌ Erro ao atualizar Power BI: {e}")
    
    def run_continuous_analysis(self):
        """Executa análise contínua em tempo real"""
        print("\n" + "=" * 60)
        print("MODO DE ANÁLISE CONTÍNUA ATIVADO")
        print("=" * 60)
        
        # Agendar tarefas
        schedule.every(5).minutes.do(self.sync_erp_data)
        schedule.every(15).minutes.do(self.run_full_analysis)
        schedule.every(1).hour.do(self.update_power_bi)
        schedule.every().day.at("08:00").do(self.send_scheduled_reports)
        
        print("\n📊 Tarefas agendadas:")
        print("   - Sincronização ERP: a cada 5 minutos")
        print("   - Análise completa: a cada 15 minutos")
        print("   - Atualização Power BI: a cada hora")
        print("   - Relatórios por e-mail: diariamente às 08:00")
        print("\n🎯 Sistema em execução... Pressione Ctrl+C para parar.\n")
        
        # Executar primeira análise imediatamente
        self.sync_erp_data()
        initial_analysis = self.run_full_analysis()
        
        # Salvar análise inicial
        with open('analysis_results.json', 'w') as f:
            json.dump(initial_analysis, f, indent=2, default=str)
        
        print("📁 Resultados salvos em 'analysis_results.json'")
        
        # Loop principal
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 Sistema finalizado pelo usuário.")
    
    def interactive_mode(self):
        """Modo interativo para consultas específicas"""
        print("\n" + "=" * 60)
        print("MODO INTERATIVO - CONSULTAS ESPECÍFICAS")
        print("=" * 60)
        
        while True:
            print("\n" + "-" * 40)
            print("OPÇÕES DISPONÍVEIS:")
            print("1. Análise de Estoque")
            print("2. Análise de Vendas")
            print("3. Análise Financeira")
            print("4. Estratégias de Negócio")
            print("5. Relatório Completo")
            print("6. Previsões ML")
            print("7. Recomendações")
            print("0. Sair")
            
            option = input("\nEscolha uma opção: ")
            
            if option == '1':
                analysis = self.stock_agent.analyze_stock_health()
                print("\n📦 ANÁLISE DE ESTOQUE:")
                print(f"Total de produtos: {analysis['total_products']}")
                print(f"Produtos críticos: {len(analysis['critical_products'])}")
                print(f"Produtos em alerta: {len(analysis['alert_products'])}")
                
                if analysis['critical_products']:
                    print("\n⚠️ PRODUTOS CRÍTICOS:")
                    for product in analysis['critical_products'][:5]:
                        print(f"  - {product['name']} (SKU: {product['sku']}): {product['quantity']} unidades")
            
            elif option == '2':
                performance = self.sales_agent.analyze_sales_performance()
                print("\n💰 PERFORMANCE DE VENDAS:")
                print(f"Receita total (30d): R$ {performance['total_revenue_30d']:,.2f}")
                print(f"Ticket médio: R$ {performance['avg_ticket']:,.2f}")
                print(f"Taxa de crescimento: {performance['growth_rate']:.1f}%")
            
            elif option == '3':
                financial = self.financial_agent.analyze_financial_health()
                print("\n🏦 ANÁLISE FINANCEIRA:")
                print(f"Margem bruta: {financial['margins']['gross_margin']:.1f}%")
                print(f"Lucro bruto: R$ {financial['margins']['gross_profit']:,.2f}")
            
            elif option == '4':
                strategy = self.strategy_agent.generate_complete_strategy()
                print("\n🎯 ESTRATÉGIAS GERADAS:")
                print("Estratégias de marketing:")
                if 'marketing_strategy' in strategy:
                    for s in strategy['marketing_strategy']['strategies']:
                        print(f"  - {s['type']}: {s['action']}")
            
            elif option == '5':
                print("\n📊 Gerando relatório completo...")
                analysis = self.run_full_analysis()
                with open('analysis_results.json', 'w') as f:
                    json.dump(analysis, f, indent=2, default=str)
                print("✅ Relatório salvo em 'analysis_results.json'")
            
            elif option == '6':
                print("\n🔮 PREVISÕES:")
                sales_pred = self.sales_agent.predict_sales(7)
                print("\nPrevisão de vendas (7 dias):")
                for pred in sales_pred.to_dict('records'):
                    print(f"  {pred['date']}: R$ {pred['predicted_revenue']:,.2f}")
                
                cashflow_pred = self.financial_agent.predict_cashflow(30)
                print("\nPrevisão de fluxo de caixa (30 dias):")
                total_cashflow = sum([p['projected_balance'] for p in cashflow_pred.to_dict('records')])
                print(f"  Saldo projetado: R$ {total_cashflow:,.2f}")
            
            elif option == '7':
                recommendations = self.stock_agent.generate_stock_recommendations()
                print("\n💡 RECOMENDAÇÕES:")
                for rec in recommendations[:5]:
                    print(f"  [{rec['priority']}] {rec['name']}: {rec['action']}")
                    if 'suggested_quantity' in rec:
                        print(f"    Quantidade sugerida: {rec['suggested_quantity']}")
            
            elif option == '0':
                print("\n👋 Até logo!")
                break
            
            else:
                print("❌ Opção inválida!")

def main():
    """Função principal"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     SISTEMA AVANÇADO DE ANÁLISE DE DADOS PARA VAREJO     ║
    ║          Machine Learning & Agentes de IA                ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Inicializar sistema
    system = RetailAnalyticsSystem()
    
    # Menu principal
    print("\nESCOLHA O MODO DE OPERAÇÃO:")
    print("1. Modo Contínuo (análise em tempo real)")
    print("2. Modo Interativo (consultas específicas)")
    print("3. Executar análise única")
    print("0. Sair")
    
    choice = input("\nOpção: ")
    
    if choice == '1':
        system.run_continuous_analysis()
    elif choice == '2':
        system.sync_erp_data()
        system.interactive_mode()
    elif choice == '3':
        system.sync_erp_data()
        results = system.run_full_analysis()
        with open('analysis_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print("\n✅ Análise concluída! Resultados em 'analysis_results.json'")
    elif choice == '0':
        print("👋 Sistema finalizado.")
    else:
        print("❌ Opção inválida!")

if __name__ == "__main__":
    main()