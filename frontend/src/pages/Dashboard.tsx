import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  ChevronDown,
  CircleCheck,
  MapPin,
  Plus,
  Sparkles,
  Users,
  Video,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { api, exportCSV, type Analytics, type Application, type Job, type User } from '../api/client';
import { Avatar, Badge, dateLabel, Empty, Loading, Match, Metric, PageHeading } from '../components/ui';
export function ApplicationsTable({
  rows,
  onSelect,
  compact = false,
}: {
  rows: Application[];
  onSelect: (a: Application) => void;
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table className="applications-table">
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Applied role</th>
            <th>
              AI match <Sparkles size={11} />
            </th>
            <th>Status</th>
            {!compact && <th>Applied on</th>}
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((a, i) => (
            <tr key={a.id} onClick={() => onSelect(a)}>
              <td>
                <div className="person">
                  <Avatar name={a.name} index={i} />
                  <span>
                    <button
                      className="name-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(a);
                      }}
                    >
                      {a.name}
                    </button>
                    <small>{a.email}</small>
                  </span>
                </div>
              </td>
              <td>
                <span className="role-title">{a.job_title}</span>
                <small>{a.department}</small>
              </td>
              <td>
                <Match value={a.match_score} />
              </td>
              <td>
                <Badge status={a.status} />
              </td>
              {!compact && <td className="muted">{dateLabel(a.created_at)}</td>}
              <td>
                <button
                  className="icon-btn"
                  aria-label={`View ${a.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(a);
                  }}
                >
                  <ArrowUpRight size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <Empty
          title="No applications yet"
          description="Applications will appear here as candidates find their next opportunity."
        />
      )}
    </div>
  );
}
export function JobMini({ job, onSelect }: { job: Job; onSelect: () => void }) {
  const Icon =
    job.department === 'Design' ? Sparkles : job.department === 'Engineering' ? Zap : BriefcaseBusiness;
  return (
    <button className="job-mini" onClick={onSelect}>
      <div className="job-mini-top">
        <span className={`department-icon dept-${job.department.toLowerCase()}`}>
          <Icon size={19} />
        </span>
        <Badge status="active">Active</Badge>
      </div>
      <h3>{job.title}</h3>
      <div className="job-meta">
        <span>
          <MapPin size={12} />
          {job.location}
        </span>
        <i />
        {job.employment_type}
      </div>
      <div className="job-mini-footer">
        <span>
          <Users size={14} />
          <b>{job.applicants}</b> applicants
        </span>
        <ArrowUpRight size={16} />
      </div>
    </button>
  );
}
export function AnalyticsPanels({
  data,
  days,
  setDays,
}: {
  data: Analytics;
  days: number;
  setDays: (d: number) => void;
}) {
  return (
    <div className="analytics-grid">
      <section className="card applications-chart">
        <div className="section-head">
          <div>
            <h2>Application overview</h2>
            <p>Your talent pipeline, at a glance.</p>
          </div>
          <select
            aria-label="Chart period"
            className="small-select"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={30}>Last 30 days</option>
            <option value={7}>Last 7 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        <div className="chart-summary">
          <strong>{data.applications.toLocaleString()}</strong>
          <span className="trend">
            <TrendingUp size={13} />
            {data.application_change === null
              ? 'New activity'
              : `${data.application_change > 0 ? '+' : ''}${data.application_change}%`}
          </span>
          <span className="muted">vs. previous period</span>
          <div className="chart-legend">
            <span>
              <i />
              Applications
            </span>
            <span>
              <i />
              Shortlisted
            </span>
          </div>
        </div>
        <div className="line-chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.series} margin={{ top: 15, right: 10, bottom: 0, left: -28 }}>
              <defs>
                <linearGradient id="applicationFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#64c6a2" stopOpacity={0.23} />
                  <stop offset="95%" stopColor="#64c6a2" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9eeeb" />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#929b97', fontSize: 11 }}
                dy={10}
                minTickGap={15}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                tick={{ fill: '#929b97', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  border: '1px solid #e8eeeb',
                  borderRadius: 10,
                  fontSize: 12,
                  boxShadow: '0 8px 25px #163c1910',
                }}
              />
              <Area
                isAnimationActive={false}
                type="monotone"
                dataKey="applications"
                name="Applications"
                stroke="#329b75"
                strokeWidth={2.5}
                fill="url(#applicationFill)"
              />
              <Area
                isAnimationActive={false}
                type="monotone"
                dataKey="shortlisted"
                name="Shortlisted"
                stroke="#a1b9ae"
                strokeDasharray="5 5"
                strokeWidth={1.7}
                fill="transparent"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="card funnel-card">
        <div className="section-head">
          <div>
            <h2>Hiring funnel</h2>
            <p>Every step, one closer to the right hire.</p>
          </div>
          <span className="subtle-icon">
            <TrendingUp size={18} />
          </span>
        </div>
        <div className="funnel-bars">
          {data.funnel.map((f, i) => (
            <div className="funnel-row" key={f.name}>
              <div>
                <span>{f.name}</span>
                <strong>{f.value.toLocaleString()}</strong>
              </div>
              <div className="funnel-track">
                <div
                  style={{
                    width: `${Math.max(2, (f.value / Math.max(1, data.funnel[0].value)) * 100)}%`,
                    background: ['#a8dbc6', '#86cbb0', '#65b697', '#359b75', '#187e59'][i],
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="funnel-bottom">
          <span className="check-circle">
            <CircleCheck size={15} />
          </span>
          <b>
            {Math.round(((data.funnel[4]?.value || 0) / Math.max(1, data.applications)) * 100)}% conversion
            rate
          </b>
          <span>application to hire</span>
        </div>
      </section>
    </div>
  );
}
export default function Dashboard({
  user,
  navigate,
  onCreate,
  onCandidate,
  onJob,
  notify,
}: {
  user: User;
  navigate: (p: string) => void;
  onCreate: () => void;
  onCandidate: (a: Application) => void;
  onJob: (j: Job) => void;
  notify: (s: string) => void;
}) {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', days],
    queryFn: () => api<Analytics>(`/dashboard/recruiter/analytics?days=${days}`),
  });
  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api<Application[]>('/applications'),
  });
  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/jobs') });
  if (isLoading) return <Loading />;
  if (!data)
    return (
      <Empty title="We couldn't load your overview" description={error?.message || 'Please try again.'} />
    );
  const activeJobs = jobs.filter((j) => j.status === 'active');
  const exportReport = () => {
    exportCSV(
      [
        {
          period_days: days,
          active_jobs: data.active_jobs,
          applications: data.applications,
          interviews: data.interviews,
          average_match: data.average_match,
          shortlisted: data.shortlisted,
        },
      ],
      'smarthire-overview.csv',
    );
    notify('Overview report exported');
  };
  return (
    <>
      <PageHeading
        title={`Good morning, ${user.name.split(' ')[0]} ☀`}
        description="Here’s what’s happening with your hiring today."
      >
        <button className="btn secondary" onClick={exportReport}>
          <ArrowDownToLine size={15} />
          Export report
        </button>
        <button className="btn primary" onClick={onCreate}>
          <Plus size={17} />
          Post a job
        </button>
      </PageHeading>
      <div className="overview-toolbar">
        <div className="overview-tabs">
          <button className="active">Overview</button>
          <button onClick={() => navigate('Analytics')}>
            Analytics <ArrowUpRight size={12} />
          </button>
        </div>
        <div className="date-range">
          <CalendarDays size={14} />
          {new Date(Date.now() - days * 86400000).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          })}{' '}
          – {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          <ChevronDown size={13} />
          <select
            aria-label="Dashboard date range"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={30}>Last 30 days</option>
            <option value={7}>Last 7 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>
      <div className="metrics-grid">
        <Metric
          title="Active jobs"
          value={data.active_jobs}
          note={`${data.new_jobs} new jobs|this period`}
          icon={<BriefcaseBusiness size={17} />}
          points="0,32 10,32 20,25 30,27 40,19 50,21 60,12 70,16 80,8 90,9 100,3"
        />
        <Metric
          title="Total applications"
          value={data.applications.toLocaleString()}
          note={
            data.application_change === null
              ? 'New activity|this period'
              : `${data.application_change > 0 ? '+' : ''}${data.application_change}%|vs. previous period`
          }
          icon={<Users size={17} />}
          points="0,36 10,28 20,32 30,22 40,26 50,19 60,22 70,12 80,14 90,4 100,7"
        />
        <Metric
          title="AI interviews"
          value={data.interviews}
          note={`${data.completed_interviews} completed|this period`}
          icon={<Video size={17} />}
          points="0,33 10,34 20,28 30,29 40,18 50,22 60,17 70,21 80,10 90,10 100,4"
        />
        <Metric
          title="Avg. match score"
          value={`${data.average_match}%`}
          note="AI-powered|candidate matching"
          icon={<Sparkles size={17} />}
          points="0,34 10,30 20,30 30,22 40,24 50,17 60,18 70,11 80,14 90,6 100,4"
          green
        />
      </div>
      <div className="ai-insight">
        <span className="insight-icon">
          <Sparkles size={20} />
        </span>
        <div>
          <div>
            <b>A little intelligence. A big hiring advantage.</b>
            <span className="tiny-tag">SMART INSIGHT</span>
          </div>
          <p>
            You have{' '}
            <strong>
              {
                applications.filter((a) => a.match_score >= 90 && !['Hired', 'Rejected'].includes(a.status))
                  .length
              }{' '}
              high-match candidates
            </strong>{' '}
            waiting to be explored. Your next great hire could be one of them.
          </p>
        </div>
        <button onClick={() => navigate('Candidates')}>
          Review candidates <ArrowRight size={15} />
        </button>
        <div className="insight-decoration" />
      </div>
      <AnalyticsPanels data={data} days={days} setDays={setDays} />
      <section className="card recent-card">
        <div className="section-head">
          <div className="inline-heading">
            <h2>Top matched candidates</h2>
            <span className="count-chip">{applications.length}</span>
            <span className="section-caption">Great talent. Ranked for you.</span>
          </div>
          <button className="text-button" onClick={() => navigate('Candidates')}>
            View all candidates <ArrowRight size={14} />
          </button>
        </div>
        <ApplicationsTable rows={applications.slice(0, 5)} onSelect={onCandidate} />
        <div className="table-footer">
          <span>
            <Sparkles size={13} />
            Matches are a starting point. Great hiring always needs a human.
          </span>
          <span>{data.ai_mode === 'Demo' ? 'Sample workspace data' : 'Powered by SmartHire AI'}</span>
        </div>
      </section>
      <section className="active-jobs">
        <div className="section-head">
          <div className="inline-heading">
            <h2>Active job openings</h2>
            <span className="count-chip">{activeJobs.length}</span>
          </div>
          <button className="text-button" onClick={() => navigate('Jobs')}>
            View all jobs <ArrowRight size={14} />
          </button>
        </div>
        <div className="jobs-mini-grid">
          {activeJobs.slice(0, 3).map((j) => (
            <JobMini key={j.id} job={j} onSelect={() => onJob(j)} />
          ))}
        </div>
      </section>
      <div className="page-footer">
        <span>Better matches. Meaningful conversations. Great hires.</span>
        <span>
          <span className="live-dot" />
          Workspace connected
        </span>
      </div>
    </>
  );
}
