import { integer, pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";

export const documentosTable = pgTable("documentos", {
  id: serial("id").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => usersTable.id, { onDelete: "cascade" }),
  nome: text("nome").notNull(),
  categoria: text("categoria").notNull().default("outro"), // edital | proposta | habilitacao | recurso | contrato | outro
  licitacaoId: text("licitacao_id"),
  licitacaoObjeto: text("licitacao_objeto"),
  url: text("url"),
  tamanho: integer("tamanho"),
  tipo: text("tipo"), // MIME type
  descricao: text("descricao"),
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});

export const insertDocumentoSchema = createInsertSchema(documentosTable).omit({
  id: true,
  criadoEm: true,
  atualizadoEm: true,
});
export type InsertDocumento = z.infer<typeof insertDocumentoSchema>;
export type Documento = typeof documentosTable.$inferSelect;
