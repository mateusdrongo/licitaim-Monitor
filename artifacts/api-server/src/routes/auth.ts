import { Router } from "express";
import { db, usersTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { randomUUID } from "crypto";

declare module "express-session" {
  interface SessionData {
    userId: string;
  }
}

const router = Router();

router.get("/auth/me", async (req, res): Promise<void> => {
  const userId = req.session.userId;
  if (!userId) {
    res.status(401).json({ error: "Não autenticado" });
    return;
  }
  const users = await db.select().from(usersTable).where(eq(usersTable.id, userId)).limit(1);
  if (!users[0]) {
    req.session.destroy(() => {});
    res.status(401).json({ error: "Usuário não encontrado" });
    return;
  }
  const u = users[0];
  res.json({
    id: u.id,
    nome: u.nome,
    email: u.email,
    empresa: u.empresa ?? null,
    cnpj: u.cnpj ?? null,
    plano: u.plano,
    avatarUrl: u.avatarUrl ?? null,
    criadoEm: u.criadoEm.toISOString(),
  });
});

router.post("/auth/login", async (req, res): Promise<void> => {
  const { email, password } = req.body as { email?: string; password?: string };
  if (!email) {
    res.status(400).json({ error: "Email obrigatório" });
    return;
  }

  // Find or create user (demo auth — no real password check)
  let existing = await db.select().from(usersTable).where(eq(usersTable.email, email)).limit(1);
  let user = existing[0];

  if (!user) {
    const [created] = await db
      .insert(usersTable)
      .values({
        id: randomUUID(),
        nome: email.split("@")[0] ?? "Usuário",
        email,
        plano: "profissional",
        empresa: "Minha Empresa Ltda",
      })
      .returning();
    user = created;
  }

  req.session.userId = user.id;
  req.session.save((err) => {
    if (err) {
      req.log.error({ err }, "Session save error");
      res.status(500).json({ error: "Erro ao criar sessão" });
      return;
    }
    res.json({
      id: user.id,
      nome: user.nome,
      email: user.email,
      empresa: user.empresa ?? null,
      cnpj: user.cnpj ?? null,
      plano: user.plano,
      avatarUrl: user.avatarUrl ?? null,
      criadoEm: user.criadoEm.toISOString(),
    });
  });
});

router.post("/auth/logout", (req, res): void => {
  req.session.destroy((err) => {
    if (err) {
      req.log.error({ err }, "Session destroy error");
    }
    res.json({ message: "Sessão encerrada com sucesso" });
  });
});

export default router;
