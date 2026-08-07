---
name: Tabelas faltando no schema inicial
description: agenda_eventos e notifications não existiam; users precisava de colunas de notificação
---

O `licitaim_database.sql` importado não continha todas as tabelas usadas pelo backend.

**Tabelas criadas:**
- `agenda_eventos` (id, user_id, titulo, descricao, data, observacao, criado_em)
- `notifications` (id, user_id, title, body, tipo, channel, lida, metadata, criado_em)

**Colunas adicionadas a `users`:**
- notif_email, notif_push, notif_whatsapp, notif_telegram (boolean)
- telegram_chat_id, phone (text)

**Why:** O código do backend referenciava essas tabelas/colunas, mas elas não existiam no banco → 500 Internal Server Error nas páginas Agenda e Notificações.

**How to apply:** Todas as correções foram adicionadas como DDL idempotente em `artifacts/api-server/app/db/migrations.py` — rodam automaticamente no startup.
