"""TaskFlow - gerenciador de tarefas com logging em arquivo para Promtail/Loki/Grafana."""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# -----------------------------------------------------------------------------
# Configuração de Logging para arquivo (logs/taskflow.log) e Terminal
# -----------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
LOG_FILE = os.path.join("logs", "taskflow.log")


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", "general"),
            "request_id": getattr(g, "request_id", None),
        }
        # Mescla atributos extras na raiz do JSON para a consulta LogQL funcionar
        if hasattr(record, "extra_fields"):
            log_record.update(record.extra_fields)
        return json.dumps(log_record)


logger = logging.getLogger("taskflow")
logger.setLevel(logging.INFO)

formatter = JSONFormatter()

# 1. Envia para o arquivo que o Promtail monitora
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 2. Envia também para o terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())


_secret_key = os.environ.get("TASKFLOW_SECRET_KEY")
if not _secret_key:
    raise RuntimeError("Variavel de ambiente TASKFLOW_SECRET_KEY nao definida.")

app.config["SECRET_KEY"] = _secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE = os.environ.get("TASKFLOW_DB", "taskflow.db")


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

    admin_password = os.environ.get("TASKFLOW_ADMIN_PASSWORD")
    if admin_password:
        db.execute(
            "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash(admin_password)),
        )
        db.commit()


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("tasks"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = (
            get_db()
            .execute("SELECT * FROM users WHERE username = ?", (username,))
            .fetchone()
        )

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            # Log de Login Sucesso compatível com LogQL
            logger.info(
                "login realizado",
                extra={
                    "event": "login_attempt",
                    "extra_fields": {
                        "result": "success",
                        "username": username,
                        "ip": request.remote_addr,
                    },
                },
            )
            return redirect(url_for("tasks"))

        error = "Usuário ou senha inválidos. Tente novamente."

        # Log de Login Falhou compatível com LogQL do seu Grafana
        logger.warning(
            "login falhou",
            extra={
                "event": "login_attempt",
                "extra_fields": {
                    "result": "failure",
                    "username": username,
                    "ip": request.remote_addr,
                },
            },
        )

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
        rows = db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND title LIKE ?",
            (session["user_id"], f"%{search}%"),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM tasks WHERE user_id = ?", (session["user_id"],)
        ).fetchall()

    logger.info(
        "listagem de tarefas",
        extra={
            "event": "task_listed",
            "extra_fields": {"username": session.get("username")},
        },
    )
    return render_template("tasks.html", rows=rows, username=session["username"])


@app.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        db = get_db()
        db.execute(
            "INSERT INTO tasks (user_id, title, description) VALUES (?, ?, ?)",
            (session["user_id"], title, description),
        )
        db.commit()

        logger.info(
            "tarefa criada",
            extra={
                "event": "task_created",
                "extra_fields": {
                    "username": session.get("username"),
                    "title": title,
                },
            },
        )
        return redirect(url_for("tasks"))

    return render_template("new_task.html")


with app.app_context():
    init_db()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "t")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)vv
