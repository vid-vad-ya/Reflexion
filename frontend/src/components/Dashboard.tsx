import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { motion } from 'framer-motion';
import {
  LogOut,
  Sliders,
  Terminal,
  Activity,
  Layers,
  Cpu,
  Compass,
  Link,
  Code2,
  RotateCw,
  GitPullRequest,
} from 'lucide-react';
import Logo from './ui/Logo';
import GlassCard from './ui/GlassCard';
import StatusChip from './ui/StatusChip';
import AnimatedBackground from './ui/AnimatedBackground';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');

  const avatarUrl = user?.github_avatar_url || user?.avatar_url || undefined;
  const displayName = user?.github_username || user?.username || 'Operator';

  const systemEngines = [
    { name: 'Repository Linker', status: 'Connected', variant: 'success', desc: 'Syncs commits & pull requests' },
    { name: 'Agent Coordinator', status: 'Idle', variant: 'info', desc: 'Coordinates lifecycle executions' },
    { name: 'Planning Engine', status: 'Ready', variant: 'neutral', desc: 'Generates hierarchical implementation strategies' },
    { name: 'Repository Intelligence', status: 'Ready', variant: 'neutral', desc: 'Indexes code symbols & dependencies' },
    { name: 'Code Generator', status: 'Ready', variant: 'neutral', desc: 'Implements targeted code additions & edits' },
    { name: 'Testing Harness', status: 'Ready', variant: 'neutral', desc: 'Runs local tests and captures output logs' },
    { name: 'Reflection Engine', status: 'Ready', variant: 'neutral', desc: 'Analyzes test errors and plans self-correction' },
  ];

  const agentPipeline = [
    { label: 'Repository Connected', status: 'Waiting', icon: <Link size={14} /> },
    { label: 'Planning', status: 'Waiting', icon: <Compass size={14} /> },
    { label: 'Coding', status: 'Waiting', icon: <Code2 size={14} /> },
    { label: 'Testing', status: 'Waiting', icon: <Terminal size={14} /> },
    { label: 'Reflection', status: 'Waiting', icon: <RotateCw size={14} /> },
    { label: 'Pull Request', status: 'Waiting', icon: <GitPullRequest size={14} /> },
  ];

  return (
    <div className="dashboard-container">
      {/* Living background */}
      <AnimatedBackground />

      {/* ---- Sidebar Panel ---- */}
      <aside className="sidebar-panel">
        <div className="sidebar-header">
          <Logo size={28} className="sidebar-logo" />
          <span className="sidebar-title">Reflexion</span>
        </div>

        {/* Navigation links */}
        <nav className="sidebar-nav">
          <a
            href="#"
            onClick={(e) => { e.preventDefault(); setActiveTab('overview'); }}
            className={`sidebar-nav-item ${activeTab === 'overview' ? 'active' : ''}`}
          >
            <Activity size={16} />
            <span className="sidebar-nav-label">Overview</span>
          </a>
          <a
            href="#"
            onClick={(e) => { e.preventDefault(); setActiveTab('repos'); }}
            className={`sidebar-nav-item ${activeTab === 'repos' ? 'active' : ''}`}
          >
            <Layers size={16} />
            <span className="sidebar-nav-label">Repositories</span>
          </a>
          <a
            href="#"
            onClick={(e) => { e.preventDefault(); setActiveTab('tasks'); }}
            className={`sidebar-nav-item ${activeTab === 'tasks' ? 'active' : ''}`}
          >
            <Sliders size={16} />
            <span className="sidebar-nav-label">Tasks</span>
          </a>
        </nav>

        {/* User profile details and Sign Out */}
        <div className="sidebar-footer">
          <div className="sidebar-profile">
            {avatarUrl ? (
              <img src={avatarUrl} alt={displayName} className="sidebar-avatar" />
            ) : (
              <div className="sidebar-avatar-placeholder">
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="sidebar-profile-info">
              <span className="sidebar-profile-name">{displayName}</span>
              <span className="sidebar-profile-email">{user?.email || 'operator@reflexion'}</span>
            </div>
          </div>

          <button id="logout-btn" className="sidebar-logout-btn" onClick={logout}>
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* ---- Main Workspace Panel ---- */}
      <main className="workspace-panel">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="workspace-header"
        >
          <h1 className="workspace-title">
            Mission Control <span className="workspace-title-accent">/ system state</span>
          </h1>
          <p className="workspace-subtitle">
            Observing autonomous software engineering cycles in real-time.
          </p>
        </motion.div>

        {/* Layout Grid */}
        <div className="mission-control-grid">
          
          {/* Left Column: System Engine State */}
          <div className="flex flex-col gap-8">
            <GlassCard>
              <div className="glass-panel-header">
                <span className="glass-panel-title">
                  <Cpu size={14} /> System Engines
                </span>
                <span className="font-code text-xs text-[#06b6d4]">7 ONLINE</span>
              </div>

              <div className="mission-status-list">
                {systemEngines.map((engine, idx) => (
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    key={engine.name}
                    className="mission-status-row"
                  >
                    <div>
                      <div className="text-sm font-medium text-[#f4f4f5]">{engine.name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{engine.desc}</div>
                    </div>
                    {/* @ts-ignore */}
                    <StatusChip label={engine.status} variant={engine.variant} />
                  </motion.div>
                ))}
              </div>
            </GlassCard>

            {/* Placeholder state for Workspace operations */}
            <GlassCard>
              <div className="glass-panel-header">
                <span className="glass-panel-title">
                  <Terminal size={14} /> Workspace Activity
                </span>
              </div>

              <div className="empty-state-panel">
                <Terminal size={32} className="empty-state-icon" />
                <h3 className="empty-state-title">No Active Workspace</h3>
                <p className="empty-state-text">
                  Reflexion is listening. Connect a repository and assign a task
                  to initiate the autonomous loop.
                </p>
              </div>
            </GlassCard>
          </div>

          {/* Right Column: Signature Agent Timeline */}
          <div>
            <GlassCard>
              <div className="glass-panel-header">
                <span className="glass-panel-title">
                  <Activity size={14} /> Agent Execution Timeline
                </span>
                <span className="font-code text-xs text-zinc-500">STANDBY</span>
              </div>

              <div className="agent-timeline">
                {agentPipeline.map((step, idx) => (
                  <div
                    key={step.label}
                    className={`agent-timeline-node ${idx === 0 ? 'active' : ''}`}
                  >
                    <div className="agent-timeline-marker" />
                    <div className="flex items-center gap-2">
                      <span className="text-[#a1a1aa]">{step.icon}</span>
                      <span className="agent-timeline-label">{step.label}</span>
                    </div>
                    <span className="agent-timeline-status">{step.status}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

        </div>
      </main>
    </div>
  );
}
