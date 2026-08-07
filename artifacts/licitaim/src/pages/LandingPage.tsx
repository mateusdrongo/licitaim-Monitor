import { useLocation } from "wouter";
import {
  Activity, ArrowRight, Search, Bell, BarChart3, FileCheck,
  Users, Bot, Shield, Zap, ChevronRight, Check, Star,
  TrendingUp, Building2, Award, Globe
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ── Data ─────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Search,
    title: "Busca Inteligente",
    description:
      "Encontre licitações do PNCP, ComprasNet e demais portais com filtros avançados por palavra-chave, UF, valor, modalidade e esfera governamental.",
    color: "text-blue-600",
    bg: "bg-blue-50",
  },
  {
    icon: Bell,
    title: "Monitoramento e Alertas",
    description:
      "Crie regras de monitoramento e receba alertas multicanal (e-mail, push, WhatsApp) quando novas licitações relevantes forem publicadas.",
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  {
    icon: TrendingUp,
    title: "Pipeline Comercial",
    description:
      "Gerencie oportunidades do pipeline com estágios, probabilidade de vitória, responsáveis e prazos — tudo num CRM focado em licitações.",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
  },
  {
    icon: FileCheck,
    title: "Compliance e Certidões",
    description:
      "Cadastre suas certidões (FGTS, Receita, INSS, Trabalhista) e receba alertas 30, 15 e 5 dias antes do vencimento.",
    color: "text-purple-600",
    bg: "bg-purple-50",
  },
  {
    icon: BarChart3,
    title: "Analytics e BI",
    description:
      "Dashboards gerenciais com taxa de vitória, valor ponderado do pipeline, maiores compradores e análise de competitividade por segmento.",
    color: "text-rose-600",
    bg: "bg-rose-50",
  },
  {
    icon: Bot,
    title: "Assistente IA (RAG)",
    description:
      "Faça perguntas em linguagem natural: 'Quais licitações abertas para notebook acima de R$500 mil?' e obtenha respostas contextuais.",
    color: "text-indigo-600",
    bg: "bg-indigo-50",
  },
];

const PLANS = [
  {
    name: "Gratuito",
    price: "R$0",
    period: "/mês",
    description: "Para explorar a plataforma",
    badge: null,
    highlight: false,
    features: [
      "2 monitoramentos ativos",
      "50 alertas por mês",
      "Busca básica no PNCP",
      "Dashboard essencial",
      "1 usuário",
    ],
    cta: "Criar conta grátis",
    ctaVariant: "outline" as const,
  },
  {
    name: "Starter",
    price: "R$197",
    period: "/mês",
    description: "Para equipes em crescimento",
    badge: null,
    highlight: false,
    features: [
      "10 monitoramentos ativos",
      "Alertas ilimitados",
      "Busca avançada com filtros",
      "Pipeline comercial (CRM)",
      "Histórico de preços",
      "Até 3 usuários na equipe",
      "Suporte por e-mail",
    ],
    cta: "Começar agora",
    ctaVariant: "outline" as const,
  },
  {
    name: "Profissional",
    price: "R$497",
    period: "/mês",
    description: "Para empresas que disputam mais",
    badge: "Mais popular",
    highlight: true,
    features: [
      "Monitoramentos ilimitados",
      "Alertas ilimitados + multicanal",
      "Assistente IA (busca semântica)",
      "Analytics e BI avançado",
      "Gestão de compliance e certidões",
      "Equipe ilimitada",
      "Agenda e calendário de prazos",
      "Suporte prioritário",
    ],
    cta: "Assinar Profissional",
    ctaVariant: "primary" as const,
  },
  {
    name: "Enterprise",
    price: "Consulte",
    period: "",
    description: "Para grandes operações",
    badge: null,
    highlight: false,
    features: [
      "Tudo do Profissional",
      "Acesso à API REST",
      "SLA 99,9% garantido",
      "Multi-tenant (múltiplas empresas)",
      "Integrações personalizadas",
      "Scraping de portais exclusivos",
      "Gerente de conta dedicado",
      "Suporte 24/7",
    ],
    cta: "Falar com vendas",
    ctaVariant: "outline" as const,
  },
];

const STATS = [
  { value: "142 mil+", label: "Licitações indexadas" },
  { value: "R$890 bi+", label: "Em contratos monitorados" },
  { value: "3.200+", label: "Empresas ativas" },
  { value: "98%", label: "Taxa de satisfação" },
];

const TESTIMONIALS = [
  {
    quote:
      "Antes perdíamos editais por não termos informação a tempo. Com o LicitAIM, somos notificados minutos após a publicação.",
    author: "Carlos Mendes",
    role: "Diretor Comercial",
    company: "TechSupply Soluções",
    stars: 5,
  },
  {
    quote:
      "O pipeline comercial nos ajudou a organizar 40 oportunidades simultâneas. Nossa taxa de vitória subiu 30% em 6 meses.",
    author: "Fernanda Lima",
    role: "Gestora de Licitações",
    company: "Construbras Engenharia",
    stars: 5,
  },
  {
    quote:
      "O alerta de certidões vencendo nos salvou de uma habilitação negada. Ferramenta indispensável para conformidade.",
    author: "Ricardo Souza",
    role: "Sócio-Diretor",
    company: "Pharma Distribuidora",
    stars: 5,
  },
];

// ── Subcomponents ─────────────────────────────────────────────────────────────

function NavBar({ onLogin, onRegister }: { onLogin: () => void; onRegister: () => void }) {
  return (
    <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="text-xl font-bold text-primary">LicitAIM</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">
          <a href="#funcionalidades" className="hover:text-primary transition-colors">Funcionalidades</a>
          <a href="#planos" className="hover:text-primary transition-colors">Planos</a>
          <a href="#depoimentos" className="hover:text-primary transition-colors">Depoimentos</a>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onLogin}
            className="text-sm font-medium text-slate-600 hover:text-primary transition-colors px-3 py-2"
          >
            Entrar
          </button>
          <button
            onClick={onRegister}
            className="bg-primary text-primary-foreground text-sm font-medium px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors"
          >
            Criar conta
          </button>
        </div>
      </div>
    </nav>
  );
}

function Hero({ onRegister, onLogin }: { onRegister: () => void; onLogin: () => void }) {
  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-slate-950 via-primary to-blue-900 text-white">
      {/* grid overlay */}
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTAgMCBMNjAgMCBMNjAgNjAgTDAgNjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjA0KSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9zdmc+')] opacity-60" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-28 lg:py-36 text-center">
        <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-sm font-medium mb-8 backdrop-blur-sm">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span>Novo: Assistente IA com busca semântica</span>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight mb-6">
          A inteligência por trás das
          <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-300 to-cyan-300">
            grandes licitações
          </span>
        </h1>

        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-white/75 leading-relaxed mb-10">
          Monitore editais em tempo real, gerencie seu pipeline comercial, garanta compliance e tome
          decisões com dados — tudo num cockpit desenhado para vencer licitações.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button
            onClick={onRegister}
            className="inline-flex items-center justify-center gap-2 bg-white text-primary font-semibold px-8 py-3.5 rounded-xl hover:bg-white/90 transition-all shadow-lg hover:shadow-xl"
          >
            Começar grátis <ArrowRight className="w-4 h-4" />
          </button>
          <button
            onClick={onLogin}
            className="inline-flex items-center justify-center gap-2 border border-white/30 bg-white/10 backdrop-blur-sm text-white font-semibold px-8 py-3.5 rounded-xl hover:bg-white/20 transition-all"
          >
            Já tenho conta <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <p className="mt-6 text-sm text-white/50">
          Grátis para começar · Sem cartão de crédito · Cancele quando quiser
        </p>
      </div>

      {/* Stats band */}
      <div className="relative border-t border-white/10 bg-white/5 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 grid grid-cols-2 lg:grid-cols-4 gap-8 text-center">
          {STATS.map((s) => (
            <div key={s.label}>
              <div className="text-2xl lg:text-3xl font-bold text-white">{s.value}</div>
              <div className="text-sm text-white/60 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="funcionalidades" className="py-24 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <span className="text-primary text-sm font-semibold uppercase tracking-widest">Plataforma completa</span>
          <h2 className="mt-3 text-3xl lg:text-4xl font-bold text-slate-900">
            Tudo que você precisa para vencer
          </h2>
          <p className="mt-4 text-lg text-slate-500 max-w-2xl mx-auto">
            Do monitoramento à assinatura do contrato, o LicitAIM cobre cada etapa do processo licitatório.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="bg-white rounded-2xl p-7 shadow-sm border border-slate-100 hover:shadow-md hover:-translate-y-1 transition-all duration-200"
              >
                <div className={`w-12 h-12 ${f.bg} ${f.color} rounded-xl flex items-center justify-center mb-5`}>
                  <Icon className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{f.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function Pricing({ onRegister }: { onRegister: () => void }) {
  return (
    <section id="planos" className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <span className="text-primary text-sm font-semibold uppercase tracking-widest">Preços transparentes</span>
          <h2 className="mt-3 text-3xl lg:text-4xl font-bold text-slate-900">
            Escolha o plano ideal
          </h2>
          <p className="mt-4 text-lg text-slate-500 max-w-xl mx-auto">
            Comece gratuitamente e escale conforme o seu volume de licitações cresce.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`relative flex flex-col rounded-2xl border p-7 transition-all ${
                plan.highlight
                  ? "border-primary bg-primary text-white shadow-2xl shadow-primary/30 scale-[1.02]"
                  : "border-slate-200 bg-white text-slate-900 shadow-sm hover:shadow-md"
              }`}
            >
              {plan.badge && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="bg-amber-400 text-amber-900 text-xs font-bold px-3 py-1 rounded-full shadow">
                    {plan.badge}
                  </span>
                </div>
              )}

              <div>
                <h3 className={`text-lg font-bold ${plan.highlight ? "text-white" : "text-slate-900"}`}>
                  {plan.name}
                </h3>
                <p className={`text-sm mt-1 ${plan.highlight ? "text-white/70" : "text-slate-500"}`}>
                  {plan.description}
                </p>
                <div className="mt-5 flex items-end gap-1">
                  <span className={`text-3xl font-extrabold ${plan.highlight ? "text-white" : "text-slate-900"}`}>
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className={`text-sm mb-1 ${plan.highlight ? "text-white/60" : "text-slate-400"}`}>
                      {plan.period}
                    </span>
                  )}
                </div>
              </div>

              <ul className="mt-7 flex-1 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm">
                    <Check
                      className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                        plan.highlight ? "text-blue-200" : "text-emerald-500"
                      }`}
                    />
                    <span className={plan.highlight ? "text-white/85" : "text-slate-600"}>{f}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={onRegister}
                className={`mt-8 w-full py-3 rounded-xl font-semibold text-sm transition-all ${
                  plan.highlight
                    ? "bg-white text-primary hover:bg-white/90"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="text-center text-sm text-slate-400 mt-10">
          Todos os planos incluem período de 14 dias de avaliação gratuita do plano Profissional.
          Sem cobrança automática.
        </p>
      </div>
    </section>
  );
}

function Testimonials() {
  return (
    <section id="depoimentos" className="py-24 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <span className="text-primary text-sm font-semibold uppercase tracking-widest">Depoimentos</span>
          <h2 className="mt-3 text-3xl lg:text-4xl font-bold text-slate-900">
            Empresas que já venceram mais
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {TESTIMONIALS.map((t) => (
            <div key={t.author} className="bg-white rounded-2xl p-7 border border-slate-100 shadow-sm">
              <div className="flex mb-4">
                {Array.from({ length: t.stars }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-amber-400 fill-amber-400" />
                ))}
              </div>
              <p className="text-slate-600 text-sm leading-relaxed mb-6">"{t.quote}"</p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold text-sm flex items-center justify-center">
                  {t.author[0]}
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{t.author}</div>
                  <div className="text-xs text-slate-400">{t.role} · {t.company}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TrustBar() {
  const badges = [
    { icon: Shield, label: "LGPD Compliant" },
    { icon: Globe, label: "Integrado ao PNCP oficial" },
    { icon: Award, label: "Uptime 99,9%" },
    { icon: Building2, label: "Cobertura nacional" },
  ];
  return (
    <div className="bg-white border-y border-slate-100 py-10">
      <div className="max-w-5xl mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
        {badges.map((b) => {
          const Icon = b.icon;
          return (
            <div key={b.label} className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                <Icon className="w-5 h-5" />
              </div>
              <span className="text-sm font-medium text-slate-600">{b.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CTA({ onRegister }: { onRegister: () => void }) {
  return (
    <section className="bg-gradient-to-br from-primary to-blue-800 py-20 text-center text-white">
      <div className="max-w-3xl mx-auto px-4">
        <h2 className="text-3xl lg:text-4xl font-extrabold mb-4">
          Pronto para vencer mais licitações?
        </h2>
        <p className="text-lg text-white/75 mb-10">
          Crie sua conta gratuita agora e comece a monitorar licitações em minutos.
        </p>
        <button
          onClick={onRegister}
          className="inline-flex items-center gap-2 bg-white text-primary font-bold px-10 py-4 rounded-xl shadow-xl hover:bg-white/90 transition-all text-lg"
        >
          Criar conta grátis <ArrowRight className="w-5 h-5" />
        </button>
        <p className="mt-5 text-sm text-white/50">Sem cartão de crédito · 14 dias grátis do plano Pro</p>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-slate-950 text-slate-400 py-14">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary rounded-md flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="text-white font-bold">LicitAIM</span>
          </div>
          <p className="text-sm">
            © {new Date().getFullYear()} LicitAIM. Plataforma de inteligência em licitações públicas brasileiras.
          </p>
          <div className="flex gap-6 text-sm">
            <a href="#" className="hover:text-white transition-colors">Termos</a>
            <a href="#" className="hover:text-white transition-colors">Privacidade</a>
            <a href="#" className="hover:text-white transition-colors">Contato</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [, setLocation] = useLocation();

  const goLogin = () => setLocation("/entrar");
  const goRegister = () => setLocation("/cadastro");

  return (
    <div className="min-h-screen bg-white">
      <NavBar onLogin={goLogin} onRegister={goRegister} />
      <Hero onRegister={goRegister} onLogin={goLogin} />
      <TrustBar />
      <Features />
      <Pricing onRegister={goRegister} />
      <Testimonials />
      <CTA onRegister={goRegister} />
      <Footer />
    </div>
  );
}
