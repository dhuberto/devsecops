# TaskFlow (App de Exemplo) — Disciplina DevSecOps

Esta é a aplicação de laboratório usada em **todos os encontros práticos** da
disciplina. É um gerenciador de tarefas (to-do list) simples em Python/Flask,
propositalmente vulnerável, que evolui ao longo do curso

## ⚠️ Aviso importante

Este código contém vulnerabilidades **intencionais** para fins didáticos
(ver comentários `# FALHA` e docstring no topo de `app.py`). Nunca:

- Use este código como referência de boas práticas.
- Implante esta aplicação em ambiente de produção ou exposto à internet.
- Reutilize o padrão de código (concatenação de SQL, senhas em texto puro,
  segredo hardcoded) em projetos reais.

## Como executar localmente

```bash
git clone https://github.com/dhuberto/devsecops.git
cd devsecops
sudo apt install python3-venv
python3 -m venv .venv
source .venv/bin/activate #Linux    &     # Windows: venv\Scripts\activate
sudo apt install python3-pip
python -m pip install --upgrade flask
pip install -r requirements.txt
python app.py
```

A aplicação sobe em `http://localhost:5000`. Usuários de teste já vêm
cadastrados no banco SQLite (`taskflow.db`, criado automaticamente):

| Usuário | Senha    |
|---------|----------|
| admin   | admin123 |
| aluno   | senha123 |

## Como executar com Docker

```bash
cd app-exemplo
docker build -t taskflow:vuln .
docker run -p 5000:5000 taskflow:vuln
```

## Estrutura

```
app-exemplo/
├── app.py              # Aplicação Flask (versão vulnerável, linha de base)
├── requirements.txt    # Dependências com CVEs conhecidas (uso proposital)
├── Dockerfile           # Dockerfile inseguro (uso no Módulo 2 - Hardening)
└── README.md            # Este arquivo
```

Cada módulo cria, dentro da sua própria pasta `codigo/`, uma cópia ou um
patch desta aplicação demonstrando o "antes" (vulnerável) e o "depois"
(corrigido) referente ao tema daquele encontro.

# Relatório de Implementação e Hardening

## Resumo Executivo das Ações Realizadas

### 1. Ajuste da Aplicação (`app.py`)
- **Remediação de SQL Injection:** Adoção de consultas parametrizadas (`?`).
- **Mitigação de XSS e Injeção de HTML:** Uso de templates Jinja2 com autoescape nativo ativado.
- **Remoção de Segredos Hardcoded:** Injeção via variáveis de ambiente (`TASKFLOW_SECRET_KEY` e `TASKFLOW_ADMIN_PASSWORD`).
- **Armazenamento Seguro de Credenciais:** Aplicação de hashing com salt via Werkzeug (`generate_password_hash`).
- **Remoção de Endpoint Exposto:** Exclusão completa da rota sensível `/debug/info`.
- **Hardening no Servidor e Sessão:** Desativação do modo `debug=True`, alteração do host local para `127.0.0.1` e configuração de cookies com `HTTPOnly` e `SameSite=Lax`.

---

### 2. Ajuste nos Pipelines de CI/CD (`.github/workflows/`)

#### 2.1. Reestruturação do CI Principal (`ci.yml`)
*Renomeado de `ci_basico.yml` para `ci.yml`.*
- **Princípio do Mínimo Privilégio:** Adição de `permissions: contents: read`.
- **Centralização:** Declaração das versões de runtime e linters no bloco `env` (`PYTHON_VERSION` e `RUFF_VERSION`).
- **Imutabilidade:** Fixação das Actions via SHA do commit (`actions/checkout` e `actions/setup-python`).
- **Performance e Linter:** Adição de cache para dependências do Pip e substituição de `py_compile` por `ruff check`.

#### 2.2. Varredura de Segurança em Containers (`container.yml`)
*Criação de workflow dedicado à análise da imagem Docker.*
- **Permissões Globais:** Configuração de `permissions: contents: read`.
- **Centralização de Variáveis:** Parâmetros de build e execução centralizados no topo (`env`).
- **Pinning de Actions:** Fixação por SHA (`actions/checkout` e `aquasecurity/trivy-action`).
- **Quality Gate (Trivy):** Bloqueio da esteira em caso de vulnerabilidades `HIGH` ou `CRITICAL`.
- **Smoke Test Hardened:** Validação de runtime executando o container com `--read-only`, `--tmpfs /tmp`, `--cap-drop ALL` e `--security-opt no-new-privileges`.
- **Injeção Segura:** Geração dinâmica de `TASKFLOW_SECRET_KEY` via `openssl`.
- **Troubleshooting:** Captura e exibição de logs do container sob falha (`if: failure()` / `if: always()`).

#### 2.3. Análise Estática de Código e Segredos (`sast.yml`)
*Criaçaõ e Implementação de ferramentas SAST e Secret Scanning.*
- **Permissões Granulares:** Define `permissions: contents: read, pull-requests: read`.
- **Gatilhos Padronizados:** Execução em `push`, `pull_request` e `workflow_dispatch`.
- **Imutabilidade:** Commit SHA Pinning nas ações de checkout, setup do Python e Gitleaks.
- **Semgrep SAST:** Centralização e fixação da versão (`SEMGREP_VERSION: "1.90.0"`).
- **Gitleaks:** Varredura do histórico completo de commits (`fetch-depth: 0`) para prevenção de vazamento de segredos.

#### 2.4. Auditoria de Dependências - SCA (`sca.yml`)
*Criaçaõ para Monitoramento de vulnerabilidades em bibliotecas de terceiros.*
- **Permissões de Leitura:** Ajuste fino via `permissions: contents: read`.
- **Automação Agendada:** Execução via Cron Job semanal (`schedule: - cron: "0 9 * * 1"`).
- **Parâmetros no `env`:** Definição centralizada de `PYTHON_VERSION`, `PIP_AUDIT_VERSION` e `REQUIREMENTS_FILE`.
- **Pinning de Actions:** Uso de hashes imutáveis SHA.
- **Software Composition Analysis:** Execução do `pip-audit` com flags `--strict` e `--desc` atuando como Quality Gate.

---

### 3. Hardening da Imagem de Container (`Dockerfile`)
- **Multi-Stage Build & Base Imutável:** Substituição da tag `latest` pela versão reduzida `python:3.12-slim`.
- **Usuário Não-Root:** Criação do grupo e usuário de sistema `taskflow` sem privilégios administrativos.
- **Otimização de Camadas:** Instalação com `--no-cache-dir` e cópia seletiva de arquivos.
- **Remoção de Segredos:** Exclusão de variáveis com senhas do histórico de build (`docker history`).
- **WSGI de Produção:** Substituição do servidor de desenvolvimento do Flask pelo `gunicorn`.
- **Proteção de Leitura:** Isolamento do diretório de dados (`/app/data`) e restrição de escrita no código-fonte.

---

### 4. Governança e Gestão de Dependências

#### 4.1. Aprovação de Mudanças (`CODEOWNERS`)
- Implementação de arquivo de governança exigindo revisão e aprovação por pares antes do merge de Pull Requests na branch principal.

#### 4.2. Gestão de Pacotes (`requirements.txt`)
- **Pinning Rigoroso:** Fixação exata de versões para todas as dependências diretas.
- **Remediação de CVEs:** Atualização de bibliotecas para versões isentas de vulnerabilidades conhecidas.
- **Dependências de Produção:** Adição do `gunicorn==26.2.0` e `python-dotenv==1.2.2`.

#### 4.3. Arquivos de Ignoração (`.dockerignore` e `.gitignore`)
- **`.dockerignore`:** Exclusão de arquivos locais, históricos, diretórios `.git` e ambientes virtuais do contexto de build do Docker.
- **`.gitignore`:** Bloqueio de envio de arquivos `.env`, bancos de dados locais (`taskflow.db`), caches de Python e artefatos de teste para o repositório Git.

---

### 5. Camada de Apresentação e Modularização de Templates (`templates/`)

#### 5.1. Template de Autenticação (`templates/login.html`)
- **Separação de Responsabilidades:** Desacoplamento da interface HTML da lógica de backend no `app.py`.
- **Comentários Nativos no Jinja2:** Uso da sintaxe `{# ... #}` para evitar exceções de compilação (`TemplateSyntaxError`).
- **Mitigação de XSS:** Interpolação declarativa ativando o autoescape automático para tratamento de mensagens de erro.
- **Aprovação no Quality Gate (SAST):** Eliminação de f-strings que retornavam HTML diretamente no código Python, solucionando alertas do Semgrep (`directly-returned-format-string`).

#### 5.2. Formulário de Criação (`templates/new_task.html`)
- Interface dedicada à criação de tarefas no endpoint `@app.route("/tasks/new", methods=["GET", "POST"])`.

#### 5.3. Painel de Gestão (`templates/tasks.html`)
- Interface para visualização e busca de tarefas cadastradas usada pela rota `@app.route("/tasks", methods=["GET"])`.
- **Garantia Anti-XSS Armazenado:** A renderização via `tasks.html` garante a sanitização de caracteres especiais digitados pelos usuários no `new_task.html` (conversão automática de `<script>` para `&lt;script&gt;`).
