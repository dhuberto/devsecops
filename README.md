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
POSTGRES_PASSWORD=postgres123
POSTGRES_DB=db
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
app-exemplo/
├── app.py              # Aplicação Flask (versão vulnerável, linha de base)
├── requirements.txt    # Dependências com CVEs conhecidas (uso proposital)
├── Dockerfile           # Dockerfile inseguro (uso no Módulo 2 - Hardening)
└── README.md            # Este arquivo
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
git clone 
cd devsecops/codigo/observabilidade
sudo docker compose up -d --build
```

Acessar a aplicação no navegador em http://<IP_DA_SUA_VM>:5000 e realize múltiplas tentativas de login com senhas incorretas seguidas para gerar os logs de falha simulando a força bruta.

Consultar Logs no Grafana
Acesse o painel em http://<IP_DA_SUA_VM>:3000. Navegue até a aba "Explore", selecione a fonte de dados "Loki" e execute suas consultas LogQL (ex: {job="taskflow"}) para identificar o IP ofensor.

Documentar Evidências
Capture as telas do Grafana mostrando as falhas de login mapeadas e insira essas evidências, junto com as queries utilizadas, nos arquivos docs/observabilidade.md e docs/runbook-login-bruteforce.md já criados.
