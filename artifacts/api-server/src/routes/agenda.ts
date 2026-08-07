import { Router } from "express";
import { db, favoritosTable, oportunidadesTable, alertasTable, certidoesTable } from "@workspace/db";
import { eq, gte } from "drizzle-orm";
import { requireAuth } from "../middlewares/auth";

const router = Router();

router.get("/agenda", requireAuth, async (req, res): Promise<void> => {
  const userId = req.session.userId!;
  const hoje = new Date();
  const limite = new Date(hoje);
  limite.setDate(limite.getDate() + 60); // próximos 60 dias

  const [oportunidades, alertas, certidoes, favoritos] = await Promise.all([
    db.select().from(oportunidadesTable).where(eq(oportunidadesTable.userId, userId)),
    db.select().from(alertasTable).where(eq(alertasTable.userId, userId)),
    db.select().from(certidoesTable).where(eq(certidoesTable.userId, userId)),
    db.select().from(favoritosTable).where(eq(favoritosTable.userId, userId)),
  ]);

  const eventos: Array<{
    id: string;
    titulo: string;
    data: string;
    tipo: "prazo_oportunidade" | "prazo_certidao" | "alerta" | "favorito";
    status: string;
    urgencia: "normal" | "atencao" | "critico";
    link?: string;
    descricao?: string;
  }> = [];

  // Oportunidades com prazo
  for (const op of oportunidades) {
    if (!op.prazo || ["ganhou", "perdeu"].includes(op.estagio)) continue;
    const data = new Date(op.prazo);
    if (data < hoje || data > limite) continue;
    const diffDias = Math.ceil((data.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
    eventos.push({
      id: `op-${op.id}`,
      titulo: op.titulo,
      data: op.prazo,
      tipo: "prazo_oportunidade",
      status: op.estagio,
      urgencia: diffDias <= 3 ? "critico" : diffDias <= 7 ? "atencao" : "normal",
      link: "/oportunidades",
      descricao: `Pipeline: ${op.estagio}${op.valorEstimado ? ` · R$ ${parseFloat(op.valorEstimado).toLocaleString("pt-BR")}` : ""}`,
    });
  }

  // Certidões vencendo
  for (const cert of certidoes) {
    if (!cert.dataVencimento) continue;
    const data = new Date(cert.dataVencimento);
    const diffDias = Math.ceil((data.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDias > 60) continue;
    eventos.push({
      id: `cert-${cert.id}`,
      titulo: `Vencimento: ${cert.nome}`,
      data: cert.dataVencimento,
      tipo: "prazo_certidao",
      status: diffDias < 0 ? "vencida" : "a_vencer",
      urgencia: diffDias < 0 ? "critico" : diffDias <= 7 ? "critico" : diffDias <= 15 ? "atencao" : "normal",
      link: "/certidoes",
      descricao: cert.orgaoEmissor ?? undefined,
    });
  }

  // Alertas de prazo não lidos
  for (const alerta of alertas) {
    if (alerta.lido || alerta.tipo !== "prazo_vencendo") continue;
    eventos.push({
      id: `alerta-${alerta.id}`,
      titulo: alerta.titulo,
      data: alerta.criadoEm.toISOString(),
      tipo: "alerta",
      status: "pendente",
      urgencia: "atencao",
      link: alerta.licitacaoId ? `/licitacoes/${alerta.licitacaoId}` : "/alertas",
      descricao: alerta.descricao,
    });
  }

  // Organizar por data e calcular resumo
  eventos.sort((a, b) => new Date(a.data).getTime() - new Date(b.data).getTime());

  const resumo = {
    total: eventos.length,
    criticos: eventos.filter((e) => e.urgencia === "critico").length,
    atencao: eventos.filter((e) => e.urgencia === "atencao").length,
    proximos7dias: eventos.filter((e) => {
      const d = new Date(e.data);
      const diff = Math.ceil((d.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));
      return diff >= 0 && diff <= 7;
    }).length,
  };

  res.json({ eventos, resumo });
});

export default router;
