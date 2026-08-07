"""
search_queue.py — Fila de coleta assíncrona de licitações.

Quando o usuário pesquisa e o banco não possui dados suficientes, a busca é
enfileirada aqui. O worker Python executa a coleta completa com rotação de
headers + delays aleatórios para evitar bloqueios, e faz upsert no banco
assim que possível — sem bloquear a resposta ao usuário.

Regras:
  • Fila de no máximo 100 itens (QueueFull descarta silenciosamente).
  • Deduplicação: mesma combinação de parâmetros não entra duas vezes.
  • Uma busca de cada vez (serial), com concurrency=3 no enriquecimento.
  • Delays aleatórios entre páginas e entre modalidades para simular browser.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, timedelta
from typing import NamedTuple

import httpx

logger = logging.getLogger(__name__)

# ── Importações tardias para evitar circular import ────────────────────────────
# (cache_scheduler e licitacoes se importam mutuamente via scheduler)
def _get_fetchers():
    from ..api.licitacoes import (  # noqa: PLC0415
        _fetch_pncp_all_pages_with_cap,
        _fetch_dados_all_pages_with_cap,
        _enrich_licitacoes,
        _fmt_pncp_date,
        _pncp_headers,
        MODALIDADES_PADRAO,
        MODALIDADES_DADOSABERTOS,
        DADOSABERTOS_URL,
    )
    return (
        _fetch_pncp_all_pages_with_cap,
        _fetch_dados_all_pages_with_cap,
        _enrich_licitacoes,
        _fmt_pncp_date,
        _pncp_headers,
        MODALIDADES_PADRAO,
        MODALIDADES_DADOSABERTOS,
        DADOSABERTOS_URL,
    )

def _get_repo():
    from ..db.licitacoes_repo import upsert_licitacoes  # noqa: PLC0415
    return upsert_licitacoes

def _get_pool():
    from ..db.session import get_pool  # noqa: PLC0415
    return get_pool


# ── Pool de User-Agents — rotação anti-WAF ────────────────────────────────────
_USER_AGENTS_EXTENDED = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Mobile Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

_ACCEPT_LANGUAGES = [
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.9,en;q=0.8",
    "pt-BR,pt;q=0.8,en-US;q=0.6,en;q=0.4",
    "pt,pt-BR;q=0.9,en-US;q=0.8,en;q=0.6",
]

_REFERERS = [
    "https://www.google.com/",
    "https://pncp.gov.br/",
    "https://compras.gov.br/",
    "",  # sem referer — também válido
]


def _rotated_headers() -> dict:
    """Gera headers com rotação de UA, Accept-Language e Referer."""
    ua = random.choice(_USER_AGENTS_EXTENDED)
    is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua
    referer = random.choice(_REFERERS)

    h: dict = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site" if referer else "none",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }
    if referer:
        h["Referer"] = referer
    if not is_mobile:
        # Sec-CH-UA só para desktop Chrome/Edge
        if "Edg" in ua:
            h["Sec-CH-UA"] = '"Microsoft Edge";v="126", "Chromium";v="126", "Not-A.Brand";v="99"'
        elif "Chrome" in ua:
            h["Sec-CH-UA"] = '"Google Chrome";v="126", "Chromium";v="126", "Not-A.Brand";v="99"'
        h["Sec-CH-UA-Mobile"] = "?0"
        h["Sec-CH-UA-Platform"] = '"Windows"' if "Windows" in ua else '"macOS"' if "Mac" in ua else '"Linux"'
    return h


# ── Estrutura da fila ──────────────────────────────────────────────────────────

class SearchParams(NamedTuple):
    q: str | None
    uf: str | None
    modal_pncp: tuple[int, ...]
    modal_dados: tuple[int, ...]
    data_ini_iso: str
    data_fim_iso: str


_queue: asyncio.Queue[SearchParams] = asyncio.Queue(maxsize=100)
_in_flight: set[str] = set()   # chaves em andamento ou na fila


def _queue_key(p: SearchParams) -> str:
    return f"{p.q or ''}|{p.uf or ''}|{p.data_ini_iso}|{p.data_fim_iso}|{','.join(map(str, p.modal_pncp))}"


def enqueue_search(
    q: str | None,
    uf: str | None,
    modal_pncp: list[int],
    modal_dados: list[int],
    data_ini_iso: str,
    data_fim_iso: str,
) -> bool:
    """
    Enfileira uma busca para coleta profunda em background.

    Retorna True se foi enfileirada com sucesso,
    False se já estava na fila/em execução ou se a fila está cheia.
    """
    params = SearchParams(
        q=q, uf=uf,
        modal_pncp=tuple(modal_pncp),
        modal_dados=tuple(modal_dados),
        data_ini_iso=data_ini_iso,
        data_fim_iso=data_fim_iso,
    )
    key = _queue_key(params)
    if key in _in_flight:
        logger.debug("search_queue: busca já enfileirada/em execução — ignorando. key=%s", key)
        return False
    try:
        _queue.put_nowait(params)
        _in_flight.add(key)
        logger.info(
            "search_queue: enfileirado — q=%r uf=%s período=%s→%s modal_pncp=%s",
            q, uf, data_ini_iso, data_fim_iso, modal_pncp,
        )
        return True
    except asyncio.QueueFull:
        logger.warning("search_queue: fila cheia (%d itens) — busca descartada.", _queue.maxsize)
        return False


def queue_size() -> int:
    return _queue.qsize()


# ── Coleta profunda Python (usada pelo worker) ────────────────────────────────

async def _run_targeted_fetch(params: SearchParams) -> int:
    """
    Executa coleta completa das APIs externas com rotação de headers.
    Retorna número total de registros inseridos/atualizados no banco.
    """
    (
        _fetch_pncp_all_pages_with_cap,
        _fetch_dados_all_pages_with_cap,
        _enrich_licitacoes,
        _fmt_pncp_date,
        _pncp_headers,
        _MODALIDADES_PADRAO,
        _MODALIDADES_DADOSABERTOS,
        _DADOSABERTOS_URL,
    ) = _get_fetchers()

    upsert_licitacoes = _get_repo()
    get_pool = _get_pool()

    data_ini_pncp = _fmt_pncp_date(params.data_ini_iso)
    data_fim_pncp = _fmt_pncp_date(params.data_fim_iso)

    all_results: list[dict] = []
    source = "pncp"

    # ── 1. PNCP com rotação de headers e delays aleatórios ────────────────────
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for idx, m in enumerate(params.modal_pncp):
                # Delay entre modalidades (exceto a primeira)
                if idx > 0:
                    await asyncio.sleep(random.uniform(0.8, 2.5))

                items, capped = await _fetch_pncp_with_delays(
                    client, data_ini_pncp, data_fim_pncp, m,
                    uf=params.uf, max_pages=40,
                )
                all_results.extend(items)
                logger.info(
                    "search_queue: PNCP mod=%d → %d itens (capped=%s)",
                    m, len(items), capped,
                )
    except Exception as exc:
        logger.warning("search_queue: PNCP falhou (%s) — tentando dadosabertos...", exc)

    # ── 2. Fallback dadosabertos ───────────────────────────────────────────────
    if not all_results:
        source = "dadosabertos"
        base_params: dict = {
            "dataPublicacaoPncpInicial": params.data_ini_iso,
            "dataPublicacaoPncpFinal":   params.data_fim_iso,
        }
        if params.uf:
            base_params["unidadeOrgaoUfSigla"] = params.uf
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for idx, m in enumerate(params.modal_dados):
                    if idx > 0:
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    items, _ = await _fetch_dados_with_delays(
                        client, base_params, m, page_size=100, max_pages=40,
                    )
                    all_results.extend(items)
                    logger.info(
                        "search_queue: dadosabertos mod=%d → %d itens", m, len(items),
                    )
        except Exception as exc:
            logger.warning("search_queue: dadosabertos falhou: %s", exc)

    if not all_results:
        logger.warning("search_queue: nenhum resultado para a busca enfileirada.")
        return 0

    # Dedup por numero
    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_results:
        key = item.get("numero") or item.get("id")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    # Enriquecimento com concurrency conservadora (não sobrecarregar WAF)
    try:
        unique = await _enrich_licitacoes(unique, concurrency=3)
    except Exception as exc:
        logger.warning("search_queue: enriquecimento falhou, continuando: %s", exc)

    pool = await get_pool()
    inserted, updated = await upsert_licitacoes(pool, unique, fonte=source)
    logger.info(
        "search_queue: upsert concluído — %d inseridos, %d atualizados (fonte: %s).",
        inserted, updated, source,
    )
    return inserted + updated


async def _fetch_pncp_with_delays(
    client: httpx.AsyncClient,
    data_ini: str,
    data_fim: str,
    modalidade: int,
    uf: str | None = None,
    max_pages: int = 40,
) -> tuple[list[dict], bool]:
    """
    Variante de _fetch_pncp_all_pages_with_cap com delay aleatório entre páginas
    e headers rotacionados por página.
    """
    from ..api.licitacoes import (  # noqa: PLC0415
        PNCP_CONSULTA_URL,
        _normalize_pncp_item,
    )
    all_items: list[dict] = []
    for pagina in range(1, max_pages + 1):
        url = (
            f"{PNCP_CONSULTA_URL}"
            f"?dataInicial={data_ini}&dataFinal={data_fim}"
            f"&codigoModalidadeContratacao={modalidade}"
            f"&tamanhoPagina=20&pagina={pagina}"
        )
        if uf:
            url += f"&uf={uf}"
        try:
            resp = await client.get(url, headers=_rotated_headers())
            if resp.status_code == 200:
                page_items = [_normalize_pncp_item(i) for i in resp.json().get("data", [])]
                if not page_items:
                    return all_items, False
                all_items.extend(page_items)
                if len(page_items) < 20:
                    return all_items, False
                # Delay entre páginas (exceto última)
                await asyncio.sleep(random.uniform(0.15, 0.6))
            elif resp.status_code == 204:
                return all_items, False
            else:
                return all_items, False
        except Exception:
            return all_items, False
    return all_items, True


async def _fetch_dados_with_delays(
    client: httpx.AsyncClient,
    base_params: dict,
    modalidade: int,
    page_size: int = 100,
    max_pages: int = 40,
) -> tuple[list[dict], bool]:
    """
    Variante de _fetch_dados_all_pages_with_cap com delay aleatório entre páginas.
    """
    from ..api.licitacoes import DADOSABERTOS_URL, _normalize_dadosabertos  # noqa: PLC0415
    all_items: list[dict] = []
    for pagina in range(1, max_pages + 1):
        params = {**base_params, "codigoModalidade": modalidade, "pagina": pagina, "tamanhoPagina": page_size}
        try:
            resp = await client.get(DADOSABERTOS_URL, params=params, headers=_rotated_headers())
            if resp.status_code == 200:
                page_items = [_normalize_dadosabertos(i) for i in resp.json().get("resultado", [])]
                if not page_items:
                    return all_items, False
                all_items.extend(page_items)
                if len(page_items) < page_size:
                    return all_items, False
                await asyncio.sleep(random.uniform(0.1, 0.4))
            else:
                return all_items, False
        except Exception:
            return all_items, False
    return all_items, True


# ── Worker permanente ─────────────────────────────────────────────────────────

async def queue_worker() -> None:
    """
    Worker permanente: processa buscas enfileiradas uma a uma.
    Deve ser iniciado como asyncio.Task no lifespan do FastAPI.
    """
    logger.info("search_queue: worker iniciado e aguardando buscas.")
    while True:
        params = await _queue.get()
        key = _queue_key(params)
        try:
            logger.info(
                "search_queue: iniciando coleta — q=%r uf=%s %s→%s",
                params.q, params.uf, params.data_ini_iso, params.data_fim_iso,
            )
            total = await _run_targeted_fetch(params)
            logger.info("search_queue: coleta concluída — %d registros processados.", total)
        except Exception as exc:
            logger.error("search_queue: erro no worker: %s", exc, exc_info=True)
        finally:
            _in_flight.discard(key)
            _queue.task_done()
