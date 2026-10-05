# 🛡️ AI-Powered Security Vulnerability Detection Platform

An automated, end-to-end security analysis platform designed to scan various inputs (repositories, URLs, zip files, Docker containers) for security vulnerabilities, secrets, misconfigurations, and code quality issues. Built with **FastAPI**, **Semgrep**, **Gitleaks**, **Docker Sandbox**, **Supabase**, and **Next.js**, with **AI Triage** powered by Gemini/Groq.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture & Flow](#-architecture--flow)
- [The Four Input Pipelines](#-the-four-input-pipelines)
- [Key Features](#-key-features)
- [Tech Stack & Versions](#-tech-stack--versions)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Environment Variables](#-environment-variables)

---

## 🔍 Overview

The **AI-Powered Security Vulnerability Detection Platform** provides a streamlined web interface and backend API engine to analyze source code, artifacts, and deployed applications for security flaws. It provisions isolated **ephemeral Docker sandboxes** to ensure security during analysis, runs multiple analysis tools (SAST, DAST, Secret detection), and uses **AI Triage** to filter out false positives and intelligently analyze vulnerabilities contextually.

---

## 🏗️ Architecture & Flow

The overarching architecture ensures security and precision:
1. **Frontend**: Next.js App Router for submission and interactive dashboard.
2. **Backend**: FastAPI orchestrates requests.
3. **Queue**: Redis + ARQ manages concurrent job execution and backpressure.
4. **Sandbox**: Temporary, ephemeral Docker containers provisioned per job containing isolated runtimes (no code touches the host disk).
5. **Scanners**: Parallel execution of Semgrep (SAST) and Gitleaks (Secrets) + dependency checks.
6. **AI Triage**: Symmetrically extracts the flagged context (+/- 25 lines) and queries Gemini/Groq to classify and potentially downgrade (never upgrade) the baseline severity to eliminate false positives.
7. **Storage**: Verified JSON results inserted into Supabase (no source code is persisted).
8. **Cleanup**: Reaper sweeps ensure containers and materials are destroyed immediately on job conclusion (whether `completed`, `failed`, or `rejected`).

---

## 🔄 The Four Input Pipelines

The platform aggressively maintains strict isolation between ingestion channels:

1. **GitHub Repository**: Clones the repo (with size/time limits) into an ephemeral container.
2. **Live URL**: Executes a headless crawl (never downloading source to disk) equipped with SSRF defenses for dynamic analysis.
3. **ZIP File**: Employs Zip-bomb (max 50MB) and Zip-slip defenses before extraction into the sandbox.
4. **Docker**: Analyzes either a `Dockerfile` manifest or statically inspects a Docker registry image (MVP: public Docker Hub) without *ever* executing the container.

---

## ⚡ Key Features

- **Multi-Vector Scanning**: SAST, Secret Scanning, and Dependency Hallucination detection in one pass.
- **Strict Isolation**: 100% ephemeral processing. User inputs are never permanently stored, and environments are destroyed post-job.
- **AI Triage Engine**: Integrates LLMs with up to 60,000+ token context ingestion to evaluate and document vulnerabilities.
- **Canonical Status Engine**: Formal job transitions (`queued` -> `validating` -> `preparing` -> `scanning` -> `triaging` -> `completed` / `failed` / `rejected`).
- **Interactive Security Dashboard**: Real-time scan initiation form, pipeline tracking, severity filters, and raw JSON export.

---

## 🛠️ Tech Stack & Versions

### Backend
- **Framework**: FastAPI (Python >= 3.11)
- **Database**: Supabase PostgreSQL + Supabase Client (`2.31.0`)
- **Queue/Workers**: Redis & ARQ for asynchronous job execution.
- **Scanners Engines**: Semgrep, Gitleaks.
- **Containerization**: Docker SDK for ephemeral sandbox handling.

### Frontend
- **Framework**: Next.js `16.3.1` (App Router)
- **UI & Styling**: React `19.2.8`, Tailwind CSS `^4.0.0`, shadcn/ui.
- **Language**: TypeScript `^5.0.0`

---

## 📁 Project Directory Structure
```
Codebase/
├── backend/                         # Python FastAPI Backend
│   ├── src/                         # Core logic
│   │   ├── config/                  # Settings
│   │   ├── routers/                 # API controllers
│   │   ├── schemas/                 # Pydantic validation
│   │   ├── shared_services/         # Reusable modules (AI Triage, DB, Docker Sandbox)
│   │   └── tasks/                   # ARQ pipeline steps
│   ├── worker.py                    # Worker entrypoint
│   └── main.py                      # FastAPI entrypoint
├── frontend/                        # Next.js Frontend Client
│   ├── app/                         # App Router forms and dashboard
│   ├── components/                  # Shared UI components
│   └── lib/                         # Clients (Supabase, Utils)
└── README.md                        # Documentation
```

---

## ⚙️ Prerequisites

1. **Python 3.11+**
2. **Node.js 20.x+** and `npm`
3. **Docker Engine**: Required for the ephemeral sandbox orchestration.
4. **Redis**: Running instance for the ARQ job queue.
5. **Supabase**: Active instance/project.

---

## 🚀 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Soul-Will/AI-Security-Scanner.git
   cd AI-Security-Scanner
   ```

2. **Backend**:
   ```bash
   cd backend
   python -m venv env
   source env/bin/activate  # Or .\env\Scripts\Activate.ps1 on Windows
   pip install -r requirements.txt
   ```
   Start the API server:
   ```bash
   uvicorn main:app --reload
   ```
   Start the ARQ worker (in a new tab):
   ```bash
   arq src.worker.WorkerSettings
   ```

3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 🔑 Environment Variables

Required environment variables (`backend/.env` & `frontend/.env.local`):

| Variable | Description | Example |
|---|---|---|
| `SUPABASE_URL` | Supabase instance URL | `https://xyz.supabase.co` |
| `SUPABASE_KEY` | Supabase Service/Anon key | `eyJhbG...` |
| `REDIS_URL` | Connection for ARQ Job Queue | `redis://localhost:6379` |
| `GEMINI_API_KEY` | API Key for AI Triage / NLP | `AIza...` |
