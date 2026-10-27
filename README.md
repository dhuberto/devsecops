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


## Estrutura
```text
devsecops/
├── .dockerignore                          # Define arquivos e pastas ignorados no contexto de build do Docker.
├── .env.example                           # Modelo de variáveis de ambiente documentado sem segredos reais.
├── .gitignore                             # Impede o commit de arquivos sensíveis, temporários ou do ambiente local.
├── .github/                               # Diretório de configurações e automações da plataforma GitHub.
│   ├── dependabot.yml                     # Configuração para monitoramento e atualização automática de dependências.
│   └── workflows/                         # Pipelines de CI/CD executadas via GitHub Actions.
│       ├── ci.yml                         # Gate de CI para análise estática de qualidade e linting (Ruff).
│       ├── container.yml                  # Build da imagem, varredura de vulnerabilidades (Trivy) e smoke test.
│       ├── dast.yml                       # Pipeline de análise dinâmica de segurança usando OWASP ZAP Baseline.
│       ├── iac-scan.yml                   # Varredura de segurança em arquivos Terraform e Docker Compose (Checkov/Trivy).
│       ├── sast.yml                       # Análise estática de código (Semgrep) e varredura de segredos (Gitleaks).
│       └── sca.yml                        # Auditoria de vulnerabilidades em bibliotecas Python (pip-audit).
├── .zap/
│   └── rules.tsv                          # Tabela de regras e tratamentos de alertas do OWASP ZAP.
├── app.py                                 # Código da aplicação Flask (TaskFlow) instrumentado com logs estruturados.
├── Dockerfile                             # Script multi-stage build com usuário não-root para geração da imagem segura.
├── docker-compose.yml                     # Orquestração local da stack de observabilidade (Grafana + Loki + Promtail).
├── promtail-config.yml                    # Regras de coleta e envio de logs JSON para o banco Loki.
├── requirements.txt                       # Lista de dependências Python com versões auditadas sem CVEs.
├── README.md                              # Documentação principal com instruções de execução e arquitetura.
├── infra/                                 # Manifestos de Infraestrutura como Código (IaC).
│   ├── docker-compose.yml                 # Orquestração multi-container da app web com banco PostgreSQL isolado.
│   └── main.tf                            # Manifesto Terraform (HCL) com configurações de segurança da AWS.
├── grafana-provisioning/
│   └── datasources/
│       └── loki.yml                       # Provisionamento automático da fonte de dados Loki no Grafana.
├── templates/                             # Templates HTML/Jinja2 com autoescape ativado.
│   ├── login.html                         # Interface de autenticação tratada contra injeções refletidas.
│   ├── new_task.html                      # Formulário para cadastro de tarefas.
│   └── tasks.html                         # Painel de tarefas protegido contra XSS armazenado.
├── docs/                                  # Relatórios técnicos e documentações da atividade.
│   ├── dast.md                            # Relatório do scan dinâmico ZAP (Antes x Depois) e OWASP Top 10.
│   ├── observabilidade.md                 # Documentação de consultas LogQL no Grafana (ex: falhas de login).
│   └── runbook-login-bruteforce.md        # Plano de resposta a incidentes de força bruta baseado no NIST SP 800-61.
└── codigo/                                # Acervo didático com exemplos de código e evoluções dos módulos.
```

## Como executar localmente

```bash
# Atualiza o índice de pacotes
sudo apt update

# Instala o motor do Docker e o plugin nativo do Docker Compose
sudo apt install docker.io docker-compose-v2 -y

# Adiciona seu usuário ao grupo docker (evita 'sudo' em cada comando)
sudo usermod -aG docker $USER

newgrp docker

```


## 2. Rodar a aplicação localmente

**Pré-requisitos:** Python 3.12 e Git.

```bash
# 1. Clonar e entrar na pasta
git clone https://github.com/dhuberto/devsecops.git
cd devsecops

# 2. Ambiente virtual e dependências
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Gerar a SECRET_KEY (copie o valor impresso)
python -c "import secrets; print(secrets.token_hex(32))"

# 4. Criar o vim .env a partir do modelo
cp .env.example .env               # Windows: copy .env.example .env
```

Abra o `.env` e preencha (sem aspas e sem espaços ao redor do `=`):

```text
TASKFLOW_SECRET_KEY=valor-gerado-no-passo-3
TASKFLOW_ADMIN_PASSWORD=uma-senha-que-voce-escolher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postg
```

```bash
# 5. Subir a app
python app.py
```

### Escanear o Terraform e Compose com Checkov e TrivyNa raiz do repositório, rode as ferramentas de análise estática de infraestrutura:

```bash
cd ~/devsecops

# Checkov
docker run --rm -v $(pwd):/tf bridgecrew/checkov:latest -d /tf

# Trivy IaC / Config
docker run --rm -v $(pwd):/src aquasec/trivy config /src
```


## Como executar a aplicação com Docker

```bash
# 1. Executado UMA ÚNICA VEZ no seu terminal do Ubuntu
git clone https://github.com/dhuberto/devsecops.git
cd devsecops

# 2. Criar diretorio de logs
mkdir -p logs && chmod 777 logs

# 3. Gerar a SECRET_KEY (copie o valor impresso)
python3 -c "import secrets; print(secrets.token_hex(32))"

# 4. Criar o .env a partir do modelo
cp .env.example .env               # Windows: copy .env.example .env
```

Abra o `vim .env` e preencha (sem aspas e sem espaços ao redor do `=`):

```text
TASKFLOW_SECRET_KEY=valor-gerado-no-passo-3
TASKFLOW_ADMIN_PASSWORD=uma-senha-que-voce-escolher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postg
```
```bash
docker run -d --rm -p 5000:5000 --env-file .env -v $(pwd)/logs:/app/logs --name taskflow-app taskflow:vuln
```


Acesse http://127.0.0.1:5000 ou o IP da VM e entre com o usuário `admin` e a senha definida
em `TASKFLOW_ADMIN_PASSWORD`.

| Usuário | Senha    |
|---------|----------|
| admin   | admin123 |
| aluno   | senha123 |

### Iniciar o Grafana, loki e o promtail

```bash
docker compose up -d
```

Acessar a aplicação no navegador em http://<IP_DA_SUA_VM>:5000 e realize múltiplas tentativas de login com senhas incorretas seguidas para gerar os logs de falha simulando a força bruta.

Consultar Logs no Grafana
Acesse o painel em http://<IP_DA_SUA_VM>:3000. Navegue até a aba "Explore", selecione a fonte de dados "Loki" e execute suas consultas LogQL 
ex: 
```bash
{job="taskflow"} | json | event = "login_attempt" | result = "failure" | username = "admin"
```
Para identificar o IP ofensor.

## Limpando o ambiente
### Parando a aplicação
```bash
docker stop taskflow-app
```

### parando o Grafana, loki e o promtail
```bash
docker compose down
```

### Apagando diretório devsecops
```bash
cd ~
rm -rf devsecops
```
