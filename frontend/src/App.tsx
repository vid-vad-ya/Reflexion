import { useState, useEffect } from 'react';
import { Bot, GitPullRequest, Code2, ShieldAlert } from 'lucide-react';

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('Checking...');

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/health')
      .then((res) => res.json())
      .then((data) => {
        if (data.status === 'healthy') {
          setBackendStatus('Connected');
        } else {
          setBackendStatus('Error');
        }
      })
      .catch(() => {
        setBackendStatus('Disconnected');
      });
  }, []);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col items-center justify-center p-6">
      <header className="max-w-md text-center space-y-4">
        <div className="inline-flex p-3 bg-indigo-600/10 text-indigo-400 rounded-2xl border border-indigo-500/20">
          <Bot size={40} className="animate-pulse" />
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
          Reflexion
        </h1>
        <p className="text-neutral-400 text-sm">
          Self-correcting AI Pull Request Agent (Generate → Test → Reflect → Improve)
        </p>
      </header>

      <main className="mt-8 max-w-sm w-full bg-neutral-900 border border-neutral-800 rounded-xl p-6 shadow-xl space-y-6">
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
          <span className="text-xs text-neutral-400 font-semibold uppercase tracking-wider">
            System Connectivity
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              backendStatus === 'Connected'
                ? 'bg-green-500/15 text-green-400 border border-green-500/20'
                : 'bg-amber-500/15 text-amber-400 border border-amber-500/20'
            }`}
          >
            {backendStatus}
          </span>
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="p-1.5 bg-neutral-800 rounded-lg text-neutral-400 mt-0.5">
              <Code2 size={16} />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Self-Correcting Graph</h3>
              <p className="text-xs text-neutral-400">
                Orchestrates Analyzer, Planner, Coder, Tester and Reflector nodes.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="p-1.5 bg-neutral-800 rounded-lg text-neutral-400 mt-0.5">
              <GitPullRequest size={16} />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Git Branch Integrator</h3>
              <p className="text-xs text-neutral-400">
                Clones, branches, commits, and opens draft/open PRs automatically.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="p-1.5 bg-neutral-800 rounded-lg text-neutral-400 mt-0.5">
              <ShieldAlert size={16} />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Verification Timeout</h3>
              <p className="text-xs text-neutral-400">
                Guards execution runtimes against infinite loop testing paths.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="mt-12 text-xs text-neutral-600">
        Reflexion AI PR Agent • Portfolio Prototype MVP
      </footer>
    </div>
  );
}

export default App;
