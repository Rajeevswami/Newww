import { useState, type FormEvent } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  ArrowRight,
  Check,
  CreditCard,
  ExternalLink,
  FileText,
  HeartHandshake,
  Settings2,
  Shield,
  Sparkles,
  Users,
} from 'lucide-react';
import { api, post, type User } from '../api/client';
import { Avatar, Badge, CheckItem, PageHeading } from '../components/ui';
export default function SettingsPage({
  user,
  tab: initial,
  notify,
  refreshUser,
}: {
  user: User;
  tab: string;
  notify: (s: string) => void;
  refreshUser: () => void;
}) {
  const [tab, setTab] = useState(
    initial === 'Billing & plans'
      ? 'Billing & plans'
      : initial === 'Team members'
        ? 'Team members'
        : 'General',
  );
  const [name, setName] = useState(user.tenant.name);
  const { data: team = [] } = useQuery({
    queryKey: ['team'],
    queryFn: () => api<User[]>('/team'),
    enabled: user.role !== 'candidate',
  });
  const mutation = useMutation({
    mutationFn: () => api('/workspace', { method: 'PUT', body: JSON.stringify({ name }) }),
    onSuccess: () => {
      notify('Workspace settings saved');
      refreshUser();
    },
    onError: (e: Error) => notify(e.message),
  });
  const billing = useMutation({
    mutationFn: () => post<{ url: string }>('/billing/create-checkout-session'),
    onSuccess: (r) => {
      window.location.href = r.url;
    },
    onError: (e: Error) => notify(e.message),
  });
  return (
    <>
      <PageHeading
        title="A workspace that works for you."
        description="Your team, your preferences, your next stage of growth."
      />
      <div className="settings-layout">
        <div className="settings-tabs">
          {[
            'General',
            ...(user.role !== 'candidate' ? ['Team members', 'Billing & plans'] : []),
            'Security',
          ].map((t) => (
            <button className={tab === t ? 'active' : ''} onClick={() => setTab(t)} key={t}>
              {t === 'General' ? (
                <Settings2 size={17} />
              ) : t === 'Team members' ? (
                <Users size={17} />
              ) : t === 'Security' ? (
                <Shield size={17} />
              ) : (
                <CreditCard size={17} />
              )}{' '}
              {t}
            </button>
          ))}
        </div>
        <div>
          {tab === 'General' ? (
            <section className="card">
              <div className="section-head">
                <div>
                  <h2>Workspace details</h2>
                  <p>A little about the place your team calls home.</p>
                </div>
              </div>
              <form
                className="form"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  mutation.mutate();
                }}
              >
                <div className="workspace-profile">
                  <span className="workspace-mark">
                    a<span>✳</span>
                  </span>
                  <div>
                    <h3>{user.tenant.name}</h3>
                    <span>{user.tenant.plan} workspace</span>
                  </div>
                  <Badge status="active">Active</Badge>
                </div>
                <label>
                  Workspace name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    minLength={2}
                    maxLength={100}
                    required
                    disabled={user.role !== 'tenant_admin'}
                  />
                </label>
                <label>
                  Workspace slug
                  <input value={user.tenant.slug} disabled />
                  <small>Share this slug with candidates when they create an account.</small>
                </label>
                <div className="form-row">
                  <label>
                    Your name
                    <input value={user.name} disabled />
                  </label>
                  <label>
                    Email address
                    <input value={user.email} disabled />
                  </label>
                </div>
                {user.role === 'tenant_admin' && (
                  <div className="form-actions">
                    <button className="btn primary" disabled={mutation.isPending}>
                      {mutation.isPending ? 'Saving…' : 'Save changes'}
                      <Check size={15} />
                    </button>
                  </div>
                )}
              </form>
            </section>
          ) : tab === 'Team members' ? (
            <section className="card">
              <div className="section-head">
                <div>
                  <h2>Good work starts with good people.</h2>
                  <p>Your workspace’s recruiting team.</p>
                </div>
                <span className="count-chip">{team.length}</span>
              </div>
              <div className="team-list">
                {team.map((u, i) => (
                  <div key={u.id}>
                    <Avatar name={u.name} index={i} />
                    <div>
                      <b>{u.name}</b>
                      <small>{u.email}</small>
                    </div>
                    <span className="role-tag">
                      {u.role === 'tenant_admin' ? 'Workspace admin' : 'Recruiter'}
                    </span>
                    {u.id === user.id && <span className="tiny-tag">YOU</span>}
                  </div>
                ))}
              </div>
              <div className="table-footer">
                <Shield size={14} />
                Team invitations and granular role management are planned for a future release.
              </div>
            </section>
          ) : tab === 'Security' ? (
            <section className="card">
              <div className="section-head">
                <div>
                  <h2>Trust is built in.</h2>
                  <p>The foundations keeping your workspace protected.</p>
                </div>
                <Shield size={22} />
              </div>
              <div className="detail-body">
                <CheckItem>Short-lived access tokens and rotating refresh sessions</CheckItem>
                <CheckItem>Tenant-scoped data access on every workspace request</CheckItem>
                <CheckItem>Bcrypt password hashing and auth rate limits</CheckItem>
                <CheckItem>Role-based permissions for candidates and recruiters</CheckItem>
                <div className="ai-note">
                  <Shield size={19} />
                  <span>
                    Email status:{' '}
                    {user.is_verified ? 'Verified' : 'Not yet verified. Check your verification email.'}
                  </span>
                </div>
                <p className="muted">
                  Need to reset your password? Sign out and choose “Forgot password” on the sign-in page.
                </p>
              </div>
            </section>
          ) : (
            <>
              <div className="billing-banner">
                <Sparkles size={25} />
                <div>
                  <h2>Room for your next big chapter.</h2>
                  <p>
                    You’re currently on the <b>{user.tenant.plan}</b> plan. Find the right fit for your team.
                  </p>
                </div>
              </div>
              <div className="pricing-grid">
                {[
                  {
                    name: 'Free',
                    price: '0',
                    tagline: 'For your first great hire.',
                    features: [
                      '3 active job openings',
                      'Candidate management',
                      'Resume uploads',
                      'Basic hiring analytics',
                    ],
                  },
                  {
                    name: 'Pro',
                    price: '49',
                    tagline: 'For teams finding their stride.',
                    features: [
                      'Unlimited active jobs',
                      'Adaptive AI interviews',
                      'AI candidate matching',
                      'Scorecards & transcripts',
                    ],
                  },
                  {
                    name: 'Enterprise',
                    price: 'Custom',
                    tagline: 'Built around your ambitions.',
                    features: [
                      'Custom deployment planning',
                      'Dedicated onboarding',
                      'Enterprise API (planned)',
                      'Advanced controls (planned)',
                    ],
                  },
                ].map((plan) => (
                  <div
                    className={`card pricing-card ${plan.name === 'Pro' ? 'recommended' : ''}`}
                    key={plan.name}
                  >
                    {plan.name === 'Pro' && <span className="popular-tag">A LITTLE MORE POSSIBILITY</span>}
                    <h3>{plan.name}</h3>
                    <p>{plan.tagline}</p>
                    <div className="price">
                      {plan.price !== 'Custom' && <sup>$</sup>}
                      {plan.price}
                      {plan.price !== 'Custom' && <small>/ month</small>}
                    </div>
                    <button
                      className={`btn ${plan.name === 'Pro' ? 'primary' : 'secondary'}`}
                      disabled={
                        user.tenant.plan === plan.name ||
                        plan.name === 'Free' ||
                        billing.isPending ||
                        user.role !== 'tenant_admin'
                      }
                      onClick={() =>
                        plan.name === 'Enterprise'
                          ? notify(
                              'Enterprise is not yet available. Self-hosting instructions are included in the project README.',
                            )
                          : billing.mutate()
                      }
                    >
                      {user.tenant.plan === plan.name ? (
                        <>
                          <Check size={15} />
                          Current plan
                        </>
                      ) : plan.name === 'Enterprise' ? (
                        'Explore enterprise'
                      ) : (
                        'Upgrade to Pro'
                      )}
                      {user.tenant.plan !== plan.name && plan.name !== 'Free' && <ArrowRight size={15} />}
                    </button>
                    <div className="plan-features">
                      {plan.features.map((f) => (
                        <CheckItem key={f}>{f}</CheckItem>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <p className="billing-disclaimer">
                <Shield size={14} />
                Demo workspace: no payments will be taken. Live billing requires configured Stripe keys and a
                price.
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
export function HelpPage() {
  return (
    <>
      <PageHeading
        title="A little guidance goes a long way."
        description="Everything you need to make your next great hire—or your next great move."
      />
      <div className="help-grid">
        {[
          {
            icon: BriefcaseIcon,
            title: 'Build your talent pipeline',
            body: 'Post an active job with the skills that matter. Candidates in your workspace can upload a resume and apply. Their match scores appear automatically in your ranked candidate list.',
          },
          {
            icon: Sparkles,
            title: 'Meet your AI copilot',
            body: 'The interview assistant asks five adaptive questions based on the role and resume. Every conversation is saved, and a feedback report is generated when the interview is complete.',
          },
          {
            icon: Users,
            title: 'Try both sides of hiring',
            body: 'In the demo, use the profile menu at the bottom left to switch between recruiter and candidate. Candidate mode lets you upload a resume, apply for roles, and practice interviews.',
          },
          {
            icon: Shield,
            title: 'Your workspace, your data',
            body: 'Every account belongs to a company workspace. Data access is scoped to that workspace. AI scores support thoughtful human review; they are never autonomous hiring decisions.',
          },
        ].map((c) => (
          <div className="card help-card" key={c.title}>
            <span className="insight-icon">
              <c.icon size={23} />
            </span>
            <h2>{c.title}</h2>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
      <div className="card help-api">
        <FileText size={25} />
        <div>
          <h2>Built for the curious.</h2>
          <p>Explore the interactive API documentation, request schemas, and endpoints.</p>
        </div>
        <a className="btn secondary" href="/api/docs" target="_blank" rel="noreferrer">
          API documentation <ExternalLink size={15} />
        </a>
      </div>
    </>
  );
}
function BriefcaseIcon(props: { size?: number }) {
  return <HeartHandshake {...props} />;
}
