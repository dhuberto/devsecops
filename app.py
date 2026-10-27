# ==============================================================================
# ARQUIVO: app.py
# DESCRIÇÃO: Aplicação Flask TaskFlow com SQLite, correções de XSS,
#            remoção de rotas inseguras e logging estruturado em JSON com request_id.
# ==============================================================================

import os
import sqlite3
import uuid
import logging
import json
from datetime import datetime, timezone
from flask import Flask, request, render_template, redirect, url_for, session, g

app = Flask(__name__)

# ------------------------------------------------------------------------------
# BLOCO 1: Configuração de Segredos e Variáveis de Ambiente
# ------------------------------------------------------------------------------
_secret_key = os.environ.get("TASKFLOW_SECRET_KEY", "desenvolvimento-chave-temporaria-devsecops")
app.config["SECRET_KEY"] = _secret_key
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "t")

# Define o caminho do banco SQLite via variável de ambiente.
# Fallback para "taskflow.db" quando executado diretamente pelo terminal (python app.py)
DATABASE = os.environ.get("TASKFLOW_DB", "taskflow.db")

# ------------------------------------------------------------------------------
# BLOCO 2: Configuração do Logging Estruturado em JSON (Módulo 6)
# ------------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Formatador de logs em formato JSON estruturado com sanitização de dados sensíveis."""
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(g, "request_id", "N/A"),
            "ip": getattr(g, "client_ip", "127.0.0.1"),
            "user": session.get("username", "anonymous") if session else "anonymous"
        }
        # Adiciona campos extras na raiz do JSON para suporte às queries LogQL do Grafana
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        return json.dumps(log_data)

# Configura handler de arquivo (para o Promtail) e de terminal
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
# BLOCO 3: Middlewares, Request ID e Gestão do Banco de Dados SQLite
# ------------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    # Injeta ou gera um Request ID único por requisição
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    g.client_ip = request.remote_addr or request.headers.get("X-Forwarded-For", "127.0.0.1")

def log_event(event_type, message, extra=None):
    """Auxiliar para emitir logs sanitizados sem expor senhas ou tokens."""
    extra_info = {"event": event_type}
    if extra:
        # Garante a remoção de senhas/tokens se passados acidentalmente
        sanitized_extra = {k: v for k, v in extra.items() if k.lower() not in ["password", "token", "secret", "cookie"]}
        extra_info.update(sanitized_extra)
    
    logger.info(message, extra={"extra_data": extra_info})

def init_db():
    """Inicializa as tabelas no SQLite utilizando o caminho dinâmico em DATABASE."""
    db = sqlite3.connect(DATABASE)
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
    
    # Cria usuário admin padrão para testes
    admin_pass = os.environ.get("TASKFLOW_ADMIN_PASSWORD", "admin123")
    cur = db.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", admin_pass))
    db.commit()
    db.close()

# Executa inicialização do banco no contexto da aplicação Flask
with app.app_context():
    init_db()

# ------------------------------------------------------------------------------
# BLOCO 4: Rotas da Aplicação (Com renderização segura Jinja2)
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("tasks"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        db = get_db()
        cur = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()
        
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            log_event("login_attempt", f"Usuário {username} autenticado com sucesso", {"result": "success", "username": username})
            return redirect(url_for("tasks"))
        else:
            error = f"Credenciais inválidas para o usuário: {username}"
            log_event("login_attempt", f"Falha de autenticação para o usuário: {username}", {"result": "failure", "username": username})

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    username = session.get("username", "anonymous")
    log_event("user_logout", f"Usuário {username} realizou logout")
    session.clear()
    return redirect(url_for("login"))

@app.route("/tasks")
def tasks():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db = get_db()
    og = request.args.get("og", "")
    search = request.args.get("search", "") or request.args.get("q", "")
    
    if search:
        query = "SELECT * FROM tasks WHERE user_id = ? AND (title LIKE ? OR description LIKE ?)"
        cur = db.execute(query, (session["user_id"], f"%{search}%", f"%{search}%"))
    else:
        cur = db.execute("SELECT * FROM tasks WHERE user_id = ?", (session["user_id"],))
        
    tasks_list = cur.fetchall()
    log_event("task_listed", f"Listagem de tarefas realizada por {session['username']}")
    
    return render_template("tasks.html", tasks=tasks_list, username=session["username"], og=og, search=search)

@app.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        
        db = get_db()
        db.execute("INSERT INTO tasks (user_id, title, description, done) VALUES (?, ?, ?, 0)",
                   (session["user_id"], title, description))
        db.commit()
        log_event("task_created", f"Nova tarefa criada: {title}", {"title": title})
        return redirect(url_for("tasks"))
        
    return render_template("new_task.html")

# NOTA DIDÁTICA: A rota /debug/info foi inteiramente removida por razões de segurança.

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "t")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
