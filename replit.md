# LicitAIM — Monitor de Licitações

Plataforma SaaS para monitoramento inteligente de licitações públicas brasileiras.

## Stack

- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS + Radix UI (`artifacts/licitaim/`)
- **Backend**: FastAPI (Python 3.11) + asyncpg + PostgreSQL (`artifacts/api-server/`)
- **Collector**: Microserviço de scraping standalone Python (`collector/`)
- **Banco**: PostgreSQL (configurado via `DATABASE_URL`)

## Workflows ativos

| Workflow | Porta | Descrição |
|---|---|---|
| `artifacts/licitaim: web` | dinâmica (21607) | Frontend React/Vite — preview principal |
| `artifacts/api-server: API Server` | 8080 | Backend FastAPI |
| `Collector` | — | Scraping standalone do PNCP (iniciar manualmente) |

O frontend faz proxy `/api/*` → `http://localhost:${API_PORT:-8080}` via `vite.config.ts`.

## Variáveis de ambiente necessárias

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Conexão PostgreSQL (já configurada) |
| `SESSION_SECRET` | Segredo JWT (já configurado) |

### Opcionais
- `API_PORT` — porta do backend para o proxy Vite (padrão: `8080`)
- `ELASTICSEARCH_URL` — busca semântica (padrão: `localhost:9200`, opcional)
- `REDIS_URL` / `CELERY_BROKER_URL` — fila do collector (padrão: `localhost:6379/0`)
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` — envio de e-mails
- `TELEGRAM_BOT_TOKEN` — notificações Telegram

## Banco de dados

O schema completo está em `licitaim_database.sql`. As migrações de bootstrap rodam automaticamente no startup do backend (`artifacts/api-server/app/db/migrations.py`) — são idempotentes.

**Observação:** A API pública do PNCP está bloqueada no ambiente Replit. O timeout das chamadas externas foi reduzido para 6s; a busca usa o cache local ou dados mock como fallback.

## Instalar dependências

```bash
# Frontend + workspace (monorepo pnpm)
pnpm install

# Backend
pip install -r artifacts/api-server/requirements.txt

# Collector
pip install -r collector/requirements.txt
```

## Post-merge setup

Script configurado em `scripts/post-merge.sh` — roda automaticamente após merges de tasks.

## User preferences

- Não reescrever do zero — sempre trabalhar com o código existente
