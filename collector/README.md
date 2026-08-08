# LicitAIM Collector

Microsserviço de scraping para portais de licitação pública brasileira.

## Portais suportados

| Portal | Método | Status |
|--------|--------|--------|
| PNCP | API oficial (httpx + tenacity) | ✅ Produção |
| ComprasNet | httpx + BeautifulSoup | ✅ Implementado |
| BEC-SP | httpx + BeautifulSoup | ✅ Implementado |
| BBMNet | Playwright | ✅ Implementado |

## Estrutura

```
collector/
├── app/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Settings (pydantic-settings)
│   ├── base_scraper.py      # Classe abstrata
│   ├── scrapers/
│   │   ├── pncp.py          # API PNCP + tenacity retry
│   │   ├── comprasnet.py    # httpx + BS4
│   │   ├── bec_sp.py        # httpx + BS4
│   │   └── bbmnet.py        # Playwright
│   ├── processors/
│   │   └── tender_processor.py  # Normalize → Upsert → History → ES
│   ├── tasks.py             # Celery tasks + Beat schedule
│   └── queue.py             # RabbitMQ publisher/consumer
├── schema.sql               # DDL das tabelas tenders/*
├── requirements.txt
└── Dockerfile
```

## Setup rápido

```bash
# 1. Instalar dependências
pip install -r requirements.txt
playwright install chromium  # necessário apenas para BBMNet

# 2. Criar tabelas no banco
python -m collector.app.main sync-schema

# 3. Scraping manual (PNCP, 1 dia)
python -m collector.app.main scrape --source pncp --days 1

# 4. Scraping de data específica
python -m collector.app.main scrape --source pncp --date 2025-06-01

# 5. Worker Celery
celery -A collector.app.tasks worker --loglevel=info

# 6. Beat (agendador diário)
celery -A collector.app.tasks beat --loglevel=info

# 7. Consumer RabbitMQ para sync ES
python -m collector.app.main consume-queue
```

## Docker

```bash
# Build
docker build -t licitaim-collector .

# Worker
docker run -e DATABASE_URL=postgresql://... \
           -e RABBITMQ_URL=amqp://... \
           licitaim-collector

# Beat
docker run -e DATABASE_URL=postgresql://... \
           --entrypoint celery licitaim-collector \
           -A collector.app.tasks beat --loglevel=info

# CLI manual
docker run -e DATABASE_URL=postgresql://... \
           --entrypoint python licitaim-collector \
           -m collector.app.main scrape --source pncp --days 1
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | ES endpoint |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672//` | RabbitMQ |
| `CELERY_BROKER_URL` | igual ao `RABBITMQ_URL` | Broker Celery |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Result backend |
| `LOG_LEVEL` | `INFO` | Nível de log |
| `HEADLESS` | `true` | Playwright headless (usado pelo BBMNet) |

## Fluxo de dados

```
Portal → Scraper → TenderProcessor → PostgreSQL (tenders/items/history)
                                  ↓
                            RabbitMQ (tender.sync)
                                  ↓
                         ES Consumer → Elasticsearch
```

## Celery Beat Schedule (horário BRT)

| Task | Horário | Portal |
|------|---------|--------|
| schedule_daily_scrape | 01:00 | Todos (despacha sub-tasks) |
| scrape_pncp_task | 02:00 | PNCP |
| scrape_source_task[comprasnet] | 02:30 | ComprasNet |
| scrape_source_task[bec_sp] | 03:00 | BEC-SP |
| scrape_source_task[bbmnet] | 03:30 | BBMNet |
