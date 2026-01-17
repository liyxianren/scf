# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python 教学平台 - A Flask-based web application for learning Python programming, featuring interactive code execution, lessons, and exercises with automated grading.

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

## Architecture

### Backend Structure
- **app.py** - Flask entry point, registers blueprints, auto-initializes database
- **config.py** - Configuration (SQLite DB, 5s code execution timeout)
- **models/** - SQLAlchemy models: `Lesson`, `Exercise`, `Submission`
- **routes/** - API blueprints:
  - `/api/lessons` - Lesson content (Markdown → HTML conversion)
  - `/api/exercises` - Exercise CRUD and submission grading
  - `/api/code/run` - Code execution endpoint
- **services/** - Business logic:
  - `CodeExecutor` - Thread-based Python code execution with timeout
  - `ExerciseChecker` - Test case validation (output/function types)

### Frontend Structure
- **templates/** - Jinja2 templates extending `base.html`
- **static/css/style.css** - Main stylesheet with CSS variables (科技蓝 theme)
- **static/js/**:
  - `editor.js` - CodeMirror editor for playground
  - `exercise.js` - Exercise submission logic
  - `input-dialog.js` - Interactive input() modal system

### Data Flow
1. Lessons stored as Markdown in `data/lessons/XX_name.md`
2. Code execution: User code → `/api/code/run` → `CodeExecutor` (threaded exec with stdin/stdout capture) → JSON result
3. Exercise grading: Submission → `ExerciseChecker.check_submission()` → Compare against JSON test cases → Store result

## Key Implementation Details

### Code Execution System
`CodeExecutor` uses daemon threads with 5s timeout. It:
- Redirects stdin/stdout/stderr via `io.StringIO`
- Overrides `input()` to read from provided stdin string
- Returns `{success, output, error, timeout}` dict

### Input Dialog System
`input-dialog.js` detects `input()` calls in code:
- Parses code to count `input()` occurrences (excluding comments/strings)
- Extracts prompt messages from `input("prompt")`
- Shows modal for each input sequentially
- Concatenates inputs with newlines for backend

### Exercise Test Cases (JSON format)
```json
{
  "test_type": "output",  // or "function"
  "cases": [{"input": "...", "expected_output": "..."}]
}
```

## Database

SQLite at `instance/database.db`. Models:
- `Lesson` - chapter_num, title, content_file (path to .md)
- `Exercise` - lesson_id, test_cases (JSON), difficulty (1-3)
- `Submission` - exercise_id, code, is_correct, result

## Styling

CSS uses variables in `:root` for theming:
- Primary: `--primary-color: #0ea5e9` (科技蓝)
- Gradient: `--primary-gradient: linear-gradient(135deg, #0ea5e9, #06b6d4)`

When modifying colors, update both `style.css` variables and any inline styles in `lesson_detail.html`.
