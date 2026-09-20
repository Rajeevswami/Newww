import { useState, useRef, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  Calendar,
  Check,
  CircleCheck,
  Clock,
  FileText,
  MapPin,
  Pencil,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
  Video,
} from 'lucide-react';
import {
  api,
  post,
  exportCSV,
  type Analytics,
  type Application,
  type Interview,
  type Job,
  type Resume,
  type User,
} from '../api/client';
import {
  Avatar,
  Badge,
  CheckItem,
  dateLabel,
  Empty,
  Loading,
  Match,
  Modal,
  PageHeading,
} from '../components/ui';
import { AnalyticsPanels, ApplicationsTable } from './Dashboard';
type Notify = (message: string) => void;
export function JobForm({ job, close, notify }: { job?: Job; close: () => void; notify: Notify }) {
  const qc = useQueryClient();
  const [error, setError] = useState('');
  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api(job ? `/jobs/${job.id}` : '/jobs', { method: job ? 'PUT' : 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries();
      notify(job ? 'Job updated successfully' : 'Your new job is live. Let’s find someone great.');
      close();
    },
    onError: (e: Error) => setError(e.message),
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    mutation.mutate({
      ...f,
      required_skills: String(f.required_skills)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    });
  }
  return (
    <Modal
      title={job ? 'Edit your job' : 'Find your next great hire'}
      subtitle={
        job ? 'Keep the opportunity up to date.' : 'A great job description is the start of a great match.'
      }
      onClose={close}
      wide
    >
      <form onSubmit={submit} className="form">
        <div className="form-row">
          <label>
            Job title
            <input
              name="title"
              placeholder="e.g. Senior Product Designer"
              defaultValue={job?.title}
              required
              minLength={3}
              maxLength={150}
            />
          </label>
          <label>
            Department
            <select name="department" defaultValue={job?.department || 'Design'}>
              {['Design', 'Engineering', 'Product', 'Marketing', 'Data', 'Operations'].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Location
            <input
              name="location"
              placeholder="e.g. Remote"
              defaultValue={job?.location || 'Remote'}
              required
              maxLength={100}
            />
          </label>
          <label>
            Employment type
            <select name="employment_type" defaultValue={job?.employment_type || 'Full-time'}>
              {['Full-time', 'Part-time', 'Contract'].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Experience level
            <select name="experience_level" defaultValue={job?.experience_level || 'Mid-level'}>
              {['Entry-level', 'Mid-level', 'Senior', 'Lead'].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
          <label>
            Salary range <span className="muted">(optional)</span>
            <input name="salary" placeholder="$100k – $140k" defaultValue={job?.salary} maxLength={100} />
          </label>
        </div>
        <label>
          Required skills
          <input
            name="required_skills"
            placeholder="Figma, User research, Design systems"
            defaultValue={job?.required_skills.join(', ')}
            required
          />
          <small>Separate each skill with a comma. We’ll use these to find your best matches.</small>
        </label>
        <label>
          Job description
          <textarea
            name="description"
            rows={6}
            placeholder="Tell candidates about the role, what they’ll do, and what makes your team special…"
            defaultValue={job?.description}
            minLength={30}
            maxLength={15000}
            required
          />
        </label>
        <label>
          Visibility
          <select name="status" defaultValue={job?.status || 'active'}>
            <option value="active">Active — accepting applications</option>
            <option value="draft">Draft — only visible to your team</option>
            <option value="closed">Closed — no new applications</option>
          </select>
        </label>
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-footer">
          <span>
            <ShieldCheck size={15} />
            Only visible in your workspace
          </span>
          <button type="button" className="btn secondary" onClick={close}>
            Cancel
          </button>
          <button className="btn primary" disabled={mutation.isPending}>
            <Plus size={16} />
            {mutation.isPending ? 'Saving…' : job ? 'Save changes' : 'Publish job'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
export function JobsPage({
  candidate,
  create,
  select,
}: {
  candidate: boolean;
  create: () => void;
  select: (job: Job) => void;
}) {
  const { data: jobs = [], isLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/jobs') });
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('active');
  const [department, setDepartment] = useState('All departments');
  const filtered = jobs.filter(
    (j) =>
      (candidate || tab === 'all' || j.status === tab) &&
      `${j.title} ${j.required_skills.join(' ')}`.toLowerCase().includes(search.toLowerCase()) &&
      (department === 'All departments' || j.department === department),
  );
  return (
    <>
      <PageHeading
        title={candidate ? 'Find your next chapter.' : 'Make room for great talent.'}
        description={
          candidate
            ? 'Explore opportunities that match your skills, interests, and ambition.'
            : 'Your open roles. Their next big opportunity.'
        }
      >
        {!candidate && (
          <button className="btn primary" onClick={create}>
            <Plus size={16} />
            Post a job
          </button>
        )}
      </PageHeading>
      <div className="card workspace-list">
        <div className="list-toolbar">
          <div className="list-tabs">
            {(candidate ? ['active'] : ['active', 'draft', 'closed', 'all']).map((t) => (
              <button className={tab === t ? 'active' : ''} key={t} onClick={() => setTab(t)}>
                {t === 'all' ? 'All jobs' : t.charAt(0).toUpperCase() + t.slice(1)}
                <span>{jobs.filter((j) => t === 'all' || j.status === t).length}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="filters">
          <div className="search-field">
            <Search size={16} />
            <input
              placeholder="Search job title or skill…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            aria-label="Filter by department"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            <option>All departments</option>
            {[...new Set(jobs.map((j) => j.department))].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          <span className="muted filter-count">{filtered.length} opportunities</span>
        </div>
      </div>
      {isLoading ? (
        <Loading />
      ) : !filtered.length ? (
        <Empty title="No roles found" description="Try a different search or create a new opportunity." />
      ) : (
        <div className="job-grid">
          {filtered.map((j) => (
            <button className="card job-card" key={j.id} onClick={() => select(j)}>
              <div className="job-card-top">
                <span className={`department-icon dept-${j.department.toLowerCase()}`}>
                  <BriefcaseBusiness size={21} />
                </span>
                <Badge status={j.status} />
              </div>
              <span className="eyebrow">{j.department}</span>
              <h2>{j.title}</h2>
              <div className="job-meta">
                <span>
                  <MapPin size={13} />
                  {j.location}
                </span>
                <i />
                {j.employment_type}
              </div>
              <p>{j.description.slice(0, 150)}…</p>
              <div className="skill-tags">
                {j.required_skills.slice(0, 3).map((s) => (
                  <span key={s}>{s}</span>
                ))}
                {j.required_skills.length > 3 && <span>+{j.required_skills.length - 3}</span>}
              </div>
              <div className="job-card-bottom">
                <span>{j.salary || j.experience_level}</span>
                <span>
                  {candidate ? 'View opportunity' : `${j.applicants} applicants`}
                  <ArrowUpRight size={15} />
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  );
}
export function JobDetail({
  job,
  user,
  close,
  edit,
  notify,
  onCandidate,
}: {
  job: Job;
  user: User;
  close: () => void;
  edit: () => void;
  notify: Notify;
  onCandidate: (a: Application) => void;
}) {
  const candidate = user.role === 'candidate';
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const { data: matches = [] } = useQuery({
    queryKey: ['matches', job.id],
    queryFn: () => api<Application[]>(`/jobs/${job.id}/matches`),
    enabled: !candidate,
  });
  const { data: apps = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
    enabled: candidate,
  });
  const applied = apps.some((a) => a.job_id === job.id);
  const apply = useMutation({
    mutationFn: () => post(`/applications/${job.id}/apply`),
    onSuccess: () => {
      qc.invalidateQueries();
      notify('Application sent. Your next chapter starts here.');
    },
    onError: (e: Error) => notify(e.message),
  });
  const archive = useMutation({
    mutationFn: () => api(`/jobs/${job.id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries();
      notify('Job closed. Existing applications have been preserved.');
      close();
    },
    onError: (e: Error) => notify(e.message),
  });
  return (
    <Modal
      title={job.title}
      subtitle={`${job.department} · ${job.location} · ${job.employment_type}`}
      onClose={close}
      wide
    >
      <div className="detail-body">
        <div className="detail-summary">
          <Badge status={job.status} />
          <span>{job.salary}</span>
          <span>{job.experience_level}</span>
        </div>
        <div className="skill-tags">
          {job.required_skills.map((s) => (
            <span key={s}>{s}</span>
          ))}
        </div>
        <h3>About the opportunity</h3>
        <p className="job-description">{job.description}</p>
        {!candidate && (
          <>
            <div className="section-head">
              <h3>Matched candidates</h3>
              <span className="count-chip">{matches.length}</span>
            </div>
            {matches.length ? (
              <div className="match-list">
                {matches.slice(0, 6).map((a, i) => (
                  <button key={a.id} onClick={() => onCandidate(a)}>
                    <Avatar name={a.name} index={i} />
                    <span>
                      <b>{a.name}</b>
                      <small>{a.status}</small>
                    </span>
                    <Match value={a.match_score} />
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted">No applications yet. Your role is ready for the right person.</p>
            )}
          </>
        )}
      </div>
      <div className="modal-footer">
        {candidate ? (
          <>
            <span>
              <ShieldCheck size={15} />
              Your latest resume will be shared
            </span>
            <button
              className="btn primary"
              disabled={applied || apply.isPending}
              onClick={() => apply.mutate()}
            >
              {applied ? <Check size={16} /> : <Send size={16} />}{' '}
              {applied ? 'Applied' : apply.isPending ? 'Sending…' : 'Apply for this role'}
            </button>
          </>
        ) : (
          <>
            <button className="btn secondary" onClick={edit}>
              <Pencil size={15} />
              Edit job
            </button>
            {job.status !== 'closed' && (
              <button
                className={`btn ${confirm ? 'danger' : 'secondary'}`}
                disabled={archive.isPending}
                onClick={() => (confirm ? archive.mutate() : setConfirm(true))}
              >
                {confirm ? 'Confirm close job' : 'Close job'}
              </button>
            )}
            <span className="muted">Posted {dateLabel(job.created_at)}</span>
          </>
        )}
      </div>
    </Modal>
  );
}
export function CandidatesPage({ onSelect, notify }: { onSelect: (a: Application) => void; notify: Notify }) {
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
  });
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('All candidates');
  const [score, setScore] = useState(0);
  const [page, setPage] = useState(1);
  const filtered = rows.filter(
    (a) =>
      `${a.name} ${a.email} ${a.job_title}`.toLowerCase().includes(search.toLowerCase()) &&
      (status === 'All candidates' || a.status === status) &&
      a.match_score >= score,
  );
  const resetPage = () => setPage(1);
  return (
    <>
      <PageHeading
        title="Great people. Better possibilities."
        description="Meet your talent pool, intelligently matched to your open roles."
      >
        <button
          className="btn secondary"
          disabled={!filtered.length}
          onClick={() => {
            exportCSV(
              filtered.map((a) => ({
                name: a.name,
                email: a.email,
                role: a.job_title,
                match: a.match_score,
                status: a.status,
              })),
              'smarthire-candidates.csv',
            );
            notify('Candidate list exported');
          }}
        >
          <ArrowDownToLine size={15} />
          Export candidates
        </button>
      </PageHeading>
      <div className="ai-note">
        <Sparkles size={17} />
        <span>AI helps you discover potential. You make the final hiring decision.</span>
      </div>
      <section className="card">
        <div className="list-tabs bordered">
          {['All candidates', 'New', 'Shortlisted', 'Interview', 'Hired'].map((t) => (
            <button
              className={status === t ? 'active' : ''}
              onClick={() => {
                setStatus(t);
                resetPage();
              }}
              key={t}
            >
              {t}
              <span>{rows.filter((a) => t === 'All candidates' || a.status === t).length}</span>
            </button>
          ))}
        </div>
        <div className="filters">
          <div className="search-field">
            <Search size={16} />
            <input
              placeholder="Search by name, email, or role…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                resetPage();
              }}
            />
          </div>
          <select
            aria-label="Minimum match score"
            value={score}
            onChange={(e) => {
              setScore(Number(e.target.value));
              resetPage();
            }}
          >
            <option value={0}>All match scores</option>
            <option value={90}>90%+ · Exceptional</option>
            <option value={80}>80%+ · Strong match</option>
            <option value={70}>70%+ · Good match</option>
          </select>
          <select
            aria-label="Candidate status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              resetPage();
            }}
          >
            {['All candidates', 'New', 'Screening', 'Interview', 'Shortlisted', 'Hired', 'Rejected'].map(
              (s) => (
                <option key={s}>{s}</option>
              ),
            )}
          </select>
        </div>
        {isLoading ? (
          <Loading />
        ) : (
          <ApplicationsTable rows={filtered.slice((page - 1) * 10, page * 10)} onSelect={onSelect} />
        )}
        <div className="pagination">
          <span>
            Showing {filtered.length ? (page - 1) * 10 + 1 : 0}–{Math.min(page * 10, filtered.length)} of{' '}
            {filtered.length} applications
          </span>
          <div>
            <button className="btn secondary" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              {page} / {Math.max(1, Math.ceil(filtered.length / 10))}
            </span>
            <button
              className="btn secondary"
              disabled={page * 10 >= filtered.length}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
export function CandidateDetail({
  application: initial,
  close,
  notify,
  onInterview,
}: {
  application: Application;
  close: () => void;
  notify: Notify;
  onInterview: (i: Interview) => void;
}) {
  const qc = useQueryClient();
  const [status, setStatus] = useState(initial.status);
  const { data: interviews = [] } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => api<Interview[]>('/interviews'),
  });
  const mutation = useMutation({
    mutationFn: (next: string) =>
      api(`/applications/${initial.id}`, { method: 'PATCH', body: JSON.stringify({ status: next }) }),
    onSuccess: (_, next) => {
      setStatus(next);
      qc.invalidateQueries();
      notify(`${initial.name.split(' ')[0]} moved to ${next.toLowerCase()}`);
    },
    onError: (e: Error) => notify(e.message),
  });
  const interview = interviews.find((i) => i.application_id === initial.id);
  return (
    <Modal
      title="Candidate profile"
      subtitle="Look beyond the resume. Discover the person."
      onClose={close}
      wide
    >
      <div className="detail-body">
        <div className="candidate-profile-head">
          <Avatar name={initial.name} size="large" />
          <div>
            <h2>{initial.name}</h2>
            <p>{initial.email}</p>
            <span>{initial.job_title}</span>
          </div>
          <div className="large-match">
            <Sparkles size={17} />
            <strong>{initial.match_score}%</strong>
            <small>AI match</small>
          </div>
        </div>
        <div className="detail-summary">
          <Badge status={status} />
          <span>
            <Calendar size={14} />
            Applied {dateLabel(initial.created_at)}
          </span>
        </div>
        <h3>A little about {initial.name.split(' ')[0]}</h3>
        <p>{initial.resume.summary}</p>
        <h3>Skills & expertise</h3>
        <div className="skill-tags">
          {initial.resume.skills.map((s) => (
            <span key={s}>{s}</span>
          ))}
        </div>
        <div className="profile-columns">
          <div>
            <h3>Experience</h3>
            {initial.resume.experience.length ? (
              initial.resume.experience.map((s) => (
                <p key={s} className="bullet-copy">
                  {s}
                </p>
              ))
            ) : (
              <p className="muted">Not provided</p>
            )}
          </div>
          <div>
            <h3>Education</h3>
            {initial.resume.education.length ? (
              initial.resume.education.map((s) => (
                <p key={s} className="bullet-copy">
                  {s}
                </p>
              ))
            ) : (
              <p className="muted">Not provided</p>
            )}
          </div>
        </div>
        {interview && (
          <button className="interview-link" onClick={() => onInterview(interview)}>
            <span className="insight-icon">
              <Video size={21} />
            </span>
            <div>
              <b>Get the full conversation</b>
              <p>
                View interview transcript{' '}
                {interview.scorecard_json
                  ? `and scorecard · ${interview.scorecard_json.overall_score}/100`
                  : ''}
              </p>
            </div>
            <ArrowRight size={19} />
          </button>
        )}
        <div className="ai-note small">
          <ShieldCheck size={17} />
          Match scores are decision support, not hiring recommendations.
        </div>
      </div>
      <div className="modal-footer">
        <label className="inline-label">
          Move to
          <select
            aria-label="Change candidate status"
            value={status}
            disabled={mutation.isPending}
            onChange={(e) => mutation.mutate(e.target.value)}
          >
            {['New', 'Screening', 'Interview', 'Shortlisted', 'Hired', 'Rejected'].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <button
          className="btn primary"
          disabled={status === 'Shortlisted' || mutation.isPending}
          onClick={() => mutation.mutate('Shortlisted')}
        >
          <CircleCheck size={16} />
          {status === 'Shortlisted' ? 'Shortlisted' : 'Shortlist candidate'}
        </button>
      </div>
    </Modal>
  );
}
export function InterviewsPage({
  candidate,
  onSelect,
  notify,
}: {
  candidate: boolean;
  onSelect: (i: Interview) => void;
  notify: Notify;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState('All interviews');
  const [search, setSearch] = useState('');
  const [starting, setStarting] = useState(false);
  const [applicationId, setApplicationId] = useState('');
  const { data: interviews = [], isLoading } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => api<Interview[]>('/interviews'),
  });
  const { data: apps = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
    enabled: candidate,
  });
  const start = useMutation({
    mutationFn: () => post<Interview>('/interviews/start', { application_id: applicationId }),
    onSuccess: (i) => {
      qc.invalidateQueries({ queryKey: ['interviews'] });
      setStarting(false);
      onSelect(i);
    },
    onError: (e: Error) => notify(e.message),
  });
  const rows = interviews.filter(
    (i) =>
      `${i.name} ${i.job_title}`.toLowerCase().includes(search.toLowerCase()) &&
      (tab === 'All interviews' ||
        (tab === 'Completed' ? i.status === 'completed' : i.status !== 'completed')),
  );
  return (
    <>
      <PageHeading
        title={candidate ? 'A little practice. A lot of confidence.' : 'Meaningful conversations, at scale.'}
        description={
          candidate
            ? 'Practice with an adaptive interviewer and get actionable feedback.'
            : 'Explore interview transcripts and discover what makes each candidate unique.'
        }
      >
        {candidate && (
          <button className="btn primary" onClick={() => setStarting(true)}>
            <Plus size={16} />
            Practice interview
          </button>
        )}
      </PageHeading>
      <div className="interview-stats">
        <div className="card">
          <Video />
          <div>
            <strong>{interviews.length}</strong>
            <span>Total interviews</span>
          </div>
        </div>
        <div className="card">
          <CircleCheck />
          <div>
            <strong>{interviews.filter((i) => i.status === 'completed').length}</strong>
            <span>Completed conversations</span>
          </div>
        </div>
        <div className="card">
          <Clock />
          <div>
            <strong>{interviews.filter((i) => i.status !== 'completed').length}</strong>
            <span>In progress</span>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="list-tabs bordered">
          {['All interviews', 'Completed', 'In progress'].map((t) => (
            <button className={tab === t ? 'active' : ''} key={t} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="filters">
          <div className="search-field">
            <Search size={16} />
            <input
              placeholder="Search interviews…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        {isLoading ? (
          <Loading />
        ) : !rows.length ? (
          <Empty
            title="Your next conversation is waiting"
            description={
              candidate
                ? 'Apply to a role, then start a practice interview tailored to it.'
                : 'Completed candidate interviews will appear here.'
            }
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{candidate ? 'Interview' : 'Candidate'}</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((i, idx) => (
                  <tr key={i.id} onClick={() => onSelect(i)}>
                    <td>
                      <div className="person">
                        <Avatar name={i.name || 'You'} index={idx} />
                        <span>
                          <button className="name-button" onClick={() => onSelect(i)}>
                            {i.name || 'Practice interview'}
                          </button>
                          <small>Adaptive AI interview</small>
                        </span>
                      </div>
                    </td>
                    <td>{i.job_title || 'Role-specific interview'}</td>
                    <td>
                      <Badge status={i.status === 'completed' ? 'Completed' : 'Interview'}>
                        {i.status === 'completed' ? 'Completed' : 'In progress'}
                      </Badge>
                    </td>
                    <td>
                      {i.scorecard_json ? (
                        <span className="score-number">
                          {i.scorecard_json.overall_score}
                          <small>/100</small>
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="muted">{dateLabel(i.started_at)}</td>
                    <td>
                      <button className="icon-btn" aria-label="Open interview">
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {starting && (
        <Modal
          title="Your next step starts here"
          subtitle="Choose an application. We’ll tailor five questions to the role and your resume."
          onClose={() => setStarting(false)}
        >
          <div className="form">
            <label>
              Choose a role
              <select value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
                <option value="">Select an application</option>
                {apps.map((a) => (
                  <option value={a.id} key={a.id}>
                    {a.job_title}
                  </option>
                ))}
              </select>
            </label>
            {!apps.length && (
              <p className="muted">You haven’t applied to a job yet. Head to Browse jobs to get started.</p>
            )}
            <div className="ai-note small">
              <Sparkles size={19} />
              This is a text-based practice interview, not a final hiring assessment.
            </div>
            <button
              className="btn primary"
              disabled={!applicationId || start.isPending}
              onClick={() => start.mutate()}
            >
              {start.isPending ? 'Preparing your questions…' : 'Let’s begin'}
              <ArrowRight size={16} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function InterviewDetail({
  interview: initial,
  candidate,
  close,
  notify,
}: {
  interview: Interview;
  candidate: boolean;
  close: () => void;
  notify: Notify;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState(initial.status === 'completed' ? 'Scorecard' : 'Conversation');
  const [answer, setAnswer] = useState('');
  const { data: interview = initial } = useQuery({
    queryKey: ['interview', initial.id],
    queryFn: () => api<Interview>(`/interviews/${initial.id}`),
    initialData: initial,
  });
  const send = useMutation({
    mutationFn: () =>
      post<Interview>(`/interviews/${initial.id}/answer`, {
        answer,
        expected_count: interview.transcript_json.filter((m) => m.role === 'assistant').length,
      }),
    onSuccess: (i) => {
      qc.setQueryData(['interview', i.id], i);
      qc.invalidateQueries({ queryKey: ['interviews'] });
      setAnswer('');
      if (i.status === 'completed') {
        setTab('Scorecard');
        notify('Practice complete. Your feedback is ready.');
      }
    },
    onError: (e: Error) => notify(e.message),
  });
  const score = interview.scorecard_json;
  return (
    <Modal
      title={initial.name ? `${initial.name} · Interview` : 'Your practice interview'}
      subtitle={initial.job_title || 'A conversation tailored to you. Five questions, thoughtful feedback.'}
      onClose={close}
      wide
    >
      <div className="list-tabs bordered">
        <button className={tab === 'Conversation' ? 'active' : ''} onClick={() => setTab('Conversation')}>
          Conversation
        </button>
        <button
          className={tab === 'Scorecard' ? 'active' : ''}
          disabled={!score}
          onClick={() => setTab('Scorecard')}
        >
          Scorecard {score && <CircleCheck size={14} />}
        </button>
        <Badge status={interview.status === 'completed' ? 'Completed' : 'Interview'}>
          {interview.status === 'completed'
            ? 'Completed'
            : `Question ${interview.transcript_json.filter((m) => m.role === 'assistant').length} of 5`}
        </Badge>
      </div>
      {tab === 'Scorecard' && score ? (
        <div className="detail-body scorecard">
          <div className="scorecard-hero">
            <div className="score-ring">
              <strong>{score.overall_score}</strong>
              <span>out of 100</span>
            </div>
            <div>
              <span className="eyebrow">THE BIG PICTURE</span>
              <h2>{score.recommendation}</h2>
              <p>{score.summary}</p>
            </div>
          </div>
          <div className="profile-columns">
            <div className="feedback-block strengths">
              <h3>
                <CircleCheck size={18} />
                What went well
              </h3>
              {score.strengths.map((s) => (
                <CheckItem key={s}>{s}</CheckItem>
              ))}
            </div>
            <div className="feedback-block">
              <h3>
                <TrendingIcon />
                Room to grow
              </h3>
              {score.weaknesses.map((s) => (
                <p key={s} className="bullet-copy">
                  {s}
                </p>
              ))}
            </div>
          </div>
          <div className="ai-note small">
            <ShieldCheck size={17} />
            <span>{score.mode} · Feedback is guidance, not an automated hiring decision.</span>
          </div>
          <button
            className="btn secondary"
            onClick={() => {
              const a = document.createElement('a');
              a.href = URL.createObjectURL(
                new Blob([JSON.stringify({ ...score, transcript: interview.transcript_json }, null, 2)], {
                  type: 'application/json',
                }),
              );
              a.download = 'smarthire-feedback.json';
              a.click();
              URL.revokeObjectURL(a.href);
              notify('Feedback report downloaded');
            }}
          >
            <ArrowDownToLine size={15} />
            Download feedback
          </button>
        </div>
      ) : (
        <>
          <div className="conversation">
            {interview.transcript_json.map((m, i) => (
              <div className={`message ${m.role}`} key={i}>
                <span className="message-icon">
                  {m.role === 'assistant' ? <Sparkles size={17} /> : <Users size={17} />}
                </span>
                <div>
                  <b>
                    {m.role === 'assistant' ? 'SmartHire interviewer' : initial.name || 'You'}
                    <small>{m.role === 'assistant' ? 'AI' : ''}</small>
                  </b>
                  <p>{m.content}</p>
                  {m.evaluation && <div className="answer-feedback">{m.evaluation.feedback}</div>}
                </div>
              </div>
            ))}
          </div>
          {interview.status === 'in_progress' && candidate && (
            <form
              className="answer-form"
              onSubmit={(e) => {
                e.preventDefault();
                send.mutate();
              }}
            >
              <textarea
                aria-label="Your answer"
                placeholder="Take a breath. Tell us about your experience…"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                minLength={5}
                maxLength={6000}
                rows={4}
                required
              />
              <div>
                <span>Your answers are saved when you send them.</span>
                <button className="btn primary" disabled={send.isPending || answer.trim().length < 5}>
                  {send.isPending ? 'Thinking…' : 'Send answer'}
                  <Send size={15} />
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </Modal>
  );
}
function TrendingIcon() {
  return <ArrowUpRight size={18} />;
}
export function AnalyticsPage({ notify }: { notify: Notify }) {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ['analytics', days],
    queryFn: () => api<Analytics>(`/dashboard/recruiter/analytics?days=${days}`),
  });
  return (
    <>
      <PageHeading
        title="See the bigger picture."
        description="Meaningful insights for a more thoughtful hiring process."
      >
        <button
          className="btn secondary"
          disabled={!data}
          onClick={() => {
            if (data) {
              exportCSV(data.series, 'smarthire-analytics.csv');
              notify('Analytics exported');
            }
          }}
        >
          <ArrowDownToLine size={15} />
          Export analytics
        </button>
      </PageHeading>
      {isLoading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="interview-stats">
              <div className="card">
                <Users />
                <div>
                  <strong>{data.applications}</strong>
                  <span>Applications this period</span>
                </div>
              </div>
              <div className="card">
                <Sparkles />
                <div>
                  <strong>{data.average_match}%</strong>
                  <span>Average match score</span>
                </div>
              </div>
              <div className="card">
                <CircleCheck />
                <div>
                  <strong>{data.shortlisted}</strong>
                  <span>Shortlisted candidates</span>
                </div>
              </div>
            </div>
            <AnalyticsPanels data={data} days={days} setDays={setDays} />
            <div className="card analytics-explainer">
              <ShieldCheck size={28} />
              <div>
                <h3>Good data makes better decisions.</h3>
                <p>
                  These metrics reflect your workspace’s actual application and interview activity. The hiring
                  funnel shows current stage or later, not historical stage transitions. AI match scores are a
                  similarity signal, not a prediction of job performance.
                </p>
              </div>
            </div>
          </>
        )
      )}
    </>
  );
}
export function ResumePage({ notify }: { notify: Notify }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const { data: resumes = [], isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: () => api<Resume[]>('/resumes'),
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api<Resume>('/resumes/upload', { method: 'POST', body: form });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['resumes'] });
      notify('Resume uploaded. Your next opportunity is one step closer.');
    },
    onError: (e: Error) => notify(e.message),
  });
  function receive(file?: File) {
    if (!file || upload.isPending) return;
    if (file.size > 5 * 1024 * 1024) {
      notify('Please choose a file smaller than 5 MB');
      return;
    }
    upload.mutate(file);
  }
  const latest = resumes[0];
  return (
    <>
      <PageHeading
        title="Your experience, beautifully understood."
        description="Upload your resume and let your skills do the talking."
      />
      <div
        className={`upload-zone ${drag ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          receive(e.dataTransfer.files[0]);
        }}
      >
        <span className="upload-icon">
          <Upload size={30} />
        </span>
        <h2>{upload.isPending ? 'Getting to know your experience…' : 'Drop your resume right here'}</h2>
        <p>PDF or DOCX · Up to 5 MB · Text-based documents only</p>
        <button className="btn primary" disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
          <Plus size={16} />
          {upload.isPending ? 'Parsing resume…' : 'Choose a file'}
        </button>
        <input
          type="file"
          hidden
          ref={fileRef}
          accept=".pdf,.docx"
          onChange={(e) => {
            receive(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
        <small>
          <ShieldCheck size={13} />
          Your resume stays private to this workspace.
        </small>
      </div>
      {isLoading ? (
        <Loading />
      ) : latest ? (
        <section className="card resume-preview">
          <div className="section-head">
            <div className="person">
              <span className="department-icon">
                <FileText size={21} />
              </span>
              <div>
                <h2>{latest.filename}</h2>
                <p>Uploaded {dateLabel(latest.created_at)} · Latest resume</p>
              </div>
            </div>
            <Badge status="Completed">Parsed</Badge>
          </div>
          <div className="detail-body">
            <h3>Your profile at a glance</h3>
            <p>{latest.parsed_json.summary}</p>
            <h3>Skills we found</h3>
            <div className="skill-tags">
              {latest.parsed_json.skills.length ? (
                latest.parsed_json.skills.map((s) => <span key={s}>{s}</span>)
              ) : (
                <p>No known skills detected. Enable OpenAI for richer extraction.</p>
              )}
            </div>
            <div className="profile-columns">
              <div>
                <h3>Experience</h3>
                {latest.parsed_json.experience.map((s) => (
                  <p key={s}>{s}</p>
                ))}
              </div>
              <div>
                <h3>Education</h3>
                {latest.parsed_json.education.map((s) => (
                  <p key={s}>{s}</p>
                ))}
              </div>
            </div>
            <div className="ai-note small">
              <Sparkles size={17} />
              New applications use your latest resume. Existing applications keep the version you applied
              with.
            </div>
          </div>
        </section>
      ) : (
        <Empty
          title="A fresh start"
          description="Once uploaded, your structured resume and skills will appear here."
        />
      )}
    </>
  );
}
export function CandidateHome({
  user,
  navigate,
  onJob,
  onInterview,
  notify,
}: {
  user: User;
  navigate: (s: string) => void;
  onJob: (j: Job) => void;
  onInterview: (i: Interview) => void;
  notify: Notify;
}) {
  const { data: apps = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
  });
  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/jobs') });
  const start = useMutation({
    mutationFn: (id: string) => post<Interview>('/interviews/start', { application_id: id }),
    onSuccess: (i) => onInterview(i),
    onError: (e: Error) => notify(e.message),
  });
  return (
    <>
      <PageHeading
        title={`Your next chapter, ${user.name.split(' ')[0]}.`}
        description="A great opportunity starts with a little curiosity. Let’s find yours."
      >
        <button className="btn primary" onClick={() => navigate('Browse jobs')}>
          <Search size={16} />
          Explore opportunities
        </button>
      </PageHeading>
      <div className="candidate-hero">
        <div>
          <span className="eyebrow">A LITTLE PREPARATION GOES A LONG WAY</span>
          <h2>
            Show up as your
            <br />
            most confident self.
          </h2>
          <p>
            Role-specific practice. Thoughtful feedback.
            <br />
            An interview experience designed around you.
          </p>
          <button className="btn primary" onClick={() => navigate('AI Interviews')}>
            Start practicing <ArrowRight size={16} />
          </button>
        </div>
        <div className="hero-art">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="hero-spark">
            <Sparkles size={66} strokeWidth={1.4} />
          </div>
          <span className="floating-label label-one">
            <CircleCheck size={15} />
            Made for your next move
          </span>
          <span className="floating-label label-two">
            <Sparkles size={15} />A little smarter. A little more you.
          </span>
        </div>
      </div>
      <div className="interview-stats">
        <div className="card">
          <BriefcaseBusiness />
          <div>
            <strong>{apps.length}</strong>
            <span>Applications sent</span>
          </div>
        </div>
        <div className="card">
          <Sparkles />
          <div>
            <strong>
              {apps.length ? Math.round(apps.reduce((sum, a) => sum + a.match_score, 0) / apps.length) : 0}%
            </strong>
            <span>Your average match</span>
          </div>
        </div>
        <div className="card">
          <CircleCheck />
          <div>
            <strong>{apps.filter((a) => a.status === 'Shortlisted').length}</strong>
            <span>Shortlisted applications</span>
          </div>
        </div>
      </div>
      <section className="card">
        <div className="section-head">
          <h2>Your applications</h2>
          <span className="count-chip">{apps.length}</span>
        </div>
        {apps.length ? (
          <div className="my-applications">
            {apps.map((a) => (
              <div key={a.id}>
                <span className={`department-icon dept-${a.department.toLowerCase()}`}>
                  <BriefcaseBusiness size={21} />
                </span>
                <div>
                  <button
                    className="name-button"
                    onClick={() => {
                      const job = jobs.find((j) => j.id === a.job_id);
                      if (job) onJob(job);
                      else notify('This role is no longer accepting applications');
                    }}
                  >
                    {a.job_title}
                  </button>
                  <small>
                    Applied {dateLabel(a.created_at)} · {a.department}
                  </small>
                </div>
                <Match value={a.match_score} />
                <Badge status={a.status} />
                <button
                  className="btn secondary"
                  disabled={start.isPending}
                  onClick={() => start.mutate(a.id)}
                >
                  <Video size={15} />
                  Practice interview
                </button>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="Big things start with a first step"
            description="Browse open roles and send your first application."
          />
        )}
      </section>
    </>
  );
}
