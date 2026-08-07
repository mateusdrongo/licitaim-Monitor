import { boolean, integer, pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";
import { monitoramentosTable } from "./monitoramentos";

export const alertasTable = pgTable("alertas", {
  id: serial("id").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => usersTable.id, { onDelete: "cascade" }),
  monitoramentoId: integer("monitoramento_id").references(
    () => monitoramentosTable.id,
    { onDelete: "set null" },
  ),
  tipo: text("tipo").notNull(), // nova_licitacao | prazo_vencendo | situacao_alterada | nova_disputa | preco_referencia | tarefa_vencida | tarefa_prazo_1d | tarefa_prazo_3d | tarefa_prazo_7d
  titulo: text("titulo").notNull(),
  descricao: text("descricao").notNull(),
  lido: boolean("lido").notNull().default(false),
  licitacaoId: text("licitacao_id"),
  licitacaoObjeto: text("licitacao_objeto"),
  monitoramentoNome: text("monitoramento_nome"),
  link: text("link"), // URL interna de navegação (ex: /gerenciamento/{id})
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
});

export const insertAlertaSchema = createInsertSchema(alertasTable).omit({
  id: true,
  criadoEm: true,
});
export type InsertAlerta = z.infer<typeof insertAlertaSchema>;
export type Alerta = typeof alertasTable.$inferSelect;
