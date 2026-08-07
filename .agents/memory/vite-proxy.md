---
name: Vite proxy para API
description: Frontend precisa de proxy /api no vite.config.ts apontando para a porta da API
---

O frontend (Vite) e o backend (FastAPI) rodam em portas separadas. Sem proxy, chamadas `/api/*` caem no HTML do Vite.

**Why:** No Replit os artefatos gerenciados usam portas dinâmicas. O artifact `api-server` usa a porta definida em `$PORT`, que o sistema seta como 8080.

**How to apply:** Adicionar em `vite.config.ts` dentro de `server`:
```ts
proxy: {
  '/api': {
    target: `http://localhost:${process.env.API_PORT ?? '8080'}`,
    changeOrigin: true,
    ws: true,
  },
},
```
A variável `API_PORT` permite sobrescrever em ambientes alternativos. O padrão 8080 funciona com o workflow gerenciado.
