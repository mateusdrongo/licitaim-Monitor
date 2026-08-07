# LicitAIM — Guia de Produção

Plataforma SaaS de monitoramento inteligente de licitações públicas brasileiras.

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Variáveis de Ambiente](#3-variáveis-de-ambiente)
4. [Banco de Dados — Criação Completa](#4-banco-de-dados--criação-completa)
5. [API Backend (FastAPI)](#5-api-backend-fastapi)
6. [Frontend (React + Vite)](#6-frontend-react--vite)
7. [Collector — Scrapers de Licitações](#7-collector--scrapers-de-licitações)
8. [Cron — Agendamento dos Scrapers](#8-cron--agendamento-dos-scrapers)
9. [Scheduler Interno do FastAPI](#9-scheduler-interno-do-fastapi)
10. [Nginx — Proxy Reverso](#10-nginx--proxy-reverso)
11. [Checklist de Go-Live](#11-checklist-de-go-live)

---

## 1. Visão Geral da Arquitetura

```
                        ┌─────────────────────────────────────┐
                        │           NGINX (porta 80/443)       │
                        │   / → Frontend estático (dist/)      │
                        │   /api → FastAPI (uvicorn :8000)     │
                        └──────────────┬──────────────────────┘
                                       │
               ┌───────────────────────┼────────────────────────┐
               │                       │                        │
       ┌───────▼───────┐     ┌─────────▼────────┐    ┌─────────▼──────────┐
       │ React (Vite)  │     │  FastAPI + asyncpg│    │  Collector (Celery)│
       │ dist/public/  │     │  APScheduler      │    │  PNCP / Comprasnet │
       │ (estático)    │     │  Search Queue     │    │  BEC-SP / BBMnet   │
       └───────────────┘     └─────────┬─────────┘    └─────────┬──────────┘
                                       │                         │
                               ┌───────▼─────────────────────────▼──────┐
                               │            PostgreSQL 14+               │
                               │  licitaim_database.sql (schema)        │
                               │  licitacoes_cache (cache PNCP)         │
                               └──────────────────────────────────────────┘
```

**Componentes:**

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| `artifacts/api-server` | Python 3.11 · FastAPI · asyncpg | API REST + JWT + APScheduler |
| `artifacts/licitaim` | React 18 · Vite · Tailwind · Recharts | SPA servida como estático |
| `collector/` | Python · Celery · Playwright · httpx | Scrapers multi-fonte de licitações |
| PostgreSQL | v14+ | Banco único compartilhado |

---

## 2. Pré-requisitos

### Servidor

- Ubuntu 22.04 LTS (ou equivalente)
- Mínimo: 2 vCPU · 4 GB RAM · 40 GB SSD
- Recomendado: 4 vCPU · 8 GB RAM · 100 GB SSD

### Softwares

```bash
# Python 3.11
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# pnpm
npm install -g pnpm

# PostgreSQL 14+
sudo apt install -y postgresql postgresql-contrib

# Nginx
sudo apt install -y nginx

# Redis (usado pelo Celery do collector)
sudo apt install -y redis-server

# Chromium (necessário para scrapers Playwright: Comprasnet, BEC-SP, BBMnet)
sudo apt install -y chromium-browser
```

---

## 3. Variáveis de Ambiente

### 3.1 API Backend — `artifacts/api-server/.env`

Crie o arquivo `.env` dentro de `artifacts/api-server/`:

```env
# ── Banco de dados (OBRIGATÓRIO) ──────────────────────────────────────────────
DATABASE_URL=postgresql://licitaim:SENHA_FORTE@localhost:5432/licitaim

# ── Segredo JWT (OBRIGATÓRIO — troque em produção) ───────────────────────────
SESSION_SECRET=gere-uma-string-aleatoria-de-64-chars-aqui
# ou use JWT_SECRET (SESSION_SECRET tem prioridade)

# ── Servidor ──────────────────────────────────────────────────────────────────
ENVIRONMENT=production
PORT=8000

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30

# ── E-mail (opcional — necessário para envio de alertas por e-mail) ───────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@email.com
SMTP_PASSWORD=senha-de-app-gmail
SMTP_FROM=noreply@seudominio.com.br
SMTP_FROM_NAME=LicitAIM

# ── Telegram Bot (opcional — alertas via Telegram) ────────────────────────────
TELEGRAM_BOT_TOKEN=

# ── WhatsApp (opcional — alertas via WhatsApp) ───────────────────────────────
WHATSAPP_API_URL=
WHATSAPP_TOKEN=

# ── Administradores (e-mails separados por vírgula) ──────────────────────────
ADMIN_EMAILS=admin@seudominio.com.br

# ── Elasticsearch (opcional — desativado por padrão) ─────────────────────────
ELASTICSEARCH_URL=http://localhost:9200

# ── Redis / Celery (opcional — usado pelo collector) ─────────────────────────
REDIS_URL=redis://localhost:6379/0
```

> **Gere `SESSION_SECRET`:**
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

### 3.2 Frontend — `artifacts/licitaim/.env.production`

```env
# Caminho base onde o frontend será servido (ex: "/" para domínio raiz)
BASE_PATH=/

# Porta do servidor de preview (não usada em produção estática)
PORT=3000
```

### 3.3 Collector — `collector/.env`

```env
# ── Banco de dados (mesmo do backend) ────────────────────────────────────────
DATABASE_URL=postgresql://licitaim:SENHA_FORTE@localhost:5432/licitaim

# ── Celery Broker (Redis) ─────────────────────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ── RabbitMQ (alternativa ao Redis) ──────────────────────────────────────────
# RABBITMQ_URL=amqp://guest:guest@localhost:5672//

# ── Playwright ────────────────────────────────────────────────────────────────
HEADLESS=true
PLAYWRIGHT_TIMEOUT_MS=30000

# ── PNCP ─────────────────────────────────────────────────────────────────────
PNCP_PAGE_SIZE=50
PNCP_MAX_PAGES=200
PNCP_RATE_LIMIT_SLEEP=0.5

# ── Retry ─────────────────────────────────────────────────────────────────────
RETRY_ATTEMPTS=5
RETRY_MIN_WAIT=1.0
RETRY_MAX_WAIT=60.0

# ── Log ──────────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## 4. Banco de Dados — Criação Completa

### 4.1 Criar usuário e banco

```bash
sudo -u postgres psql <<'SQL'
-- Usuário da aplicação
CREATE USER licitaim WITH PASSWORD 'SENHA_FORTE';

-- Banco principal
CREATE DATABASE licitaim
    OWNER licitaim
    ENCODING 'UTF8'
    LC_COLLATE 'pt_BR.UTF-8'
    LC_CTYPE 'pt_BR.UTF-8'
    TEMPLATE template0;

-- Permissões
GRANT ALL PRIVILEGES ON DATABASE licitaim TO licitaim;
SQL
```

> Se `pt_BR.UTF-8` não estiver disponível, use `en_US.UTF-8` ou gere o locale:
> ```bash
> sudo locale-gen pt_BR.UTF-8
> sudo update-locale
> ```

### 4.2 Instalar extensões necessárias

```bash
sudo -u postgres psql -d licitaim <<'SQL'
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- índices GIN para ILIKE rápido
SQL
```

### 4.3 Aplicar o schema completo

O arquivo `licitaim_database.sql` na raiz do projeto contém o schema completo com tabelas, índices, funções, triggers e views. **Execute-o uma única vez:**

```bash
psql -U licitaim -d licitaim -h localhost -f licitaim_database.sql
```

Este script cria:

#### Tabelas principais

| Tabela | Descrição |
|---|---|
| `users` | Usuários — id TEXT (UUID), email, senha_hash, plano, empresa |
| `monitoramentos` | Regras de alerta automático por palavras-chave, UF, valor |
| `alertas` | Inbox de notificações geradas pelos monitores |
| `favoritos` | Licitações marcadas pelo usuário (com snapshot de dados) |
| `oportunidades` | Pipeline comercial (identificada → ganhou/perdeu) |
| `documentos` | Repositório de editais, propostas, contratos |
| `equipe_membros` | Membros da equipe com papéis (admin/editor/visualizador) |
| `certidoes` | Certidões com vencimento e alertas de expiração |
| `notifications` | Notificações push para WebSocket |
| `agenda_eventos` | Eventos customizados criados pelo usuário na Agenda |
| `precos_historico` | Histórico de preços por item/descrição para análise |

#### Tabelas do cache de licitações (criadas automaticamente pelo FastAPI no startup)

| Tabela | Descrição |
|---|---|
| `licitacoes_cache` | Cache das licitações coletadas do PNCP/dadosabertos |
| `licitacoes_cache_coverage` | Controle de cobertura e data do último sync |

#### Índices criados pelo `licitaim_database.sql`

- `idx_users_email`, `idx_users_cnpj`, `idx_users_plano`
- `idx_monitoramentos_user_id`, `idx_monitoramentos_ativo`
- `idx_alertas_user_id`, `idx_alertas_user_lido`, `idx_alertas_licitacao_id`, `idx_alertas_criado_em`
- `idx_favoritos_user_id` + GIN `idx_favoritos_objeto_trgm`
- `idx_oportunidades_user_id`, `idx_oportunidades_estagio`, `idx_oportunidades_prazo`
- `idx_documentos_user_id`, `idx_documentos_categoria` + GIN `idx_documentos_nome_trgm`
- `idx_equipe_owner_id`, `idx_equipe_member_id`, `idx_equipe_status`
- `idx_certidoes_user_id`, `idx_certidoes_vencimento`, `idx_certidoes_vencimento_usuario`

#### Índices do cache (criados automaticamente no startup do FastAPI)

```sql
CREATE INDEX IF NOT EXISTS idx_lic_uf         ON licitacoes_cache(uf);
CREATE INDEX IF NOT EXISTS idx_lic_modalidade  ON licitacoes_cache(modalidade_codigo);
CREATE INDEX IF NOT EXISTS idx_lic_situacao    ON licitacoes_cache(situacao);
CREATE INDEX IF NOT EXISTS idx_lic_publicacao  ON licitacoes_cache(data_publicacao DESC);
CREATE INDEX IF NOT EXISTS idx_lic_atualizado  ON licitacoes_cache(atualizado_em DESC);
-- Índice GIN full-text (português)
CREATE INDEX IF NOT EXISTS idx_lic_objeto_gin  ON licitacoes_cache
    USING gin(to_tsvector('portuguese',
        coalesce(objeto,'') || ' ' || coalesce(orgao_nome,'')));
```

#### Funções e Triggers (criados pelo `licitaim_database.sql`)

| Função / Trigger | Ação |
|---|---|
| `fn_set_atualizado_em()` | Atualiza `atualizado_em` automaticamente em qualquer UPDATE |
| `fn_incrementar_total_alertas()` | Incrementa `monitoramentos.total_alertas` ao inserir alerta |
| `fn_decrementar_total_alertas()` | Decrementa `monitoramentos.total_alertas` ao excluir alerta |
| `fn_status_certidao(date)` | Retorna `ativa` / `a_vencer` / `vencida` / `sem_prazo` |
| `fn_dias_para_vencer(date)` | Dias até o vencimento (negativo = já venceu) |

#### Views

| View | Uso |
|---|---|
| `v_certidoes_status` | Certidões com status calculado e dias restantes |
| `v_certidoes_expirando` | Certidões que vencem nos próximos 30 dias |
| `v_alertas_resumo` | Contagem de alertas não lidos por usuário (badges) |
| `v_oportunidades_pipeline` | Pipeline com valor numérico e urgência |
| `v_agenda` | Agenda unificada (oportunidades + certidões + alertas) |
| `v_dashboard_kpis` | KPIs agregados por usuário para o Dashboard |
| `v_monitoramentos_stats` | Monitoramentos com contagem real de alertas |

### 4.4 Schema do collector (tabelas separadas — opcional)

Se for usar o microsserviço `collector/` com persistência própria:

```bash
psql -U licitaim -d licitaim -h localhost -f collector/schema.sql
```

Cria as tabelas `tenders`, `tender_items` e `tender_history` (com UUID, JSONB e histórico de mudanças de campos).

### 4.5 Verificar schema

```bash
psql -U licitaim -d licitaim -h localhost -c "\dt"
psql -U licitaim -d licitaim -h localhost -c "\di"
```

---

## 5. API Backend (FastAPI)

### 5.1 Instalar dependências Python

```bash
cd artifacts/api-server

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

**`requirements.txt` completo:**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
asyncpg>=0.29.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
pydantic-settings>=2.4.0
httpx>=0.27.0
python-multipart>=0.0.12
pydantic[email]>=2.8.0
elasticsearch[async]>=8.0.0
apscheduler>=3.10.0
aiosmtplib>=3.0.0
celery[redis]>=5.4.0
```

### 5.2 Testar localmente

```bash
cd artifacts/api-server
source .venv/bin/activate

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: `http://localhost:8000/api/healthz` → deve retornar `{"status": "ok"}`

> **O FastAPI executa as migrações DDL automaticamente no startup.** As tabelas `licitacoes_cache` e `licitacoes_cache_coverage` são criadas/atualizadas de forma idempotente sem necessidade de comando manual.

### 5.3 Configurar serviço systemd

```bash
sudo nano /etc/systemd/system/licitaim-api.service
```

```ini
[Unit]
Description=LicitAIM API — FastAPI + uvicorn
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/licitaim/artifacts/api-server
EnvironmentFile=/var/www/licitaim/artifacts/api-server/.env
ExecStart=/var/www/licitaim/artifacts/api-server/.venv/bin/uvicorn \
    app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --log-level info \
    --access-log
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=licitaim-api

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable licitaim-api
sudo systemctl start licitaim-api
sudo systemctl status licitaim-api

# Ver logs em tempo real
sudo journalctl -u licitaim-api -f
```

> **Atenção:** Use `--workers 1` se precisar do APScheduler (o scheduler não é compartilhado entre workers). Para múltiplos workers, mova o agendamento para uma instância dedicada ou use Celery Beat.

---

## 6. Frontend (React + Vite)

### 6.1 Instalar dependências Node

```bash
# Na raiz do monorepo
npm install -g pnpm
pnpm install
```

### 6.2 Build de produção

```bash
# Variáveis necessárias para o build
export BASE_PATH=/
export PORT=3000
export NODE_ENV=production

# Build do frontend (gera artifacts/licitaim/dist/public/)
pnpm --filter @workspace/licitaim run build
```

O build gera os arquivos estáticos em:
```
artifacts/licitaim/dist/public/
├── index.html
├── assets/
│   ├── index-[hash].js
│   ├── index-[hash].css
│   └── ...
└── ...
```

### 6.3 Copiar para o diretório de serviço

```bash
sudo mkdir -p /var/www/licitaim/public
sudo cp -r artifacts/licitaim/dist/public/* /var/www/licitaim/public/
sudo chown -R www-data:www-data /var/www/licitaim/public
```

### 6.4 Script de deploy do frontend

Crie `/usr/local/bin/deploy-licitaim-frontend.sh`:

```bash
#!/bin/bash
set -e

PROJECT_DIR="/var/www/licitaim"
SERVE_DIR="/var/www/licitaim/public"

cd "$PROJECT_DIR"

echo "=== Build do frontend ==="
export BASE_PATH=/
export PORT=3000
export NODE_ENV=production

pnpm --filter @workspace/licitaim run build

echo "=== Deploy dos arquivos estáticos ==="
rm -rf "$SERVE_DIR"/*
cp -r artifacts/licitaim/dist/public/* "$SERVE_DIR/"
chown -R www-data:www-data "$SERVE_DIR"

echo "=== Deploy concluído! ==="
```

```bash
sudo chmod +x /usr/local/bin/deploy-licitaim-frontend.sh
```

---

## 7. Collector — Scrapers de Licitações

O `collector/` é um microsserviço Python independente que coleta licitações de múltiplas fontes usando Celery + Playwright.

### 7.1 Fontes de dados

| Scraper | Arquivo | URL | Método |
|---|---|---|---|
| PNCP (fonte principal) | `scrapers/pncp.py` | `pncp.gov.br/api/consulta/v1` | httpx + API REST |
| Comprasnet | `scrapers/comprasnet.py` | `comprasnet.gov.br` | Playwright (headless) |
| BEC-SP | `scrapers/bec_sp.py` | `bec.sp.gov.br` | Playwright (headless) |
| BBMnet | `scrapers/bbmnet.py` | `bbmnet.com.br` | httpx |

### 7.2 Códigos de modalidade PNCP (tabela oficial)

| Código | Modalidade |
|---|---|
| 1 | Leilão - Eletrônico |
| 2 | Diálogo Competitivo |
| 3 | Concurso |
| 4 | Concorrência - Eletrônica |
| 5 | Concorrência - Presencial |
| 6 | Pregão - Eletrônico |
| 7 | Pregão - Presencial |
| 8 | Dispensa |
| 9 | Inexigibilidade |
| 10 | Manifestação de Interesse |
| 11 | Pré-qualificação |
| 12 | Credenciamento |
| 13 | Leilão - Presencial |
| 14 | Inaplicabilidade da Licitação |
| 15 | Chamada Pública |
| 16 | Concorrência – Eletrônica Internacional |
| 17 | Concorrência – Presencial Internacional |
| 18 | Pregão – Eletrônico Internacional |
| 19 | Pregão – Presencial Internacional |

### 7.3 Instalar dependências do collector

```bash
cd collector

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Instalar browsers do Playwright (necessário para Comprasnet, BEC-SP, BBMnet)
playwright install chromium
playwright install-deps chromium
```

### 7.4 Iniciar worker Celery

```bash
cd collector
source .venv/bin/activate

# Worker com 4 processos paralelos
celery -A app.tasks worker \
    --loglevel=info \
    --concurrency=4 \
    -Q celery
```

### 7.5 Configurar Celery worker como serviço systemd

```bash
sudo nano /etc/systemd/system/licitaim-collector.service
```

```ini
[Unit]
Description=LicitAIM Collector — Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/licitaim/collector
EnvironmentFile=/var/www/licitaim/collector/.env
ExecStart=/var/www/licitaim/collector/.venv/bin/celery \
    -A app.tasks worker \
    --loglevel=info \
    --concurrency=4 \
    -Q celery
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=licitaim-collector

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable licitaim-collector
sudo systemctl start licitaim-collector
sudo systemctl status licitaim-collector
```

---

## 8. Cron — Agendamento dos Scrapers

Os scrapers do `collector/` são acionados por **cron do sistema** (ou Celery Beat). Configure o crontab do usuário `www-data`:

```bash
sudo crontab -u www-data -e
```

### 8.1 Coleta de licitações (fontes externas)

```cron
# ─── LicitAIM Collector — Agendamento de Scrapers ─────────────────────────────
# Formato: minuto hora dia mês dia_semana comando

# PNCP — coleta principal (4× ao dia, deslocado 5min para não conflitar com
# o scheduler interno do FastAPI que roda exatamente nas 00h/06h/12h/18h)
5   0  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_pncp   >> /var/log/licitaim/collector-pncp.log 2>&1
5   6  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_pncp   >> /var/log/licitaim/collector-pncp.log 2>&1
5  12  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_pncp   >> /var/log/licitaim/collector-pncp.log 2>&1
5  18  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_pncp   >> /var/log/licitaim/collector-pncp.log 2>&1

# Comprasnet — 1× ao dia às 02h30 BRT
30  2  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_comprasnet >> /var/log/licitaim/collector-comprasnet.log 2>&1

# BEC-SP — 1× ao dia às 03h00 BRT
0   3  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_bec_sp    >> /var/log/licitaim/collector-bec.log 2>&1

# BBMnet — 1× ao dia às 03h30 BRT
30  3  * * *  /var/www/licitaim/collector/.venv/bin/celery -A app.tasks call app.tasks.scrape_bbmnet    >> /var/log/licitaim/collector-bbmnet.log 2>&1
```

> **Fuso horário:** Certifique-se que o servidor está em `America/Sao_Paulo`:
> ```bash
> sudo timedatectl set-timezone America/Sao_Paulo
> timedatectl status  # confirmar "Time zone: America/Sao_Paulo (BRT, -0300)"
> ```

### 8.2 Alternativa — Celery Beat (agendamento programático)

Em vez de crontab, use o Celery Beat que já está configurado em `collector/app/tasks.py`:

```bash
# Serviço separado do worker
celery -A app.tasks beat \
    --loglevel=info \
    --scheduler celery.beat:PersistentScheduler
```

```bash
sudo nano /etc/systemd/system/licitaim-beat.service
```

```ini
[Unit]
Description=LicitAIM Celery Beat — Agendador de Tarefas
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/licitaim/collector
EnvironmentFile=/var/www/licitaim/collector/.env
ExecStart=/var/www/licitaim/collector/.venv/bin/celery \
    -A app.tasks beat \
    --loglevel=info \
    --scheduler celery.beat:PersistentScheduler
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=licitaim-beat

[Install]
WantedBy=multi-user.target
```

### 8.3 Executar scraper manualmente (CLI)

```bash
cd collector
source .venv/bin/activate

# PNCP — data específica
python -m app.main scrape pncp --start 2026-01-01 --end 2026-01-31

# PNCP — últimos 30 dias
python -m app.main scrape pncp --days 30

# Comprasnet
python -m app.main scrape comprasnet --days 7

# BEC-SP
python -m app.main scrape bec_sp --days 7

# Todas as fontes
python -m app.main scrape all --days 30
```

### 8.4 Rotação de logs do collector

```bash
sudo mkdir -p /var/log/licitaim

sudo nano /etc/logrotate.d/licitaim-collector
```

```
/var/log/licitaim/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
}
```

---

## 9. Scheduler Interno do FastAPI

O `api-server` possui um **APScheduler embutido** que roda dentro do processo uvicorn. **Não requer Redis ou Celery.** É iniciado automaticamente no startup da API.

### Jobs configurados (`app/services/cache_scheduler.py`)

| Job | Trigger | Descrição |
|---|---|---|
| `sync_licitacoes_job` | Cron — 00h, 06h, 12h, 18h BRT | Coleta PNCP + dadosabertos com rotação de headers; faz upsert em `licitacoes_cache` |
| `check_all_monitors` | Intervalo — a cada 15 min | Verifica todos os monitoramentos ativos e gera alertas |
| `check_upcoming_tenders` | Intervalo — a cada 1 hora | Detecta licitações com abertura nas próximas 24h e alerta usuários |
| `check_document_expirations` | Cron — 07h BRT diário | Verifica certidões próximas do vencimento (≤ 30 dias) |

### Worker de fila de buscas (`app/services/search_queue.py`)

Além do scheduler, há um worker `asyncio.Task` permanente que:

1. Recebe buscas enfileiradas quando um usuário pesquisa e o banco não tem dados suficientes
2. Executa coleta Python completa (até 40 páginas por modalidade) com rotação de headers e delays aleatórios entre requisições
3. Faz upsert no banco e libera a próxima busca da fila

**Este worker é iniciado automaticamente junto com a API — nenhuma configuração adicional é necessária.**

### Estratégia de coleta

1. **Cron 4×/dia** → sync geral dos últimos 30 dias (modalidades 4, 5, 6, 7, 8, 9)
2. **Busca do usuário** → se o banco não cobre o intervalo solicitado:
   - Resultado imediato: busca ao vivo na API (1 página, rápida)
   - Background: enfileira coleta completa (todas as páginas) com o worker Python
   - Frontend exibe banner "coletando dados..." com countdown de 30s para atualizar

### Fonte de dados

| Prioridade | Fonte | URL |
|---|---|---|
| 1ª | PNCP consulta pública | `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` |
| 2ª (fallback) | Dados Abertos Compras.gov | `dadosabertos.compras.gov.br/modulo-contratacoes/...` |
| 3ª (fallback dev) | Mock estático | Dados hardcoded no código |

> **Nota:** `pncp.gov.br/api` pode ser bloqueado em alguns provedores de cloud (WAF). O fallback `dadosabertos.compras.gov.br` é sempre acessível. A rotação de User-Agents mitiga bloqueios no PNCP.

---

## 10. Nginx — Proxy Reverso

### 10.1 Configuração para HTTP (sem SSL)

```bash
sudo nano /etc/nginx/sites-available/licitaim
```

```nginx
server {
    listen 80;
    server_name seudominio.com.br www.seudominio.com.br;

    # Frontend — arquivos estáticos
    root /var/www/licitaim/public;
    index index.html;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               application/wasm;

    # Cache para assets com hash no nome (imutáveis)
    location ~* /assets/.*\.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # API — proxy para FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket (para /api/ws/)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 10s;
        proxy_read_timeout 120s;
        proxy_send_timeout 30s;

        # Tamanho máximo de upload (documentos)
        client_max_body_size 50M;
    }

    # SPA — todas as rotas não encontradas servem o index.html (React Router)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/licitaim /etc/nginx/sites-enabled/
sudo nginx -t          # testar configuração
sudo systemctl reload nginx
```

### 10.2 HTTPS com Certbot (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br \
    --non-interactive --agree-tos --email admin@seudominio.com.br

sudo systemctl reload nginx
```

---

## 11. Checklist de Go-Live

Execute cada item em ordem antes de liberar para usuários.

### Banco de dados

- [ ] PostgreSQL instalado e rodando (`sudo systemctl status postgresql`)
- [ ] Usuário `licitaim` e banco criados
- [ ] Extensões `pgcrypto` e `pg_trgm` instaladas
- [ ] `licitaim_database.sql` aplicado sem erros
- [ ] `collector/schema.sql` aplicado (se usar o collector)
- [ ] Conexão testada: `psql -U licitaim -d licitaim -h localhost -c "SELECT NOW()"`

### API Backend

- [ ] `.env` configurado com `DATABASE_URL` e `SESSION_SECRET` de produção
- [ ] `SESSION_SECRET` gerado aleatoriamente (não usar o valor padrão do dev)
- [ ] Dependências instaladas: `pip install -r requirements.txt`
- [ ] API iniciada e respondendo: `curl http://localhost:8000/api/healthz`
- [ ] Logs mostram "migrations: DDL de bootstrap concluído"
- [ ] Logs mostram "search_queue: worker iniciado"
- [ ] Logs mostram "scheduler iniciado (sync 4×/dia | monitores a cada 15min | ...)"
- [ ] Serviço systemd `licitaim-api` habilitado e rodando
- [ ] `ENVIRONMENT=production` configurado no `.env`

### Frontend

- [ ] `pnpm install` executado na raiz do monorepo
- [ ] Build de produção gerado: `pnpm --filter @workspace/licitaim run build`
- [ ] Arquivos copiados para `/var/www/licitaim/public/`
- [ ] `index.html` acessível via Nginx

### Collector

- [ ] `.env` configurado com `DATABASE_URL`, `CELERY_BROKER_URL`
- [ ] Redis rodando (`sudo systemctl status redis`)
- [ ] Dependências instaladas: `pip install -r requirements.txt`
- [ ] Playwright browsers instalados: `playwright install chromium && playwright install-deps chromium`
- [ ] Serviço `licitaim-collector` habilitado e rodando
- [ ] Crontab configurado (ou `licitaim-beat` rodando)
- [ ] Fuso horário do servidor: `America/Sao_Paulo`

### Infraestrutura

- [ ] Nginx configurado, testado (`nginx -t`) e recarregado
- [ ] HTTPS configurado com Let's Encrypt (ou certificado próprio)
- [ ] Portas abertas no firewall: 80, 443 (externas); 8000 apenas loopback
- [ ] Logs do Nginx configurados: `/var/log/nginx/licitaim-access.log`
- [ ] Logrotate configurado para `/var/log/licitaim/`

### Primeiro sync após go-live

```bash
# Forçar sync imediato do cache de licitações (como admin)
curl -X POST https://seudominio.com.br/api/licitacoes/admin/sync \
    -H "Cookie: access_token=SEU_JWT_ADMIN"

# Ou aguardar o cron das 00h/06h/12h/18h BRT
# O banco estará populado na primeira execução do scheduler
```

---

## Referência rápida de comandos

```bash
# Iniciar todos os serviços
sudo systemctl start postgresql redis licitaim-api licitaim-collector nginx

# Ver logs da API em tempo real
sudo journalctl -u licitaim-api -f

# Ver logs do collector
sudo journalctl -u licitaim-collector -f

# Rebuild e redeploy do frontend
sudo /usr/local/bin/deploy-licitaim-frontend.sh

# Verificar status do cache de licitações
psql -U licitaim -d licitaim -h localhost \
    -c "SELECT scope_key, last_sync, total_found, is_complete FROM licitacoes_cache_coverage;"

# Contar licitações no cache
psql -U licitaim -d licitaim -h localhost \
    -c "SELECT COUNT(*), fonte, MAX(atualizado_em) FROM licitacoes_cache GROUP BY fonte;"

# Reiniciar API após alteração de código
sudo systemctl restart licitaim-api
```
