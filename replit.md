# LicitAIM

Plataforma SaaS de monitoramento inteligente de licitações públicas brasileiras. Empresas podem pesquisar, filtrar, monitorar automaticamente, receber alertas, gerenciar documentos, criar equipes, acompanhar oportunidades e consultar histórico de preços.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — API server Python/FastAPI (uvicorn, porta dinâmica, via workflow)
- `pnpm --filter @workspace/licitaim run dev` — Frontend React/Vite (porta dinâmica, via workflow)
- Required env: `DATABASE_URL`, `SESSION_SECRET`

## Stack

- **Backend / API**: Python 3.12 + FastAPI + asyncpg (PostgreSQL assíncrono) + APScheduler
- **Frontend**: React + Vite + TypeScript + Tailwind CSS + shadcn/ui + Recharts + Framer Motion + TanStack Query
- **DB**: PostgreSQL (schema gerenciado via SQL direto — sem ORM no backend Python)
- **Auth**: JWT em cookie `httpOnly` (`access_token`)
- **Agendador**: APScheduler (AsyncIOScheduler) integrado no lifespan do FastAPI
- **Monorepo**: pnpm workspaces (apenas o frontend e o script de dev são Node.js — **nunca o backend**)

## Where things live

- `artifacts/api-server/app/` — aplicação FastAPI
  - `app/main.py` — entry point, routers, lifespan
  - `app/api/` — rotas (auth, dashboard, licitacoes, favoritos, monitoramentos, alertas, documentos, equipe, oportunidades, agenda, precos)
  - `app/services/` — lógica de negócio (monitor_worker, cache_scheduler, notification_service, pncp_client)
  - `app/db.py` — pool asyncpg, helper `get_db()`
  - `app/auth.py` — JWT + cookie
- `artifacts/licitaim/src/` — frontend React
  - `src/pages/` — páginas (Dashboard, Licitacoes, Agenda, Alertas, Monitoramentos, …)
  - `src/lib/api.ts` — BASE_URL + fetch helpers

## Architecture decisions

- **API 100% Python/FastAPI** — sem Node.js, sem Express, sem TypeScript no backend.
- Auth via JWT em cookie `httpOnly`; nenhuma sessão server-side.
- Licitações armazenadas em `licitacoes_cache` (cache local do dadosabertos.compras.gov.br). Busca via `ILIKE` no banco — Elasticsearch não é usado.
- Fonte de dados: `dadosabertos.compras.gov.br` (pncp.gov.br/api está bloqueado no servidor).
- Agendador APScheduler roda dentro do processo FastAPI; Celery existe em `app/tasks.py` mas **não é iniciado** — ignorar.
- `users.id` é `TEXT` (não integer); todos os FKs para usuários usam `TEXT`.
- `last_checked_at` é `timestamptz`; `ultima_execucao` é `timestamp without time zone` — usar parâmetros separados em queries que atualizam ambos.

## Product

- **Pesquisa de Licitações**: busca textual + filtros avançados (modalidade, UF, município, status, valor, data, esfera, poder)
- **Favoritos**: marcar licitações com notas pessoais
- **Monitoramentos**: regras automáticas de alerta por palavras-chave e filtros (verificação a cada 15 min via APScheduler)
- **Alertas**: inbox de notificações (nova licitação, prazo vencendo, situação alterada, disputa, preço referência)
- **Documentos**: repositório de editais, propostas, habilitações, contratos
- **Pipeline de Oportunidades**: kanban por estágio (identificada → qualificada → proposta → disputa → ganhou/perdeu)
- **Histórico de Preços**: busca por item com gráfico temporal e estatísticas
- **Agenda**: eventos de licitações + eventos customizados criados pelo usuário
- **Equipe**: convidar membros com papéis (admin/editor/visualizador)

## User preferences

- **Backend SEMPRE em Python com FastAPI** — nunca usar Node.js, Express ou qualquer framework JavaScript/TypeScript no servidor/API.

## Gotchas

- `dadosabertos.compras.gov.br` é a fonte real; pncp.gov.br/api está bloqueado no servidor Replit.
- APScheduler jobs: `check_all_monitors` (15 min), `check_upcoming_tenders` (1h), `check_document_expirations` (07h diário).
- Primeira execução do monitor usa janela de 30 dias para evitar zero matches (cache pode ter até 3 dias de defasagem).
- Frontend usa `fetch` com `credentials: "include"` e BASE de `import.meta.env.BASE_URL.replace(/\/$/, "")` — nunca hardcodar porta.
- Para adicionar tabelas novas: executar SQL diretamente via `executeSql` (sem ORM migration).
