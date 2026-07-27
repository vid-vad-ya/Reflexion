# Reflexion: Refined Implementation Roadmap & Development Sequence

This revised roadmap outlines the **14 development phases** to build Reflexion as a flagship portfolio project. It maintains the simplified infrastructure (FastAPI BackgroundTasks, Neon PostgreSQL) while preserving a fully modular agent system, a centralized LLM abstraction layer, and the complete web application user experience.

---

## Revised Development Sequence & Dependencies

```
[Phase 1: Bootstrap] ──► [Phase 2: Database] ──► [Phase 3: GitHub Auth]
       │                                                 │
       ▼                                                 ▼
[Phase 4: LLM Service]                           [Phase 5: Git Sync]
       │                                                 │
       └───────────────► [Phase 6: Analyzer] ◄───────────┘
                                 │
                                 ▼
                         [Phase 7: Planner]
                                 │
                                 ▼
                     [Phase 8: LangGraph Skeleton]
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
          [Phase 9: Coder] [Phase 10: Tester] [Phase 12: Frontend UI]
                 │               │               │
                 └───────┬───────┘               │
                         ▼                       │
                 [Phase 11: Reflector]           │
                         │                       │
                         ▼                       │
                 [Phase 13: GitHub PR Creation] ◄┘
                         │
                         ▼
                 [Phase 14: Live Deployment]
```

---

## Phase 1: Project Bootstrap & Folder Structure
* **Goal**: Setup monorepo workspace environment, configure compiler settings, and verify backend/frontend startup.
* **Phase Dependencies**: None (Starting Point).
* **Features Implemented**:
  * Healthcheck routing.
  * Dotenv configuration parsing.
  * Vite frontend bundling pipeline.
* **Files to Create**:
  * [requirements.txt](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/requirements.txt)
  * [config.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/core/config.py)
  * [main.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/main.py)
  * [package.json](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/package.json)
  * [vite.config.ts](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/vite.config.ts)
* **Dependencies Required**:
  * Backend: `fastapi`, `uvicorn`, `pydantic-settings`, `python-dotenv`
  * Frontend: `react`, `react-dom`, `typescript`, `tailwindcss`, `vite`
* **Acceptance Criteria**:
  * FastAPI serves documentation page on `http://localhost:8000/docs`.
  * Frontend project compiles and displays landing page on `http://localhost:5173`.
* **Expected Deliverables**: Initial monorepo layout and running development build targets.
* **Estimated Difficulty**: **Easy**

---

## Phase 2: Database Models & Neon Integration
* **Goal**: Define relational models via SQLModel and initialize migrations connected to serverless Neon PostgreSQL.
* **Phase Dependencies**: Depends on **Phase 1**.
* **Features Implemented**:
  * Combined SQLModel schemas (Users, Repositories, Tasks, Attempts).
  * Alembic migration version controls.
  * Database connection pooling context managers.
* **Files to Create**:
  * [database.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/database.py)
  * [models.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/models.py)
  * [alembic.ini](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/alembic.ini)
* **Dependencies Required**: `sqlmodel`, `psycopg2-binary`, `alembic`
* **Acceptance Criteria**:
  * Migration commands successfully initialize tables on the live Neon cloud PostgreSQL database.
  * Code schemas cleanly support relationship queries (e.g. `task.attempts`).
* **Expected Deliverables**: Live relational database tables connected to FastAPI application.
* **Estimated Difficulty**: **Medium**

---

## Phase 3: GitHub OAuth Authentication
* **Goal**: Implement secure user identity verification using GitHub OAuth and HTTP-Only session JWT cookies.
* **Phase Dependencies**: Depends on **Phase 2**.
* **Features Implemented**:
  * Redirect URI endpoints for GitHub authorization scope requests.
  * Exchange code helper handlers fetching OAuth user data.
  * JWT claims generators and verification route check gates.
  * Plaintext/simple base64 token storage configuration inside DB.
* **Files to Create**:
  * [security.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/core/security.py)
  * [auth.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/routes/auth.py)
* **Dependencies Required**: `httpx`, `pyjwt`, `cryptography`
* **Acceptance Criteria**:
  * Hitting auth callback endpoint creates a user in PostgreSQL and sets a secure JWT cookie that passes subsequent API requests.
* **Expected Deliverables**: Backend authentication routes and session cookie validations.
* **Estimated Difficulty**: **Medium**

---

## Phase 4: Shared LLM Service Abstraction
* **Goal**: Abstract LLM client operations into a unified service wrapper, isolating agents from Gemini SDK configurations.
* **Phase Dependencies**: Depends on **Phase 1**.
* **Features Implemented**:
  * Centralized Gemini client loader using `google-genai`.
  * Helper method for raw text prompts: `generate_text(prompt, system_instruction)`.
  * Helper method for parsing structured outputs: `generate_structured_json(prompt, response_schema)`.
* **Files to Create**:
  * [llm.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/services/llm.py)
* **Dependencies Required**: `google-genai`, `pydantic`
* **Acceptance Criteria**:
  * Service maps Gemini calls via a mock script, successfully enforcing schema validation constraints on JSON outputs.
* **Expected Deliverables**: Consolidated backend LLM gateway.
* **Estimated Difficulty**: **Medium**

---

## Phase 5: Git Integration & Repository Connection
* **Goal**: Download connected user repositories onto local disk workspaces using GitPython.
* **Phase Dependencies**: Depends on **Phase 3**.
* **Features Implemented**:
  * Repository checkouts API routing.
  * Filesystem working folders allocator.
  * Git workspace clone, branch checkout, pull and tracking workflows.
* **Files to Create**:
  * [repos.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/routes/repos.py)
  * [git_service.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/services/git_service.py)
* **Dependencies Required**: `GitPython`
* **Acceptance Criteria**:
  * Invoking repo connect routes downloads the codebase cleanly into local file system directories named after user database IDs.
* **Expected Deliverables**: Git management helper service that reads user folders on disk.
* **Estimated Difficulty**: **Easy**

---

## Phase 6: Repository Analysis Agent
* **Goal**: Create the repository scan node which detects coding patterns, frameworks, and files list configurations.
* **Phase Dependencies**: Depends on **Phase 4** and **Phase 5**.
* **Features Implemented**:
  * Directory structure scanner.
  * LLM-driven programming language and framework detector.
  * Workspace index JSON compiler.
* **Files to Create**:
  * [state.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/state.py)
  * [analyzer.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/analyzer.py)
* **Dependencies Required**: `langchain-core` / `langgraph`
* **Acceptance Criteria**:
  * Analysis script returns JSON indicating primary language frameworks, file locations, and populates `structure_json` database values.
* **Expected Deliverables**: Working folder scanner returning files metadata.
* **Estimated Difficulty**: **Medium**

---

## Phase 7: Planning Agent
* **Goal**: Establish the Planning Agent to outline steps and target changes from user prompt definitions.
* **Phase Dependencies**: Depends on **Phase 6**.
* **Features Implemented**:
  * Feature specifications prompt generator.
  * Target files identifier logic.
  * Markdown format implementation steps layout builder.
* **Files to Create**:
  * [planner.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/planner.py)
* **Dependencies Required**: `langchain-core`
* **Acceptance Criteria**:
  * Planning execution routes produce text plan blocks and targets list in `affected_files` array.
* **Expected Deliverables**: Context planner node mapping features to files modifications.
* **Estimated Difficulty**: **Medium**

---

## Phase 8: LangGraph Framework Skeleton & State Graph Routing
* **Goal**: Scaffold the orchestration state machine graph structure, using mock execution steps to test loop pathways.
* **Phase Dependencies**: Depends on **Phase 6** and **Phase 7**.
* **Features Implemented**:
  * LangGraph state class structures.
  * Graph compilation and nodes wiring.
  * Dynamic conditional routers checking loop counters.
  * Mock runner nodes for Coder, Tester, and Reflector.
* **Files to Create**:
  * [graph.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/graph.py)
  * [tasks.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/routes/tasks.py)
* **Dependencies Required**: `langgraph`
* **Acceptance Criteria**:
  * Executing task routes activates background routing, executing analyzer, planner, mock steps, checking attempts loops, and updating task statuses.
* **Expected Deliverables**: Functional state machine skeleton linking routes to mock background task nodes.
* **Estimated Difficulty**: **Hard**

---

## Phase 9: Coding Agent Integration
* **Goal**: Build the target files patch generator agent, replacing mock coder nodes in the LangGraph graph.
* **Phase Dependencies**: Depends on **Phase 8**.
* **Features Implemented**:
  * Workspace file loader and parser integrations.
  * LLM-driven file patching operations.
  * Simple search-and-replace code modification logic.
* **Files to Create**:
  * [coder.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/coder.py) (replaces mock node)
* **Dependencies Required**: `google-genai` integration through LLM service.
* **Acceptance Criteria**:
  * Coding Node reads the plan and target codebase, edits files, and saves actual changes to local workspaces.
* **Expected Deliverables**: Fully functional code generator agent updating file contents on disk.
* **Estimated Difficulty**: **Hard**

---

## Phase 10: Testing Agent Integration
* **Goal**: Replace mock tester steps with actual test execution pipelines using subprocesses.
* **Phase Dependencies**: Depends on **Phase 8**.
* **Features Implemented**:
  * Commands parser (extracts scripts e.g. `npm test`, `pytest`).
  * Subprocess invocation wrapper.
  * Maximum timeout logic (30s) preventing thread freezes.
  * stdout and stderr crash logs collector.
* **Files to Create**:
  * [tester.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/tester.py) (replaces mock node)
* **Dependencies Required**: Standard Python subprocess package.
* **Acceptance Criteria**:
  * Node successfully launches the local test suite, capturing exit codes and trace logs, saving summary objects in DB.
* **Expected Deliverables**: Subprocess runner checking compile statuses and test logs.
* **Estimated Difficulty**: **Easy**

---

## Phase 11: Reflection Agent Integration (Core Self-Correction)
* **Goal**: Replace mock reflection steps with the core AI debugger, assessing logs to suggest code changes.
* **Phase Dependencies**: Depends on **Phase 9** and **Phase 10**.
* **Features Implemented**:
  * Compiler and test runner output parser.
  * Root cause identifier prompts.
  * Next attempt code directives builder.
  * Stack history comparison engine.
* **Files to Create**:
  * [reflector.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/agents/reflector.py) (replaces mock node)
* **Dependencies Required**: `google-genai` via LLM service.
* **Acceptance Criteria**:
  * When tests fail, this agent produces structured reflection logs which the Coding agent uses in the next iteration.
* **Expected Deliverables**: Fully functional self-correction loop in LangGraph.
* **Estimated Difficulty**: **Hard**

---

## Phase 12: Frontend Dashboard & Task Execution View
* **Goal**: Create the dashboard console frontend matching mock UI pages.
* **Phase Dependencies**: Depends on **Phase 3** and **Phase 8**.
* **Features Implemented**:
  * Main login landing and authenticated dashboard.
  * Repositories connection panel.
  * Active task monitoring console polling route states.
  * Interactive Monaco editor side-by-side diff displays.
* **Files to Create**:
  * [dashboard.tsx](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/src/pages/dashboard.tsx)
  * [repo-detail.tsx](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/src/pages/repo-detail.tsx)
  * [task-execution.tsx](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/src/pages/task-execution.tsx)
  * [diff-viewer.tsx](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/src/components/diff-viewer.tsx)
* **Dependencies Required**: `@monaco-editor/react`, shadcn/ui components.
* **Acceptance Criteria**:
  * User can click repos, spawn execution loops, monitor attempts logs, and review final changes side-by-side.
* **Expected Deliverables**: Developer web console UI client dashboard.
* **Estimated Difficulty**: **Medium**

---

## Phase 13: Pull Request Review & GitHub PR Creation
* **Goal**: Finalize user approval loops, pushing branches and opening PR requests on GitHub.
* **Phase Dependencies**: Depends on **Phase 12**.
* **Features Implemented**:
  * Split diff PR review landing view.
  * Git remote push operations using User tokens.
  * GitHub pull request generator endpoint clients.
* **Files to Create**:
  * [pull_requests.py](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/app/routes/pull_requests.py)
  * [pr-review.tsx](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/src/pages/pr-review.tsx)
* **Dependencies Required**: `httpx`, `GitPython`
* **Acceptance Criteria**:
  * Approving changes pushes the local feature branch to GitHub, creates a PR, and updates state DB entries.
* **Expected Deliverables**: Integration flows opening pull requests.
* **Estimated Difficulty**: **Medium**

---

## Phase 14: Deployment (Vercel + Render + Neon)
* **Goal**: Launch frontend and backend apps on cloud providers with webhook pipelines.
* **Phase Dependencies**: Depends on **Phase 13**.
* **Features Implemented**:
  * Monorepo Vercel static build definitions.
  * Render FastAPI docker container configs.
  * Neon environment production credentials integration.
* **Files to Create**:
  * [vercel.json](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/frontend/vercel.json)
  * [Dockerfile](file:///c:/Users/Dhivya%20Prabha/Desktop/Projects/Reflexion/backend/Dockerfile)
* **Dependencies Required**: Vercel CLI, Render web service config.
* **Acceptance Criteria**:
  * System operates end-to-end on live domains, carrying out analysis, plans, edits, and pull requests.
* **Expected Deliverables**: Public URLs and production dashboards.
* **Estimated Difficulty**: **Medium**
