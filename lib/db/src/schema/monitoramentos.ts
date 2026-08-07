import { boolean, integer, pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";

export const monitoramentosTable = pgTable("monitoramentos", {
  id: serial("id").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => usersTable.id, { onDelete: "cascade" }),
  nome: text("nome").notNull(),
  ativo: boolean("ativo").notNull().default(true),
  palavrasChave: text("palavras_chave").notNull().default("[]"), // JSON array
  modalidades: text("modalidades").notNull().default("[]"), // JSON array
  ufs: text("ufs").notNull().default("[]"), // JSON array
  esferas: text("esferas").notNull().default("[]"), // JSON array
  valorMin: text("valor_min"), // stored as string to avoid float issues
  valorMax: text("valor_max"),
  totalAlertas: integer("total_alertas").notNull().default(0),
  ultimaExecucao: timestamp("ultima_execucao"),
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});

export const insertMonitoramentoSchema = createInsertSchema(monitoramentosTable).omit({
  id: true,
  totalAlertas: true,
  ultimaExecucao: true,
  criadoEm: true,
  atualizadoEm: true,
});
export type InsertMonitoramento = z.infer<typeof insertMonitoramentoSchema>;
export type Monitoramento = typeof monitoramentosTable.$inferSelect;
