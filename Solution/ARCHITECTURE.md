# Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
│                    http://localhost:5000                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP/AJAX
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Flask Web Application                         │
│                         (app.py)                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Routes: /, /api/fetch-issue, /api/create-pr, etc.      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Orchestrates
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   Workflow Orchestrator                          │
│                      (workflow.py)                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Coordinates all services in sequence                    │  │
│  │  Maintains progress log                                  │  │
│  │  Handles errors and retries                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
      │          │          │          │          │
      │          │          │          │          │
┌─────▼────┐ ┌──▼──────┐ ┌─▼──────┐ ┌─▼──────┐ ┌─▼──────────┐
│  Jira    │ │   LLM   │ │  Git   │ │ GitHub │ │   Config   │
│ Service  │ │ Service │ │Service │ │Service │ │  (config)  │
└─────┬────┘ └──┬──────┘ └─┬──────┘ └─┬──────┘ └─┬──────────┘
      │          │          │          │          │
      │          │          │          │          │
┌─────▼────┐ ┌──▼──────┐ ┌─▼──────┐ ┌─▼──────┐ ┌─▼──────────┐
│   Jira   │ │ Azure   │ │  Git   │ │GitHub  │ │   .env     │
│   API    │ │ OpenAI  │ │  CLI   │ │  API   │ │   File     │
└──────────┘ └─────────┘ └────────┘ └────────┘ └────────────┘
```

## Data Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │ 1. Enter Jira Key
     ▼
┌─────────────┐
│   Web UI    │
└────┬────────┘
     │ 2. POST /api/fetch-issue
     ▼
┌─────────────┐    3. Fetch Issue     ┌──────────┐
│ Jira Service├──────────────────────►│   Jira   │
└────┬────────┘                       └──────────┘
     │ 4. Return Issue Data
     ▼
┌─────────────┐
│   Web UI    │ ◄─── Display Issue
└────┬────────┘
     │ 5. POST /api/create-pr
     ▼
┌──────────────┐
│  Workflow    │
│ Orchestrator │
└──┬───────────┘
   │ 6. Analyze Issue
   ▼
┌─────────────┐    7. AI Analysis    ┌──────────────┐
│ LLM Service ├────────────────────►│ Azure OpenAI │
└────┬────────┘                      └──────────────┘
     │ 8. Return Analysis
     ▼
┌─────────────┐    9. Clone/Update   ┌──────────┐
│ Git Service ├────────────────────►│  GitHub  │
└────┬────────┘                      └──────────┘
     │ 10. Create Branch
     ▼
┌─────────────┐    11. Generate Fix  ┌──────────────┐
│ LLM Service ├────────────────────►│ Azure OpenAI │
└────┬────────┘                      └──────────────┘
     │ 12. Return Patch
     ▼
┌─────────────┐
│ Git Service │ ◄─── 13. Apply Patch
└────┬────────┘
     │ 14. Commit & Push
     ▼
┌──────────────┐   15. Create PR     ┌──────────┐
│GitHub Service├───────────────────►│  GitHub  │
└────┬─────────┘                     └──────────┘
     │ 16. Return PR URL
     ▼
┌─────────────┐
│   Web UI    │ ◄─── Display Success
└─────────────┘
```

## Component Interactions

```
┌────────────────────────────────────────────────────────────────┐
│                        config.py                                │
│  - Loads .env file                                             │
│  - Provides configuration to all services                      │
│  - Validates required settings                                 │
└───────────────────────────┬────────────────────────────────────┘
                            │ Used by
                ┌───────────┼───────────┐
                │           │           │
        ┌───────▼─────┐ ┌──▼────────┐ ┌▼──────────┐
        │jira_service │ │llm_service│ │git_service│
        │             │ │           │ │           │
        │- JIRA API   │ │- Azure    │ │- Git CLI  │
        │- Fetch      │ │  OpenAI   │ │- Branch   │
        │  issues     │ │- Analysis │ │- Commit   │
        │- Parse ADF  │ │- Code gen │ │- Push     │
        └─────────────┘ └───────────┘ └───────────┘
                            │
                    ┌───────┴───────┐
                    │               │
            ┌───────▼────────┐ ┌───▼──────────┐
            │github_service  │ │  workflow.py │
            │                │ │              │
            │- GitHub API    │ │- Orchestrate │
            │- Create PR     │ │- Log progress│
            │- Add comments  │ │- Handle errors│
            └────────────────┘ └──────┬───────┘
                                      │
                              ┌───────▼────────┐
                              │    app.py      │
                              │                │
                              │- Flask routes  │
                              │- REST API      │
                              │- WebSocket alt │
                              └────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend Layer                         │
├─────────────────────────────────────────────────────────────┤
│  HTML5 + CSS3 + Vanilla JavaScript                          │
│  - Responsive design with CSS Grid/Flexbox                  │
│  - Fetch API for AJAX calls                                 │
│  - Real-time polling for status updates                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Backend Layer                           │
├─────────────────────────────────────────────────────────────┤
│  Python 3.10+ with Flask                                    │
│  - REST API endpoints                                       │
│  - Threading for async workflows                            │
│  - Session management                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Integration Layer                         │
├─────────────────────────────────────────────────────────────┤
│  - Jira API (jira library)                                  │
│  - Azure OpenAI API (openai library)                        │
│  - GitHub API (requests library)                            │
│  - Git CLI (subprocess)                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     External Services                        │
├─────────────────────────────────────────────────────────────┤
│  Jira          │  Azure OpenAI   │  GitHub                  │
│  (Issue DB)    │  (AI Engine)    │  (Code Repo)             │
└─────────────────────────────────────────────────────────────┘
```

## Security Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
└────────────────────────────────────────────────────────────┘

1. Environment Variables (.env)
   ├── Jira API Token
   ├── Azure OpenAI API Key
   ├── GitHub Personal Access Token
   └── Flask Secret Key

2. Configuration Validation (config.py)
   ├── Check all required variables
   ├── Fail fast on missing config
   └── No hardcoded credentials

3. API Authentication
   ├── Jira: Basic Auth with token
   ├── Azure: API key in header
   └── GitHub: Bearer token auth

4. Git Authentication
   ├── Token embedded in clone URL
   └── Automatic credential handling

5. Application Security
   ├── Flask secret key for sessions
   ├── No credential exposure in UI
   └── Error messages sanitized
```

## File System Layout

```
AgenticAI-1/
│
├── .env                          (Configuration - NOT in repo)
│
├── Reference/                    (Original reference code)
│   ├── agent.py
│   ├── jira_api.py
│   ├── llm_client.py
│   └── ... (other files)
│
└── Solution/                     (New WebUI implementation)
    │
    ├── app.py                    (Main Flask application)
    ├── config.py                 (Load config from .env)
    ├── workflow.py               (Orchestrator)
    │
    ├── jira_service.py           (Jira integration)
    ├── llm_service.py            (Azure OpenAI integration)
    ├── git_service.py            (Git operations)
    ├── github_service.py         (GitHub API)
    │
    ├── templates/
    │   └── index.html            (Web UI)
    │
    ├── workspace/                (Git repos - auto-created)
    │   └── AIAgent/              (Cloned repository)
    │
    ├── requirements.txt          (Dependencies)
    ├── README.md                 (Documentation)
    ├── QUICKSTART.md             (Quick guide)
    ├── SOLUTION_SUMMARY.md       (This file)
    ├── ARCHITECTURE.md           (Architecture diagrams)
    ├── .gitignore                (Git ignore rules)
    └── __init__.py               (Package init)
```

## Request/Response Flow

### 1. Fetch Issue Request

```
Browser                 Flask App              Jira Service           Jira API
   │                       │                       │                     │
   ├─POST /api/fetch────►│                       │                     │
   │  {issue_key: "X"}    │                       │                     │
   │                      ├──fetch_issue("X")───►│                     │
   │                      │                       ├──GET /rest/api/───►│
   │                      │                       │                     │
   │                      │                       ◄──Issue JSON────────┤
   │                      ◄──Issue data──────────┤                     │
   ◄─Issue JSON───────────┤                       │                     │
```

### 2. Create PR Request

```
Browser              Flask App           Workflow           Services          External
   │                    │                   │                  │                 │
   ├─POST /api/cr────►│                   │                  │                 │
   │  {issue_key}      │                   │                  │                 │
   │                   ├──execute()──────►│                  │                 │
   │                   │   (async)         │                  │                 │
   ◄─{workflow_id}─────┤                   │                  │                 │
   │                   │                   │                  │                 │
   ├─Poll status───────►                   │                  │                 │
   │  (every 2s)       │                   ├──fetch_issue──►│──Jira API────►│
   │                   │                   │                  │                 │
   │                   │                   ├──analyze─────►│──OpenAI API───►│
   │                   │                   │                  │                 │
   │                   │                   ├──clone_repo──►│──Git clone────►│
   │                   │                   │                  │                 │
   │                   │                   ├──create_br───►│──Git branch────►│
   │                   │                   │                  │                 │
   │                   │                   ├──gen_fix─────►│──OpenAI API───►│
   │                   │                   │                  │                 │
   │                   │                   ├──apply_patch─►│──Git apply────►│
   │                   │                   │                  │                 │
   │                   │                   ├──commit──────►│──Git commit───►│
   │                   │                   │                  │                 │
   │                   │                   ├──push────────►│──Git push─────►│
   │                   │                   │                  │                 │
   │                   │                   └──create_pr───►│──GitHub API───►│
   │                   │                                      │                 │
   ◄─{pr_url}───────────◄──result─────────◄─────────────────┤                 │
```

---

**This architecture ensures:**
- ✅ Separation of concerns
- ✅ Modular design
- ✅ Easy testing
- ✅ Scalability
- ✅ Maintainability
- ✅ Security
