---
name: PNCP inacessível no Replit
description: A API pública do PNCP está bloqueada no ambiente Replit; timeout precisa ser curto
---

`pncp.gov.br` e `dadosabertos.compras.gov.br` não respondem a partir do Replit (requests silenciosamente travam).

**Why:** O ambiente Replit bloqueia ou limita certas origens externas do governo brasileiro.

**How to apply:** Manter timeout ≤ 6s em `artifacts/api-server/app/api/licitacoes.py` para os blocos `httpx.AsyncClient(timeout=6.0)` do PNCP e dadosabertos. Assim a busca cai rapidamente para o mock ou para dados do cache local, sem travar o request do usuário por 50s.

O cache local (`licitacoes_cache`) é populado pelo scheduler 4x ao dia e pelo collector standalone — se estiver populado, a busca usa o banco sem chamar o PNCP.
