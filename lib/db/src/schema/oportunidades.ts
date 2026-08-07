import { integer, pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";

export const oportunidadesTable = pgTable("oportunidades", {
  id: serial("id").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => usersTable.id, { onDelete: "cascade" }),
  titulo: text("titulo").notNull(),
  estagio: text("estagio").notNull().default("identificada"), // identificada | qualificada | proposta | disputa | ganhou | perdeu
  valorEstimado: text("valor_estimado"), // stored as string
  probabilidade: integer("probabilidade"), // 0-100
  licitacaoId: text("licitacao_id"),
  licitacaoObjeto: text("licitacao_objeto"),
  responsavelNome: text("responsavel_nome"),
  responsavelId: integer("responsavel_id"),
  prazo: text("prazo"), // ISO date string
  notas: text("notas"),
  tags: text("tags").notNull().default("[]"), // JSON array
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});

export const insertOportunidadeSchema = createInsertSchema(
  oportunidadesTable,
).omit({
  id: true,
  criadoEm: true,
  atualizadoEm: true,
});
export type InsertOportunidade = z.infer<typeof insertOportunidadeSchema>;
export type Oportunidade = typeof oportunidadesTable.$inferSelect;
