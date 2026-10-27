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

# 4. Criar o .env a partir do modelo
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

Acesse http://127.0.0.1:5001 e entre com o usuário `admin` e a senha definida
em `TASKFLOW_ADMIN_PASSWORD`.

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
devsecops/
├── .dockerignore                          # Define arquivos e pastas ignorados no contexto de build do Docker[cite: 34].
├── .env.example                           # Modelo de variáveis de ambiente documentado sem segredos reais[cite: 2, 182].
├── .gitignore                             # Impede o commit de arquivos sensíveis, temporários ou do ambiente local[cite: 2, 34, 189].
├── .github/                               # Diretório de configurações e automações da plataforma GitHub.
│   ├── dependabot.yml                     # Configuração para monitoramento e atualização automática de dependências[cite: 62, 75].
│   └── workflows/                         # Pipelines de CI/CD executadas via GitHub Actions[cite: 2, 222].
│       ├── ci.yml                         # Gate de CI para análise estática de qualidade e linting (Ruff)[cite: 222].
│       ├── container.yml                  # Build da imagem, varredura de vulnerabilidades (Trivy) e smoke test[cite: 2, 40, 48].
│       ├── dast.yml                       # Pipeline de análise dinâmica de segurança usando OWASP ZAP Baseline[cite: 2, 170, 171].
│       ├── iac-scan.yml                   # Varredura de segurança em arquivos Terraform e Docker Compose (Checkov/Trivy)[cite: 2, 208, 209].
│       ├── sast.yml                       # Análise estática de código (Semgrep) e varredura de segredos (Gitleaks)[cite: 64, 80].
│       └── sca.yml                        # Auditoria de vulnerabilidades em bibliotecas Python (pip-audit)[cite: 60, 77].
├── .zap/
│   └── rules.tsv                          # Tabela de regras e tratamentos de alertas do OWASP ZAP[cite: 2].
├── app.py                                 # Código da aplicação Flask (TaskFlow) instrumentado com logs estruturados[cite: 1, 2, 54].
├── Dockerfile                             # Script multi-stage build com usuário não-root para geração da imagem segura[cite: 2, 28, 31, 33, 45].
├── docker-compose.yml                     # Orquestração local da stack de observabilidade (Grafana + Loki + Promtail)[cite: 2].
├── promtail-config.yml                    # Regras de coleta e envio de logs JSON para o banco Loki[cite: 2].
├── requirements.txt                       # Lista de dependências Python com versões auditadas sem CVEs[cite: 54, 69].
├── README.md                              # Documentação principal com instruções de execução e arquitetura[cite: 2, 223].
├── infra/                                 # Manifestos de Infraestrutura como Código (IaC)[cite: 2, 182, 218].
│   ├── docker-compose.yml                 # Orquestração multi-container da app web com banco PostgreSQL isolado[cite: 2, 182, 190].
│   └── main.tf                            # Manifesto Terraform (HCL) com configurações de segurança da AWS[cite: 2, 218].
├── grafana-provisioning/
│   └── datasources/
│       └── loki.yml                       # Provisionamento automático da fonte de dados Loki no Grafana[cite: 2].
├── templates/                             # Templates HTML/Jinja2 com autoescape ativado[cite: 1, 146, 166].
│   ├── login.html                         # Interface de autenticação tratada contra injeções refletidas[cite: 1, 166].
│   ├── new_task.html                      # Formulário para cadastro de tarefas[cite: 1, 166].
│   └── tasks.html                         # Painel de tarefas protegido contra XSS armazenado[cite: 1, 146, 167].
├── docs/                                  # Relatórios técnicos e documentações da atividade[cite: 2].
│   ├── dast.md                            # Relatório do scan dinâmico ZAP (Antes x Depois) e OWASP Top 10[cite: 2, 138].
│   ├── observabilidade.md                 # Documentação de consultas LogQL no Grafana (ex: falhas de login)[cite: 2].
│   └── runbook-login-bruteforce.md        # Plano de resposta a incidentes de força bruta baseado no NIST SP 800-61[cite: 2].
└── codigo/                                # Acervo didático com exemplos de código e evoluções dos módulos[cite: 1, 45, 165, 185, 214, 225].
```

Cada módulo cria, dentro da sua própria pasta `codigo/`, uma cópia ou um
patch desta aplicação demonstrando o "antes" (vulnerável) e o "depois"
(corrigido) referente ao tema daquele encontro.


Teste PR parte - 2

Levantando o ambiente localmente.

```bash
# Atualiza o índice de pacotes
sudo apt update

# Instala o motor do Docker e o plugin nativo do Docker Compose
sudo apt install docker.io docker-compose-v2 -y

# Adiciona seu usuário ao grupo docker (evita 'sudo' em cada comando)
sudo usermod -aG docker $USER

newgrp docker


```

```bash
cd ~/devsecops
```

3.2. Escanear o Terraform e Compose com Checkov e TrivyNa raiz do repositório, rode as ferramentas de análise estática de infraestrutura:  
```bash
# Checkov
docker run --rm -v $(pwd):/tf bridgecrew/checkov:latest -d /tf

# Trivy IaC / Config
docker run --rm -v $(pwd):/src aquasec/trivy config /src
```

```bash
docker compose up -d
```

Acessar a aplicação no navegador em http://<IP_DA_SUA_VM>:5000 e realize múltiplas tentativas de login com senhas incorretas seguidas para gerar os logs de falha simulando a força bruta.

Consultar Logs no Grafana
Acesse o painel em http://<IP_DA_SUA_VM>:3000. Navegue até a aba "Explore", selecione a fonte de dados "Loki" e execute suas consultas LogQL 
ex: 
```bash
sum by (ip) (count_over_time({app="taskflow", event="login_attempt"} | json | result = "failure" [5m])))
```
para identificar o IP ofensor.

Documentar Evidências
Capture as telas do Grafana mostrando as falhas de login mapeadas e insira essas evidências, junto com as queries utilizadas, nos arquivos docs/observabilidade.md e docs/runbook-login-bruteforce.md já criados.
