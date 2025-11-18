# VoiceOffers: Voice-Powered Coupon Discovery Platform

**Find personalized deals and discounts using your voice**

VoiceOffers is a voice-activated search platform that helps retail customers discover relevant coupons and discounts through natural language voice queries. Simply speak what you're looking for (e.g., "vitamins," "skincare"), and the system returns personalized coupon recommendations.

## Current Status

✅ **Working Features:**
- Voice recording with spacebar control
- Speech-to-Text using OpenAI Whisper API
- Supabase authentication and user management
- Semantic coupon search with re-ranking
- Real-time transcript display
- **Product recommendations** with voice search
- 3-column layout (Products | Front-store Offers | Category Offers)

🚧 **In Progress:**
- Multi-environment deployment (dev/staging/production)
- Production-ready infrastructure setup

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI (Python 3.11), Gunicorn, Uvicorn
- **Database**: Supabase (PostgreSQL + Auth)
- **Speech-to-Text**: OpenAI Whisper API
- **Search**: PostgreSQL full-text search + OpenAI embeddings
- **Deployment**: Vercel (frontend), Railway (backend), Supabase (database)

---

## Quick Start

### Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.11+ (for backend)
- **OpenAI API Key** - [Get one here](https://platform.openai.com/api-keys)
- **Supabase Account** - [Sign up](https://supabase.com/)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/VoiceOffers.git
cd VoiceOffers
```

### 2. Set Up Environment Variables

#### Backend

```bash
# Copy the development template
cp .env.development .env

# Edit .env and add your API keys:
# - OPENAI_API_KEY
# - SUPABASE_URL
# - SUPABASE_KEY
# - SUPABASE_JWT_SECRET
```

#### Frontend

```bash
cd frontend
cp .env.development.local .env

# Edit .env and add Supabase credentials
```

### 3. Set Up Database

1. Create a Supabase project at [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Go to **SQL Editor**
3. Run `migrations/postgres_schema.sql`
4. Run `migrations/seed_dev.sql` (for test data)

### 4. Start Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python -m app.main
# Backend running at http://localhost:8000
```

### 5. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Frontend running at http://localhost:5174
```

### 6. Test the App

1. Open [http://localhost:5174](http://localhost:5174)
2. Sign up / log in with Supabase
3. Press **spacebar** to record
4. Say: "Show me vitamin coupons"
5. View personalized coupon results!

---

## Project Structure

```
VoiceOffers/
├── frontend/                       # React + TypeScript frontend
│   ├── src/
│   │   ├── components/            # UI components
│   │   │   ├── ProductCard.tsx    # NEW: Product display card
│   │   │   └── CouponCard.tsx     # Coupon display card
│   │   ├── hooks/                 # Custom React hooks (voice recording)
│   │   ├── lib/                   # Utilities (Supabase, API client)
│   │   └── types/                 # TypeScript interfaces
│   │       ├── product.ts         # NEW: Product type definition
│   │       └── coupon.ts          # Coupon type definition
│   └── package.json
│
├── app/                            # FastAPI backend
│   ├── main.py                    # Main application & API endpoints
│   ├── ingestion/                 # Data ingestion scripts
│   │   ├── ingest_coupons.py     # Load coupons into DB
│   │   └── ingest_products.py    # NEW: Load products into DB
│   └── supabase_client.py         # Supabase initialization
│
├── data/                           # Sample data files
│   ├── coupons.json               # Sample coupon data
│   └── products.json              # NEW: Sample product data
│
├── migrations/                     # Database schema & seed data
│   ├── postgres_schema.sql        # Complete DB schema (includes products table)
│   ├── seed_dev.sql               # Development test data
│   └── seed_staging.sql           # Staging test data
│
├── alembic/                        # Database migration tool
│
├── .github/workflows/              # CI/CD pipelines
│   ├── pr-checks.yml              # Run on PRs
│   ├── deploy-staging.yml         # Deploy to staging
│   └── deploy-production.yml      # Deploy to production
│
├── PRODUCT_FEATURE_SUMMARY.md      # NEW: Product feature quick reference
├── PRODUCT_FEATURE_DEPLOYMENT.md   # NEW: Product feature deployment guide
├── IMAGE_STORAGE_GUIDE.md          # NEW: Guide for managing product images
├── DEPLOYMENT.md                   # Deployment guide
├── .env.example                    # Backend environment template
├── vercel.json                     # Vercel deployment config
├── railway.json                    # Railway deployment config
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## Deployment

This project supports **three environments**:

- **Development**: Local (localhost) + Supabase dev project
- **Staging**: Vercel preview + Railway staging + Supabase staging
- **Production**: Vercel + Railway + Supabase production

### Deploy to Staging/Production

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for complete step-by-step instructions.

**Quick Summary:**

1. **Supabase**: Create 3 projects (dev/staging/prod), apply schema
2. **Railway**: Deploy backend from GitHub repo
3. **Vercel**: Deploy frontend from GitHub repo
4. **GitHub Actions**: Auto-deploys on push to `staging` or `main` branches

**Estimated Costs:**
- Staging: **$0/month** (free tiers)
- Production: **$5-30/month** + OpenAI usage

---

## Environment Variables

### Backend (`.env`)

```bash
ENV=development
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_JWT_SECRET=...
DATABASE_URL=postgresql://...
FRONTEND_URL=http://localhost:5174
```

See `.env.example` for complete list.

### Frontend (`frontend/.env`)

```bash
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=/api  # Uses Vite proxy in dev
```

---

## Development Workflow

### Local Development

1. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes** (backend or frontend)

3. **Test locally**:
   ```bash
   # Backend
   python -m app.main

   # Frontend
   cd frontend && npm run dev
   ```

4. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature
   ```

5. **Create Pull Request** to `staging` branch

### Staging Deployment

1. **Merge PR to `staging` branch**
2. **GitHub Actions** runs tests and deploys
3. **Test at**: `https://voiceoffers-staging.vercel.app`

### Production Deployment

1. **Merge `staging` → `main`**
2. **GitHub Actions** runs security scans and deploys
3. **Live at**: `https://voiceoffers.vercel.app`

---

## API Endpoints

### Authentication

- `POST /api/auth/verify` - Verify Supabase session token
- `GET /api/auth/me` - Get current user profile

### Speech-to-Text

- `POST /api/stt` - Convert audio to text (authenticated, rate limited: 10/min)
  - Body: `multipart/form-data` with `file` field
  - Returns: `{ transcript, duration_ms, user_id }`

### Coupon Search

- `POST /api/coupons/search` - Semantic coupon search (authenticated, rate limited: 30/min)
  - Body: `{ question: "vitamin coupons" }`
  - Returns: `{ results: [...coupons] }`

### Product Search

- `POST /api/products/search` - Full-text product search (authenticated, rate limited: 30/min)
  - Body: `{ query: "moisturizer", limit: 10 }`
  - Returns: `{ products: [...products], count: 10 }`
- `GET /api/products/search?query=moisturizer&limit=10` - Same as POST, but via query params

### Health Check

- `GET /healthz` - Health check with database status

---

## Key Features

### Voice Recording
- **Press spacebar** to start/stop recording
- Auto-stops after 7 seconds
- Supports WebM, WAV, MP3, M4A audio formats

### Speech-to-Text
- Uses **OpenAI Whisper** for high accuracy
- Rate limited to prevent abuse
- Environment tracking for cost monitoring

### Coupon Search
- **Hybrid search**: PostgreSQL full-text + OpenAI embeddings
- **Personalized results**: Only shows user-assigned coupons
- **Ranked by relevance**: Cosine similarity scoring

### Security
- **JWT authentication** via Supabase
- **Rate limiting** on expensive endpoints
- **Environment-based CORS** configuration
- **Token refresh** handling

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request to `staging` branch

### Code Style

- **Backend**: Follow PEP 8 (use `black` and `flake8`)
- **Frontend**: Follow ESLint rules (run `npm run lint`)
- **Commits**: Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)

---

## Troubleshooting

### Microphone not working
- Grant browser microphone permission
- Check that you're on `localhost` or `https://` (required for mic access)

### Backend returns 401 Unauthorized
- Check that you're logged in to Supabase
- Verify `SUPABASE_JWT_SECRET` matches your project

### CORS errors
- Verify `FRONTEND_URL` in backend matches frontend URL exactly
- Check CORS configuration in `app/main.py`

### No coupons returned
- Ensure you have coupons assigned in the database
- Run `migrations/seed_dev.sql` for test data

### No products showing
- Load sample products: `python app/ingestion/ingest_products.py`
- Verify database: `SELECT COUNT(*) FROM products;`

---

## Product Recommendation Feature

**NEW:** The platform now includes a product recommendation column that displays relevant products based on voice search queries.

### Quick Start
1. **Update Database**: Run `migrations/postgres_schema.sql` (adds `products` table)
2. **Load Products**: `python app/ingestion/ingest_products.py`
3. **Deploy**: Push changes to staging/production

### Documentation
- 📖 **[PRODUCT_FEATURE_SUMMARY.md](./PRODUCT_FEATURE_SUMMARY.md)** - Quick reference guide
- 🚀 **[PRODUCT_FEATURE_DEPLOYMENT.md](./PRODUCT_FEATURE_DEPLOYMENT.md)** - Step-by-step deployment
- 🖼️ **[IMAGE_STORAGE_GUIDE.md](./IMAGE_STORAGE_GUIDE.md)** - Managing product images

### Features
- 3-column layout (Products | Front-store Offers | Category Offers)
- Full-text product search via `/api/products/search`
- Product cards with images, prices, ratings, and promo text
- Responsive design (mobile-friendly)
- Supabase Storage integration for images

---

## License

MIT License - see [LICENSE](./LICENSE) for details

---

## Support

- **Documentation**: 
  - [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment guide
  - [PRODUCT_FEATURE_DEPLOYMENT.md](./PRODUCT_FEATURE_DEPLOYMENT.md) - Product feature setup
  - [IMAGE_STORAGE_GUIDE.md](./IMAGE_STORAGE_GUIDE.md) - Image management
  - [migrations/README.md](./migrations/README.md) - Database migrations
- **Issues**: [GitHub Issues](https://github.com/yourusername/VoiceOffers/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/VoiceOffers/discussions)

---

**Built with** ❤️ **by the VoiceOffers team**

*Last Updated: 2025-11-14*
