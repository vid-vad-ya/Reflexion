import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { motion } from 'framer-motion';
import { Github } from 'lucide-react';
import Logo from './ui/Logo';
import AnimatedBackground from './ui/AnimatedBackground';

const LIFECYCLE_STAGES = ['Observe', 'Plan', 'Code', 'Test', 'Reflect', 'Improve'];

export default function Login() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const [activeStage, setActiveStage] = useState(0);
  const [isRedirecting, setIsRedirecting] = useState(false);

  // If already authenticated, redirect straight to dashboard
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Loop through lifecycle stages with smooth timing
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStage((prev) => (prev + 1) % LIFECYCLE_STAGES.length);
    }, 2800);
    return () => clearInterval(timer);
  }, []);

  const handleLoginClick = () => {
    setIsRedirecting(true);
    login();
  };

  return (
    <div className="login-layout">
      {/* Living background */}
      <AnimatedBackground />

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="login-hero-container"
      >
        {/* Abstract Logo */}
        <div className="login-logo-container">
          <Logo size={72} />
        </div>

        {/* Core Headline */}
        <h1 className="login-headline">Reflexion</h1>

        {/* Subheadline */}
        <h2 className="login-subheadline">
          An autonomous software engineer that learns from its own mistakes.
        </h2>

        {/* Context Description */}
        <p className="login-description">
          Reflexion silently connects to your repositories to plan implementations,
          write clean code, run comprehensive tests, reflect on runtime and test
          failures, and continuously improve its work—delivering verified production-ready
          pull requests for human approval.
        </p>

        {/* GitHub Auth CTA */}
        <motion.button
          id="login-github-btn"
          onClick={handleLoginClick}
          disabled={isLoading || isRedirecting}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          className="github-btn"
        >
          {isRedirecting || isLoading ? (
            <span className="auth-loading-spinner mr-2" style={{ width: 16, height: 16 }} />
          ) : (
            <Github size={18} />
          )}
          <span>{isRedirecting ? 'Connecting to GitHub...' : 'Continue with GitHub'}</span>
        </motion.button>

        {/* Autonomous Engineering Lifecycle Timeline */}
        <div className="lifecycle-rail">
          {LIFECYCLE_STAGES.map((stage, idx) => (
            <div
              key={stage}
              className={`lifecycle-node ${idx === activeStage ? 'active' : ''}`}
            >
              <motion.div
                className="lifecycle-node-dot"
                animate={
                  idx === activeStage
                    ? { scale: [1, 1.4, 1.2], opacity: 1 }
                    : { scale: 1, opacity: 0.4 }
                }
                transition={{ duration: 0.4 }}
              />
              <span className="lifecycle-node-label">{stage}</span>
            </div>
          ))}
          <div className="lifecycle-connector" />
        </div>
      </motion.div>
    </div>
  );
}
