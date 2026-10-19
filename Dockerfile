# Dockerfile HARDENED (Alpine) - corrige as seis falhas do Dockerfile original.

# CORRIGIDO (FALHA 1): tag fixada e imagem ultra-leve (Alpine Linux - menos
# pacotes de SO e menor superficie de ataque que a slim), em vez de "latest".
# Build multi-stage: o estagio final nao carrega cache nem ferramentas de instalacao.
FROM python:3.12-alpine AS build

WORKDIR /app

COPY requirements.txt .

# CORRIGIDO (FALHA 3): versoes fixadas no requirements.txt (auditadas pelo
# pip-audit no sca.yml) e --no-cache-dir para nao deixar cache na camada.
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-alpine AS runtime

# Banco aponta para /app/data (volume no docker run).
# TMPDIR e PYTHONPYCACHEPREFIX sao direcionados para /tmp (tmpfs) para permitir
# escrita de arquivos temporarios/cache mesmo com a flag --read-only ativa.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp \
    PYTHONPYCACHEPREFIX=/tmp \
    TASKFLOW_DATABASE=/app/data/taskflow.db

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

WORKDIR /app

# CORRIGIDO (FALHA 2): usuario e grupo dedicados, sem privilegios de root.
# ADAPTADO PARA ALPINE: utiliza addgroup e adduser (BusyBox) pois groupadd/useradd
# sao exclusivos do Debian/Ubuntu. So a pasta data/ (banco SQLite) e gravavel.
RUN addgroup -S taskflow && \
    adduser -S -G taskflow -H -s /sbin/nologin taskflow && \
    mkdir -p /app/data && \
    chown -R taskflow:taskflow /app/data && \
    chmod 770 /app/data

# ANTES: "COPY --chown=taskflow:taskflow . ." levava .env, .git, codigo/ e o
#        banco local para a imagem, e deixava o codigo alteravel pela app.
# AGORA: copia SO o necessario; arquivos ficam do root (somente leitura p/ app).
COPY app.py .
COPY templates/ templates/

# CORRIGIDO (FALHA 4): nenhum segredo em ENV/ARG. TASKFLOW_SECRET_KEY e
# TASKFLOW_ADMIN_PASSWORD sao injetadas em tempo de execucao (docker run -e).

# CORRIGIDO (FALHA 5): EXPOSE apenas documenta a porta do gunicorn; o
# servidor de desenvolvimento do Flask nao e mais usado.
EXPOSE 5000

USER taskflow

# CORRIGIDO (FALHA 6): gunicorn (WSGI de producao) no lugar de "python app.py".
# Sem debug: o bloco __main__ do app.py nao e executado. O init_db() roda
# na importacao do app.py, entao nao precisa de comando extra.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]


# =============================================================================
# RESUMO DAS CORREÇÕES E PRÁTICAS DE HARDENING APLICADAS NO DOCKERFILE (ALPINE)
# =============================================================================

# Correção 1: Fixação de Imagem Base e Multi-Stage Build (Substituição da tag `latest`)
# - O que mudou: Substituição da imagem `python:latest` pela versão ultra-reduzida `python:3.12-alpine` com estratégia de build em múltiplos estágios (build e runtime).
# - Por quê: Reduz significativamente a dimensão da imagem e vulnerabilidades (CVEs) do SO em relação à imagem slim, mantendo o ambiente reprodutível e sem ferramentas de compilação na camada final.

# Correção 2: Execução com Usuário Não-Root com Utilitários do Alpine (Princípio do Mínimo Privilégio)
# - O que mudou: Criação do grupo/usuário de sistema sem diretório home e sem acesso a shell (`taskflow`) usando `addgroup -S` e `adduser -S`, seguido da instrução `USER taskflow`.
# - Por quê: Adapta a gestão de usuários para o Alpine (BusyBox) enquanto mantém a proteção contra execução em `root`, impedindo a escalada de privilégios e o comprometimento do host.

# Correção 3: Instalação Limpa de Dependências e Seleção Seletiva de Arquivos
# - O que mudou: Adição da flag `--no-cache-dir` na instalação de pacotes e substituição do `COPY . .` pela cópia explícita de apenas arquivos necessários (`app.py` e `templates/`).
# - Por quê: Reduz o tamanho final da imagem, otimiza o tempo de build e previne o vazamento não intencional de arquivos locais sensíveis (como `.env`, `.git` ou repositórios de testes).

# Correção 4: Remoção de Credenciais e Segredos na Construção
# - O que mudou: Exclusão total de variáveis como `ENV ADMIN_PASSWORD` das camadas da imagem.
# - Por quê: Elimina o vazamento de segredos via histórico do container (`docker history`), exigindo que chaves e senhas sejam fornecidas dinamicamente no runtime.

# Correção 5: Servidor de Aplicação de Produção (Substituição do Dev Server do Flask)
# - O que mudou: Troca do comando de execução direta em Python por um servidor WSGI pronto para produção (`gunicorn`).
# - Por quê: Garante melhor performance, resiliência no tratamento de requisições simultâneas e atende às boas práticas de implantação em produção.

# Correção 6: Desativação do Modo Debug e Permissões de Leitura
# - O que mudou: Remoção do parâmetro `debug=True` e isolamento de escrita apenas para o diretório de dados (`/app/data`).
# - Por quê: Desativa a execução remota de código via Werkzeug debugger e protege os arquivos do código-fonte contra modificações ou sobrescritas por parte do processo do container em execução.
