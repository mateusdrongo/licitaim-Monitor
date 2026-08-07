"""
Rotas administrativas — requer usuário com plano 'enterprise' ou email @licitaim.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from ..core.deps import get_current_user
from ..services.elasticsearch_service import get_es_service
from ..services.sync_service import get_sync_service

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Dependency: superuser ─────────────────────────────────────────────────────

async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Considera admin quem tem plano 'enterprise' OU e-mail @licitaim.com.br.
    Adapte conforme a regra de negócio real (campo is_superuser, role, etc.).
    """
    plano = current_user.get("plano", "")
    email = current_user.get("email", "")
    is_admin = plano == "enterprise" or email.endswith("@licitaim.com.br")
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return current_user


# ── Elasticsearch status ──────────────────────────────────────────────────────

@router.get("/elasticsearch/status")
async def es_status(_: dict = Depends(get_admin_user)):
    """Verifica conectividade com o Elasticsearch."""
    es = get_es_service()
    alive = await es.ping()
    return {"elasticsearch": "online" if alive else "offline"}


# ── Sync — single tender ──────────────────────────────────────────────────────

@router.post("/sync/elasticsearch/{tender_id}")
async def sync_single(
    tender_id: str,
    _: dict = Depends(get_admin_user),
):
    """Indexa/atualiza uma licitação específica no Elasticsearch."""
    svc = get_sync_service()
    ok = await svc.sync_tender(tender_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' não encontrado ou falha ao indexar.",
        )
    return {"status": "ok", "tender_id": tender_id, "indexed": True}


# ── Sync — full reindex ───────────────────────────────────────────────────────

@router.post("/sync/elasticsearch")
async def sync_all_elasticsearch(
    background_tasks: BackgroundTasks,
    _: dict = Depends(get_admin_user),
):
    """
    Dispara sincronização completa de todas as licitações no Elasticsearch.
    A operação é executada em background; retorna imediatamente com status 202.
    """
    async def _run():
        svc = get_sync_service()
        stats = await svc.sync_all()
        import logging
        logging.getLogger(__name__).info("Sync completo: %s", stats)

    background_tasks.add_task(_run)
    return {
        "status": "accepted",
        "message": "Sincronização iniciada em background. Consulte os logs para acompanhar.",
    }


# ── Ensure index (idempotente) ────────────────────────────────────────────────

@router.post("/elasticsearch/ensure-index")
async def ensure_index(_: dict = Depends(get_admin_user)):
    """Cria o índice 'tenders' no ES (idempotente — não recria se já existir)."""
    es = get_es_service()
    created = await es.ensure_index()
    return {
        "status": "ok",
        "index": "tenders",
        "created": created,
        "message": "Índice criado." if created else "Índice já existia.",
    }
