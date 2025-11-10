# Frontend-Backend Integration Guide

> **Quick guide for connecting the React frontend with the Python FastAPI backend**

---

## Current Status

- **Frontend**: ✅ Fully functional voice recording UI with mock data
- **Backend**: ✅ Complete API endpoints ready (STT, search, manual resolution)
- **Integration**: ⚠️ 90% complete - needs frontend to call backend search APIs

---

## Quick Start

### 1. Start Both Servers

**Terminal 1 - Backend (Python/FastAPI)**:
```bash
# From project root
python -m app.main
# Runs on http://localhost:8000
```

**Terminal 2 - Frontend (React/Vite)**:
```bash
# From project root
cd frontend
npm run dev
# Runs on http://localhost:5174
```

**Access the app**: http://localhost:5174

---

## How It Currently Works

### Voice Recording Flow (Already Working)

```
User presses Spacebar
    ↓
Frontend records audio (7 seconds)
    ↓
Sends audio to: POST /api/stt
    ↓
Backend → OpenAI Whisper API → Transcript
    ↓
Frontend displays transcript in sidebar
    ✅ THIS WORKS!
```

### What's Missing (Search Integration)

```
Transcript displayed in sidebar
    ↓
Frontend should call: GET /api/manual/resolve?q={transcript}
    ↓
Backend returns which manual matches
    ↓
Frontend should call: POST /api/manual/{id}/search
    ↓
Backend returns relevant page with snippet
    ↓
Frontend displays search results
    ❌ THIS IS NOT YET CONNECTED!
```

---

## Integration Steps

### Step 1: Update MainLayout.tsx

**File**: `frontend/src/components/MainLayout.tsx`

**Find this function** (around line 30):
```typescript
const handleTranscriptChange = (newTranscript: string) => {
  setTranscript(newTranscript)
  console.log('New transcript received:', newTranscript)
  // TODO: Integrate with backend API
}
```

**Replace with**:
```typescript
import { useState } from 'react'

// Add these state variables at the top of MainLayout component
const [searchResults, setSearchResults] = useState<any>(null)
const [isLoading, setIsLoading] = useState(false)
const [error, setError] = useState<string | null>(null)

// Replace the handleTranscriptChange function
const handleTranscriptChange = async (newTranscript: string) => {
  setTranscript(newTranscript)

  // Reset if transcript is empty
  if (!newTranscript.trim()) {
    setSearchResults(null)
    return
  }

  setIsLoading(true)
  setError(null)

  try {
    // STEP 1: Resolve which manual the user is asking about
    console.log('Resolving manual for:', newTranscript)
    const resolveResponse = await fetch(
      `/api/manual/resolve?q=${encodeURIComponent(newTranscript)}`
    )
    const resolveData = await resolveResponse.json()
    console.log('Manual resolution:', resolveData)

    // Handle ambiguous results (multiple manuals match)
    if (resolveData.message === 'ambiguous') {
      const titles = resolveData.candidates.map((c: any) => c.title).join(', ')
      setError(`Multiple manuals found. Did you mean: ${titles}?`)
      setIsLoading(false)
      return
    }

    // Handle no match
    if (resolveData.message === 'no_match' || !resolveData.manual_id) {
      setError('No manual found. Try asking about "Pixel 9" or "LG refrigerator".')
      setIsLoading(false)
      return
    }

    // STEP 2: Search the resolved manual
    console.log('Searching manual:', resolveData.manual_id)
    const searchResponse = await fetch(
      `/api/manual/${resolveData.manual_id}/search`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: newTranscript })
      }
    )
    const searchData = await searchResponse.json()
    console.log('Search results:', searchData)

    // Handle no results
    if (searchData.message === 'no_results') {
      setError('No matching pages found in the manual.')
      setIsLoading(false)
      return
    }

    // STEP 3: Store results to display
    setSearchResults({
      manual: resolveData,
      search: searchData
    })

  } catch (err: any) {
    console.error('Search error:', err)
    setError(`Error: ${err.message}`)
  } finally {
    setIsLoading(false)
  }
}
```

### Step 2: Update the UI to Display Results

**In the same file**, find the return statement and replace the main content area:

```typescript
<main className="flex-1 p-6 overflow-y-auto">
  <div className="max-w-7xl mx-auto">
    <h1 className="text-3xl font-bold mb-6">VoiceOffers Search</h1>

    {/* Loading State */}
    {isLoading && (
      <div className="text-center p-8">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
        <p className="text-lg mt-4">Searching...</p>
      </div>
    )}

    {/* Error State */}
    {error && (
      <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6">
        <p className="font-semibold">Error</p>
        <p>{error}</p>
      </div>
    )}

    {/* Search Results */}
    {searchResults && !isLoading && (
      <div className="bg-white border rounded-lg p-6 shadow-lg mb-6">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            {searchResults.manual.title}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Page {searchResults.search.page} •
            Confidence: {(searchResults.search.score * 100).toFixed(1)}%
          </p>
        </div>
        <div className="prose max-w-none">
          <div className="bg-gray-50 p-4 rounded border border-gray-200">
            <p className="text-gray-800">{searchResults.search.snippet}</p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            <strong>Query:</strong> "{transcript}"
          </p>
        </div>
      </div>
    )}

    {/* Mock Data (shown when no search active) */}
    {!transcript && !isLoading && (
      <>
        <h2 className="text-2xl font-semibold mb-4">Front-store Offers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {mockFrontstoreCoupons.map(coupon => (
            <CouponCard key={coupon.id} coupon={coupon} />
          ))}
        </div>

        <h2 className="text-2xl font-semibold mb-4">Category & Brand Offers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {mockCategoryBrandCoupons.map(coupon => (
            <CouponCard key={coupon.id} coupon={coupon} />
          ))}
        </div>
      </>
    )}
  </div>
</main>
```

---

## Testing the Integration

### Test 1: Pixel 9 Battery Question

1. **Start both servers** (see Quick Start above)
2. **Open**: http://localhost:5174
3. **Press Spacebar** to start recording
4. **Say**: "Pixel 9 battery replacement"
5. **Release Spacebar**
6. **Wait** for transcript to appear in sidebar
7. **Expected Result**:
   - Manual: "Pixel 9 Pro Repair Manual V1.1"
   - Page: 12 (example)
   - Snippet: "Battery Removal Procedure: 1. Power off device..."
   - Confidence: ~87%

### Test 2: LG Refrigerator Question

1. **Press Spacebar**
2. **Say**: "LG refrigerator temperature control"
3. **Release Spacebar**
4. **Expected Result**:
   - Manual: "LG Refrigerator Model GR"
   - Relevant page with temperature instructions

### Test 3: Ambiguous Query

1. **Press Spacebar**
2. **Say**: "LG appliance manual"
3. **Expected Result**:
   - Error message: "Multiple manuals found. Did you mean: LG Refrigerator..., LG Air Conditioner...?"

### Test 4: No Match

1. **Press Spacebar**
2. **Say**: "iPhone 15 screen replacement"
3. **Expected Result**:
   - Error message: "No manual found. Try asking about Pixel 9 or LG refrigerator."

---

## How the Vite Proxy Works

**Vite configuration** (`frontend/vite.config.ts`):
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

**What this means**:
- Frontend runs on `:5174`
- When you call `fetch('/api/stt')` from frontend
- Vite automatically forwards it to `http://localhost:8000/api/stt`
- No CORS issues because it looks like same-origin request

**In production**:
- Frontend is built and served from backend
- API calls go to same server (no proxy needed)

---

## Backend Endpoints Reference

### 1. Speech to Text
```bash
POST /api/stt
Content-Type: multipart/form-data

Request:
  file: <audio blob>

Response:
{
  "transcript": "Pixel 9 battery replacement",
  "duration_ms": 2341,
  "api_duration_ms": 2150
}
```

### 2. Manual Resolution
```bash
GET /api/manual/resolve?q=Pixel%209

Response (Success):
{
  "manual_id": "Pixel9",
  "title": "Pixel 9 Pro Repair Manual V1.1",
  "score": 0.92
}

Response (Ambiguous):
{
  "candidates": [
    {"manual_id": "Pixel9", "title": "...", "score": 0.78},
    {"manual_id": "PixelFold", "title": "...", "score": 0.76}
  ],
  "message": "ambiguous"
}

Response (No Match):
{
  "candidates": [],
  "message": "no_match"
}
```

### 3. Semantic Search
```bash
POST /api/manual/Pixel9/search
Content-Type: application/json

Request:
{
  "question": "How do I replace the battery?"
}

Response:
{
  "page": 12,
  "score": 0.87,
  "snippet": "Battery Removal Procedure: 1. Power off device 2. Remove back cover..."
}

Response (No Results):
{
  "message": "no_results"
}
```

---

## Troubleshooting

### Problem: "Failed to fetch" errors

**Symptom**: Network errors in browser console

**Causes**:
1. Backend not running
2. Backend on wrong port
3. Vite proxy misconfigured

**Fixes**:
```bash
# Check backend is running
curl http://localhost:8000/healthz

# Should return:
{"status":"ok","version":"0.1.0",...}

# If not running, start it:
python -m app.main
```

### Problem: "OpenAI API key not configured"

**Symptom**: 400 error from `/api/stt`

**Fix**:
```bash
# Create .env file
cp .env.example .env

# Edit .env and add your key
OPENAI_API_KEY=sk-proj-your-key-here

# Restart backend
python -m app.main
```

### Problem: "No manual found" for all queries

**Symptom**: Always get "no_match" response

**Fix**:
```bash
# Check if database has data
python -c "from sqlalchemy import create_engine, text; \
engine = create_engine('sqlite:///data/sqlite/manuals.db'); \
with engine.connect() as conn: \
  print(conn.execute(text('SELECT COUNT(*) FROM manuals')).scalar())"

# If 0, run ingestion:
python -m app.ingestion.ingest_manuals --rebuild

# This will:
# 1. Create database tables
# 2. Extract text from PDFs in data/manuals/
# 3. Generate embeddings
# 4. Build FAISS index
```

### Problem: Transcript works but search doesn't

**Check**:
1. Open browser DevTools (F12)
2. Go to Network tab
3. Press Spacebar and speak
4. Watch for API calls:
   - `/api/stt` should return 200 with transcript
   - `/api/manual/resolve?q=...` should return 200 with manual_id
   - `/api/manual/{id}/search` should return 200 with page/snippet

**Debug**:
- Look at response in Network tab
- Check Console tab for JavaScript errors
- Check backend terminal for Python errors

---

## Environment Setup Checklist

### Backend Requirements

- [ ] Python 3.10+ installed
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created with `OPENAI_API_KEY`
- [ ] Database initialized (SQLite auto-created or PostgreSQL migrated)
- [ ] Sample data ingested: `python -m app.ingestion.ingest_manuals --rebuild`
- [ ] Backend running: `python -m app.main` on port 8000

### Frontend Requirements

- [ ] Node.js 18+ installed
- [ ] Dependencies installed: `cd frontend && npm install`
- [ ] Frontend running: `npm run dev` on port 5174
- [ ] Browser microphone permission granted

---

## Next Steps After Integration

Once the basic integration works, you can enhance it:

### 1. Better Error Handling
```typescript
// Show user-friendly messages for different error types
if (err.message.includes('NetworkError')) {
  setError('Backend server is not running. Please start it with: python -m app.main')
} else if (err.message.includes('API key')) {
  setError('OpenAI API key not configured. Check your .env file.')
}
```

### 2. Loading States with Skeletons
```typescript
import { Skeleton } from '@/components/ui/skeleton'

{isLoading && (
  <div className="space-y-4">
    <Skeleton className="h-8 w-3/4" />
    <Skeleton className="h-32 w-full" />
  </div>
)}
```

### 3. Handle Ambiguous Resolutions
```typescript
// Let user pick from candidates
{ambiguousCandidates.length > 0 && (
  <div className="space-y-2">
    <p>Multiple manuals found. Which one?</p>
    {ambiguousCandidates.map(c => (
      <button onClick={() => searchManual(c.manual_id)}>
        {c.title}
      </button>
    ))}
  </div>
)}
```

### 4. Display PDF Pages
```typescript
// Show actual page image (requires PDF rendering)
<iframe
  src={`/api/manual/${manual_id}/page/${page_number}`}
  className="w-full h-96 border rounded"
/>
```

### 5. Conversation History
```typescript
const [history, setHistory] = useState<SearchResult[]>([])

// Add each search to history
setHistory(prev => [...prev, searchResults])

// Display history
{history.map((result, i) => (
  <HistoryCard key={i} result={result} />
))}
```

---

## Additional Resources

- **Full codebase guide**: `.claude/claude.md`
- **Project README**: `README.md`
- **Deployment guide**: `DEPLOYMENT.md`
- **Backend code**: `app/main.py`
- **Frontend code**: `frontend/src/components/MainLayout.tsx`

---

## Quick Commands Reference

```bash
# Start backend
python -m app.main

# Start frontend
cd frontend && npm run dev

# Rebuild database and embeddings
python -m app.ingestion.ingest_manuals --rebuild

# Check backend health
curl http://localhost:8000/healthz

# Test STT endpoint
curl -X POST http://localhost:8000/api/stt \
  -F "file=@recording.webm"

# Test manual resolution
curl "http://localhost:8000/api/manual/resolve?q=Pixel%209"

# Test search
curl -X POST http://localhost:8000/api/manual/Pixel9/search \
  -H "Content-Type: application/json" \
  -d '{"question": "battery replacement"}'
```

---

*Integration guide created: 2025-11-09*
