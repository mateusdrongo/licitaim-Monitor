import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import dashboardRouter from "./dashboard";
import licitacoesRouter from "./licitacoes";
import favoritosRouter from "./favoritos";
import monitoramentosRouter from "./monitoramentos";
import alertasRouter from "./alertas";
import documentosRouter from "./documentos";
import equipeRouter from "./equipe";
import oportunidadesRouter from "./oportunidades";
import precosRouter from "./precos";
import aiRouter from "./ai";
import agendaRouter from "./agenda";
import certidoesRouter from "./certidoes";
import analyticsRouter from "./analytics";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(dashboardRouter);
router.use(licitacoesRouter);
router.use(favoritosRouter);
router.use(monitoramentosRouter);
router.use(alertasRouter);
router.use(documentosRouter);
router.use(equipeRouter);
router.use(oportunidadesRouter);
router.use(precosRouter);
router.use(aiRouter);
router.use(agendaRouter);
router.use(certidoesRouter);
router.use(analyticsRouter);

export default router;
