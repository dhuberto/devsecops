# ==============================================================================
# ARQUIVO: app.py
# DESCRIÇÃO: Aplicação Flask TaskFlow com suporte híbrido (PostgreSQL + SQLite),
#            correções de XSS, remoção de rotas inseguras, higiene de segredos
#            e logging estruturado em JSON com request_id.
# ==============================================================================

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# ------------------------------------------------------------------------------
# BLOCO 1: Configuração de Segredos e Variáveis de Ambiente
# ------------------------------------------------------------------------------
_secret_key = os.environ.get("TASKFLOW_SECRET_KEY", "desenvolvimento-chave-temporaria-devsecops")
app.config["SECRET_KEY"] = _secret_key
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "t")

# Proteção de cookies de sessão contra exfiltração por XSS e CSRF
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Inspeciona variáveis para determinar o tipo de banco (PostgreSQL no Docker vs SQLite no Terminal)
DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_PATH = os.environ.get("TASKFLOW_DB", "taskflow.db")

# ------------------------------------------------------------------------------
# BLOCO 2: Configuração do Logging Estruturado em JSON (Módulo 6 / Observabilidade)
# ------------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Formatador de logs em formato JSON estruturado para coleta pelo Promtail/Loki."""
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", "general"),
            "request_id": getattr(g, "request_id", "N/A"),
            "ip": getattr(g, "client_ip", "127.0.0.1"),
            "user": session.get("username", "anonymous") if session and "username" in session else "anonymous"
        }
        # Mescla atributos extras na raiz do JSON para suporte a buscas em LogQL no Grafana
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        return json.dumps(log_data)

# Garante o diretório de logs para gravação
os.makedirs("logs", exist_ok=True)
file_handler = logging.FileHandler("logs/taskflow.log")
file_handler.setFormatter(JSONFormatter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(JSONFormatter())

logger = logging.getLogger("taskflow")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ------------------------------------------------------------------------------
# BLOCO 3: Middlewares, Request ID e Gestão de Conexão de Banco de Dados Híbrida
# ------------------------------------------------------------------------------
def get_db():
    """Retorna a conexão ativa com o banco (PostgreSQL se DATABASE_URL estiver presente, senão SQLite)."""
    if "db" not in g:
        if DATABASE_URL:
            import psycopg2
            import psycopg2.extras
            g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        else:
            g.db = sqlite3.connect(SQLITE_PATH)
            g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Encerra a conexão com o banco ao finalizar o contexto da requisição."""
    db = g.pop("db", None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    """Rastreia cada requisição injetando Request ID único e IP do cliente."""
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    g.client_ip = request.remote_addr or request.headers.get("X-Forwarded-For", "127.0.0.1")

def log_event(event_type, message, extra=None):
    """Auxiliar para emitir logs sanitizados sem expor senhas ou tokens."""
    extra_info = {"event": event_type}
    if extra:
        # Higiene de dados sensíveis para não persistir senhas em texto puro nos logs
        sanitized_extra = {k: v for k, v in extra.items() if k.lower() not in ["password", "token", "secret", "cookie"]}
        extra_info.update(sanitized_extra)
    
    logger.info(message, extra={"extra_data": extra_info})

def init_db():
    """Inicializa as tabelas no PostgreSQL ou SQLite e cria o usuário admin padrão."""
    admin_pass = os.environ.get("TASKFLOW_ADMIN_PASSWORD", "admin123")
    hashed_pass = generate_password_hash(admin_pass)

    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(200) NOT NULL,
                description TEXT,
                done INTEGER DEFAULT 0
            );
        """)
        cur.execute("SELECT * FROM users WHERE username = %s;", ("admin",))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s);", ("admin", hashed_pass))
        conn.commit()
        conn.close()
    else:
        db = sqlite3.connect(SQLITE_PATH)
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                done INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        cur = db.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        if not cur.fetchone():
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", hashed_pass))
        db.commit()
        db.close()

# Executa inicialização do banco dentro do contexto da aplicação
