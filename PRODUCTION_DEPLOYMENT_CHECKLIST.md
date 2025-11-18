# Production Deployment Checklist - Staging → Main

**Date:** 2025-11-18
**Commits:** 18 commits ahead of main
**Migration:** products table + full-text search

---

## ✅ Step 1: Create Database Backup (CRITICAL - DO THIS FIRST!)

### Option A: Supabase Dashboard Backup

1. Go to https://supabase.com/dashboard
2. Select your **PRODUCTION** project
3. Navigate to **Database** → **Backups** (left sidebar)
4. Click **"Create Backup"** or download latest automated backup
5. Save backup file as: `backup_production_YYYYMMDD.sql`

### Option B: Command Line Backup (if you have DATABASE_URL)

```bash
# Set production DATABASE_URL
export DATABASE_URL="postgresql://postgres:[password]@[host]:5432/postgres"

# Create backup
pg_dump $DATABASE_URL > backup_production_$(date +%Y%m%d_%H%M%S).sql

# Verify backup file
ls -lh backup_production_*.sql
```

---

## ✅ Step 2: Verify Migration File

Migration file created: `alembic/versions/2025_11_18_1846-5da34d5930f8_add_products_table_with_fts.py`

**What it does:**
- Creates `products` table with UUID primary key
- Adds 4 indexes (category, brand, text_vector GIN, in_stock)
- Creates `products_text_vector_update()` function
- Creates 2 triggers (text_vector auto-update, updated_at auto-update)

**Rollback available:** `alembic downgrade -1` (drops everything)

---

## ✅ Step 3: Pull Request Created

PR will be created by Claude Code:
- **Base:** `main` ← **Head:** `staging`
- **Title:** "Production deployment: Staging changes (18 commits)"
- **Files changed:** 16 files (+2574, -115)

---

## ✅ Step 4: Merge PR (Triggers Auto-Deployment)

Once PR is merged:
- **GitHub Actions** will run tests
- **Railway** will auto-deploy backend
- **Vercel** will auto-deploy frontend

**Expected deploy time:** 5-10 minutes

---

## ✅ Step 5: Run Migration on Production Database

### After code is deployed, run migration:

```bash
# Connect to production environment (set DATABASE_URL)
export DATABASE_URL="[your-production-database-url]"

# Run migration
alembic upgrade head

# Verify products table was created
psql $DATABASE_URL -c "\dt products"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM products"
```

### Expected Output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 5da34d5930f8, add_products_table_with_fts
```

---

## ✅ Step 6: Load Sample Products (Optional)

If you want to populate the products table with sample data:

```bash
python app/ingestion/ingest_products.py
```

This loads products from `data/products.json`.

---

## ✅ Step 7: Verify Production Deployment

### Backend Health Checks:

```bash
# Check health endpoint
curl https://[your-backend].railway.app/health

# Test products search endpoint
curl https://[your-backend].railway.app/api/products/search?query=skincare
```

### Frontend Verification:

1. Visit: https://voiceoffers.vercel.app
2. Verify 3-column layout loads (Products | Frontstore | Category)
3. Test voice search
4. Check browser console for errors

### Railway Logs:

```bash
# View Railway logs
railway logs --environment production

# Or use Railway dashboard
```

---

## ✅ Step 8: Monitor for 15 Minutes

Watch for errors in:
- Railway deployment logs
- Vercel deployment logs
- Supabase dashboard (database connections)

**Success criteria:**
- ✅ No 500 errors in Railway logs
- ✅ `/health` returns 200 OK
- ✅ `/api/products/search` returns results
- ✅ Frontend renders without console errors

---

## 🚨 ROLLBACK PROCEDURE (if deployment fails)

### Code Rollback:

```bash
# Revert the merge commit
git revert HEAD~1
git push origin main

# OR use Railway/Vercel dashboard "Rollback" button
```

### Database Rollback:

```bash
# Option 1: Alembic downgrade
alembic downgrade -1

# Option 2: Restore from backup
psql $DATABASE_URL < backup_production_YYYYMMDD.sql

# Option 3: Manual cleanup
psql $DATABASE_URL -c "DROP TABLE IF EXISTS products CASCADE"
```

---

## 📊 Deployment Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Database Backup | 2-3 min | ⏳ Pending |
| Create PR | 1 min | ⏳ Pending |
| Merge PR | 1 min | ⏳ Pending |
| Auto-Deploy (Railway/Vercel) | 5-10 min | ⏳ Pending |
| Run Migration | 1-2 min | ⏳ Pending |
| Verification | 5 min | ⏳ Pending |
| Monitoring | 15 min | ⏳ Pending |
| **TOTAL** | **~30 min** | |

---

## 🔗 Useful Links

- **Railway Dashboard:** https://railway.app
- **Vercel Dashboard:** https://vercel.com/dashboard
- **Supabase Dashboard:** https://supabase.com/dashboard
- **GitHub Actions:** https://github.com/[your-repo]/actions

---

## ✅ Post-Deployment Checklist

After deployment completes:

- [ ] Products table exists in production database
- [ ] Migration status shows `head` in Alembic
- [ ] `/health` endpoint returns 200 OK
- [ ] `/api/products/search` endpoint works
- [ ] Frontend 3-column layout renders
- [ ] No errors in Railway logs for 15 min
- [ ] No errors in Vercel logs for 15 min
- [ ] Backup file saved securely

---

**Created by:** Claude Code
**Migration file:** alembic/versions/2025_11_18_1846-5da34d5930f8_add_products_table_with_fts.py
