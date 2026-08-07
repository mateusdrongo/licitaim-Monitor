import { pgTable, text, timestamp, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const usersTable = pgTable("users", {
  id: text("id").primaryKey(), // UUID or session ID
  nome: text("nome").notNull(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  senhaHash: text("senha_hash"),
  empresa: text("empresa"),
  cnpj: varchar("cnpj", { length: 20 }),
  plano: varchar("plano", { length: 20 }).notNull().default("gratuito"),
  avatarUrl: text("avatar_url"),
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});

export const insertUserSchema = createInsertSchema(usersTable).omit({
  criadoEm: true,
  atualizadoEm: true,
});
export type InsertUser = z.infer<typeof insertUserSchema>;
export type User = typeof usersTable.$inferSelect;
