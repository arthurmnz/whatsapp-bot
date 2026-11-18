import React, { useCallback, useState } from 'react';
import { AppShell, type ActiveTab } from './components/AppShell';
import { AuthPage } from './components/AuthPage';
import { ToastProvider } from './components/ui/Toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import type { TailorPrefillContext } from './types/api';
import { ApplicationsView } from './views/ApplicationsView';
import { ChatView } from './views/ChatView';
import { CvStudioView } from './views/CvStudioView';
import { JobsRadarView } from './views/JobsRadarView';
import { ProfileView } from './views/ProfileView';
import { SystemView } from './views/SystemView';

const AuthenticatedWorkspace: React.FC = () => {
  const { user, loading } = useAuth();
  const [activeTab, setActiveTab] = useState<ActiveTab>('chat');
  const [cvPrefill, setCvPrefill] = useState<TailorPrefillContext | null>(null);

  const handleOpenCvStudio = useCallback((prefill: TailorPrefillContext) => {
    setCvPrefill(prefill);
    setActiveTab('cv');
  }, []);

  const handleClearPrefill = useCallback(() => {
    setCvPrefill(null);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#0b0e14] text-slate-200">
        <div className="w-full max-w-sm space-y-4 px-6">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 animate-pulse rounded-lg border border-emerald-500/30 bg-emerald-500/10" />
            <div className="space-y-1.5">
              <div className="h-4 w-32 animate-pulse rounded bg-slate-800" />
              <div className="h-3 w-48 animate-pulse rounded bg-slate-800/70" />
            </div>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-emerald-500" />
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <AppShell activeTab={activeTab} onSelectTab={setActiveTab}>
      {activeTab === 'chat' && (
        <ChatView
          onOpenCvStudio={handleOpenCvStudio}
          onNavigateTab={(tab) => setActiveTab(tab)}
        />
      )}
      {activeTab === 'jobs' && (
        <JobsRadarView
          onOpenCvStudio={handleOpenCvStudio}
          onOpenApplications={() => setActiveTab('applications')}
        />
      )}
      {activeTab === 'cv' && (
        <CvStudioView
          prefillContext={cvPrefill}
          onClearPrefill={handleClearPrefill}
          onNavigateApplications={() => setActiveTab('applications')}
        />
      )}
      {activeTab === 'applications' && (
        <ApplicationsView onOpenCvStudio={handleOpenCvStudio} />
      )}
      {activeTab === 'profile' && <ProfileView />}
      {activeTab === 'system' && <SystemView />}
    </AppShell>
  );
};

export const App: React.FC = () => (
  <ToastProvider>
    <AuthProvider>
      <AuthenticatedWorkspace />
    </AuthProvider>
  </ToastProvider>
);

export default App;
