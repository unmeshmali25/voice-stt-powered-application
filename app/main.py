"""
VoiceOffers Coupon Platform - FastAPI Backend

Serves:
- GET /           : frontend index
- GET /healthz    : liveness/readiness
- POST /api/stt   : Speech-to-text (authenticated)
- POST /api/auth/verify : Verify Supabase session
- GET /api/auth/me : Get current user profile
- POST /api/coupons/search : Semantic coupon search (authenticated)
"""
from __future__ import annotations

import os
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from functools import wraps

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, status, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from supabase import create_client, Client
import jwt
from jwt import PyJWTError

# --- Env / Config ---
load_dotenv()

# Environment detection
ENV = os.getenv("ENV", "development")
IS_DEV = ENV == "development"
IS_STAGING = ENV == "staging"
IS_PROD = ENV == "production"

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
# Railway provides PORT, fallback to APP_PORT or 8000
APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Frontend URL for CORS configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5174")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev@localhost:5432/voiceoffers")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", "./data/index/faiss.index")).resolve()
FAISS_META_PATH = Path(os.getenv("FAISS_META_PATH", "./data/index/meta.json")).resolve()

# Database engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

FRONTEND_DIR = (Path(__file__).resolve().parent.parent / "frontend").resolve()
FRONTEND_INDEX = FRONTEND_DIR / "index.html"

ENABLE_TIMING_LOGS = os.getenv("ENABLE_TIMING_LOGS", "true").lower() == "true"

# Initialize Supabase client
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logging.error(f"Failed to initialize Supabase client: {e}")

# --- App ---
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("voiceoffers")

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="VoiceOffers Coupon Platform",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

# Add rate limit exceeded handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - environment-based configuration
def get_cors_origins():
    """Get CORS origins based on environment."""
    if IS_DEV:
        # Development: Allow localhost ports
        return [
            "http://localhost:5174",
            "http://localhost:3000",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:3000"
        ]
    elif IS_STAGING:
        # Staging: Allow Vercel preview URLs
        return [
            FRONTEND_URL,
            "https://voiceoffers-staging.vercel.app",
            "https://*.vercel.app"  # Vercel preview deployments
        ]
    elif IS_PROD:
        # Production: Only allow production domain
        return [
            FRONTEND_URL,
            "https://voiceoffers.vercel.app",
            "https://voiceoffers.com"  # Add your custom domain if applicable
        ]
    else:
        # Fallback to localhost
        return ["http://localhost:5174"]

cors_origins = get_cors_origins()
logger.info(f"Environment: {ENV}")
logger.info(f"CORS origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


def ensure_dirs() -> None:
    """Create minimal data directory structure."""
    (DATA_DIR).mkdir(parents=True, exist_ok=True)
    (FAISS_INDEX_PATH.parent).mkdir(parents=True, exist_ok=True)
    (FAISS_META_PATH.parent).mkdir(parents=True, exist_ok=True)


ensure_dirs()

# Serve frontend static files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR), html=False), name="static")


# --- Authentication Utilities ---

def get_db():
    """Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_token(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Verify Supabase JWT token and return user data.
    Expects Authorization header: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use: Bearer <token>"
        )

    token = authorization.replace("Bearer ", "")

    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWT secret not configured"
        )

    try:
        # Decode and verify JWT
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        return {
            "user_id": user_id,
            "email": email,
            "payload": payload
        }

    except PyJWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )


# --- Routes ---

@app.get("/")
async def root():
    """Serve the frontend index."""
    logger.info("Received GET request for root path.")

    if FRONTEND_INDEX.exists():
        logger.info(f"Serving frontend from: {FRONTEND_INDEX}")
        return FileResponse(str(FRONTEND_INDEX), media_type="text/html")

    # Placeholder HTML if frontend not built
    logger.info("Frontend not found. Serving placeholder.")
    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>VoiceOffers</title>
        <style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:2rem} .muted{color:#666}</style>
      </head>
      <body>
        <h1>VoiceOffers Coupon Platform</h1>
        <p class="muted">Frontend not found. Build the frontend or visit <code>/static/</code>.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@app.get("/health")
async def health():
    """
    Simple health check endpoint for Railway deployment.
    Returns 200 OK if the application is running.
    """
    return {"status": "ok"}


@app.get("/healthz", response_class=JSONResponse)
async def healthz(db: Session = Depends(get_db)) -> JSONResponse:
    """
    Detailed health check endpoint with database connectivity test.
    """
    checks: Dict[str, Any] = {
        "frontend_index_exists": FRONTEND_INDEX.exists(),
        "data_dir_exists": DATA_DIR.exists(),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_JWT_SECRET),
    }

    # Test database connection
    try:
        # Check if coupons table exists
        result = db.execute(text("SELECT COUNT(*) FROM coupons"))
        coupon_count = result.scalar()
        checks["database_connected"] = True
        checks["coupons_table_exists"] = True
        checks["coupon_count"] = coupon_count
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database_connected"] = False
        checks["coupons_table_exists"] = False
        checks["error"] = str(e)

    status_overall = "ok" if all([
        checks["frontend_index_exists"],
        checks["supabase_configured"],
        checks.get("database_connected", False)
    ]) else "degraded"

    payload = {
        "status": status_overall,
        "version": app.version,
        "checks": checks,
    }
    return JSONResponse(payload, status_code=200 if status_overall == "ok" else 503)


# --- Authentication Endpoints ---

@app.post("/api/auth/verify")
async def auth_verify(user: Dict[str, Any] = Depends(verify_token)) -> JSONResponse:
    """
    Verify the current Supabase session token.
    Returns user information if valid.
    """
    return JSONResponse({
        "valid": True,
        "user_id": user["user_id"],
        "email": user["email"]
    }, status_code=200)


@app.get("/api/auth/me")
async def auth_me(
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get current user profile from database.
    Syncs user from Supabase if not exists in local DB.
    """
    user_id = user["user_id"]
    email = user["email"]

    # Check if user exists in local database
    result = db.execute(
        text("SELECT id, email, full_name, created_at FROM users WHERE id = :user_id"),
        {"user_id": user_id}
    )
    user_row = result.fetchone()

    if not user_row:
        # Sync user from Supabase to local database
        logger.info(f"Syncing new user {user_id} to local database")
        try:
            db.execute(
                text("""
                    INSERT INTO users (id, email, full_name)
                    VALUES (:id, :email, :full_name)
                """),
                {
                    "id": user_id,
                    "email": email,
                    "full_name": user.get("payload", {}).get("user_metadata", {}).get("full_name")
                }
            )
            db.commit()

            # Fetch the newly created user
            result = db.execute(
                text("SELECT id, email, full_name, created_at FROM users WHERE id = :user_id"),
                {"user_id": user_id}
            )
            user_row = result.fetchone()
        except Exception as e:
            logger.error(f"Failed to sync user: {e}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to sync user profile"
            )

    return JSONResponse({
        "id": str(user_row[0]),
        "email": user_row[1],
        "full_name": user_row[2],
        "created_at": user_row[3].isoformat() if user_row[3] else None
    }, status_code=200)


# --- Speech-to-Text Endpoint ---

@app.post("/api/stt")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute per IP
async def stt(
    request: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(verify_token)
) -> JSONResponse:
    """
    Speech-to-text endpoint using OpenAI Whisper API (authenticated).
    - Accepts multipart file under "file" (audio/webm, audio/wav, audio/mp3, audio/m4a)
    - Returns: { "transcript": "...", "duration_ms": 123, "user_id": "..." }
    """
    t0 = time.time()
    user_id = user["user_id"]

    # Validate API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY not configured"
        )

    # Validate file
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided"
        )

    # Validate MIME type
    allowed_mimes = os.getenv("ALLOWED_AUDIO_MIME", "audio/webm,audio/wav,audio/mp3,audio/mpeg,audio/m4a,audio/x-m4a").split(",")
    content_type = file.content_type or ""

    logger.info(f"User {user_id} uploaded audio file: {file.filename}, content_type: {content_type}")

    # Read file content
    try:
        audio_bytes = await file.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read audio file"
        )

    # Validate file size (OpenAI limit is 25MB)
    max_size_mb = int(os.getenv("MAX_UPLOAD_MB", "25"))
    if len(audio_bytes) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large. Max {max_size_mb}MB allowed."
        )

    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty"
        )

    # Determine file extension
    filename = file.filename or "audio.webm"
    if filename.endswith(".webm"):
        ext = "webm"
    elif filename.endswith(".wav"):
        ext = "wav"
    elif filename.endswith(".mp3"):
        ext = "mp3"
    elif filename.endswith(".m4a"):
        ext = "m4a"
    else:
        if "webm" in content_type:
            ext = "webm"
        elif "wav" in content_type:
            ext = "wav"
        elif "mp3" in content_type or "mpeg" in content_type:
            ext = "mp3"
        elif "m4a" in content_type:
            ext = "m4a"
        else:
            ext = "webm"

    # Call OpenAI Whisper API
    try:
        logger.info(f"Initializing OpenAI client for user {user_id}")
        # Add environment tracking header for OpenAI usage monitoring
        client = OpenAI(
            api_key=api_key,
            default_headers={
                "X-Environment": ENV,
                "X-User-Agent": f"VoiceOffers/{app.version}/{ENV}"
            }
        )

        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{ext}"
        
        logger.info(f"Audio file prepared: {len(audio_bytes)} bytes, extension: {ext}")

        t_api_start = time.time()
        logger.info(f"Calling OpenAI Whisper API for user {user_id}")
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="json"
        )
        t_api_end = time.time()
        
        logger.info(f"OpenAI API response received. Type: {type(response)}, Has 'text' attr: {hasattr(response, 'text')}")

        # Extract transcript from response
        # When response_format="json", OpenAI returns a Transcription object with .text attribute
        if hasattr(response, 'text'):
            transcript = response.text.strip() if response.text else ""
        elif isinstance(response, str):
            transcript = response.strip()
        elif isinstance(response, dict):
            transcript = response.get('text', '').strip() if isinstance(response.get('text'), str) else ""
        else:
            # Fallback: convert to string
            logger.warning(f"Unexpected response type: {type(response)}, value: {response}")
            transcript = str(response).strip() if response else ""
        
        logger.info(f"Extracted transcript length: {len(transcript)} characters")

        t_total = time.time() - t0
        api_duration_ms = int((t_api_end - t_api_start) * 1000)
        total_duration_ms = int(t_total * 1000)

        if ENABLE_TIMING_LOGS:
            logger.info(f"STT completed for user {user_id}: {total_duration_ms}ms total (API: {api_duration_ms}ms)")

        logger.info(f"Transcript from user {user_id}: {transcript}")

        return JSONResponse({
            "transcript": transcript,
            "duration_ms": total_duration_ms,
            "api_duration_ms": api_duration_ms,
            "user_id": user_id
        }, status_code=200)

    except Exception as e:
        logger.exception("OpenAI Whisper API error: %s", e)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {repr(e)}")

        error_msg = str(e)
        error_type = type(e).__name__
        
        # Check for specific OpenAI API errors
        if "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
            detail = f"OpenAI quota exceeded. Error: {error_msg}"
        elif "rate_limit" in error_msg.lower():
            detail = f"Rate limit exceeded. Please try again later. Error: {error_msg}"
        elif "invalid_api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
            detail = f"Invalid OpenAI API key. Please check your OPENAI_API_KEY environment variable. Error: {error_msg}"
        elif "timeout" in error_msg.lower():
            detail = f"Request timeout. Please try with shorter audio. Error: {error_msg}"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            detail = f"Network error connecting to OpenAI API. Error: {error_msg}"
        else:
            detail = f"Speech-to-text failed ({error_type}): {error_msg}"

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


# --- Coupon Search Endpoint ---

@app.post("/api/coupons/search")
@limiter.limit("30/minute")  # Rate limit: 30 searches per minute per IP
async def coupon_search(
    request: Request,
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Semantic search for coupons assigned to the authenticated user.

    Hybrid retrieval:
    1) Shortlist coupons with PostgreSQL full-text search (user's assigned coupons only)
    2) Re-rank using OpenAI embeddings cosine similarity

    Returns: { "results": [{ coupon_id, type, discount_details, score, ... }] }
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    question = (payload or {}).get("question", "")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'question' in request body"
        )

    user_id = user["user_id"]

    # Tunables
    try:
        fts_top_k = int(os.getenv("FTS_TOP_K", "15"))
    except Exception:
        fts_top_k = 15

    try:
        rerank_top_n = int(os.getenv("RERANK_TOP_N", "3"))
    except Exception:
        rerank_top_n = 3

    # Step 1: Clean query
    stop_words = {'what', 'how', 'when', 'where', 'why', 'who', 'is', 'are', 'the', 'a', 'an', 'to', 'do', 'does'}
    cleaned_question = question.replace('?', ' ').replace('.', ' ').replace(',', ' ')
    words = [w.strip() for w in cleaned_question.lower().split() if w.strip() and w.lower() not in stop_words]
    search_query = ' '.join(words) if words else question.replace('"', '').replace('.', ' ').replace('?', ' ')
    logger.info(f"User {user_id} searching with query: '{search_query}' (from: '{question}')")

    # Step 2: Full-text search on user's assigned coupons
    try:
        result = db.execute(
            text("""
                SELECT c.id, c.type, c.discount_details, c.category_or_brand,
                       c.expiration_date, c.terms
                FROM coupons c
                JOIN user_coupons uc ON c.id = uc.coupon_id
                WHERE uc.user_id = :user_id
                  AND (uc.eligible_until IS NULL OR uc.eligible_until > NOW())
                  AND c.expiration_date > NOW()
                  AND c.text_vector @@ websearch_to_tsquery('english', :query)
                ORDER BY ts_rank_cd(c.text_vector, websearch_to_tsquery('english', :query), 32) DESC
                LIMIT :limit
            """),
            {
                "user_id": user_id,
                "query": search_query,
                "limit": fts_top_k
            }
        )
        rows = result.fetchall()
        logger.info(f"FTS returned {len(rows)} candidates for user {user_id}")

        if not rows:
            # Fallback to ILIKE if no FTS results
            logger.info("FTS returned no results. Falling back to ILIKE.")
            result = db.execute(
                text("""
                    SELECT c.id, c.type, c.discount_details, c.category_or_brand,
                           c.expiration_date, c.terms
                    FROM coupons c
                    JOIN user_coupons uc ON c.id = uc.coupon_id
                    WHERE uc.user_id = :user_id
                      AND (uc.eligible_until IS NULL OR uc.eligible_until > NOW())
                      AND c.expiration_date > NOW()
                      AND (c.discount_details ILIKE :pattern
                           OR c.category_or_brand ILIKE :pattern
                           OR c.terms ILIKE :pattern)
                    LIMIT :limit
                """),
                {
                    "user_id": user_id,
                    "pattern": f"%{search_query}%",
                    "limit": fts_top_k
                }
            )
            rows = result.fetchall()
            logger.info(f"ILIKE search returned {len(rows)} candidates")

        if not rows:
            return JSONResponse({"results": [], "message": "no_results"}, status_code=200)

        # Build candidate list
        candidates = []
        for row in rows:
            candidates.append({
                "id": str(row[0]),
                "type": row[1],
                "discount_details": row[2],
                "category_or_brand": row[3],
                "expiration_date": row[4].isoformat() if row[4] else None,
                "terms": row[5]
            })

        # Step 3: Embedding re-ranking
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Return FTS results without scores
            logger.warning("No OpenAI API key, returning FTS results without re-ranking")
            return JSONResponse({
                "results": candidates[:rerank_top_n],
                "message": "no_reranking"
            }, status_code=200)

        emb_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        # Create texts for embedding
        texts = [question] + [
            f"{c['discount_details']} {c.get('category_or_brand', '')} {c.get('terms', '')}"
            for c in candidates
        ]

        try:
            # Add environment tracking header for OpenAI usage monitoring
            client = OpenAI(
                api_key=api_key,
                default_headers={
                    "X-Environment": ENV,
                    "X-User-Agent": f"VoiceOffers/{app.version}/{ENV}"
                }
            )
            resp = client.embeddings.create(model=emb_model, input=texts)
            vecs = [np.array(item.embedding, dtype=np.float32) for item in resp.data]
        except Exception as e:
            logger.exception("Embeddings failed: %s", e)
            # Fallback to FTS order
            return JSONResponse({
                "results": candidates[:rerank_top_n],
                "message": "embedding_failed"
            }, status_code=200)

        # Normalize and compute scores
        def _norm(v: np.ndarray) -> np.ndarray:
            n = np.linalg.norm(v) + 1e-12
            return v / n

        qv = _norm(vecs[0])
        coupon_vecs = [_norm(v) for v in vecs[1:]]
        scores = [float(np.dot(cv, qv)) for cv in coupon_vecs]

        # Add scores to candidates and sort
        for i, candidate in enumerate(candidates):
            candidate["score"] = round(scores[i], 4)

        candidates.sort(key=lambda x: x["score"], reverse=True)

        top_results = candidates[:rerank_top_n]

        logger.info(f"Re-ranked coupons for user {user_id}. Top score: {top_results[0]['score'] if top_results else 'N/A'}")

        return JSONResponse({
            "results": top_results,
            "total_candidates": len(candidates)
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Coupon search failed for user {user_id}: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


if __name__ == "__main__":
    try:
        import uvicorn
    except Exception as exc:
        logger.error("Uvicorn is required to run directly: %s", exc)
        raise
    uvicorn.run(
        "app.main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower()
    )
