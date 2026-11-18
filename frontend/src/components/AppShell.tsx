import React, { useState } from 'react';
import {
  BriefcaseBusiness,
  FileCheck2,
  KanbanSquare,
  LogOut,
  Menu,
  MessageSquareText,
  MonitorCog,
  UserCog,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { PasswordBadgeButton, SetPasswordModal } from './SetPasswordModal';

export type ActiveTab =
  | 'chat'
  | 'jobs'
  | 'cv'
  | 'applications'
  | 'profile'
  | 'system';

interface NavItem {
  id: ActiveTab;
  label: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'chat',
    label: 'Chat Omnichannel',
    subtitle: 'Comandos & IA',
    icon: MessageSquareText,
  },
  {
    id: 'jobs',
    label: 'Radar de Vagas',
    subtitle: 'Busca & Match',
    icon: BriefcaseBusiness,
  },
  {
    id: 'cv',
    label: 'CV Studio',
    subtitle: 'ATS, PDF & DOCX',
    icon: FileCheck2,
  },
  {
    id: 'applications',
    label: 'Candidaturas',
    subtitle: 'Kanban & Entrevista',
    icon: KanbanSquare,
  },
  {
    id: 'profile',
    label: 'Perfil & Vontades',
    subtitle: 'Skills & Filtros',
    icon: UserCog,
  },
  {
    id: 'system',
    label: 'Sistema & PC',
    subtitle: 'LLM, Devices & Auth',
    icon: MonitorCog,
  },
];

interface AppShellProps {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ activeTab, onSelectTab, children }) => {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [pwdModalOpen, setPwdModalOpen] = useState(false);

  const handleNav = (tab: ActiveTab) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  const activeNav = NAV_ITEMS.find((n) => n.id === activeTab) || NAV_ITEMS[0];

  const SidebarContent = (
    <div className="flex h-full flex-col justify-between">
      <div>
        <div className="flex items-center justify-between border-b border-slate-800/80 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10">
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M5 7h14M5 12h9M5 17h14"
                  stroke="#34d399"
                  strokeWidth="2.3"
                  strokeLinecap="round"
                />
                <circle cx="18.5" cy="12" r="2.2" fill="#38bdf8" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-slate-100">C3PO</div>
              <div className="text-[11px] text-[#8896ab]">Career Studio</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(false)}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100 lg:hidden"
            aria-label="Fechar menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav aria-label="Navegação principal" className="space-y-1 p-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const selected = item.id === activeTab;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNav(item.id)}
                className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                  selected
                    ? 'bg-emerald-500/12 text-emerald-300 ring-1 ring-inset ring-emerald-500/30'
                    : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-50'
                }`}
              >
                <Icon
                  className={`h-4 w-4 shrink-0 ${
                    selected ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-200'
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium leading-tight">{item.label}</div>
                  <div className="truncate text-[11px] text-[#8896ab]">{item.subtitle}</div>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="space-y-2.5 border-t border-slate-800/80 p-3">
        <PasswordBadgeButton onClick={() => setPwdModalOpen(true)} />

        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-[#0d111a] px-3 py-2.5">
          <div className="min-w-0">
            <div className="truncate text-xs font-semibold text-slate-100">
              {user?.nome || 'Operador'}
            </div>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
                {user?.role || 'user'}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => logout()}
            title="Encerrar sessão"
            className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-rose-500/15 hover:text-rose-300"
            aria-label="Sair da conta"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#0b0e14] text-slate-100">
      {/* Desktop persistent sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-slate-800/90 bg-[#0f141e] lg:block">
        {SidebarContent}
      </aside>

      {/* Mobile slide-over drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/70"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative z-10 h-full w-72 border-r border-slate-800 bg-[#0f141e]">
            {SidebarContent}
          </aside>
        </div>
      )}

      {/* Main workspace */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Mobile header bar */}
        <header className="flex items-center justify-between border-b border-slate-800/90 bg-[#0f141e] px-4 py-3 lg:hidden">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="rounded-md border border-slate-700 bg-slate-800/70 p-1.5 text-slate-200"
              aria-label="Abrir navegação"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-sm font-semibold text-slate-100">{activeNav.label}</h1>
              <p className="text-[11px] text-[#8896ab]">{activeNav.subtitle}</p>
            </div>
          </div>
          <span className="rounded border border-slate-800 bg-[#131926] px-2 py-1 font-mono text-[11px] text-slate-300">
            {user?.nome}
          </span>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>

      <SetPasswordModal open={pwdModalOpen} onClose={() => setPwdModalOpen(false)} />
    </div>
  );
};
