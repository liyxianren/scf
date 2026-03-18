# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

SCF Hub - A Flask-based educational platform supporting Python and C programming, featuring interactive code execution, lessons, exercises with automated grading, AI-powered creative project generation agents, engineering handbook generation, and an internal OA system.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database (auto-runs on first app start, or manually)
python init_db.py

# Run development server
python app.py

# Production server (Zeabur deployment)
gunicorn app:app --bind 0.0.0.0:$PORT
```

The app runs on port 5000 by default, or uses the `PORT` environment variable.

```bash
# Docker build & run (production uses Zeabur)
docker build -t scf-hub .
docker run -p 8080:8080 scf-hub
```

**Note:** There is no test suite or linter configured in this project. C code execution requires `gcc` installed on the host (included in Dockerfile).

## Environment Variables

- `PORT` - Server port (default: 5000)
- `SECRET_KEY` - Flask secret key (default: 'python-teaching-website-secret-key')
- `SCF_DB_PATH` - Database file path (default: `/data/database.db`)
- `HANDBOOK_STORAGE_ROOT` - Handbook file storage root (default: `/data/handbooks`)
- `DEEPSEEK_API_KEY` - DeepSeek AI API key
- `ZHIPU_API_KEY` - Zhipu (ChatGLM) AI API key
- `MINIMAX_API_KEY` - MiniMax AI API key

## Architecture

### Application Factory Pattern

The app uses Flask Application Factory (`create_app()` in `app.py`). Bottom-level `app = create_app()` provides backward compatibility with `gunicorn app:app`.

### Directory Structure

```
scf-main/
├── app.py                  # Application Factory: create_app() + page routes
├── config.py               # Unified config (DB, AI keys from env vars)
├── extensions.py           # db = SQLAlchemy() singleton
├── init_db.py              # Database seed data
│
├── core/                   # Shared infrastructure
│   ├── ai/                 # AI provider clients
│   │   ├── base.py         # AIClient abstract base class
│   │   ├── deepseek.py     # DeepSeekClient (key from config)
│   │   ├── zhipu.py        # ZhipuClient (key from config)
│   │   └── __init__.py     # get_ai_client() factory
│   ├── tasks.py            # TaskRunner (async abstraction, currently threads)
│   └── storage.py          # File storage utilities
│
├── modules/                # Business domain modules
│   ├── education/          # Programming learning system
│   │   ├── models.py       # Lesson, Exercise, Submission
│   │   ├── routes/         # lesson_bp, exercise_bp, code_runner_bp
│   │   └── services/       # CodeExecutor, CExecutor, ExerciseChecker
│   │
│   ├── agents/             # AI creative agent system
│   │   ├── models.py       # Agent, CreativeProject, ProjectPlan
│   │   ├── routes.py       # agent_bp
│   │   ├── services.py     # CreativeAgent pipeline
│   │   └── templates/agents/
│   │
│   ├── handbook/           # Engineering handbook system
│   │   ├── models.py       # EngineeringHandbook
│   │   ├── routes.py       # handbook_bp
│   │   ├── services/       # HandbookAgent, HandbookExporter
│   │   └── templates/handbook/
│   │
│   └── oa/                 # Internal OA system
│       ├── models.py       # CourseSchedule, OATodo
│       ├── routes.py       # oa_bp
│       ├── services.py     # Excel importer
│       └── templates/oa/
│
├── templates/              # Shared templates
│   ├── base.html
│   ├── landing.html
│   └── education/          # Education page templates
│
├── static/                 # Static assets
├── data/                   # Lesson markdown files
└── requirements.txt
```

### Blueprint Registration

| Blueprint | URL Prefix | Module |
|-----------|-----------|--------|
| `lessons` | `/api/lessons` | `modules.education` |
| `exercises` | `/api/exercises` | `modules.education` |
| `code_runner` | `/api/code` | `modules.education` |
| `agent` | `/company` | `modules.agents` |
| `handbook` | `/company/handbook` | `modules.handbook` |
| `oa` | `/oa` | `modules.oa` |

### Core Infrastructure

**AI Clients** (`core/ai/`): Abstract base class with DeepSeek and Zhipu implementations. API keys read from `flask.current_app.config` (not hardcoded). Factory: `get_ai_client('deepseek')`.

**TaskRunner** (`core/tasks.py`): Async task abstraction. Currently uses daemon threads with automatic Flask app context injection. Designed for future Celery/RQ migration.

**Storage** (`core/storage.py`): File storage utilities for handbook uploads and generated files.

### Multi-Language Support
Routes are namespaced by language (`/python/*`, `/c/*`, `/vibe/*`). Legacy routes redirect to Python. Each language has:
- Lessons at `data/lessons/XX_*.md`
- Separate executor: `CodeExecutor` (Python) or `CExecutor` (C via gcc)

### AI Agent System (CreativeAgent)
Located in `modules/agents/services.py`. Four-node pipeline:
1. **Node 1 (analyze_input)** - Expands keywords into 3 directions (Tool/Platform/Hardware)
2. **Node 2 (brainstorm)** - Generates 6-9 project ideas per direction
3. **Node 3 (assess_feasibility)** - Filters to top 3 feasible projects
4. **Node 4 (generate_report)** - Produces detailed Markdown project plan

Supports dual-model execution (ChatGLM + DeepSeek) via `brainstorm_dual_full()`.

### Data Flow
1. Lessons stored as Markdown in `data/lessons/XX_name.md`
2. Code execution: User code → `/api/code/run` → `CodeExecutor`/`CExecutor` → JSON result
3. Exercise grading: Submission → `ExerciseChecker.check_submission()` → Compare against JSON test cases
4. Creative generation: Keywords → CreativeAgent pipeline → Streamed Markdown report (NDJSON)
5. Handbook generation: Project materials → HandbookAgent → Multi-system Markdown → HandbookExporter → DOCX download

## Key Implementation Details

### Code Execution (Python)
`CodeExecutor` (`modules/education/services/code_executor.py`) uses daemon threads with 5s timeout:
- Redirects stdin/stdout/stderr via `io.StringIO`
- Overrides `input()` to read from provided stdin string
- Returns `{success, output, error, timeout}` dict

### Code Execution (C)
`CExecutor` (`modules/education/services/c_executor.py`) compiles via gcc, then runs binary:
- Compile timeout: 10s, Run timeout: 5s
- Handles cross-platform paths (Windows .exe vs Unix binary)
- Translates return codes to user-friendly error messages (SIGSEGV, SIGFPE, etc.)

### Input Dialog System
`input-dialog.js` detects `input()` calls in code:
- Parses code to count `input()` occurrences (excluding comments/strings)
- Extracts prompt messages from `input("prompt")`
- Shows modal for each input sequentially
- Concatenates inputs with newlines for backend

### Exercise Test Cases (JSON format)
```json
{
  "test_type": "output",
  "cases": [{"input": "...", "expected_output": "..."}]
}
```

### Background Task Generation
Uses `core.tasks.TaskRunner` for async operations:
- Plan generation: Plans expire after 3 days unless favorited
- Handbook generation: Handbooks expire after 30 days unless favorited
- TaskRunner auto-injects Flask app context

### Engineering Handbook System
`modules/handbook/services/agent.py` generates college application engineering portfolios:
- **Multi-system support**: US (Common App), UK (UCAS), HK-SG (technical-focused)
- **System-specific styling**: Each system has different content weights and writing styles
- **Section structure**: metadata, executive_summary, problem_definition, system_design, implementation, testing, reflection, appendix
- **Input materials**: Project description, source code (URL/file), process materials
- **Export formats**: Markdown and DOCX (professional Word format with styled headers, tables, code blocks)

### DOCX Export System
`modules/handbook/services/exporter.py` converts Markdown to professionally formatted Word documents:
- **Custom styles**: Configurable fonts (Chinese: 黑体/宋体, English: Times New Roman)
- **Advanced features**: Table of contents, header/footer, styled tables, code blocks
- **Markdown support**: Headings, lists, tables, code blocks, inline formatting
- **Page layout**: A4 size with proper margins

### OA System
`modules/oa/` provides internal office automation:
- **Course scheduling**: Calendar-based course management with Excel import
- **Todo management**: Priority-based todos with batch operations
- **Dashboard**: Statistics and today's schedule overview

## File Storage

Handbook materials stored in configurable directory:
- **Storage root**: Configurable via `HANDBOOK_STORAGE_ROOT` env var
- **Structure**: `uploads/{handbook_id}/{subdir}/` for user uploads, `generated/{handbook_id}/` for AI-generated files
- **File handling**: Uses `werkzeug.secure_filename()` for safe file naming

## Database

SQLite (configurable via `SCF_DB_PATH` env var, defaults to `/data/database.db`). All models import `db` from `extensions.py`.

Models by module:
- **education**: `Lesson`, `Exercise`, `Submission`
- **agents**: `Agent`, `CreativeProject`, `ProjectPlan`
- **handbook**: `EngineeringHandbook`
- **oa**: `CourseSchedule`, `OATodo`

## Styling

CSS uses variables in `:root` for theming:
- Primary: `--primary-color: #0ea5e9` (科技蓝)
- Gradient: `--primary-gradient: linear-gradient(135deg, #0ea5e9, #06b6d4)`

When modifying colors, update both `style.css` variables and any inline styles in templates.
