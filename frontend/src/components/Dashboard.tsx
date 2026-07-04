import { useAuth } from '../context/AuthContext';
import {
  LogOut,
  GitFork,
  ListTodo,
  CheckCircle2,
  Activity,
  Bot,
  ChevronRight,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Dashboard – Authenticated user home
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const { user, logout } = useAuth();

  const avatarUrl =
    user?.github_avatar_url || user?.avatar_url || undefined;
  const displayName = user?.github_username || user?.username || 'User';

  return (
    <div className="dashboard-layout">
      {/* ---- Sidebar ---- */}
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar-header">
          <div className="dashboard-logo-mark">
            <Bot size={22} strokeWidth={1.6} />
          </div>
          <span className="dashboard-logo-text">Reflexion</span>
        </div>

        {/* User profile card */}
        <div className="dashboard-profile">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt={displayName}
              className="dashboard-avatar"
            />
          ) : (
            <div className="dashboard-avatar dashboard-avatar--placeholder">
              {displayName.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="dashboard-profile-info">
            <span className="dashboard-profile-name">{displayName}</span>
            <span className="dashboard-profile-email">
              {user?.email || 'No email'}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="dashboard-nav">
          <a href="#" className="dashboard-nav-item dashboard-nav-item--active">
            <Activity size={18} />
            <span>Overview</span>
          </a>
          <a href="#" className="dashboard-nav-item">
            <GitFork size={18} />
            <span>Repositories</span>
          </a>
          <a href="#" className="dashboard-nav-item">
            <ListTodo size={18} />
            <span>Tasks</span>
          </a>
        </nav>

        <div className="dashboard-sidebar-spacer" />

        <button
          id="logout-btn"
          className="dashboard-logout-btn"
          onClick={logout}
        >
          <LogOut size={18} />
          <span>Sign Out</span>
        </button>
      </aside>

      {/* ---- Main content ---- */}
      <main className="dashboard-main">
        <header className="dashboard-main-header">
          <div>
            <h1 className="dashboard-greeting">
              Welcome back, <span className="dashboard-greeting-name">{displayName}</span>
            </h1>
            <p className="dashboard-greeting-sub">
              Here's an overview of your Reflexion workspace.
            </p>
          </div>
        </header>

        {/* Metric cards */}
        <div className="dashboard-cards">
          <MetricCard
            icon={<GitFork size={22} />}
            label="Linked Repositories"
            value="0"
            accent="var(--accent-blue)"
            hint="Connect repositories in the next phase"
          />
          <MetricCard
            icon={<ListTodo size={22} />}
            label="Active Tasks"
            value="0"
            accent="var(--accent-purple)"
            hint="Submit tasks once repos are linked"
          />
          <MetricCard
            icon={<CheckCircle2 size={22} />}
            label="Successful Attempts"
            value="0"
            accent="var(--accent-green)"
            hint="Completed agent runs will appear here"
          />
          <MetricCard
            icon={<Activity size={22} />}
            label="Agent Activity"
            value="Idle"
            accent="var(--accent-amber)"
            hint="Real-time agent status coming soon"
          />
        </div>

        {/* Activity feed placeholder */}
        <section className="dashboard-activity-section">
          <h2 className="dashboard-section-title">Recent Activity</h2>
          <div className="dashboard-empty-state">
            <Bot size={48} strokeWidth={1.2} className="dashboard-empty-icon" />
            <p className="dashboard-empty-text">
              No activity yet. Once you link a repository and submit a task,
              Reflexion will begin its Generate → Test → Reflect loop.
            </p>
            <button className="dashboard-empty-cta" disabled>
              <span>Link a Repository</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

function MetricCard({
  icon,
  label,
  value,
  accent,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent: string;
  hint: string;
}) {
  return (
    <div className="metric-card" style={{ '--card-accent': accent } as React.CSSProperties}>
      <div className="metric-card-header">
        <div className="metric-card-icon">{icon}</div>
        <span className="metric-card-label">{label}</span>
      </div>
      <span className="metric-card-value">{value}</span>
      <span className="metric-card-hint">{hint}</span>
    </div>
  );
}
