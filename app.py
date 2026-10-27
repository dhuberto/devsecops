# ==============================================================================
# ARQUIVO: app.py
# DESCRIÇÃO: Aplicação Flask TaskFlow com correções de XSS, rotas de debug removidas,
#            higiene de segredos e logging estruturado em JSON com request_id.
# ==============================================================================

import os
import sqlite3
import uuid
import logging
import json
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, g

app = Flask(__name__)

# ------------------------------------------------------------------------------
# BLOCO 1: Configuração de Segredos e Variáveis de Ambiente
# ------------------------------------------------------------------------------
_secret_key = os.environ.get("TASKFLOW_SECRET_KEY")
if not _secret_key:
    # Em produção, a aplicação deve falhar caso a secret não seja injetada via container/env
    _secret_key = "desenvolvimento-chave-temporaria-devsecops"

app.config["SECRET_KEY"] = _secret_key
# Debug desativado por padrão. Habilitado apenas se FLASK_DEBUG=1
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

# ------------------------------------------------------------------------------
# BLOCO 2: Configuração do Logging Estruturado em JSON (Módulo 6)
# ------------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Formatador de logs em formato JSON estruturado com sanitização de dados sensíveis."""
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "N/A"),
            "ip": getattr(record, "client_ip", "N/A"),
            "user": getattr(record, "username", "anonymous")
        }
        # Adiciona campos extras do record se existirem
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        return json.dumps(log_data)

# Configura handler de log salvando em arquivo para coleta do Promtail
os.makedirs("logs", exist_ok=True)
log_handler = logging.FileHandler("logs/taskflow.log")
log_handler.setFormatter(JSONFormatter())

logger = logging.getLogger("taskflow")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# ------------------------------------------------------------------------------
# BLOCO 3: Middlewares e Gestão de Request ID e Banco de Dados
# ------------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("taskflow.db")
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
        # Garantia de higiene: remove senhas/tokens se presentes por engano
        sanitized_extra = {k: v for k, v in extra.items() if k.lower() not in ["password", "token", "secret", "cookie"]}
        extra_info.update(sanitized_extra)
    
    extra_dict = {
        "request_id": getattr(g, "request_id", "N/A"),
        "client_ip": getattr(g, "client_ip", "N/A"),
        "username": session.get("username", "anonymous"),
        "extra_data": extra_info
    }
    logger.info(message, extra=extra_dict)

# Init DB
def init_db():
    db = sqlite3.connect("taskflow.db")
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, description TEXT, done INTEGER)")
    # Usuário padrão para testes didáticos
    cur = db.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "admin123"))
    db.commit()
    db.close()

init_db()

# ------------------------------------------------------------------------------
# BLOCO 4: Rotas da Aplicação (Com templates Jinja2 sem | safe)
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
        # Query parametrizada contra SQL Injection
        cur = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()
        
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            log_event("login_success", f"Usuário {username} autenticado com sucesso")
            return redirect(url_for("tasks"))
        else:
            # Mensagem de erro renderizada de forma segura via Jinja2 no template
            error = f"Credenciais inválidas para o usuário: {username}"
            log_event("login_failure", f"Falha de autenticação para o usuário: {username}")

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
    og = request.args.get("og", "")  # Parâmetro da busca da aula 9
    search = request.args.get("search", "")
    
    if search:
        query = "SELECT * FROM tasks WHERE user_id = ? AND (title LIKE ? OR description LIKE ?)"
        cur = db.execute(query, (session["user_id"], f"%{search}%", f"%{search}%"))
    else:
        cur = db.execute("SELECT * FROM tasks WHERE user_id = ?", (session["user_id"],))
        
    tasks_list = cur.fetchall()
    log_event("task_list", f"Listagem de tarefas realizada por {session['username']}")
    
    # render_template faz autoescape por padrão de og e task.description
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
        log_event("task_created", f"Nova tarefa criada: {title}")
        return redirect(url_for("tasks"))
        
    return render_template("new_task.html")

# NOTA DIDÁTICA: A rota /debug/info foi inteiramente removida por razões de segurança.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

# ==============================================================================
# RESUMO DAS ALTERAÇÕES NO app.py:
# 1. Removida a rota insegura /debug/info.
# 2. Adicionado autoescape nativo via render_template nos sinks og, error e tasks.
# 3. Adicionada estruturação de logs JSON com request_id e filtro contra senhas.
# ==============================================================================
