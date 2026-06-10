markdown
# 🚀 SEICTECH - ERP Agent Local v3.0

[![Python](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Omie](https://img.shields.io/badge/Omie-API-orange.svg)](https://developer.omie.com.br)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black.svg)](https://github.com/sichoski14/seictech-erp-agent)

> **ERP Agent Local** - Agente de integração para sincronização de dados entre ERPs (Omie, SAP, TOTVS, etc.) e sistemas SEICTECH.

## 📋 Índice

- [Arquitetura](#-arquitetura)
- [Funcionalidades](#-funcionalidades)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Execução](#-execução)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [APIs Suportadas](#-apis-suportadas)
- [Tratamento de Erros](#-tratamento-de-erros)
- [Monitoramento](#-monitoramento)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

---

## 🏗️ Arquitetura
┌─────────────────────────────────────────────────────────────────┐
│ SEICTECH CENTRAL │
│ (Nuvem / Servidor Local) │
└─────────────────────────────────────────────────────────────────┘
▲
│ HTTPS / Webhook
│
┌─────────────────────────────────────────────────────────────────┐
│ ERP AGENT LOCAL v3.0 │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ API REST │ │ Database │ │ CSV/XML │ │
│ │ Extractor │ │ Extractor │ │ Extractor │ │
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │
│ │ │ │ │
│ └─────────────────┼─────────────────┘ │
│ ▼ │
│ ┌─────────────────┐ │
│ │ Local Queue │ │
│ │ (SQLite) │ │
│ └────────┬────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────┐ │
│ │ Transmitter │ │
│ │ (Retry/Backoff)│ │
│ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ ERP SOURCE │
│ (Omie / SAP / TOTVS / Conta Azul) │
└─────────────────────────────────────────────────────────────────┘

text

---

## ⚡ Funcionalidades

| Módulo | Descrição | Status |
|--------|-----------|--------|
| **API REST Extractor** | Conexão com ERPs via API REST (Omie, Conta Azul) | ✅ |
| **Database Extractor** | Conexão direta com bancos de dados (PostgreSQL, MySQL, MSSQL) | ✅ |
| **CSV/XML Extractor** | Importação de arquivos exportados do ERP | ✅ |
| **Webhook Server** | Recebimento de dados via push do ERP | ✅ |
| **Local Queue** | Fila persistente para dados offline (SQLite) | ✅ |
| **Auto Retry** | Retry automático com backoff exponencial | ✅ |
| **Heartbeat** | Monitoramento contínuo da central | ✅ |
| **Structured Logging** | Logs estruturados com níveis (INFO, WARNING, ERROR) | ✅ |

---

## 📦 Pré-requisitos

### Sistema Operacional
- Windows 10/11 (x64)
- Linux (Ubuntu 20.04+)
- macOS 11+

### Software Necessário

```bash
# Python 3.14+
python --version  # Deve retornar 3.14 ou superior

# Git (opcional, para versionamento)
git --version

# Pip (gerenciador de pacotes)
pip --version
Dependências Python
bash
# Core
pip install requests>=2.31.0
pip install schedule>=1.2.0

# Database Drivers (opcionais)
pip install psycopg2-binary>=2.9.0   # PostgreSQL
pip install pymysql>=1.1.0            # MySQL
pip install pyodbc>=5.0.0             # ODBC
pip install pymssql>=2.2.0            # SQL Server
pip install fdb>=2.0.0                # Firebird

# Interface Web (opcional)
pip install streamlit>=1.28.0
pip install pandas>=2.0.0
pip install openpyxl>=3.1.0
🛠️ Instalação
1. Clone o repositório
bash
git clone https://github.com/sichoski14/seictech-erp-agent.git
cd seictech-erp-agent
2. Crie ambiente virtual (recomendado)
bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python -m venv venv
source venv/bin/activate
3. Instale dependências
bash
pip install -r requirements.txt
4. Configure o arquivo de configuração
bash
# O arquivo será criado automaticamente na primeira execução
python erp_agent_local.py

# Edite o arquivo gerado
notepad erp_agent_config.ini  # Windows
nano erp_agent_config.ini     # Linux/macOS
⚙️ Configuração
Configuração para Omie (Exemplo)
ini
[erp_source]
source_type      = api_rest
api_url          = https://app.omie.com.br/api/v1/
api_auth_type    = omie
app_key          = SEU_APP_KEY
app_secret       = SEU_APP_SECRET
Configuração para Banco de Dados
ini
[erp_source]
source_type      = postgresql
db_host          = localhost
db_port          = 5432
db_name          = erp_database
db_user          = erp_user
db_password      = erp_senha
Configuração para CSV
ini
[erp_source]
source_type      = csv_folder
files_folder     = ./dados_erp
file_encoding    = utf-8
Configuração da Central (SEICTECH)
ini
[central]
central_url      = http://localhost:5000
api_key          = SEU_API_KEY
verify_ssl       = false
send_to_central  = false  # Modo teste
🚀 Execução
Modo Normal
bash
python erp_agent_local.py
Modo Webhook
bash
# Configurar source_type = webhook no arquivo INI
python erp_agent_local.py
Modo Streamlit (Interface Web)
bash
streamlit run app_streamlit.py
Modo Financeiro
bash
streamlit run financeiro_app.py
📁 Estrutura do Projeto
text
seictech-erp-agent/
├── erp_agent_local.py          # Core do agente (998+ linhas)
├── sistema_seictech_completo.py # Sistema completo (legado)
├── app_streamlit.py            # Interface Streamlit
├── financeiro_app.py           # Dashboard financeiro
├── generate_report.py          # Gerador de relatórios
├── config.py                   # Configurações centrais
├── requirements.txt            # Dependências
├── iniciar.bat                 # Script de inicialização (Windows)
│
├── agents/                     # Módulo de agentes
│   └── *.py
│
├── api_integration/            # Integração com APIs
│   └── omie_client.py
│
├── database/                   # Camada de banco de dados
│   ├── models.py
│   └── repository.py
│
├── ml_models/                  # Modelos de ML
│   └── forecasting.py
│
├── power_bi/                   # Dashboards Power BI
│   └── relatorio.pbix
│
├── reports/                    # Relatórios gerados
│   ├── vendas.pdf
│   └── estoque.xlsx
│
├── logs/                       # Logs do sistema
│   └── erp_agent.log
│
├── data/                       # Dados persistentes
│   └── agent_queue.db
│
└── README.md                   # Documentação
🔌 APIs Suportadas
ERPs Oficialmente Suportados
ERP	Tipo	Endpoint	Método
Omie	API REST	/api/v1/	POST
Conta Azul	API REST	/v1/	GET/POST
SAP Business One	OData	/b1s/v1/	GET
TOTVS Fluig	REST API	/api/public/	GET
RD Station	API REST	/v1/	GET
Métodos de Extração
python
# Vendas
extract_sales(date_from: str, date_to: str) -> List[dict]

# Estoque
extract_inventory() -> List[dict]

# Clientes
extract_customers() -> List[dict]

# Financeiro
extract_financial() -> List[dict]
🛡️ Tratamento de Erros
Estratégia de Retry
python
retry_attempts   = 3      # Tentativas máximas
retry_delay      = 30     # Delay inicial (segundos)
# Backoff exponencial: 30s, 60s, 120s
Fila Local (Offline)
Dados são armazenados em data/agent_queue.db

Persistência em SQLite

Retry automático quando central voltar

Máximo 5 tentativas por item

Logs Estruturados
bash
2026-05-05 22:30:12,313 [INFO] 🔄 Iniciando sincronização
2026-05-05 22:30:12,730 [ERROR] Omie API: 403 Forbidden
2026-05-05 22:35:12,706 [WARNING] Tentativa 1/3: Central inacessível
📊 Monitoramento
Verificar Status
bash
# Ver logs
tail -f logs/erp_agent.log  # Linux/macOS
Get-Content logs/erp_agent.log -Wait  # PowerShell

# Verificar fila
sqlite3 data/agent_queue.db "SELECT COUNT(*) FROM sync_queue WHERE status='pending'"

# Verificar heartbeat
curl http://localhost:5000/api/agent/heartbeat
Métricas Disponíveis
Métrica	Descrição
records_synced	Total de registros sincronizados
queue_size	Tamanho da fila pendente
retry_count	Número de retentativas
last_sync	Última sincronização bem-sucedida
uptime	Tempo de atividade do agente
🤝 Contribuição
Padrão de Commits (Conventional Commits)
bash
feat: Nova funcionalidade
fix: Correção de bug
docs: Documentação
style: Formatação
refactor: Refatoração
test: Testes
chore: Manutenção
Fluxo de Contribuição
Fork o repositório

Crie uma branch: git checkout -b feature/nova-feature

Commit: git commit -m "feat: descrição"

Push: git push origin feature/nova-feature

Abra um Pull Request

📄 Licença
Este projeto está sob a licença MIT.

text
MIT License

Copyright (c) 2026 SEICTECH

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
📞 Suporte
Canal	Contato
Issues	GitHub Issues do projeto
Documentação	Wiki do Projeto
Email	sichoski.analista@gmail.com
🏆 Créditos
Desenvolvido por SEICTECH | Versão 3.0 | Atualizado em Junho/2026

commit




