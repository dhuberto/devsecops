"""
TaskFlow - Aplicação de exemplo (Versão Segura/Corrigida)

Este arquivo demonstra as correções aplicadas sobre a linha de base vulnerável.
As correções abordam falhas comuns identificadas em processos de SAST, DAST e revisão de código.
"""

import os
import sqlite3

# Importação de bibliotecas para segurança e gerenciamento de ambiente
from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# CORREÇÃO: Gerenciamento de Configuração (12-Factor App)
# Nunca comite segredos. Usamos dotenv para carregar variáveis locais durante o desenvolvimento.
# Em produção, essas variáveis devem ser injetadas pela infraestrutura (ex: Kubernetes Secrets).
load_dotenv()

app = Flask(__name__)

# CORREÇÃO (Vulnerabilidade #3): Remoção de Segredos Hardcoded
# Antes: app.config["SECRET_KEY"] = "s3gr3d0-super-secreto..."
# O uso de segredos no código fonte é uma falha crítica. Agora, exigimos que
# seja injetado via variável de ambiente, aplicando o padrão "fail-fast".
_secret_key = os.environ.get("TASKFLOW_SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "ERRO CRÍTICO: TASKFLOW_SECRET_KEY não definida. "
        "A aplicação não pode iniciar de forma segura sem uma chave de sessão."
    )
app.config["SECRET_KEY"] = _secret_key

# CORREÇÃO ADICIONAL: Hardening de Cookies de Sessão
# Impede que o cookie seja lido via JavaScript (mitigando roubo de sessão por XSS)
app.config["SESSION_COOKIE_HTTPONLY"] = True
# Limita o envio do cookie em requisições cross-site (mitigando CSRF)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Caminho do banco parametrizado para facilitar deployments em containers (ex: volumes Docker)
DATABASE = os.environ.get("TASKFLOW_DATABASE", "taskflow.db")


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            done INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()

    # CORREÇÃO (Vulnerabilidade #4): Senhas em Texto Puro
    # Antes: as senhas eram inseridas no banco sem nenhum tratamento ("admin123").
    # Agora: A senha inicial do admin não fica no código. Se fornecida via ambiente,
    # é armazenada usando um hash criptográfico seguro com salt (pbkdf2:sha256).
    admin_password = os.environ.get("TASKFLOW_ADMIN_PASSWORD")
    cur = db.execute("SELECT COUNT(*) AS total FROM users")
    if cur.fetchone()["total"] == 0 and admin_password:
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash(admin_password)),
        )
        db.commit()


# Inicializa o DB ao carregar o módulo, permitindo execução correta via Gunicorn.
with app.app_context():
    init_db()


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("tasks"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        db = get_db()
        
        # CORREÇÃO (Vulnerabilidade #1): SQL Injection
        # Antes: A query usava concatenação ("... WHERE username = '" + username + "'...")
        # Agora: Usamos consultas parametrizadas (?). O driver sqlite3 escapa as entradas,
        # impedindo que payloads maliciosos alterem a estrutura da query.
        cur = db.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()

        # Verificação do hash da senha e não do texto puro
        if user and check_password_hash(user["password"], password):
            # CORREÇÃO ADICIONAL: Fixação de Sessão
            # Limpar a sessão antes de logar garante a renovação do ID da sessão.
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("tasks"))
        error = "Usuário ou senha inválidos."

    # CORREÇÃO (Vulnerabilidade #2): Cross-Site Scripting (XSS)
    # Antes: O HTML era retornado via f-strings no Python (diretamente).
    # Agora: O uso de render_template garante que o Jinja2 aplique autoescape em
    # variáveis interpoladas (como o erro), neutralizando payloads XSS.
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/tasks", methods=["GET"])
def tasks():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("q", "")
    db = get_db()

    if search:
        # CORREÇÃO (Vulnerabilidade #1): SQL Injection na Busca
        # O padrão do LIKE é construído em memória e passado como parâmetro
        like_pattern = f"%{search}%"
        rows = db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND title LIKE ?",
            (session["user_id"], like_pattern),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM tasks WHERE user_id = ?", (session["user_id"],)
        ).fetchall()

    # CORREÇÃO (Vulnerabilidade #2): Cross-Site Scripting (XSS)
    # A renderização de listas de tarefas via templates protege contra scripts
    # inseridos na descrição da tarefa por usuários mal-intencionados.
    return render_template(
        "tasks.html",
        rows=rows,
        search=search,
        username=session["username"],
    )


@app.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "")
        if title:
            db = get_db()
            # Uso correto de parametrização na inserção de dados
            db.execute(
                "INSERT INTO tasks (user_id, title, description) VALUES (?, ?, ?)",
                (session["user_id"], title, description),
            )
            db.commit()
        return redirect(url_for("tasks"))

    return render_template("new_task.html")


# CORREÇÃO (Vulnerabilidade #5): Vazamento de Informações
# O endpoint `/debug/info` que existia na versão base foi REMOVIDO.
# Ele expunha dados críticos como a SECRET_KEY para qualquer visitante não autenticado.


if __name__ == "__main__":
    # CORREÇÃO (Vulnerabilidade #6): Configuração de Execução Insegura
    # Antes: app.run(host="0.0.0.0", port=5000, debug=True)
    # O modo `debug=True` ativa o console do Werkzeug, permitindo Execução Remota
    # de Código (RCE) se exposto. Agora, a aplicação restringe o binding ao localhost
    # e desativa o debug. Em produção, deve-se usar um servidor WSGI adequado (Gunicorn).
    app.run(host="127.0.0.1", port=5001)
