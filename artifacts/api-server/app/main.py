import asyncio
import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .db.session import get_pool, close_pool
from .db.migrations import run_migrations
from .core.camel import _convert
from .core.security import decode_token
from .api import auth, dashboard, licitacoes, favoritos, monitoramentos
from .api import alertas, documentos, equipe, oportunidades
from .api import certidoes, agenda, analytics, precos, ai, admin, gerenciamento
from .services.elasticsearch_service import get_es_service
from .services.websocket_manager import get_ws_manager
from .services.cache_scheduler import start_scheduler, stop_scheduler, sync_licitacoes_job
from .services.task_alerts import check_task_deadlines
from .services.monitor_worker import check_document_expirations
from .services.search_queue import queue_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up DB pool
    pool = await get_pool()

    # DDL de bootstrap — idempotente; falha é registrada mas não impede startup
    # (cache fica desativado via set_cache_ready(False) e queries caem no fallback externo)
    await run_migrations(pool)

    # Elasticsearch — ensure index exists (não bloqueia se ES offline)
    es = get_es_service()
    try:
        await es.ensure_index()
    except Exception as exc:
        logger.warning("ES startup: %s", exc)

    # Cache scheduler — atualiza licitações 4× ao dia
    try:
        start_scheduler()
    except Exception as exc:
        logger.warning("Scheduler startup: %s", exc)

    # Worker de fila de buscas — processa coletas sob demanda (Python puro)
    worker_task = asyncio.create_task(queue_worker(), name="search_queue_worker")
    logger.info("lifespan: search_queue worker iniciado.")

    # Warm-up: se a tabela estiver vazia na primeira inicialização, dispara sync imediato
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM licitacoes_cache")
        if (count or 0) == 0:
            logger.info("lifespan: banco vazio — disparando sync inicial em background.")
            asyncio.create_task(sync_licitacoes_job())
    except Exception as exc:
        logger.warning("lifespan: warm-up check falhou (%s) — sync não disparado.", exc)

    # Misfire recovery: verifica se check_task_deadlines já rodou hoje (BRT).
    # Se o servidor estava fora às 08h, o APScheduler perde o disparo (misfire_grace_time=300s).
    # Basta uma execução por dia — a deduplicação interna de 24h evita alertas duplicados.
    try:
        ran_today = await pool.fetchval(
            """
            SELECT id FROM job_runs
            WHERE job_name = 'check_task_deadlines'
              AND ran_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'America/Sao_Paulo')
                            AT TIME ZONE 'America/Sao_Paulo'
            LIMIT 1
            """
        )
        if ran_today is None:
            logger.info(
                "lifespan: check_task_deadlines não rodou hoje — disparando em background."
            )
            asyncio.create_task(check_task_deadlines())
        else:
            logger.info("lifespan: check_task_deadlines já rodou hoje — nenhuma ação necessária.")
    except Exception as exc:
        logger.warning(
            "lifespan: misfire-recovery check falhou (%s) — check_task_deadlines não disparado.", exc
        )

    # Misfire recovery: verifica se check_document_expirations já rodou hoje (BRT).
    # Se o servidor estava fora às 07h, o APScheduler perde o disparo (misfire_grace_time=300s).
    # Basta uma execução por dia — a deduplicação interna de thresholds evita alertas duplicados.
    try:
        ran_today = await pool.fetchval(
            """
            SELECT id FROM job_runs
            WHERE job_name = 'check_document_expirations'
              AND ran_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'America/Sao_Paulo')
                            AT TIME ZONE 'America/Sao_Paulo'
            LIMIT 1
            """
        )
        if ran_today is None:
            logger.info(
                "lifespan: check_document_expirations não rodou hoje — disparando em background."
            )
            asyncio.create_task(check_document_expirations())
        else:
            logger.info("lifespan: check_document_expirations já rodou hoje — nenhuma ação necessária.")
    except Exception as exc:
        logger.warning(
            "lifespan: misfire-recovery check falhou (%s) — check_document_expirations não disparado.", exc
        )

    yield

    # Shutdown
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    stop_scheduler()
    await close_pool()
    try:
        await es.close()
    except Exception:
        pass


app = FastAPI(
    title="LicitAIM API",
    version="2.0.0",
    description="API FastAPI para plataforma SaaS de monitoramento de licitações brasileiras",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── camelCase middleware ───────────────────────────────────────────────────────
@app.middleware("http")
async def camelcase_middleware(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body)
            converted = _convert(data)
            new_body = json.dumps(converted, ensure_ascii=False).encode("utf-8")
        except Exception:
            new_body = body
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
    return response


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/healthz", tags=["health"])
async def healthz():
    return {"status": "ok", "service": "licitaim-api", "version": "2.0.0"}


@app.get("/api", tags=["health"])
async def root():
    return {"message": "LicitAIM FastAPI — OK"}


# ── Routers (todos sob /api) ──────────────────────────────────────────────────
PREFIX = "/api"

app.include_router(auth.router,           prefix=PREFIX)
app.include_router(dashboard.router,      prefix=PREFIX)
app.include_router(licitacoes.router,     prefix=PREFIX)
app.include_router(favoritos.router,      prefix=PREFIX)
app.include_router(monitoramentos.router, prefix=PREFIX)
app.include_router(alertas.router,        prefix=PREFIX)
app.include_router(documentos.router,     prefix=PREFIX)
app.include_router(equipe.router,         prefix=PREFIX)
app.include_router(oportunidades.router,  prefix=PREFIX)
app.include_router(certidoes.router,      prefix=PREFIX)
app.include_router(agenda.router,         prefix=PREFIX)
app.include_router(analytics.router,      prefix=PREFIX)
app.include_router(precos.router,         prefix=PREFIX)
app.include_router(ai.router,             prefix=PREFIX)
app.include_router(admin.router,          prefix=PREFIX)
app.include_router(gerenciamento.router,  prefix=PREFIX)

from .api import notifications as notifications_api  # noqa: E402
app.include_router(notifications_api.router, prefix=PREFIX)


# ── WebSocket /api/ws/{token} ─────────────────────────────────────────────────

@app.websocket("/api/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Conexão WebSocket autenticada por JWT no path.
    O cliente conecta em: ws://<host>/api/ws/<jwt_token>

    Mensagens do servidor:
      {"type": "notification", "id": ..., "title": ..., "body": ..., ...}
      {"type": "ping"}

    Mensagens do cliente aceitas:
      {"type": "pong"}
      {"type": "mark_read", "notification_id": <id>}
    """
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Token inválido")
        return

    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, nome, email FROM users WHERE id=$1", user_id
    )
    if not user:
        await websocket.close(code=4001, reason="Usuário não encontrado")
        return

    ws_manager = get_ws_manager()
    await ws_manager.connect(str(user_id), websocket)

    # Entrega notificações push não lidas acumuladas
    unread = await pool.fetch(
        """SELECT id, title, body, tipo, metadata, criado_em
           FROM notifications WHERE user_id=$1 AND lida=false
           ORDER BY criado_em DESC LIMIT 20""",
        user_id,
    )
    for n in unread:
        try:
            await websocket.send_text(json.dumps({
                "type":     "notification",
                "id":       n["id"],
                "title":    n["title"],
                "body":     n["body"],
                "tipo":     n["tipo"],
                "metadata": n["metadata"] or {},
                "criadoEm": n["criado_em"].isoformat(),
            }, default=str))
        except Exception:
            break

    # Loop de mensagens do cliente
    try:
        while True:
            try:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue

            if msg.get("type") == "mark_read":
                notif_id = msg.get("notification_id")
                if notif_id:
                    await pool.execute(
                        "UPDATE notifications SET lida=true WHERE id=$1 AND user_id=$2",
                        int(notif_id), user_id,
                    )
            # pong e outros tipos ignorados silenciosamente

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(str(user_id), websocket)
