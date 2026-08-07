---
name: Bcrypt/Passlib incompatibility
description: passlib 1.7.4 quebra com bcrypt>=4 (sem __about__); solução é usar bcrypt direto
---

O módulo `passlib` (versão 1.7.4, não mantida) usa `bcrypt.__about__.__version__` que não existe mais no bcrypt>=4. Isso causa `AttributeError` no startup e `ValueError: password cannot be longer than 72 bytes` ao tentar fazer hash.

**Why:** passlib está abandonada e não acompanhou a API do bcrypt moderno.

**How to apply:** Substituir `passlib.context.CryptContext` por chamadas diretas ao `bcrypt`:
```python
import bcrypt
def verify_password(plain, hashed): return bcrypt.checkpw(plain.encode(), hashed.encode())
def get_password_hash(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
```
Arquivo afetado: `artifacts/api-server/app/core/security.py`
