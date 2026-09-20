import { useState, type FormEvent } from 'react';
import { ArrowRight, CheckCircle, ShieldCheck, Sparkles } from 'lucide-react';
import { Logo } from '../components/ui';
import { post, type Session } from '../api/client';
export default function Auth({
  onSession,
  demoEnabled,
}: {
  onSession: (session: Session) => void;
  demoEnabled: boolean;
}) {
  const params = new URLSearchParams(window.location.search);
  const [mode, setMode] = useState(
    params.get('action') === 'reset' ? 'reset' : params.get('action') === 'verify' ? 'verify' : 'login',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [role, setRole] = useState('tenant_admin');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try {
      if (mode === 'forgot') {
        const result = await post('/auth/forgot-password', values);
        if (result.reset_token) {
          window.history.replaceState(null, '', `?action=reset&token=${result.reset_token}`);
          setMode('reset');
          setMessage('Demo mode: use this form to choose a new password.');
        } else setMessage(result.message);
      } else if (mode === 'reset' || mode === 'verify') {
        const result = await post(mode === 'reset' ? '/auth/reset-password' : '/auth/verify-email', {
          ...values,
          token: params.get('token'),
        });
        setMessage(result.message);
        window.history.replaceState(null, '', '/');
        setMode('login');
      } else {
        const session = await post<Session>(`/auth/${mode}`, {
          ...values,
          ...(mode === 'signup' ? { role } : {}),
        });
        if (session.verification_token) {
          await post('/auth/verify-email', { token: session.verification_token });
          session.user.is_verified = true;
        }
        onSession(session);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <aside className="auth-story">
        <Logo />
        <div>
          <span className="eyebrow">GOOD PEOPLE. GREAT POSSIBILITIES.</span>
          <h1>
            The right match
            <br />
            changes everything.
          </h1>
          <p>
            A more thoughtful way to hire.
            <br />A more confident way to take your next step.
          </p>
          <div className="auth-art">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <Sparkles size={95} strokeWidth={1.2} />
          </div>
          <div className="auth-benefits">
            <span>
              <CheckCircle size={17} />
              Find the right potential
            </span>
            <span>
              <CheckCircle size={17} />
              Make every conversation count
            </span>
            <span>
              <CheckCircle size={17} />
              Keep people at the center
            </span>
          </div>
        </div>
        <small>YOUR NEXT GREAT CHAPTER STARTS HERE.</small>
      </aside>
      <main className="auth-main">
        <form onSubmit={submit} className="auth-form">
          <span className="auth-spark">
            <Sparkles size={26} />
          </span>
          <h2>
            {mode === 'signup'
              ? 'Great things start here.'
              : mode === 'forgot'
                ? 'Let’s get you back in.'
                : mode === 'reset'
                  ? 'A fresh start.'
                  : mode === 'verify'
                    ? 'One last little step.'
                    : 'Good to have you back.'}
          </h2>
          <p>
            {mode === 'signup'
              ? 'Create your SmartHire account.'
              : mode === 'forgot'
                ? 'We’ll send a reset link to your email.'
                : mode === 'reset'
                  ? 'Choose a strong new password.'
                  : mode === 'verify'
                    ? 'Confirm your email to complete your profile.'
                    : 'Sign in to your SmartHire workspace.'}
          </p>
          {mode === 'signup' && (
            <>
              <div className="role-selector">
                <button
                  type="button"
                  className={role === 'tenant_admin' ? 'active' : ''}
                  onClick={() => setRole('tenant_admin')}
                >
                  I’m hiring
                </button>
                <button
                  type="button"
                  className={role === 'candidate' ? 'active' : ''}
                  onClick={() => setRole('candidate')}
                >
                  I’m a candidate
                </button>
              </div>
              <label>
                Your name
                <input name="name" autoComplete="name" required placeholder="Alex Morgan" minLength={2} />
              </label>
              {role === 'tenant_admin' && (
                <label>
                  Company name
                  <input name="company" required placeholder="Acme Studio" />
                </label>
              )}
            </>
          )}
          {!['reset', 'verify'].includes(mode) && (
            <>
              <label>
                Workspace slug
                <input
                  name="workspace"
                  placeholder="acme"
                  defaultValue={demoEnabled ? 'acme' : ''}
                  pattern="[a-z0-9\-]{2,80}"
                  required
                />
                <small>
                  {mode === 'signup' && role === 'tenant_admin'
                    ? 'Choose a unique lowercase workspace address.'
                    : 'Ask your team for their workspace slug.'}
                </small>
              </label>
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  required
                />
              </label>
            </>
          )}
          {!['forgot', 'verify'].includes(mode) && (
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={8}
                maxLength={72}
                placeholder="At least 8 characters"
                required
              />
            </label>
          )}
          {mode === 'login' && (
            <button
              type="button"
              className="forgot-link"
              onClick={() => {
                setMode('forgot');
                setError('');
              }}
            >
              Forgot password?
            </button>
          )}
          {error && <div className="error-banner">{error}</div>}
          {message && <div className="success-banner">{message}</div>}
          <button className="btn primary auth-submit" disabled={busy}>
            {busy
              ? 'One moment…'
              : mode === 'signup'
                ? 'Create account'
                : mode === 'forgot'
                  ? 'Send reset link'
                  : mode === 'reset'
                    ? 'Reset password'
                    : mode === 'verify'
                      ? 'Verify email'
                      : 'Sign in'}
            <ArrowRight size={16} />
          </button>
          <p className="auth-switch">
            {mode === 'login' ? 'New to SmartHire?' : 'Already have an account?'}{' '}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'signup' : 'login');
                setError('');
                setMessage('');
              }}
            >
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
          {demoEnabled && (
            <>
              <div className="auth-divider">
                <span>or take a look around</span>
              </div>
              <button
                type="button"
                className="btn secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    onSession(await post<Session>('/auth/demo'));
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <Sparkles size={16} />
                Explore the demo workspace
              </button>
            </>
          )}
          <small className="auth-security">
            <ShieldCheck size={13} />
            Your next chapter is in safe hands.
          </small>
        </form>
      </main>
    </div>
  );
}
