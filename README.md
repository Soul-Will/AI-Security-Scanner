# 🛡️ AI Security Scanner

An automated Static Application Security Testing (SAST) application designed to scan code repositories for security vulnerabilities, secrets, misconfigurations, and code quality issues. Built with **FastAPI**, **Semgrep**, **Supabase**, and **Next.js**.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Tech Stack & Versions](#-tech-stack--versions)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Backend Setup (FastAPI)](#2-backend-setup-fastapi)
  - [3. Frontend Setup (Next.js)](#3-frontend-setup-nextjs)
- [Configuration & Environment Variables](#-configuration--environment-variables)
- [API Reference](#-api-reference)
- [Database Schema](#-database-schema)
- [Troubleshooting](#-troubleshooting)

---

## 🔍 Overview

The **AI Security Scanner** provides a streamlined web interface and backend API engine to analyze source code for security flaws. It clones public or private Git repositories into isolated temporary environments, runs **Semgrep** static security analysis rules (`--config=auto`), records scan metrics and findings into **Supabase**, and presents real-time findings to the user via a modern responsive UI.

---

## ⚡ Key Features

- **Automated Repository Scanning**: Clone and perform lightweight depth-1 shallow scans on GitHub repositories.
- **Static Analysis Engine**: Leverages **Semgrep SAST** to detect OWASP Top 10 vulnerabilities, leaked credentials, insecure crypto usage, and common anti-patterns.
- **Cloud Database Persistence**: Tracks scan history, statuses, and detailed findings in **Supabase**.
- **Interactive Security Dashboard**: Real-time scan initiation form, severity filter, rule viewer, line/column locator, and raw JSON findings inspector.
- **RESTful API**: Easily integrate scan triggers and health monitoring into CI/CD pipelines.

---

## 🛠️ Tech Stack & Versions

### Backend

| Component | Framework / Tool | Version | Description |
|---|---|---|---|
| **Language** | Python | `>= 3.11` | Primary runtime environment |
| **API Framework** | FastAPI | `0.141.1` | High-performance asynchronous REST API framework |
| **ASGI Server** | Uvicorn | `0.52.3` | ASGI web server for FastAPI |
| **Database SDK** | Supabase Python | `2.31.0` | Client for Supabase database & storage |
| **Security Scanner** | Semgrep | `1.173.0` | Command-line static analysis engine |
| **Data Validation** | Pydantic | `2.13.4` | Data modeling & settings validation (`pydantic-settings 2.15.0`) |
| **Environment** | python-dotenv | `1.2.2` | `.env` environment configuration loader |

### Frontend

| Component | Framework / Tool | Version | Description |
|---|---|---|---|
| **Framework** | Next.js | `16.3.1` | React framework (App Router architecture) |
| **UI Library** | React | `19.2.8` | Core UI engine |
| **Styling** | Tailwind CSS | `^4.0.0` | Utility-first CSS styling framework |
| **Language** | TypeScript | `^5.0.0` | Type-safe web development |
| **Client Database** | @supabase/supabase-js | `^2.112.3` | Client SDK for browser queries |

---

## 📁 Project Directory Structure

```
Codebase/
├── backend/                         # Python FastAPI Backend
│   ├── config.py                    # Environment variable parser & config manager
│   ├── main.py                      # FastAPI app entry point, CORS, & primary routes
│   ├── requirements.txt             # Python dependencies manifest
│   ├── .env                         # Environment variable configurations (secrets)
│   ├── database/                    # Database models and migration utilities
│   ├── logs/                        # Application runtime execution logs
│   └── src/                         # Core backend application modules
│       ├── routers/
│       │   └── scans.py             # Router defining /api/scans endpoints
│       └── utils/
│           └── github.py            # Git cloning & Semgrep execution engine
├── frontend/                        # Next.js Frontend Client
│   ├── app/                         # App router pages & components
│   │   ├── page.tsx                 # Home page displaying backend health check
│   │   ├── scan/
│   │   │   └── page.tsx             # Scan submission form & interactive findings dashboard
│   │   ├── layout.tsx               # Root application layout
│   │   └── globals.css              # Global styles & Tailwind CSS imports
│   ├── public/                      # Static branding assets & icons
│   ├── eslint.config.mjs            # ESLint rules configuration
│   ├── next.config.ts               # Next.js configuration
│   ├── package.json                 # Node dependencies and build scripts
│   ├── postcss.config.mjs           # PostCSS setup for Tailwind CSS v4
│   └── tsconfig.json                # TypeScript project configuration
├── .gitignore                       # Ignored repository files and directories
└── README.md                        # Project documentation
```

---

## ⚙️ Prerequisites

Before installing and running the project, ensure you have the following installed on your operating system:

1. **Python 3.11 or higher**: Download from [python.org](https://www.python.org/downloads/).
2. **Node.js 20.x or higher** and `npm`: Download from [nodejs.org](https://nodejs.org/).
3. **Git CLI**: Required in system `PATH` to perform repository cloning. Verify with:
   ```bash
   git --version
   ```
4. **Semgrep CLI**: Required in system `PATH` to execute security analysis. Install via pip or Homebrew:
   ```bash
   pip install semgrep
   # Verify installation:
   semgrep --version
   ```
5. **Supabase Project**: A valid Supabase URL and Anon/Service Key.

---

## 🚀 Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/Soul-Will/AI-Security-Scanner.git
cd AI-Security-Scanner
```

---

### 2. Backend Setup (FastAPI)

Navigate to the `backend` directory:

```bash
cd backend
```

#### Create & Activate Virtual Environment

- **On Windows (PowerShell)**:
  ```powershell
  python -m venv env
  .\env\Scripts\Activate.ps1
  ```

- **On Linux / macOS**:
  ```bash
  python3 -m venv env
  source env/bin/activate
  ```

#### Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### Configure Environment Variables

Create or edit the `.env` file inside the `backend/` directory:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-key
```

#### Start FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

*The backend server will run at [http://localhost:8000](http://localhost:8000).*

---

### 3. Frontend Setup (Next.js)

Open a new terminal tab and navigate to the `frontend` directory:

```bash
cd frontend
```

#### Install Node Dependencies

```bash
npm install
```

#### Start Development Server

```bash
npm run dev
```

*The frontend application will run at [http://localhost:3000](http://localhost:3000).*

---

## 🔑 Configuration & Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required | Example |
|---|---|---|---|
| `SUPABASE_URL` | Supabase API URL | Yes | `https://xyzcompany.supabase.co` |
| `SUPABASE_KEY` | Supabase API Service / Anon key | Yes | `eyJhbGciOi...` |

---

## 📡 API Reference

### Health Check

- **Endpoint**: `GET /`
- **Description**: Returns operational status of the backend API service.
- **Response**:
  ```json
  {
    "status": "ok",
    "message": "Backend is running!"
  }
  ```

---

### Submit Security Scan

- **Endpoint**: `POST /api/scans`
- **Description**: Initiates static security scan on target input (e.g. GitHub repository).
- **Request Body**:
  ```json
  {
    "input_type": "github",
    "input_value": "https://github.com/user/repository"
  }
  ```
- **Response**:
  ```json
  {
    "scan_id": "c1f2e3d4-5678-90ab-cdef-1234567890ab",
    "status": "completed",
    "total_findings": 3,
    "findings": [
      {
        "check_id": "python.lang.security.audit.hardcoded-password",
        "path": "config.py",
        "start": { "line": 12, "col": 5 },
        "extra": {
          "message": "Hardcoded password detected",
          "severity": "ERROR"
        }
      }
    ]
  }
  ```

---

### Get Scan Status & Findings

- **Endpoint**: `GET /api/scans/{scan_id}`
- **Description**: Fetches details and scan status for a specific `scan_id`.
- **Response**:
  ```json
  {
    "scan_id": "c1f2e3d4-5678-90ab-cdef-1234567890ab",
    "status": "completed",
    "vulnerabilities": []
  }
  ```

---

## 📊 Database Schema (Supabase)

Create a table named `scans` in your Supabase project database with the following schema:

```sql
CREATE TABLE scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_type TEXT NOT NULL,
    input_value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
```

---

## ❓ Troubleshooting

1. **`Git clone failed` or `Semgrep scan failed`**:
   - Ensure `git` and `semgrep` executable binaries are installed and accessible on your environment `PATH`.
   - Test by running `git --version` and `semgrep --version` in terminal.

2. **CORS Error from Frontend**:
   - Ensure `backend/main.py` CORS origins match your frontend host (`http://localhost:3000`).

3. **Supabase Connection Errors**:
   - Verify `SUPABASE_URL` and `SUPABASE_KEY` values in `backend/.env`.
