import React, { useEffect } from "react";
import { Link, useLocation } from "wouter";
import { useGetMe, useLogout } from "@workspace/api-client-react";
import { useTheme } from "@/context/ThemeContext";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/apiFetch";

import {
  LayoutDashboard,
  Search,
  Star,
  Bell,
  FileText,
  Briefcase,
  LineChart,
  BrainCircuit,
  Users,
  Settings,
  LogOut,
  Activity,
  CalendarDays,
  ShieldCheck,
  BarChart3,
  Sun,
  Moon,
  ClipboardList,
} from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export function Sidebar() {
  const [location] = useLocation();
  const logout = useLogout();
  const { data: user } = useGetMe();
  const { theme, toggle } = useTheme();

  const { data: unreadData } = useQuery({
    queryKey: ["alertas", "nao-lidos"],
    queryFn: async () => {
      const res = await apiFetch(`${BASE}/api/alertas/nao-lidos`, { credentials: "include" });
      if (!res.ok) return { count: 0 };
      return res.json() as Promise<{ count: number }>;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const unreadCount = unreadData?.count ?? 0;

  useEffect(() => {
    const base = "LicitAIM — Terminal de Inteligência";
    document.title = unreadCount > 0 ? `(${unreadCount}) ${base}` : base;
  }, [unreadCount]);

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSuccess: () => {
        window.location.href = "/entrar";
      }
    });
  };

  const navItems = [
    { label: "Dashboard",       href: "/dashboard",        icon: LayoutDashboard },
    { label: "Licitações",      href: "/licitacoes",       icon: Search },
    { label: "Favoritos",       href: "/favoritos",        icon: Star },
    { label: "Gerenciadas",     href: "/gerenciamento",    icon: ClipboardList },
    { label: "Monitoramentos",  href: "/monitoramentos",   icon: Activity },
    { label: "Alertas",         href: "/alertas",          icon: Bell },
    { label: "Documentos",      href: "/documentos",       icon: FileText },
    { label: "Pipeline",        href: "/oportunidades",    icon: Briefcase },
    { label: "Preços",          href: "/historico-precos", icon: LineChart },
    { label: "AI Search",       href: "/ai-search",        icon: BrainCircuit },
    { label: "Agenda",          href: "/agenda",           icon: CalendarDays },
    { label: "Certidões",       href: "/certidoes",        icon: ShieldCheck },
    { label: "BI / Analytics",  href: "/analytics",        icon: BarChart3 },
  ];

  const adminItems = [
    { label: "Equipe",          href: "/equipe",           icon: Users },
    { label: "Configurações",   href: "/configuracoes",    icon: Settings },
  ];

  return (
    <div className="w-64 bg-card border-r border-border h-screen flex flex-col fixed left-0 top-0 overflow-y-auto">
      {/* Logo */}
      <div className="p-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary flex items-center gap-2">
            <Activity className="w-6 h-6" />
            LicitAIM
          </h1>
          <p className="text-xs text-muted-foreground mt-1">Terminal de Inteligência</p>
        </div>
        {/* Theme toggle */}
        <button
          onClick={toggle}
          title={theme === "dark" ? "Mudar para claro" : "Mudar para escuro"}
          className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>

      <nav className="flex-1 px-4 space-y-1">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-4 px-2">
          Principal
        </div>
        {navItems.map((item) => {
          const isActive = location.startsWith(item.href);
          const showBadge = item.href === "/alertas" && unreadCount > 0;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <span className="relative shrink-0">
                <item.icon className="w-4 h-4" />
                {showBadge && (
                  <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-0.5 flex items-center justify-center rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold leading-none">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                )}
              </span>
              {item.label}
            </Link>
          );
        })}

        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-8 px-2">
          Administração
        </div>
        {adminItems.map((item) => {
          const isActive = location.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="p-4 border-t border-border mt-auto">
        <div className="flex items-center gap-3 px-3 py-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
            {user?.nome?.charAt(0)?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="text-sm font-medium text-foreground truncate">{user?.nome}</p>
            <p className="text-xs text-muted-foreground truncate">{user?.empresa}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sair do Sistema
        </button>
      </div>
    </div>
  );
}
