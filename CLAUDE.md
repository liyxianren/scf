# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SCF Hub - A Flask-based educational platform supporting Python and C programming, featuring interactive code execution, lessons, exercises with automated grading, and AI-powered creative project generation agents.

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

## Environment Variables

- `PORT` - Server port (default: 5000)
- `SECRET_KEY` - Flask secret key (default: 'python-teaching-website-secret-key')
- `SCF_DB_PATH` - Database file path (default: `/data/database.db`)
- `HANDBOOK_STORAGE_ROOT` - Handbook file storage root (default: `/data/handbooks`)
- AI API keys (required for handbook/creative agents): Configure in client files or via environment

## Architecture

### Backend Structure
- **app.py** - Flask entry point, registers blueprints, auto-initializes database, cleans expired plans
- **config.py** - Configuration (SQLite DB, 5s code execution timeout)
- **models/** - SQLAlchemy models: `Lesson`, `Exercise`, `Submission`, `Agent`, `CreativeProject`, `ProjectPlan`, `EngineeringHandbook`
- **routes/** - API blueprints:
  - `/api/lessons` - Lesson content (Markdown → HTML conversion)
  - `/api/exercises` - Exercise CRUD and submission grading
  - `/api/code/run` - Code execution endpoint (Python and C)
  - `/company/*` - AI agent routes (creative project generator, plans management)
  - `/company/handbook/*` - Engineering handbook generator and library
- **services/** - Business logic:
  - `CodeExecutor` - Thread-based Python code execution with timeout
  - `CExecutor` - C code compilation (gcc) and execution with timeout
  - `ExerciseChecker` - Test case validation (output/function types)
- **utils/** - AI client wrappers:
  - `ZhipuClient` - ChatGLM API wrapper
  - `DeepSeekClient` - DeepSeek API wrapper
  - `CreativeAgent` - Multi-node AI pipeline for project idea generation
  - `HandbookAgent` - Engineering handbook generator with multi-system support
  - `HandbookExporter` - Markdown to Word (DOCX) converter with professional styling

### Multi-Language Support
Routes are namespaced by language (`/python/*` and `/c/*`). Legacy routes redirect to Python. Each language has:
- Lessons at `data/lessons/XX_*.md`
- Separate executor: `CodeExecutor` (Python) or `CExecutor` (C via gcc)

### AI Agent System (CreativeAgent)
Located in `utils/ai_nodes.py`. Four-node pipeline:
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
`CodeExecutor` uses daemon threads with 5s timeout:
- Redirects stdin/stdout/stderr via `io.StringIO`
- Overrides `input()` to read from provided stdin string
- Returns `{success, output, error, timeout}` dict

### Code Execution (C)
`CExecutor` compiles via gcc, then runs binary:
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

### Background Plan Generation
`agent_routes.py` spawns daemon threads for async plan generation:
- Plans expire after 3 days unless favorited
- Status polling via `/api/plans/<id>`

### Engineering Handbook System
`handbook_agent.py` generates college application engineering portfolios:
- **Multi-system support**: US (Common App), UK (UCAS), HK-SG (technical-focused)
- **System-specific styling**: Each system has different content weights and writing styles
  - US: Personal narrative, emotional growth, reflection-heavy
  - UK: Academic rigor, technical depth, formal references
  - HK-SG: Data-driven, code samples, architecture diagrams
- **Section structure**: metadata, executive_summary, problem_definition, system_design, implementation, testing, reflection, appendix
- **Input materials**: Project description, source code (URL/file), process materials
- **Background generation**: Async generation via daemon threads, 30-day expiration (unless favorited)
- **Export formats**: Markdown and DOCX (professional Word format with styled headers, tables, code blocks)

### DOCX Export System
`export_helper.py` converts Markdown to professionally formatted Word documents:
- **Custom styles**: Configurable fonts (Chinese: 微软雅黑/宋体, English: Arial/Times New Roman)
- **Advanced features**: Table of contents, header/footer, styled tables, code blocks with syntax highlighting
- **Markdown support**: Headings, lists (bullet/numbered), tables, code blocks, inline formatting (bold, italic, code, links)
- **Page layout**: A4 size with proper margins (1.25" left/right, 1" top/bottom)

## File Storage

Handbook materials stored in configurable directory:
- **Storage root**: Configurable via `HANDBOOK_STORAGE_ROOT` env var, defaults to `/data/handbooks` (or `data/handbooks` locally)
- **Structure**: `uploads/{handbook_id}/{subdir}/` for user uploads, `generated/{handbook_id}/` for AI-generated files
- **File handling**: Uses `werkzeug.secure_filename()` for safe file naming

## Database

SQLite at `instance/database.db` (configurable via `SCF_DB_PATH` env var, defaults to `/data/database.db`). Models:
- `Lesson` - language, chapter_num, title, content_file
- `Exercise` - language, lesson_id, test_cases (JSON), difficulty (1-3)
- `Submission` - exercise_id, code, is_correct, result
- `Agent` - AI agent metadata (name, description, icon, status)
- `CreativeProject` - Saved creative project archives
- `ProjectPlan` - Async-generated project plans with expiration (3 days)
- `EngineeringHandbook` - Multi-system engineering portfolios with expiration (30 days)

## Styling

CSS uses variables in `:root` for theming:
- Primary: `--primary-color: #0ea5e9` (科技蓝)
- Gradient: `--primary-gradient: linear-gradient(135deg, #0ea5e9, #06b6d4)`

When modifying colors, update both `style.css` variables and any inline styles in `lesson_detail.html`.
