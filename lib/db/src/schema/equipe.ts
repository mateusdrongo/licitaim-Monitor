import { pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";

export const equipeMembrosTable = pgTable("equipe_membros", {
  id: serial("id").primaryKey(),
  ownerId: text("owner_id")
    .notNull()
    .references(() => usersTable.id, { onDelete: "cascade" }),
  memberId: text("member_id").references(() => usersTable.id, {
    onDelete: "set null",
  }),
  nome: text("nome").notNull(),
  email: text("email").notNull(),
  papel: text("papel").notNull().default("visualizador"), // admin | editor | visualizador
  status: text("status").notNull().default("pendente"), // ativo | pendente | inativo
  avatarUrl: text("avatar_url"),
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});

export const insertEquipeMembroSchema = createInsertSchema(
  equipeMembrosTable,
).omit({
  id: true,
  criadoEm: true,
  atualizadoEm: true,
});
export type InsertEquipeMembro = z.infer<typeof insertEquipeMembroSchema>;
export type EquipeMembro = typeof equipeMembrosTable.$inferSelect;
