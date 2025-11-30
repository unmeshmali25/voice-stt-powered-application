# VoiceOffers

VoiceOffers is an AI-powered search platform that helps retail customers discover relevant coupons and products using natural language and multi-modal inputs.

## Architecture

The application follows a modern 3-tier architecture:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          🎯 VoiceOffers Data Flow                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

    👤 USER                                                     ☁️  CLOUD SERVICES
     │                                                               │
     │  🎤 Voice                                                     │
     │  ⌨️  Text         ┌─────────────────────────────┐             │
     │  📸 Image    ────▶│   🎨 FRONTEND               │             │
     │  🔍 AR Scan       │   React + Vite + Tailwind   │             │
     │                   └──────────┬──────────────────┘             │
     │                              │                                │
     │                              │ 🔊 Audio Blob                  │
     │                              ▼                                │
     │                   ┌─────────────────────────────┐             │
     │                   │  🤖 OpenAI Whisper API      │◀────────────┘
     │                   │  (Speech-to-Text)           │
     │                   └──────────┬──────────────────┘
     │                              │
     │                              │ 📝 Transcript
     │                              ▼
     │                   ┌─────────────────────────────┐
     │                   │   🎨 FRONTEND               │
     │                   │   (Updates UI in real-time) │
     │                   └──────────┬──────────────────┘
     │                              │
     │                              │ 🔍 Search Query (text/vector)
     │                              ▼
     │                   ┌─────────────────────────────┐
     │                   │   ⚡ BACKEND API            │
     │                   │   FastAPI + Python 3.11     │
     │                   └──────────┬──────────────────┘
     │                              │
     │                              │ 🔎 Vector/Text Search
     │                              ▼
     │                   ┌─────────────────────────────┐
     │                   │   🗄️  DATABASE              │
     │                   │   Supabase PostgreSQL       │
     │                   │   (pg_trgm + vector)        │
     │                   └──────────┬──────────────────┘
     │                              │
     │                              │ 📦 Results (Coupons + Products)
     │                              ▼
     │                   ┌─────────────────────────────┐
     │                   │   ⚡ BACKEND API            │
     │                   │   (Processes & Formats)     │
     │                   └──────────┬──────────────────┘
     │                              │
     │                              │ 📊 JSON Response
     │                              ▼
     │                   ┌─────────────────────────────┐
     │              ┌───▶│   🎨 FRONTEND               │
     │              │    │   (Displays Results)        │
     └──────────────┘    └─────────────────────────────┘
      ✨ Beautiful UI
```

## 🏗️ Architecture Overview

```
┌─────────────────────┐
│   GitHub Repository │
│   (main/staging)    │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐  ┌─────────┐
│ Vercel  │  │ Railway │
│Frontend │  │ Backend │
└────┬────┘  └────┬────┘
     │            │
     └────┬───────┘
          ▼
    ┌──────────┐
    │ Supabase │
    │ Database │
    └──────────┘
```

```
Development:
├── Local machine (localhost:5174, localhost:8000)
└── Supabase dev project

Staging:
├── Vercel Preview (voiceoffers-staging.vercel.app)
├── Railway Staging (voiceoffers-staging.up.railway.app)
└── Supabase Staging Project

Production:
├── Vercel Production (voiceoffers.vercel.app)
├── Railway Production (voiceoffers-prod.up.railway.app)
└── Supabase Production Project
```


### Components

*   **Frontend**: React 18, TypeScript, Tailwind CSS (Hosted on Vercel)
*   **Backend**: FastAPI, Python 3.11 (Hosted on Railway)
*   **Database**: PostgreSQL with `pg_trgm` and `vector` extensions (Hosted on Supabase)
*   **AI Services**: OpenAI Whisper (STT) and Embeddings

## Screenshots

### Home Screen
![Home Screen](./screenshots/home.png)
*AI-powered search interface with real-time transcription.*

### Product Results
![Product Results](./screenshots/products.png)
*3-column layout showing Products, Front-store offers, and Category offers.*

## Development Workflow

We use a Git-based workflow with three environments:

### 1. Local Development (`localhost`)
*   **Frontend**: `npm run dev` (Port 5174)
*   **Backend**: `python -m app.main` (Port 8000)
*   **Database**: Connects to Supabase `dev` project.
*   **Flow**: Create feature branches, test locally, and push to GitHub.

### 2. Staging (`voiceoffers-staging.vercel.app`)
*   **Trigger**: Push/Merge to `staging` branch.
*   **CI/CD**: GitHub Actions automatically deploys:
    *   Backend to Railway (Staging service)
    *   Frontend to Vercel (Preview deployment)
*   **Database**: Connects to Supabase `staging` project.
*   **Purpose**: Integration testing and feature verification.

### 3. Production (`voiceoffers.vercel.app`)
*   **Trigger**: Merge `staging` to `main` branch.
*   **CI/CD**: GitHub Actions deploys to production environments.
*   **Database**: Connects to Supabase `production` project.
*   **Purpose**: Live traffic.

## Supabase Postgres Schema Design

Our database design follows strict relational principles to ensure data integrity and performance:

1.  **Normalization & Integrity**:
    *   **Foreign Keys**: Strict relationships between `users`, `coupons`, and `products` with `ON DELETE CASCADE` to maintain referential integrity.
    *   **Constraints**: `CHECK` constraints on coupon types ensure data validity at the database level.

2.  **Performance Optimization**:
    *   **Indexing**: B-tree indexes on high-cardinality columns (IDs, categories) and GIN indexes on `tsvector` columns for fast full-text search.
    *   **Computed Columns**: `text_vector` columns are automatically updated via **Triggers** whenever relevant data changes, ensuring search is always up-to-date without application overhead.

3.  **Authentication Integration**:
    *   The `users` table is designed to sync directly with Supabase's `auth.users`, serving as a public profile extension to the secure authentication system.

### Core Tables

*   `users`: Extended profile data linked to Supabase Auth.
*   `products`: Catalog with full-text search vectors.
*   `coupons`: Offers with validity periods and types.
*   `user_coupons`: Many-to-many relationship tracking assigned offers.

## Quick Start

1.  **Clone**: `git clone <repo>`
2.  **Env Vars**: Copy `.env.example` to `.env` and fill in API keys.
3.  **Install**:
    *   Backend: `pip install -r requirements.txt`
    *   Frontend: `cd frontend && npm install`
4.  **Run**:
    *   Backend: `python -m app.main`
    *   Frontend: `npm run dev`
