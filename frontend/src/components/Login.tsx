import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Github,
  Bot,
  Sparkles,
  GitPullRequest,
  RefreshCw,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Login – Premium landing / sign-in page
// ---------------------------------------------------------------------------

export default function Login() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();

  // If already authenticated, send straight to dashboard
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  return (
    <div className="login-page">
      {/* Animated background orbs */}
      <div className="login-bg-orb login-bg-orb--1" />
      <div className="login-bg-orb login-bg-orb--2" />
      <div className="login-bg-orb login-bg-orb--3" />

      <div className="login-container">
        {/* ---- Hero section ---- */}
        <header className="login-hero">
          <div className="login-logo-ring">
            <Bot size={44} strokeWidth={1.5} />
          </div>

          <h1 className="login-title">
            <span className="login-title-gradient">Reflexion</span>
          </h1>

          <p className="login-subtitle">
            The Self-Correcting AI Coding Agent
          </p>

          <p className="login-tagline">
            Describe a feature. Reflexion generates code, runs tests, reflects
            on failures, and iterates — then opens a pull request when it's
            right.
          </p>
        </header>

        {/* ---- Glass card ---- */}
        <div className="login-card">
          <div className="login-card-inner">
            {/* Feature pills */}
            <div className="login-features">
              <FeaturePill
                icon={<Sparkles size={16} />}
                label="Generate"
                description="AI writes implementation code"
              />
              <FeaturePill
                icon={<RefreshCw size={16} />}
                label="Test & Reflect"
                description="Runs tests, learns from failures"
              />
              <FeaturePill
                icon={<GitPullRequest size={16} />}
                label="Ship"
                description="Opens a polished pull request"
              />
              <FeaturePill
                icon={<ShieldCheck size={16} />}
                label="Verify"
                description="Multi-attempt self-correction"
              />
            </div>

            {/* CTA */}
            <button
              id="login-github-btn"
              className="login-cta"
              onClick={login}
              disabled={isLoading}
            >
              <Github size={20} />
              <span>Continue with GitHub</span>
              <ArrowRight size={16} className="login-cta-arrow" />
            </button>

            <p className="login-disclaimer">
              We only request <strong>read:user</strong> and{' '}
              <strong>user:email</strong> scopes. Your code stays on GitHub.
            </p>
          </div>
        </div>

        {/* ---- Footer ---- */}
        <footer className="login-footer">
          Reflexion AI PR Agent &middot; Portfolio Prototype
        </footer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

function FeaturePill({
  icon,
  label,
  description,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <div className="login-feature-pill">
      <div className="login-feature-pill-icon">{icon}</div>
      <div>
        <span className="login-feature-pill-label">{label}</span>
        <span className="login-feature-pill-desc">{description}</span>
      </div>
    </div>
  );
}
