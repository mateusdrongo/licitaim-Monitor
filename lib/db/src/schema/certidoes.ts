import { pgTable, serial, text, date, timestamp } from "drizzle-orm/pg-core";
import { usersTable } from "./users";

export const certidoesTable = pgTable("certidoes", {
  id: serial("id").primaryKey(),
  userId: text("user_id").notNull().references(() => usersTable.id, { onDelete: "cascade" }),
  nome: text("nome").notNull(),
  tipo: text("tipo").notNull().default("outro"),
  orgaoEmissor: text("orgao_emissor"),
  numero: text("numero"),
  dataEmissao: date("data_emissao"),
  dataVencimento: date("data_vencimento"),
  descricao: text("descricao"),
  arquivoUrl: text("arquivo_url"),
  criadoEm: timestamp("criado_em").notNull().defaultNow(),
  atualizadoEm: timestamp("atualizado_em").notNull().defaultNow(),
});
