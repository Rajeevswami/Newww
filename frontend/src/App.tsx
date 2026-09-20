import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ArrowUpRight,
  Bell,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  CheckCircle,
  ChevronRight,
  ChevronsUpDown,
  CircleHelp,
  CreditCard,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  Video,
  X,
  Zap,
} from 'lucide-react';
import {
  api,
  post,
  setToken,
  type Application,
  type Interview,
  type Job,
  type Session,
  type User,
} from './api/client';
import { Avatar, Loading, Logo, Modal } from './components/ui';
import Dashboard from './pages/Dashboard';
import {
  AnalyticsPage,
  CandidateDetail,
  CandidateHome,
  CandidatesPage,
  InterviewDetail,
  InterviewsPage,
  JobDetail,
  JobForm,
  JobsPage,
  ResumePage,
} from './pages/Workspace';
import SettingsPage, { HelpPage } from './pages/Settings';
import Auth from './pages/Auth';
type Notification = {
  id: string;
  action: string;
  details: { name?: string; title?: string; status?: string };
  created_at: string;
};
const pageNames = [
  'Overview',
  'Jobs',
  'Candidates',
  'AI Interviews',
  'Analytics',
  'Team members',
  'Billing & plans',
  'Settings',
  'Help & resources',
  'My dashboard',
  'Browse jobs',
  'My resume',
];
export default function App() {
  const qc = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [page, setPage] = useState(() => decodeURIComponent(location.hash.slice(1)) || 'Overview');
  const [toast, setToast] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [notificationRead, setNotificationRead] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [jobForm, setJobForm] = useState<boolean | Job>(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<Application | null>(null);
  const [selectedInterview, setSelectedInterview] = useState<Interview | null>(null);
  const candidate = session?.user.role === 'candidate';
  const notify = useCallback((s: string) => setToast(s), []);
  const navigate = useCallback((p: string) => {
    setPage(p);
    window.location.hash = encodeURIComponent(p);
    setSidebarOpen(false);
    setProfileOpen(false);
    setWorkspaceOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);
  const acceptSession = useCallback(
    (s: Session) => {
      setToken(s.access_token);
      setSession(s);
      qc.clear();
    },
    [qc],
  );
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const health = await api<{ demo: boolean }>('/health');
        if (!alive) return;
        setDemoEnabled(health.demo);
        if (
          new URLSearchParams(location.search).has('action') ||
          sessionStorage.getItem('smarthire-signed-out')
        )
          return;
        try {
          const s = await post<Session>('/auth/refresh');
          if (alive) acceptSession(s);
        } catch {
          if (health.demo && !sessionStorage.getItem('smarthire-signed-out')) {
            const s = await post<Session>('/auth/demo');
            if (alive) acceptSession(s);
          }
        }
      } catch (e) {
        if (alive) notify('Could not connect to SmartHire. Make sure the API is running.');
      } finally {
        if (alive) setInitializing(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [acceptSession, notify]);
  useEffect(() => {
    const listener = () => setPage(decodeURIComponent(location.hash.slice(1)) || 'Overview');
    window.addEventListener('hashchange', listener);
    return () => window.removeEventListener('hashchange', listener);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 5500);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
      if (e.key === 'Escape') {
        setProfileOpen(false);
        setNotifications(false);
        setWorkspaceOpen(false);
      }
    };
    const expired = () => {
      setSession(null);
      setToken('');
      qc.clear();
      notify('Your session expired. Please sign in again.');
    };
    window.addEventListener('keydown', key);
    window.addEventListener('session-expired', expired);
    return () => {
      window.removeEventListener('keydown', key);
      window.removeEventListener('session-expired', expired);
    };
  }, [qc, notify]);
  const { data: activity = [] } = useQuery({
    queryKey: ['activity'],
    queryFn: () => api<Notification[]>('/activity'),
    enabled: !!session && !candidate,
  });
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api<Job[]>('/jobs'),
    enabled: !!session,
  });
  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
    enabled: !!session,
  });
  async function switchRole() {
    try {
      const s = await post<Session>(`/auth/demo?role=${candidate ? 'recruiter' : 'candidate'}`);
      acceptSession(s);
      navigate(s.user.role === 'candidate' ? 'My dashboard' : 'Overview');
      setSelectedCandidate(null);
      setSelectedJob(null);
      setSelectedInterview(null);
      notify(`Switched to ${s.user.role === 'candidate' ? 'candidate' : 'recruiter'} demo`);
    } catch (e) {
      notify((e as Error).message);
    }
  }
  async function logout() {
    try {
      await post('/auth/logout');
    } catch {}
    setSession(null);
    setToken('');
    qc.clear();
    sessionStorage.setItem('smarthire-signed-out', 'true');
    setProfileOpen(false);
  }
  async function refreshUser() {
    const u = await api<User>('/auth/me');
    setSession((s) => (s ? { ...s, user: u } : null));
  }
  if (initializing)
    return (
      <div className="splash">
        <Logo />
        <Loading />
      </div>
    );
  if (!session)
    return (
      <>
        <Auth
          demoEnabled={demoEnabled}
          onSession={(s) => {
            sessionStorage.removeItem('smarthire-signed-out');
            acceptSession(s);
            navigate(s.user.role === 'candidate' ? 'My dashboard' : 'Overview');
          }}
        />
        {toast && (
          <div className="toast" role="status">
            <CircleHelp size={19} />
            {toast}
            <button aria-label="Dismiss" onClick={() => setToast('')}>
              <X size={16} />
            </button>
          </div>
        )}
      </>
    );
  const user = session.user;
  const currentPage =
    candidate &&
    ['Overview', 'Jobs', 'Candidates', 'Analytics', 'Team members', 'Billing & plans'].includes(page)
      ? 'My dashboard'
      : !candidate && ['My dashboard', 'Browse jobs', 'My resume'].includes(page)
        ? 'Overview'
        : pageNames.includes(page)
          ? page
          : 'Overview';
  const nav = candidate
    ? [
        { name: 'My dashboard', icon: LayoutDashboard },
        {
          name: 'Browse jobs',
          icon: BriefcaseBusiness,
          count: jobs.filter((j) => j.status === 'active').length,
        },
        { name: 'My resume', icon: FileText },
        { name: 'AI Interviews', icon: Video, ai: true },
      ]
    : [
        { name: 'Overview', icon: LayoutDashboard },
        { name: 'Jobs', icon: BriefcaseBusiness, count: jobs.filter((j) => j.status === 'active').length },
        { name: 'Candidates', icon: Users },
        { name: 'AI Interviews', icon: Video, ai: true },
        { name: 'Analytics', icon: ChartNoAxesCombined },
      ];
  const manageNav = candidate
    ? [{ name: 'Settings', icon: Settings }]
    : [
        { name: 'Team members', icon: Users },
        { name: 'Billing & plans', icon: CreditCard },
        { name: 'Settings', icon: Settings },
      ];
  const openJob = (j: Job) => {
    setSelectedJob(j);
    setSearchOpen(false);
  };
  const openCandidate = (a: Application) => {
    setSelectedCandidate(a);
    setSelectedJob(null);
    setSearchOpen(false);
  };
  const openInterview = (i: Interview) => {
    setSelectedInterview(i);
    setSelectedCandidate(null);
  };
  return (
    <div className="app-shell">
      {sidebarOpen && <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <button
            className="brand-button"
            aria-label="Go to overview"
            onClick={() => navigate(candidate ? 'My dashboard' : 'Overview')}
          >
            <Logo />
          </button>
          <button
            className="mobile-only icon-btn"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-switch-wrap">
          <button
            className={`workspace-switch ${workspaceOpen ? 'open' : ''}`}
            onClick={() => setWorkspaceOpen((v) => !v)}
          >
            <span className="workspace-mark">
              a<span>✳</span>
            </span>
            <span>
              <b>{user.tenant.name}</b>
              <small>{user.tenant.plan} workspace</small>
            </span>
            <ChevronsUpDown size={14} />
          </button>
          {workspaceOpen && (
            <div className="workspace-menu popover">
              <span className="eyebrow">YOUR WORKSPACE</span>
              <button
                onClick={() => {
                  setWorkspaceOpen(false);
                  navigate('Settings');
                }}
              >
                <span className="workspace-mark">
                  a<span>✳</span>
                </span>
                <span>
                  {user.tenant.name}
                  <small>{user.tenant.slug}</small>
                </span>
                <CheckCircle size={15} />
              </button>
              <p>One account, one company workspace.</p>
              <button onClick={logout}>
                <Plus size={15} />
                Sign in to another workspace
              </button>
            </div>
          )}
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="main-nav">
          {nav.map((n) => (
            <button
              key={n.name}
              className={currentPage === n.name ? 'active' : ''}
              onClick={() => navigate(n.name)}
            >
              <n.icon size={18} strokeWidth={1.65} />
              <span>{n.name}</span>
              {'count' in n && <span className="nav-count">{n.count}</span>}
              {'ai' in n && <span className="nav-ai">AI</span>}
            </button>
          ))}
        </nav>
        <div className="nav-section-label manage-label">MANAGE</div>
        <nav className="main-nav">
          {manageNav.map((n) => (
            <button
              key={n.name}
              className={currentPage === n.name ? 'active' : ''}
              onClick={() => navigate(n.name)}
            >
              <n.icon size={18} strokeWidth={1.65} />
              <span>{n.name}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="upgrade-card">
            <div className="upgrade-icon">
              <Zap size={19} fill="currentColor" />
            </div>
            <h3>A little AI. A lot of potential.</h3>
            <p>
              {candidate
                ? 'Practice with purpose. Walk into your next interview ready.'
                : 'Less busywork. More great hires. Unlock your team’s full potential.'}
            </p>
            <button onClick={() => navigate(candidate ? 'AI Interviews' : 'Billing & plans')}>
              {candidate ? 'Start practicing' : 'Explore plans'}
              <ArrowUpRight size={15} />
            </button>
            <span className="upgrade-decor" />
          </div>
          <button
            className={`help-link ${currentPage === 'Help & resources' ? 'active' : ''}`}
            onClick={() => navigate('Help & resources')}
          >
            <CircleHelp size={18} />
            Help & resources
            <ArrowUpRight size={14} />
          </button>
          <div className="sidebar-profile-wrap">
            {profileOpen && (
              <div className="profile-menu popover">
                <div>
                  <b>{user.name}</b>
                  <small>{user.email}</small>
                  <span>{candidate ? 'Candidate account' : 'Workspace administrator'}</span>
                </div>
                {session.demo && (
                  <button onClick={switchRole}>
                    <Users size={16} />
                    Try {candidate ? 'recruiter' : 'candidate'} view
                    <ArrowRight size={14} />
                  </button>
                )}
                <button onClick={() => navigate('Settings')}>
                  <Settings size={16} />
                  Account settings
                </button>
                <button onClick={logout}>
                  <LogOut size={16} />
                  Sign out
                </button>
              </div>
            )}
            <button className="sidebar-profile" onClick={() => setProfileOpen((v) => !v)}>
              <Avatar name={user.name} index={3} />
              <span>
                <b>{user.name}</b>
                <small>{candidate ? 'Candidate' : 'Workspace admin'}</small>
              </span>
              <ChevronsUpDown size={15} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="mobile-only icon-btn"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <Home size={16} />
            <ChevronRight size={13} />
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{currentPage}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="global-search"
              aria-label="Search workspace"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={16} />
              <span>Search anything…</span>
              <kbd>⌘ K</kbd>
            </button>
            <span className="top-divider" />
            <button
              className="icon-btn header-help"
              aria-label="Help and resources"
              onClick={() => navigate('Help & resources')}
            >
              <CircleHelp size={19} />
            </button>
            <div className="notification-wrap">
              <button
                className="icon-btn notification-button"
                aria-label="Notifications"
                onClick={() => {
                  setNotifications((v) => !v);
                  setNotificationRead(true);
                }}
              >
                <Bell size={19} />
                {!notificationRead && !candidate && activity.length > 0 && <i />}
              </button>
              {notifications && (
                <div className="notification-panel popover">
                  <div className="section-head">
                    <h3>Workspace activity</h3>
                    <button
                      className="icon-btn"
                      aria-label="Close notifications"
                      onClick={() => setNotifications(false)}
                    >
                      <X size={16} />
                    </button>
                  </div>
                  {(candidate ? [] : activity).slice(0, 6).map((a) => (
                    <div className="notification-item" key={a.id}>
                      <span className="insight-icon">
                        <Sparkles size={15} />
                      </span>
                      <div>
                        <b>{a.action.replaceAll('.', ' ').replaceAll('_', ' ')}</b>
                        <p>
                          {a.details.name || a.details.title || 'Your workspace is moving forward.'}
                          {a.details.status ? ` · ${a.details.status}` : ''}
                        </p>
                        <small>
                          {new Date(a.created_at).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </small>
                      </div>
                    </div>
                  ))}
                  {(candidate || !activity.length) && (
                    <div className="notification-empty">
                      <CheckCircle size={25} />
                      <p>You’re all caught up.</p>
                    </div>
                  )}
                  <div className="notification-footer">
                    <ShieldCheck size={13} />
                    Only activity from your workspace
                  </div>
                </div>
              )}
            </div>
            <button
              className="topbar-avatar"
              aria-label="Account settings"
              onClick={() => navigate('Settings')}
            >
              <Avatar name={user.name} size="small-avatar" index={3} />
            </button>
          </div>
        </header>
        <main className="main-content" key={currentPage}>
          {currentPage === 'Overview' && (
            <Dashboard
              user={user}
              navigate={navigate}
              onCreate={() => setJobForm(true)}
              onCandidate={openCandidate}
              onJob={openJob}
              notify={notify}
            />
          )}{' '}
          {currentPage === 'My dashboard' && (
            <CandidateHome
              user={user}
              navigate={navigate}
              onJob={openJob}
              onInterview={openInterview}
              notify={notify}
            />
          )}{' '}
          {['Jobs', 'Browse jobs'].includes(currentPage) && (
            <JobsPage candidate={!!candidate} create={() => setJobForm(true)} select={openJob} />
          )}{' '}
          {currentPage === 'Candidates' && <CandidatesPage onSelect={openCandidate} notify={notify} />}{' '}
          {currentPage === 'AI Interviews' && (
            <InterviewsPage candidate={!!candidate} onSelect={openInterview} notify={notify} />
          )}{' '}
          {currentPage === 'Analytics' && <AnalyticsPage notify={notify} />}{' '}
          {currentPage === 'My resume' && <ResumePage notify={notify} />}{' '}
          {['Settings', 'Team members', 'Billing & plans'].includes(currentPage) && (
            <SettingsPage
              key={currentPage}
              user={user}
              tab={currentPage}
              notify={notify}
              refreshUser={refreshUser}
            />
          )}{' '}
          {currentPage === 'Help & resources' && <HelpPage />}
        </main>
        <div className="demo-indicator">
          <span className="live-dot" />
          {session.demo ? 'Demo workspace' : 'Secure workspace'}
          <span>·</span>
          {session.ai_mode === 'Demo' ? 'Simulated AI' : 'OpenAI connected'}
        </div>
      </div>
      {jobForm && (
        <JobForm
          job={typeof jobForm === 'object' ? jobForm : undefined}
          close={() => setJobForm(false)}
          notify={notify}
        />
      )}{' '}
      {selectedJob && (
        <JobDetail
          job={selectedJob}
          user={user}
          close={() => setSelectedJob(null)}
          edit={() => {
            setJobForm(selectedJob);
            setSelectedJob(null);
          }}
          notify={notify}
          onCandidate={openCandidate}
        />
      )}{' '}
      {selectedCandidate && (
        <CandidateDetail
          application={selectedCandidate}
          close={() => setSelectedCandidate(null)}
          notify={notify}
          onInterview={openInterview}
        />
      )}{' '}
      {selectedInterview && (
        <InterviewDetail
          interview={selectedInterview}
          candidate={!!candidate}
          close={() => setSelectedInterview(null)}
          notify={notify}
        />
      )}{' '}
      {searchOpen && (
        <Modal
          title="A little help finding things."
          subtitle="Search your workspace’s jobs, people, and pages."
          onClose={() => {
            setSearchOpen(false);
            setSearch('');
          }}
        >
          <div className="search-modal">
            <div className="search-field">
              <Search size={20} />
              <input
                autoFocus
                placeholder="What are you looking for?"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>ESC</kbd>
            </div>
            <span className="eyebrow">QUICK NAVIGATION</span>
            <div className="search-results">
              {[...nav, ...manageNav]
                .filter((n) => n.name.toLowerCase().includes(search.toLowerCase()))
                .map((n) => (
                  <button
                    key={n.name}
                    onClick={() => {
                      navigate(n.name);
                      setSearchOpen(false);
                    }}
                  >
                    <n.icon size={18} />
                    <span>{n.name}</span>
                    <ArrowRight size={15} />
                  </button>
                ))}
            </div>
            {search.length > 1 && (
              <>
                <span className="eyebrow">JOBS</span>
                <div className="search-results">
                  {jobs
                    .filter((j) => j.title.toLowerCase().includes(search.toLowerCase()))
                    .slice(0, 5)
                    .map((j) => (
                      <button key={j.id} onClick={() => openJob(j)}>
                        <BriefcaseBusiness size={18} />
                        <span>
                          {j.title}
                          <small>
                            {j.department} · {j.location}
                          </small>
                        </span>
                        <ArrowUpRight size={15} />
                      </button>
                    ))}
                </div>
                {!candidate && (
                  <>
                    <span className="eyebrow">CANDIDATES</span>
                    <div className="search-results">
                      {applications
                        .filter((a) => a.name.toLowerCase().includes(search.toLowerCase()))
                        .slice(0, 5)
                        .map((a) => (
                          <button key={a.id} onClick={() => openCandidate(a)}>
                            <Avatar name={a.name} />
                            <span>
                              {a.name}
                              <small>{a.job_title}</small>
                            </span>
                            <ArrowUpRight size={15} />
                          </button>
                        ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle size={19} />
          <span>{toast}</span>
          <button aria-label="Dismiss notification" onClick={() => setToast('')}>
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
