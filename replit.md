# LicitAIM — Monitor de Licitações

Plataforma SaaS para monitoramento inteligente de licitações públicas brasileiras.

## Stack

- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS + Radix UI (`artifacts/licitaim/`)
- **Backend**: FastAPI (Python 3.11) + asyncpg + PostgreSQL (`artifacts/api-server/`)
- **Collector**: Microserviço de scraping Python (`collector/`) — opcional, requer Redis/Celery
- **Banco**: PostgreSQL (configurado via `DATABASE_URL`)

## Como rodar

Dois workflows configurados no Replit:

| Workflow | Comando | Porta |
|---|---|---|
| **Start application** | `PORT=5000 BASE_PATH=/ pnpm --filter @workspace/licitaim run dev` | 5000 (preview) |
| **Backend API** | `cd artifacts/api-server && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 |

O frontend faz chamadas à API em `/api/*` (configurar proxy se necessário).

## Variáveis de ambiente necessárias

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Conexão PostgreSQL (já configurada) |
| `SESSION_SECRET` | Segredo JWT (já configurado) |

### Opcionais
- `ELASTICSEARCH_URL` — busca semântica (padrão: `localhost:9200`)
- `REDIS_URL` / `CELERY_BROKER_URL` — fila do collector (padrão: `localhost:6379/0`)
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` — envio de e-mails
- `TELEGRAM_BOT_TOKEN` — notificações Telegram

## Banco de dados

O schema completo está em `licitaim_database.sql`. As migrações de bootstrap rodam automaticamente no startup do backend (`artifacts/api-server/app/db/migrations.py`).

## Instalar dependências

```bash
# Frontend (monorepo pnpm)
pnpm install

# Backend
cd artifacts/api-server && pip install -r requirements.txt
```

## User preferences

- Não reescrever do zero — sempre trabalhar com o código existente
