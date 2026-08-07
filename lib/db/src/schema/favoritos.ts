import { pgTable, serial, text, timestamp, uniqueIndex } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { usersTable } from "./users";

export const favoritosTable = pgTable(
  "favoritos",
  {
    id: serial("id").primaryKey(),
    userId: text("user_id")
      .notNull()
      .references(() => usersTable.id, { onDelete: "cascade" }),
    licitacaoId: text("licitacao_id").notNull(),
    nota: text("nota"),
    // Snapshot of licitacao data for display
    licitacaoObjeto: text("licitacao_objeto"),
    licitacaoOrgao: text("licitacao_orgao"),
    licitacaoUf: text("licitacao_uf"),
    licitacaoModalidade: text("licitacao_modalidade"),
    licitacaoSituacao: text("licitacao_situacao"),
    licitacaoValor: text("licitacao_valor"),
    criadoEm: timestamp("criado_em").notNull().defaultNow(),
  },
  (t) => [uniqueIndex("favoritos_user_licitacao_idx").on(t.userId, t.licitacaoId)],
);

export const insertFavoritoSchema = createInsertSchema(favoritosTable).omit({
  id: true,
  criadoEm: true,
});
export type InsertFavorito = z.infer<typeof insertFavoritoSchema>;
export type Favorito = typeof favoritosTable.$inferSelect;
