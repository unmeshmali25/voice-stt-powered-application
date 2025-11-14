# VoiceOffers Deployment Guide

This guide covers deploying VoiceOffers to dev, staging, and production environments using **Vercel** (frontend), **Railway** (backend), and **Supabase** (database).

---

## Architecture Overview

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

**Environments:**
- **Development**: Local (localhost) + Supabase dev project
- **Staging**: Vercel preview + Railway staging + Supabase staging project
- **Production**: Vercel production + Railway production + Supabase production project

---

## Prerequisites

Before deploying, ensure you have:

1. **GitHub account** with VoiceOffers repository
2. **Vercel account** (free) - [https://vercel.com/signup](https://vercel.com/signup)
3. **Railway account** (free tier available) - [https://railway.app/](https://railway.app/)
4. **Supabase account** (free) - [https://supabase.com/](https://supabase.com/)
5. **OpenAI API key** - [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

---

## Part 1: Supabase Setup (Database)

### Create 3 Supabase Projects

1. **Go to Supabase Dashboard**: [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Create three new projects:
   - **voiceoffers-dev** (Development)
   - **voiceoffers-staging** (Staging)
   - **voiceoffers-prod** (Production)

### For Each Project:

#### Step 1: Apply Database Schema

1. Go to **SQL Editor** in Supabase dashboard
2. Copy contents of `migrations/postgres_schema.sql`
3. Paste and run the SQL
4. Verify tables created: users, coupons, user_coupons, etc.

#### Step 2: Apply Seed Data (Dev & Staging Only)

**For Development:**
```sql
-- Run migrations/seed_dev.sql in SQL Editor
```

**For Staging:**
```sql
-- Run migrations/seed_staging.sql in SQL Editor
```

**For Production:**
- Do NOT run seed data
- Production will use real customer data

#### Step 3: Get API Credentials

1. Go to **Project Settings → API**
2. Copy these values:
   - **Project URL**: `https://xxx.supabase.co`
   - **anon/public key**: `eyJ...` (starts with eyJ)
   - **JWT Secret**: Found under **Project Settings → API → JWT Settings**

3. Save these for later configuration.

---

## Part 2: Railway Backend Deployment

### Initial Setup

1. **Go to Railway Dashboard**: [https://railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select the `VoiceOffers` repository

### Create Two Services (Staging & Production)

#### Service 1: Staging Backend

1. **Create Service**:
   - Name: `voiceoffers-backend-staging`
   - Branch: `staging` (you'll create this branch)
   - Root directory: `/` (leave as root)

2. **Configure Environment Variables** (see full list in `.env.staging.template`)

3. **Deploy**: Railway will auto-deploy on push to `staging` branch

#### Service 2: Production Backend

Same as staging, but using `main` branch and production Supabase credentials.

---

## Part 3: Vercel Frontend Deployment

### Initial Setup

1. **Go to Vercel Dashboard**: [https://vercel.com/dashboard](https://vercel.com/dashboard)
2. Click **"Add New... → Project"**
3. **Import Git Repository**: Select `VoiceOffers` from GitHub

### Configure Project

1. **Framework Preset**: Vite
2. **Root Directory**: `frontend`
3. **Build Command**: `npm run build`
4. **Output Directory**: `dist`

### Configure Environment Variables

Use templates in `frontend/.env.staging.template` and `frontend/.env.production.template`

---

## Part 4: Create Staging Branch

```bash
git checkout -b staging
git push -u origin staging
```

---

## Environment Variable Summary

See `.env.example` and `.env.staging.template` for complete lists.

---

## Cost Breakdown

### Free Tier (Staging)
- **Vercel**: Free
- **Railway**: Free (500 hours/month)
- **Supabase**: Free (500MB DB)
- **Total**: $0/month + OpenAI usage

### Production (Recommended)
- **Vercel**: $0-20/month
- **Railway**: $5-10/month
- **Supabase**: Free (or $25/month Pro)
- **Total**: $5-30/month + OpenAI usage

---

## Troubleshooting

### Backend Returns 503
- Check DATABASE_URL in Railway
- Verify Supabase project is active

### CORS Errors
- Verify FRONTEND_URL matches Vercel URL
- Redeploy backend after updating

### Rate Limit Errors (429)
- STT: 10 req/min per IP
- Search: 30 req/min per IP

---

For detailed step-by-step instructions, see the original DEPLOYMENT.md sections above or contact the development team.

*Last Updated: 2025-11-14*
