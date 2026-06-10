"""
SEICTECH - ERP AGENT LOCAL v3.0
================================
Agente que roda localmente na máquina/servidor do cliente.
Conecta com QUALQUER ERP (nuvem ou local) e envia os dados
para o sistema central SEICTECH hospedado em nuvem ou local.

Suporta:
  - APIs REST/JSON (ERPs em nuvem: Omie, Conta Azul, SAP B1, TOTVS Fluig, etc.)
  - Banco de dados direto (PostgreSQL, MySQL, MSSQL, SQLite, Firebird)
  - Arquivos XML/CSV exportados pelo ERP
  - Webhook/Push (ERP que envia dados ao agente)
  - ODBC (qualquer ERP legado via driver ODBC)
  - Polling (varredura periódica)
"""

import os
import sys
import json
import time
import uuid
import logging
import hashlib
import sqlite3
import threading
import schedule
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import configparser

# ─── OPCIONAL: instalar extras conforme necessidade ───────────────────────────
try:
    import psycopg2
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

try:
    import pymysql
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    import pyodbc
    HAS_ODBC = True
except ImportError:
    HAS_ODBC = False

try:
    import fdb  # Firebird
    HAS_FIREBIRD = True
except ImportError:
    HAS_FIREBIRD = False

try:
    import pymssql
    HAS_MSSQL = True
except ImportError:
    HAS_MSSQL = False

# ─── LOGGING ──────────────────────────────────────────────────────────────────
LOG_FILE = Path("logs/erp_agent.log")
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ERPAgent")

# ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────
CONFIG_FILE = Path("erp_agent_config.ini")

DEFAULT_CONFIG = """
[agent]
agent_id         = {agent_id}
agent_name       = Agente Local SEICTECH
company_id       = 1
sync_interval    = 300
retry_attempts   = 3
retry_delay      = 30
log_level        = INFO

[central]
# URL do sistema SEICTECH central (nuvem ou IP local de outro servidor)
central_url      = http://localhost:5000
api_key          = SEU_API_KEY_AQUI
# Se o sistema central estiver em rede local, pode usar IP:
# central_url    = http://192.168.1.100:5000
# Para HTTPS com certificado autoassinado:
verify_ssl       = true
# Desabilitar envio para central (útil para testes)
send_to_central  = false

[erp_source]
# Tipo: api_rest | postgresql | mysql | mssql | sqlite | firebird | odbc | csv_folder | xml_folder | webhook
source_type      = api_rest

# ─── API REST (Omie) ───────────────────────────────────────────────────────
api_url          = https://app.omie.com.br/api/v1/
api_auth_type    = omie
# Credenciais Omie
app_key          = SUA_APP_KEY_AQUI
app_secret       = SEU_APP_SECRET_AQUI
# Para outras APIs:
api_user         =
api_password     =
api_token        =
api_key_header   = X-Api-Key
api_key_value    =

# ─── BANCO DE DADOS DIRETO ──────────────────────────────────────────────────
db_host          = localhost
db_port          = 5432
db_name          = erp_database
db_user          = erp_user
db_password      = erp_senha
db_charset       = utf8

# Para ODBC:
odbc_dsn         =
odbc_connection_string =

# Para arquivos:
files_folder     = C:/ERP_Exports
file_encoding    = latin-1

# Para webhook (o agente abre um servidor HTTP para receber dados):
webhook_port     = 8765
webhook_secret   = meu_segredo_webhook

[erp_mapping]
# Mapeamento de colunas do ERP para o formato SEICTECH
# Formato: campo_seictech = nome_campo_no_erp
# Deixe em branco para usar os nomes padrão

# Vendas
sale_date        = data_venda
gross_revenue    = valor_bruto
net_revenue      = valor_liquido
returns          = devolucoes
taxes            = impostos
total_transactions = qtd_transacoes
category         = categoria_produto

# Estoque
product_sku      = codigo_produto
product_name     = descricao_produto
quantity         = saldo_estoque
unit_cost        = custo_medio
unit_price       = preco_venda
min_stock        = estoque_minimo
max_stock        = estoque_maximo
""".format(agent_id=str(uuid.uuid4())[:8])


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG, encoding="utf-8")
        log.info(f"✅ Arquivo de configuração criado: {CONFIG_FILE}")
        log.info("   ⚠️  Edite o arquivo e reinicie o agente.")
    cfg.read(CONFIG_FILE, encoding="utf-8")
    return cfg


# ─── BANCO LOCAL DE CACHE / FILA ──────────────────────────────────────────────
QUEUE_DB = Path("data/agent_queue.db")
QUEUE_DB.parent.mkdir(exist_ok=True)


def init_queue_db():
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS sync_queue (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        data_type  TEXT NOT NULL,
        payload    TEXT NOT NULL,
        status     TEXT DEFAULT 'pending',
        attempts   INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        sent_at    TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sync_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        data_type  TEXT,
        records    INTEGER,
        status     TEXT,
        message    TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()


def queue_add(data_type: str, payload: dict):
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute(
        "INSERT INTO sync_queue (data_type, payload) VALUES (?, ?)",
        (data_type, json.dumps(payload, default=str)),
    )
    conn.commit()
    conn.close()


def queue_get_pending(limit=100) -> List[dict]:
    conn = sqlite3.connect(QUEUE_DB)
    rows = conn.execute(
        "SELECT id, data_type, payload, attempts FROM sync_queue WHERE status='pending' AND attempts < 5 LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "data_type": r[1], "payload": json.loads(r[2]), "attempts": r[3]} for r in rows]


def queue_mark_sent(ids: List[int]):
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute(
        f"UPDATE sync_queue SET status='sent', sent_at=datetime('now') WHERE id IN ({','.join('?' for _ in ids)})",
        ids,
    )
    conn.commit()
    conn.close()


def queue_mark_failed(ids: List[int]):
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute(
        f"UPDATE sync_queue SET attempts=attempts+1 WHERE id IN ({','.join('?' for _ in ids)})",
        ids,
    )
    conn.commit()
    conn.close()


def log_sync(data_type: str, records: int, status: str, message: str = ""):
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute(
        "INSERT INTO sync_log (data_type, records, status, message) VALUES (?,?,?,?)",
        (data_type, records, status, message),
    )
    conn.commit()
    conn.close()


# ─── EXTRATORES DE DADOS ERP ──────────────────────────────────────────────────


class ERPExtractorBase:
    """Classe base para todos os extratores"""

    def __init__(self, cfg: configparser.ConfigParser):
        self.cfg = cfg
        self.mapping = dict(cfg["erp_mapping"]) if "erp_mapping" in cfg else {}

    def _map(self, row: dict, field: str) -> Any:
        """Aplica mapeamento de campo"""
        erp_field = self.mapping.get(field, "").strip()
        if erp_field and erp_field in row:
            return row[erp_field]
        return row.get(field)

    def extract_sales(self, date_from: str, date_to: str) -> List[dict]:
        raise NotImplementedError

    def extract_inventory(self) -> List[dict]:
        raise NotImplementedError

    def extract_customers(self) -> List[dict]:
        raise NotImplementedError

    def extract_financial(self) -> List[dict]:
        raise NotImplementedError


class APIRestExtractor(ERPExtractorBase):
    """Extrator para ERPs com API REST (Omie, ContaAzul, SAP B1, TOTVS Fluig, etc.)"""

    def __init__(self, cfg):
        super().__init__(cfg)
        s = cfg["erp_source"]
        self.base_url = s.get("api_url", "").rstrip("/")
        self.auth_type = s.get("api_auth_type", "basic")
        self.app_key = s.get("app_key", "")
        self.app_secret = s.get("app_secret", "")
        self.session = requests.Session()
        self.session.timeout = 30

        if self.auth_type == "basic":
            self.session.auth = (s.get("api_user", ""), s.get("api_password", ""))
        elif self.auth_type == "bearer":
            self.session.headers["Authorization"] = f"Bearer {s.get('api_token', '')}"
        elif self.auth_type == "apikey":
            self.session.headers[s.get("api_key_header", "X-Api-Key")] = s.get("api_key_value", "")

    def _post_omie(self, call: str, param: dict = None) -> dict:
        """Método específico para API Omie (usa POST com autenticação no body)"""
        if self.auth_type != "omie" or not self.app_key or not self.app_secret:
            return {}
            
        url = self.base_url
        payload = {
            "call": call,
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": param or []
        }
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.error(f"Omie API POST {call}: {e}")
            return {}

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            r = self.session.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"API GET {url}: {e}")
            return {}

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        try:
            r = self.session.post(url, json=body)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"API POST {url}: {e}")
            return {}

    def extract_sales(self, date_from: str, date_to: str) -> List[dict]:
        """
        Extrai vendas da Omie usando API correta
        Endpoint: /financas/contareceber/
        """
        result = []
        
        # Para Omie, usamos o método POST específico
        if self.auth_type == "omie" and self.app_key:
            # Buscar contas a receber no período
            data = self._post_omie("ListarContasReceber", {
                "dataEmissaoDe": date_from,
                "dataEmissaoAte": date_to,
                "pagina": 1,
                "registros_por_pagina": 100
            })
            
            records = data.get("contas_receber_cadastro", data.get("lista", []))
            
            for row in records:
                result.append({
                    "sale_date": row.get("data_emissao", "")[:10],
                    "gross_revenue": float(row.get("valor_documento", 0)),
                    "net_revenue": float(row.get("valor_liquido", row.get("valor_documento", 0))),
                    "returns": 0,
                    "taxes": float(row.get("valor_impostos", 0)),
                    "total_transactions": 1,
                    "total_items": int(row.get("quantidade_itens", 1)),
                    "category": "Geral",
                })
        else:
            # Fallback para APIs REST genéricas
            data = self._get("/sales", params={"from": date_from, "to": date_to})
            records = data.get("items", data.get("records", data.get("data", [])))
            
            for row in records:
                result.append({
                    "sale_date": self._map(row, "sale_date"),
                    "gross_revenue": float(self._map(row, "gross_revenue") or 0),
                    "net_revenue": float(self._map(row, "net_revenue") or 0),
                    "returns": float(self._map(row, "returns") or 0),
                    "taxes": float(self._map(row, "taxes") or 0),
                    "total_transactions": int(self._map(row, "total_transactions") or 1),
                    "total_items": int(row.get("total_items", 1)),
                    "category": self._map(row, "category") or "Geral",
                })
        
        return result

    def extract_inventory(self) -> List[dict]:
        """Extrai estoque da Omie"""
        result = []
        
        if self.auth_type == "omie" and self.app_key:
            data = self._post_omie("ListarProdutos", {
                "pagina": 1,
                "registros_por_pagina": 100
            })
            
            records = data.get("produtos", data.get("lista", []))
            
            for row in records:
                result.append({
                    "product_sku": str(row.get("codigo", "")),
                    "product_name": row.get("descricao", "Produto"),
                    "category": row.get("categoria", "Geral"),
                    "quantity": float(row.get("estoque_atual", 0)),
                    "unit_cost": float(row.get("custo_medio", 0)),
                    "unit_price": float(row.get("preco_venda", 0)),
                    "min_stock": int(row.get("estoque_minimo", 5)),
                    "max_stock": int(row.get("estoque_maximo", 100)),
                })
        else:
            data = self._get("/inventory", params={"page": 1, "limit": 1000})
            records = data.get("items", data.get("records", data.get("data", [])))
            
            for row in records:
                result.append({
                    "product_sku": self._map(row, "product_sku") or row.get("id"),
                    "product_name": self._map(row, "product_name") or "Produto",
                    "category": self._map(row, "category") or "Geral",
                    "quantity": int(self._map(row, "quantity") or 0),
                    "unit_cost": float(self._map(row, "unit_cost") or 0),
                    "unit_price": float(self._map(row, "unit_price") or 0),
                    "min_stock": int(self._map(row, "min_stock") or 5),
                    "max_stock": int(self._map(row, "max_stock") or 100),
                })
        
        return result

    def extract_customers(self) -> List[dict]:
        """Extrai clientes da Omie"""
        result = []
        
        if self.auth_type == "omie" and self.app_key:
            data = self._post_omie("ListarClientes", {
                "pagina": 1,
                "registros_por_pagina": 100
            })
            
            records = data.get("clientes", data.get("lista", []))
            
            for row in records:
                result.append({
                    "customer_id": str(row.get("codigo_cliente", "")),
                    "name": row.get("razao_social", row.get("nome_fantasia", "Cliente")),
                    "total_purchases": float(row.get("total_compras", 0)),
                    "visit_count": int(row.get("quantidade_pedidos", 1)),
                    "last_purchase": row.get("ultima_compra", datetime.now().strftime("%Y-%m-%d")),
                    "nps_score": int(row.get("nps_score", 7)),
                })
        else:
            data = self._get("/customers", params={"page": 1, "limit": 500})
            records = data.get("items", data.get("records", data.get("data", [])))
            
            for row in records:
                result.append({
                    "customer_id": str(row.get("id") or row.get("codigo")),
                    "name": row.get("name") or row.get("nome") or "Cliente",
                    "total_purchases": float(row.get("total_purchases") or row.get("total_compras") or 0),
                    "visit_count": int(row.get("visit_count") or row.get("qtd_visitas") or 1),
                    "last_purchase": row.get("last_purchase") or row.get("ultima_compra") or datetime.now().strftime("%Y-%m-%d"),
                    "nps_score": int(row.get("nps_score") or 7),
                })
        
        return result

    def extract_financial(self) -> List[dict]:
        """Extrai resumo financeiro da Omie"""
        result = []
        
        if self.auth_type == "omie" and self.app_key:
            # Buscar últimos 12 meses
            for months_ago in range(12):
                period_dt = datetime.now().replace(day=1) - timedelta(days=months_ago * 28)
                period = period_dt.strftime("%Y%m")
                
                # Buscar resumo do período
                data = self._post_omie("ResumoPorPeriodo", {"periodo": period})
                
                if data:
                    result.append({
                        "period": period_dt.strftime("%Y-%m"),
                        "total_revenue": float(data.get("receita_total", 0)),
                        "total_costs": float(data.get("custo_total", 0)),
                        "fixed_costs": float(data.get("custo_fixo", 0)),
                        "variable_costs": float(data.get("custo_variavel", 0)),
                        "ebitda": float(data.get("ebitda", 0)),
                        "cmv": float(data.get("cmv", 0)),
                        "break_even": float(data.get("ponto_equilibrio", 0)),
                    })
        else:
            # Fallback genérico
            now = datetime.now()
            for months_ago in range(12):
                period_dt = now.replace(day=1) - timedelta(days=months_ago * 28)
                period = period_dt.strftime("%Y-%m")
                data = self._get("/financial/summary", params={"period": period})
                if data:
                    result.append({
                        "period": period,
                        "total_revenue": float(data.get("total_revenue") or 0),
                        "total_costs": float(data.get("total_costs") or 0),
                        "fixed_costs": float(data.get("fixed_costs") or 0),
                        "variable_costs": float(data.get("variable_costs") or 0),
                        "ebitda": float(data.get("ebitda") or 0),
                        "cmv": float(data.get("cmv") or 0),
                        "break_even": float(data.get("break_even") or 0),
                    })
        
        return result


class DatabaseExtractor(ERPExtractorBase):
    """
    Extrator para conexão direta no banco de dados do ERP.
    Suporta PostgreSQL, MySQL, MSSQL, SQLite, Firebird, ODBC.
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        s = cfg["erp_source"]
        self.db_host = s.get("db_host", "localhost")
        self.db_port = s.get("db_port", "5432")
        self.db_name = s.get("db_name", "")
        self.db_user = s.get("db_user", "")
        self.db_password = s.get("db_password", "")
        self.source_type = s.get("source_type", "postgresql")
        self.odbc_conn_str = s.get("odbc_connection_string", "")
        self.odbc_dsn = s.get("odbc_dsn", "")

    def _get_connection(self):
        st = self.source_type
        if st == "postgresql" and HAS_POSTGRES:
            return psycopg2.connect(
                host=self.db_host, port=int(self.db_port),
                dbname=self.db_name, user=self.db_user, password=self.db_password,
            )
        elif st == "mysql" and HAS_MYSQL:
            return pymysql.connect(
                host=self.db_host, port=int(self.db_port),
                database=self.db_name, user=self.db_user, password=self.db_password,
                charset="utf8mb4",
            )
        elif st == "mssql" and HAS_MSSQL:
            return pyodbc.connect(
                f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={self.db_host},{self.db_port};DATABASE={self.db_name};UID={self.db_user};PWD={self.db_password}"
            )
        elif st == "sqlite":
            return sqlite3.connect(self.db_name)
        elif st == "firebird" and HAS_FIREBIRD:
            return fdb.connect(
                host=self.db_host, database=self.db_name,
                user=self.db_user, password=self.db_password,
            )
        elif st == "odbc" and HAS_ODBC:
            if self.odbc_conn_str:
                return pyodbc.connect(self.odbc_conn_str)
            return pyodbc.connect(f"DSN={self.odbc_dsn};UID={self.db_user};PWD={self.db_password}")
        else:
            raise RuntimeError(f"Driver '{st}' não disponível. Instale o pacote necessário.")

    def _query(self, sql: str, params=()) -> List[dict]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def extract_sales(self, date_from: str, date_to: str) -> List[dict]:
        """
        ⚡ ADAPTE as queries abaixo para as tabelas do seu ERP.
        Exemplos fornecidos são genéricos.
        """
        sql = """
            SELECT
                CAST(data_emissao AS DATE)     AS sale_date,
                SUM(valor_bruto)               AS gross_revenue,
                SUM(valor_liquido)             AS net_revenue,
                COALESCE(SUM(devolucoes), 0)   AS returns,
                COALESCE(SUM(impostos), 0)     AS taxes,
                COUNT(*)                       AS total_transactions,
                SUM(qtd_itens)                 AS total_items,
                categoria                      AS category
            FROM pedidos_venda
            WHERE data_emissao BETWEEN ? AND ?
              AND situacao = 'FATURADO'
            GROUP BY CAST(data_emissao AS DATE), categoria
            ORDER BY sale_date ASC
        """
        try:
            rows = self._query(sql, (date_from, date_to))
            return [{
                "sale_date": str(r.get("sale_date", "")),
                "gross_revenue": float(r.get("gross_revenue") or 0),
                "net_revenue": float(r.get("net_revenue") or 0),
                "returns": float(r.get("returns") or 0),
                "taxes": float(r.get("taxes") or 0),
                "total_transactions": int(r.get("total_transactions") or 1),
                "total_items": int(r.get("total_items") or 1),
                "category": r.get("category") or "Geral",
            } for r in rows]
        except Exception as e:
            log.error(f"DB extract_sales: {e}")
            return []

    def extract_inventory(self) -> List[dict]:
        sql = """
            SELECT
                codigo_produto    AS product_sku,
                descricao         AS product_name,
                categoria         AS category,
                departamento      AS department,
                saldo_atual       AS quantity,
                custo_medio       AS unit_cost,
                preco_venda       AS unit_price,
                estoque_minimo    AS min_stock,
                estoque_maximo    AS max_stock
            FROM produtos
            WHERE ativo = 1
        """
        try:
            rows = self._query(sql)
            return [{
                "product_sku": str(r.get("product_sku", "")),
                "product_name": r.get("product_name", "Produto"),
                "category": r.get("category") or "Geral",
                "department": r.get("department") or "",
                "quantity": int(r.get("quantity") or 0),
                "unit_cost": float(r.get("unit_cost") or 0),
                "unit_price": float(r.get("unit_price") or 0),
                "min_stock": int(r.get("min_stock") or 5),
                "max_stock": int(r.get("max_stock") or 100),
            } for r in rows]
        except Exception as e:
            log.error(f"DB extract_inventory: {e}")
            return []

    def extract_customers(self) -> List[dict]:
        sql = """
            SELECT
                codigo_cliente   AS customer_id,
                nome             AS name,
                total_compras    AS total_purchases,
                qtd_visitas      AS visit_count,
                ultima_compra    AS last_purchase
            FROM clientes
            WHERE ativo = 1
        """
        try:
            rows = self._query(sql)
            return [{
                "customer_id": str(r.get("customer_id", "")),
                "name": r.get("name", "Cliente"),
                "total_purchases": float(r.get("total_purchases") or 0),
                "visit_count": int(r.get("visit_count") or 1),
                "last_purchase": str(r.get("last_purchase") or datetime.now().strftime("%Y-%m-%d")),
                "nps_score": int(r.get("nps_score") or 7),
            } for r in rows]
        except Exception as e:
            log.error(f"DB extract_customers: {e}")
            return []

    def extract_financial(self) -> List[dict]:
        sql = """
            SELECT
                strftime('%Y-%m', data_lancamento) AS period,
                SUM(receita_total)                 AS total_revenue,
                SUM(custo_mercadoria)              AS cmv,
                SUM(custo_fixo)                    AS fixed_costs,
                SUM(custo_variavel)                AS variable_costs,
                SUM(ebitda)                        AS ebitda,
                SUM(ponto_equilibrio)              AS break_even
            FROM lancamentos_financeiros
            WHERE data_lancamento >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', data_lancamento)
            ORDER BY period ASC
        """
        try:
            rows = self._query(sql)
            return [{
                "period": r.get("period", ""),
                "total_revenue": float(r.get("total_revenue") or 0),
                "cmv": float(r.get("cmv") or 0),
                "fixed_costs": float(r.get("fixed_costs") or 0),
                "variable_costs": float(r.get("variable_costs") or 0),
                "ebitda": float(r.get("ebitda") or 0),
                "break_even": float(r.get("break_even") or 0),
            } for r in rows]
        except Exception as e:
            log.error(f"DB extract_financial: {e}")
            return []


class CSVFolderExtractor(ERPExtractorBase):
    """Extrator para pasta com arquivos CSV/XML exportados pelo ERP"""

    def __init__(self, cfg):
        super().__init__(cfg)
        self.folder = Path(cfg["erp_source"].get("files_folder", "./erp_exports"))
        self.encoding = cfg["erp_source"].get("file_encoding", "latin-1")

    def _read_csv(self, pattern: str) -> List[dict]:
        import csv
        result = []
        for f in sorted(self.folder.glob(pattern), reverse=True)[:5]:
            try:
                with open(f, encoding=self.encoding, errors="replace") as fp:
                    reader = csv.DictReader(fp, delimiter=";")
                    result.extend([{k.lower().strip(): v for k, v in row.items()} for row in reader])
            except Exception as e:
                log.warning(f"CSV read {f}: {e}")
        return result

    def _read_xml(self, pattern: str, root_tag: str) -> List[dict]:
        import xml.etree.ElementTree as ET
        result = []
        for f in sorted(self.folder.glob(pattern), reverse=True)[:5]:
            try:
                tree = ET.parse(f)
                for elem in tree.getroot().iter(root_tag):
                    result.append({child.tag.lower(): child.text for child in elem})
            except Exception as e:
                log.warning(f"XML read {f}: {e}")
        return result

    def extract_sales(self, date_from: str, date_to: str) -> List[dict]:
        rows = self._read_csv("vendas*.csv") or self._read_xml("vendas*.xml", "venda")
        result = []
        for row in rows:
            date = row.get("data_venda") or row.get("sale_date") or ""
            if date_from <= date[:10] <= date_to:
                result.append({
                    "sale_date": date[:10],
                    "gross_revenue": float(row.get("valor_bruto") or row.get("gross_revenue") or 0),
                    "net_revenue": float(row.get("valor_liquido") or row.get("net_revenue") or 0),
                    "returns": float(row.get("devolucoes") or 0),
                    "taxes": float(row.get("impostos") or 0),
                    "total_transactions": int(row.get("qtd_transacoes") or 1),
                    "total_items": int(row.get("total_items") or 1),
                    "category": row.get("categoria") or "Geral",
                })
        return result

    def extract_inventory(self) -> List[dict]:
        rows = self._read_csv("estoque*.csv") or self._read_xml("estoque*.xml", "produto")
        return [{
            "product_sku": row.get("codigo") or row.get("product_sku") or str(i),
            "product_name": row.get("descricao") or row.get("product_name") or "Produto",
            "category": row.get("categoria") or "Geral",
            "quantity": int(row.get("saldo") or row.get("quantity") or 0),
            "unit_cost": float(row.get("custo") or row.get("unit_cost") or 0),
            "unit_price": float(row.get("preco") or row.get("unit_price") or 0),
            "min_stock": int(row.get("estoque_min") or 5),
            "max_stock": int(row.get("estoque_max") or 100),
        } for i, row in enumerate(rows)]

    def extract_customers(self) -> List[dict]:
        rows = self._read_csv("clientes*.csv") or []
        return [{
            "customer_id": row.get("codigo") or str(i),
            "name": row.get("nome") or "Cliente",
            "total_purchases": float(row.get("total_compras") or 0),
            "visit_count": int(row.get("qtd_visitas") or 1),
            "last_purchase": row.get("ultima_compra") or datetime.now().strftime("%Y-%m-%d"),
            "nps_score": int(row.get("nps") or 7),
        } for i, row in enumerate(rows)]

    def extract_financial(self) -> List[dict]:
        rows = self._read_csv("financeiro*.csv") or []
        return [{
            "period": row.get("periodo") or row.get("period") or "",
            "total_revenue": float(row.get("receita") or 0),
            "cmv": float(row.get("cmv") or 0),
            "fixed_costs": float(row.get("custo_fixo") or 0),
            "variable_costs": float(row.get("custo_variavel") or 0),
            "ebitda": float(row.get("ebitda") or 0),
            "break_even": float(row.get("ponto_equilibrio") or 0),
        } for row in rows]


def get_extractor(cfg: configparser.ConfigParser) -> ERPExtractorBase:
    source_type = cfg["erp_source"].get("source_type", "api_rest")
    if source_type == "api_rest":
        return APIRestExtractor(cfg)
    elif source_type in ("postgresql", "mysql", "mssql", "sqlite", "firebird", "odbc"):
        return DatabaseExtractor(cfg)
    elif source_type in ("csv_folder", "xml_folder"):
        return CSVFolderExtractor(cfg)
    else:
        raise ValueError(f"source_type desconhecido: {source_type}")


# ─── TRANSMISSOR PARA O SISTEMA CENTRAL ───────────────────────────────────────


class CentralTransmitter:
    """Envia dados para o sistema SEICTECH central (nuvem ou local)"""

    def __init__(self, cfg: configparser.ConfigParser):
        c = cfg["central"]
        self.base_url = c.get("central_url", "http://localhost:5000").rstrip("/")
        self.api_key = c.get("api_key", "")
        self.company_id = int(cfg["agent"].get("company_id", 1))
        self.agent_id = cfg["agent"].get("agent_id", "unknown")
        self.verify_ssl = c.get("verify_ssl", "true").lower() == "true"
        self.retry_attempts = int(cfg["agent"].get("retry_attempts", 3))
        self.retry_delay = int(cfg["agent"].get("retry_delay", 30))
        self.send_to_central = c.get("send_to_central", "false").lower() == "true"
        self.session = requests.Session()
        self.session.headers.update({
            "X-Agent-ID": self.agent_id,
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        })

    def _post(self, endpoint: str, payload: dict) -> bool:
        """Envia dados para a central (se habilitado)"""
        if not self.send_to_central:
            return True  # Simula sucesso
            
        url = f"{self.base_url}{endpoint}"
        for attempt in range(1, self.retry_attempts + 1):
            try:
                r = self.session.post(url, json=payload, timeout=60, verify=self.verify_ssl)
                if r.status_code in (200, 201):
                    return True
                log.warning(f"POST {url} → {r.status_code}: {r.text[:200]}")
            except requests.exceptions.ConnectionError:
                log.warning(f"Tentativa {attempt}/{self.retry_attempts}: Central inacessível ({url})")
            except Exception as e:
                log.error(f"Transmit error: {e}")
            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay)
        return False

    def send_sales(self, records: List[dict]) -> bool:
        return self._post(
            f"/api/agent/ingest/sales",
            {"company_id": self.company_id, "agent_id": self.agent_id, "records": records},
        )

    def send_inventory(self, records: List[dict]) -> bool:
        return self._post(
            f"/api/agent/ingest/inventory",
            {"company_id": self.company_id, "agent_id": self.agent_id, "records": records},
        )

    def send_customers(self, records: List[dict]) -> bool:
        return self._post(
            f"/api/agent/ingest/customers",
            {"company_id": self.company_id, "agent_id": self.agent_id, "records": records},
        )

    def send_financial(self, records: List[dict]) -> bool:
        return self._post(
            f"/api/agent/ingest/financial",
            {"company_id": self.company_id, "agent_id": self.agent_id, "records": records},
        )

    def heartbeat(self) -> bool:
        if not self.send_to_central:
            return True
        return self._post(
            "/api/agent/heartbeat",
            {"agent_id": self.agent_id, "company_id": self.company_id, "ts": datetime.now().isoformat()},
        )

    def send_queued(self) -> int:
        """Envia itens da fila local (dados que falharam anteriormente)"""
        pending = queue_get_pending(200)
        if not pending:
            return 0
        sent_ids, failed_ids = [], []
        for item in pending:
            endpoint_map = {
                "sales": self.send_sales,
                "inventory": self.send_inventory,
                "customers": self.send_customers,
                "financial": self.send_financial,
            }
            fn = endpoint_map.get(item["data_type"])
            if fn:
                records = item["payload"].get("records", [item["payload"]])
                ok = fn(records)
                (sent_ids if ok else failed_ids).append(item["id"])

        if sent_ids:
            queue_mark_sent(sent_ids)
            log.info(f"✅ Fila: {len(sent_ids)} itens enviados")
        if failed_ids:
            queue_mark_failed(failed_ids)
        return len(sent_ids)


# ─── CICLO DE SINCRONIZAÇÃO ───────────────────────────────────────────────────


class SyncAgent:
    def __init__(self, cfg: configparser.ConfigParser):
        self.cfg = cfg
        self.extractor = get_extractor(cfg)
        self.transmitter = CentralTransmitter(cfg)
        self.company_id = int(cfg["agent"].get("company_id", 1))

    def run_sync(self):
        log.info("═" * 60)
        log.info("🔄 Iniciando ciclo de sincronização ERP → SEICTECH")
        ts = datetime.now()

        # ── Vendas (últimos 30 dias) ──
        date_to = ts.strftime("%Y-%m-%d")
        date_from = (ts - timedelta(days=30)).strftime("%Y-%m-%d")

        try:
            sales = self.extractor.extract_sales(date_from, date_to)
            if sales:
                ok = self.transmitter.send_sales(sales)
                status = "ok" if ok else "queued"
                if not ok:
                    queue_add("sales", {"company_id": self.company_id, "records": sales})
                log_sync("sales", len(sales), status)
                log.info(f"  Vendas: {len(sales)} registros → {status.upper()}")
            else:
                log.info("  Vendas: nenhum dado novo")
        except Exception as e:
            log.error(f"  Vendas ERROR: {e}")
            log_sync("sales", 0, "error", str(e))

        # ── Estoque (snapshot completo) ────────────────────────────────────────
        try:
            inventory = self.extractor.extract_inventory()
            if inventory:
                ok = self.transmitter.send_inventory(inventory)
                status = "ok" if ok else "queued"
                if not ok:
                    queue_add("inventory", {"company_id": self.company_id, "records": inventory})
                log_sync("inventory", len(inventory), status)
                log.info(f"  Estoque: {len(inventory)} produtos → {status.upper()}")
            else:
                log.info("  Estoque: nenhum dado novo")
        except Exception as e:
            log.error(f"  Estoque ERROR: {e}")
            log_sync("inventory", 0, "error", str(e))

        # ── Clientes ──────────────────────────────────────────────────────────
        try:
            customers = self.extractor.extract_customers()
            if customers:
                ok = self.transmitter.send_customers(customers)
                status = "ok" if ok else "queued"
                if not ok:
                    queue_add("customers", {"company_id": self.company_id, "records": customers})
                log_sync("customers", len(customers), status)
                log.info(f"  Clientes: {len(customers)} registros → {status.upper()}")
            else:
                log.info("  Clientes: nenhum dado novo")
        except Exception as e:
            log.error(f"  Clientes ERROR: {e}")

        # ── Financeiro ────────────────────────────────────────────────────────
        try:
            financial = self.extractor.extract_financial()
            if financial:
                ok = self.transmitter.send_financial(financial)
                status = "ok" if ok else "queued"
                if not ok:
                    queue_add("financial", {"company_id": self.company_id, "records": financial})
                log_sync("financial", len(financial), status)
                log.info(f"  Financeiro: {len(financial)} períodos → {status.upper()}")
            else:
                log.info("  Financeiro: nenhum dado novo")
        except Exception as e:
            log.error(f"  Financeiro ERROR: {e}")

        # ── Fila de pendentes ─────────────────────────────────────────────────
        n = self.transmitter.send_queued()
        if n:
            log.info(f"  Fila: {n} itens pendentes reenviados")

        # ── Heartbeat ─────────────────────────────────────────────────────────
        self.transmitter.heartbeat()

        elapsed = (datetime.now() - ts).total_seconds()
        log.info(f"✅ Sincronização concluída em {elapsed:.1f}s")

    def run_forever(self):
        interval = int(self.cfg["agent"].get("sync_interval", 300))
        log.info(f"🚀 ERP Agent iniciado — Sincronização a cada {interval}s")
        log.info(f"   Empresa: {self.company_id}")
        log.info(f"   Fonte: {self.cfg['erp_source'].get('source_type', '?')}")
        log.info(f"   Central: {self.cfg['central'].get('central_url', '?')}")
        log.info(f"   Envio para central: {self.cfg['central'].get('send_to_central', 'false')}")

        # Sincroniza imediatamente ao iniciar
        self.run_sync()

        # Agenda para repetir
        schedule.every(interval).seconds.do(self.run_sync)
        while True:
            schedule.run_pending()
            time.sleep(10)


# ─── MODO WEBHOOK (ERP envia para o agente) ───────────────────────────────────

def start_webhook_server(cfg: configparser.ConfigParser):
    """
    Sobe um servidor HTTP local que recebe dados do ERP via push/webhook.
    Útil quando o ERP tem suporte a notificações automáticas.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler

    port = int(cfg["erp_source"].get("webhook_port", 8765))
    secret = cfg["erp_source"].get("webhook_secret", "")
    transmitter = CentralTransmitter(cfg)

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            sig = self.headers.get("X-Webhook-Secret", "")

            if secret and sig != secret:
                self.send_response(401)
                self.end_headers()
                return

            try:
                data = json.loads(body)
                data_type = data.get("type", "sales")
                records = data.get("records", [data])
                fn_map = {
                    "sales": transmitter.send_sales,
                    "inventory": transmitter.send_inventory,
                    "customers": transmitter.send_customers,
                    "financial": transmitter.send_financial,
                }
                fn = fn_map.get(data_type, transmitter.send_sales)
                ok = fn(records)
                if not ok:
                    queue_add(data_type, {"records": records})
                log.info(f"Webhook: {data_type} ({len(records)} registros) → {'OK' if ok else 'QUEUED'}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                log.error(f"Webhook error: {e}")
                self.send_response(500)
                self.end_headers()

        def log_message(self, *args):
            pass  # silencia logs do HTTPServer

    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    log.info(f"🌐 Servidor Webhook ativo na porta {port}")
    threading.Thread(target=server.serve_forever, daemon=True).start()


# ─── ENTRYPOINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SEICTECH — ERP AGENT LOCAL v3.0")
    print("=" * 60)

    init_queue_db()
    cfg = load_config()

    # Se estiver em modo webhook, sobe o servidor em background
    if cfg["erp_source"].get("source_type") == "webhook":
        start_webhook_server(cfg)
        # Em modo webhook puro só processa fila periodicamente
        transmitter = CentralTransmitter(cfg)
        interval = int(cfg["agent"].get("sync_interval", 300))
        schedule.every(interval).seconds.do(transmitter.send_queued)
        schedule.every(60).seconds.do(transmitter.heartbeat)
        log.info("Agente em modo WEBHOOK — aguardando dados do ERP...")
        while True:
            schedule.run_pending()
            time.sleep(10)
    else:
        agent = SyncAgent(cfg)
        agent.run_forever()