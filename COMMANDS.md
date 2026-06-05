# Project Commands Documentation

This file consolidates all useful commands for developing, running, testing, and deploying the **AI‑Recruiter** project.

## Backend (FastAPI & SQLite)

- **Create virtual environment**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate   # Windows PowerShell
  ```

- **Install dependencies**
  ```powershell
  pip install -r requirements.txt
  ```

- **Run FastAPI development server**
  ```powershell
  uvicorn app.main:app --reload
  ```
  The API docs are available at `http://127.0.0.1:8000/docs`.

- **Run unit/verification tests**
  ```powershell
  python test_scoring.py
  ```

- **Export CSV of candidates** (exposed via the admin UI – no CLI command needed, but the helper utility is `src/lib/csv.ts`).

## Frontend (Next.js with TypeScript & Tailwind)

> The frontend lives under `frontend/`.

- **Install Node dependencies**
  ```bash
  cd frontend
  npm install
  ```

- **Start the development server**
  ```bash
  npm run dev
  ```
  The app will be served at `http://localhost:3000`.

- **Build for production**
  ```bash
  npm run build
  ```

- **Run lint & formatting**
  ```bash
  npm run lint   # eslint
  npm run format # prettier
  ```

- **Run End‑to‑End tests with Playwright**
  ```bash
  npx playwright test
  ```

## Docker (optional quick start)

- **Build the image**
  ```bash
  docker build -t ai-recruiter .
  ```

- **Run the container**
  ```bash
  docker run -p 8000:8000 -p 8501:8501 ai-recruiter
  ```
  This starts both the FastAPI backend (`8000`) and the Streamlit UI (`8501`).

## CI / GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that automatically:

1. Sets up Python and Node environments.
2. Installs dependencies.
3. Runs `python -m pytest` (backend unit tests).
4. Executes `npm run lint && npx playwright test` (frontend lint + E2E).
5. Builds Docker image on push to `main`.

## Utility Scripts (Node)

- **Generate CSV** – The helper `src/lib/csv.ts` is used by the admin UI; the exposed function is `downloadCSV(filename, data)`.
- **Resume PDF viewer** – Implemented in `src/components/admin/ResumeViewer.tsx`.
- **Score visualisation** – Implemented in `src/components/admin/ScoreVisualization.tsx`.

---

*Keep this file updated whenever new scripts or commands are added.*
