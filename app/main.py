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

import os
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urlunparse, quote_plus, parse_qsl, urlencode
import socket
from functools import wraps

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, status, UploadFile, File, Depends, Header, Query
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

# Robustly handle special characters in DB credentials by URL-encoding them
try:
    parsed_db_url = urlparse(DATABASE_URL)
    # Only rebuild if we have a recognizable netloc and scheme
    if parsed_db_url.scheme and parsed_db_url.netloc:
        username = parsed_db_url.username or ""
        password = parsed_db_url.password or ""
        host = parsed_db_url.hostname or ""
        port = parsed_db_url.port

        # Encode username/password to safely handle characters like '@', ':', etc.
        if username or password:
            encoded_username = quote_plus(username)
            encoded_password = quote_plus(password)
            netloc = f"{encoded_username}:{encoded_password}@{host}"
        else:
            netloc = host

        if port:
            netloc += f":{port}"

        # Ensure sslmode=require for hosted providers (e.g., Supabase)
        query_params = dict(parse_qsl(parsed_db_url.query, keep_blank_values=True))
        query_params.setdefault("sslmode", "require")

        # Prefer IPv4 if available to avoid IPv6-only connectivity issues on some hosts
        try:
            if host not in {"localhost", "127.0.0.1"}:
                addr_info_list = socket.getaddrinfo(host, port or 5432, socket.AF_INET, socket.SOCK_STREAM)
                if addr_info_list:
                    ipv4_addr = addr_info_list[0][4][0]
                    # Provide hostaddr while keeping host for TLS/SNI
                    query_params.setdefault("hostaddr", ipv4_addr)
        except Exception:
            # If DNS resolution fails, continue without hostaddr
            pass

        DATABASE_URL = urlunparse(
            (
                parsed_db_url.scheme,
                netloc,
                parsed_db_url.path,
                parsed_db_url.params,
                urlencode(query_params),
                parsed_db_url.fragment,
            )
        )
except Exception:
    # If anything goes wrong, fall back to the original DATABASE_URL
    pass

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
        # Staging: Allow Vercel preview URLs. Add base domain just in case.
        return [
            FRONTEND_URL,
            "https://voice-stt-powered-application-staging.vercel.app",
            "https://voiceoffers-staging.vercel.app",
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

# Add regex pattern for Vercel preview deployments
cors_regex = None
if IS_STAGING or IS_PROD:
    # Allow both preview deployments (voice-stt-powered-application-<id>.vercel.app)
    # and the root domain (voice-stt-powered-application.vercel.app), plus voiceoffers.* on vercel
    # It also handles staging URLs by making '-staging' optional.
    cors_regex = r'https://(voice-stt-powered-application(-staging)?(-[a-z0-9]+)?|voiceoffers.*)\.vercel\.app'
    logger.info(f"CORS regex pattern: {cors_regex}")

app.add_middleware(
    CORSMiddleware,
    # Always honor explicit allowlist based on environment
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
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


def assign_random_coupons_to_user(db: Session, user_id: str) -> int:
    """
    Assign random coupons to user's wallet:
    - 2 frontstore coupons
    - 30 category/brand coupons
    - All expire in 14 days
    
    Returns: Number of coupons assigned
    """
    try:
        # Check current active coupon counts by type
        result = db.execute(
            text("""
                SELECT 
                    c.type,
                    COUNT(*) as count
                FROM user_coupons uc
                JOIN coupons c ON uc.coupon_id = c.id
                WHERE uc.user_id = :user_id
                  AND uc.eligible_until > NOW()
                GROUP BY c.type
            """),
            {"user_id": user_id}
        )
        
        current_counts = {row[0]: row[1] for row in result.fetchall()}
        frontstore_count = current_counts.get('frontstore', 0)
        category_brand_count = current_counts.get('category', 0) + current_counts.get('brand', 0)
        
        # Calculate how many coupons to assign
        frontstore_needed = max(0, 2 - frontstore_count)
        category_brand_needed = max(0, 30 - category_brand_count)
        
        total_assigned = 0
        
        # Assign frontstore coupons
        if frontstore_needed > 0:
            result = db.execute(
                text("""
                    SELECT id FROM coupons
                    WHERE type = 'frontstore'
                      AND expiration_date > NOW()
                      AND id NOT IN (
                          SELECT coupon_id FROM user_coupons WHERE user_id = :user_id
                      )
                    ORDER BY RANDOM()
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": frontstore_needed}
            )
            
            for row in result.fetchall():
                db.execute(
                    text("""
                        INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
                        VALUES (:user_id, :coupon_id, NOW() + INTERVAL '14 days')
                        ON CONFLICT (user_id, coupon_id) DO NOTHING
                    """),
                    {"user_id": user_id, "coupon_id": row[0]}
                )
                total_assigned += 1
        
        # Assign category/brand coupons
        if category_brand_needed > 0:
            result = db.execute(
                text("""
                    SELECT id FROM coupons
                    WHERE type IN ('category', 'brand')
                      AND expiration_date > NOW()
                      AND id NOT IN (
                          SELECT coupon_id FROM user_coupons WHERE user_id = :user_id
                      )
                    ORDER BY RANDOM()
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": category_brand_needed}
            )
            
            for row in result.fetchall():
                db.execute(
                    text("""
                        INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
                        VALUES (:user_id, :coupon_id, NOW() + INTERVAL '14 days')
                        ON CONFLICT (user_id, coupon_id) DO NOTHING
                    """),
                    {"user_id": user_id, "coupon_id": row[0]}
                )
                total_assigned += 1
        
        db.commit()
        
        if total_assigned > 0:
            logger.info(f"Assigned {total_assigned} coupons to user {user_id} ({frontstore_needed} frontstore, {category_brand_needed} category/brand)")
        
        return total_assigned
        
    except Exception as e:
        logger.error(f"Failed to assign coupons to user {user_id}: {e}")
        db.rollback()
        return 0


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
    Auto-assigns coupons to user's wallet if needed.
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

    # Check if user needs coupon assignment (for new or existing users)
    # Count active coupons (eligible_until > NOW())
    result = db.execute(
        text("""
            SELECT COUNT(*) FROM user_coupons
            WHERE user_id = :user_id
              AND eligible_until > NOW()
        """),
        {"user_id": user_id}
    )
    active_coupon_count = result.scalar() or 0
    
    # Assign coupons if user has less than 32 active coupons
    if active_coupon_count < 32:
        logger.info(f"User {user_id} has {active_coupon_count} active coupons, assigning more")
        assign_random_coupons_to_user(db, user_id)

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
                  AND uc.eligible_until > NOW()
                  AND c.expiration_date > NOW()
                  AND (c.type = 'frontstore' OR c.text_vector @@ websearch_to_tsquery('english', :query))
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
                      AND uc.eligible_until > NOW()
                      AND c.expiration_date > NOW()
                      AND (c.type = 'frontstore'
                           OR c.discount_details ILIKE :pattern
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


# --- Product Search Endpoint ---

# Search aliases
PRODUCT_SEARCH_ALIASES = {
    "multivitamins": "vitamins",
    "multivitamin": "vitamin"
}

@app.post("/api/products/search")
@limiter.limit("30/minute")  # Rate limit: 30 searches per minute per IP
async def product_search(
    request: Request,
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Search for products using full-text search.
    
    Returns: { "products": [{ id, name, description, imageUrl, price, rating, ... }], "count": int }
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    
    query = (payload or {}).get("query", "")
    limit = min(int(payload.get("limit", 10)), 50)  # Max 50 products
    
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'query' in request body"
        )
    
    user_id = user["user_id"]
    logger.info(f"User {user_id} searching products with query: '{query}'")
    
    # Clean query
    search_query = query.strip()

    # Apply aliases
    if search_query.lower() in PRODUCT_SEARCH_ALIASES:
        search_query = PRODUCT_SEARCH_ALIASES[search_query.lower()]
        logger.info(f"Applied alias: {query} -> {search_query}")
    
    try:
        # Full-text search on products
        result = db.execute(
            text("""
                SELECT 
                    id, name, description, image_url, price, 
                    rating, review_count, category, brand, 
                    promo_text, in_stock,
                    ts_rank(text_vector, websearch_to_tsquery('english', :query)) as rank
                FROM products
                WHERE text_vector @@ websearch_to_tsquery('english', :query)
                    AND in_stock = true
                ORDER BY rank DESC, rating DESC NULLS LAST
                LIMIT :limit
            """),
            {"query": search_query, "limit": limit}
        )
        rows = result.fetchall()
        logger.info(f"Product search returned {len(rows)} results")
        
        if not rows:
            # Fallback to ILIKE if no FTS results
            logger.info("FTS returned no products. Falling back to ILIKE.")
            result = db.execute(
                text("""
                    SELECT 
                        id, name, description, image_url, price, 
                        rating, review_count, category, brand, 
                        promo_text, in_stock,
                        0 as rank
                    FROM products
                    WHERE in_stock = true
                        AND (name ILIKE :pattern
                             OR description ILIKE :pattern
                             OR category ILIKE :pattern
                             OR brand ILIKE :pattern)
                    ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
                    LIMIT :limit
                """),
                {
                    "pattern": f"%{search_query}%",
                    "limit": limit
                }
            )
            rows = result.fetchall()
            logger.info(f"ILIKE search returned {len(rows)} products")
        
        # Build product list
        products = []
        for row in rows:
            products.append({
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "imageUrl": row[3],
                "price": float(row[4]) if row[4] else 0.0,
                "rating": float(row[5]) if row[5] else None,
                "reviewCount": row[6] if row[6] else 0,
                "category": row[7],
                "brand": row[8],
                "promoText": row[9],
                "inStock": row[10]
            })
        
        return JSONResponse({
            "products": products,
            "count": len(products)
        }, status_code=200)
    
    except Exception as e:
        logger.exception(f"Product search failed for user {user_id}: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Product search failed: {str(e)}"
        )


@app.get("/api/products/search")
@limiter.limit("30/minute")
async def product_search_get(
    request: Request,
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """GET version of product search for easier testing"""
    user_id = user["user_id"]
    logger.info(f"User {user_id} searching products (GET) with query: '{query}'")
    
    search_query = query.strip()

    # Apply aliases
    if search_query.lower() in PRODUCT_SEARCH_ALIASES:
        search_query = PRODUCT_SEARCH_ALIASES[search_query.lower()]
        logger.info(f"Applied alias: {query} -> {search_query}")
    
    try:
        # Full-text search on products
        result = db.execute(
            text("""
                SELECT 
                    id, name, description, image_url, price, 
                    rating, review_count, category, brand, 
                    promo_text, in_stock,
                    ts_rank(text_vector, websearch_to_tsquery('english', :query)) as rank
                FROM products
                WHERE text_vector @@ websearch_to_tsquery('english', :query)
                    AND in_stock = true
                ORDER BY rank DESC, rating DESC NULLS LAST
                LIMIT :limit
            """),
            {"query": search_query, "limit": limit}
        )
        rows = result.fetchall()
        
        if not rows:
            # Fallback to ILIKE
            result = db.execute(
                text("""
                    SELECT 
                        id, name, description, image_url, price, 
                        rating, review_count, category, brand, 
                        promo_text, in_stock,
                        0 as rank
                    FROM products
                    WHERE in_stock = true
                        AND (name ILIKE :pattern
                             OR description ILIKE :pattern
                             OR category ILIKE :pattern
                             OR brand ILIKE :pattern)
                    ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
                    LIMIT :limit
                """),
                {"pattern": f"%{search_query}%", "limit": limit}
            )
            rows = result.fetchall()
        
        products = []
        for row in rows:
            products.append({
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "imageUrl": row[3],
                "price": float(row[4]) if row[4] else 0.0,
                "rating": float(row[5]) if row[5] else None,
                "reviewCount": row[6] if row[6] else 0,
                "category": row[7],
                "brand": row[8],
                "promoText": row[9],
                "inStock": row[10]
            })
        
        return JSONResponse({"products": products, "count": len(products)}, status_code=200)
    
    except Exception as e:
        logger.exception(f"Product search (GET) failed for user {user_id}: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Product search failed: {str(e)}"
        )


@app.get("/api/products/recommendations")
@limiter.limit("60/minute")
async def product_recommendations(
    request: Request,
    limit: int = Query(5, ge=1, le=20),
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get personalized product recommendations for user.

    Logic:
    1. Analyze user's search history and coupon usage
    2. Find most frequent categories/brands
    3. Return products matching user preferences
    4. Fallback to top-rated products if no history

    Returns: { "products": [...], "count": int, "personalized": bool }
    """
    user_id = user["user_id"]
    logger.info(f"User {user_id} requesting {limit} product recommendations")

    try:
        # Try to get personalized recommendations based on user's coupon categories
        result = db.execute(
            text("""
                WITH user_categories AS (
                    SELECT DISTINCT c.category_or_brand as category
                    FROM user_coupons uc
                    JOIN coupons c ON uc.coupon_id = c.id
                    WHERE uc.user_id = :user_id
                        AND c.type IN ('category', 'brand')
                        AND c.category_or_brand IS NOT NULL
                    LIMIT 5
                )
                SELECT DISTINCT
                    p.id, p.name, p.description, p.image_url, p.price,
                    p.rating, p.review_count, p.category, p.brand,
                    p.promo_text, p.in_stock
                FROM products p
                WHERE p.in_stock = true
                    AND (p.category IN (SELECT category FROM user_categories)
                         OR p.brand IN (SELECT category FROM user_categories))
                ORDER BY p.rating DESC NULLS LAST, p.review_count DESC NULLS LAST
                LIMIT :limit
            """),
            {"user_id": user_id, "limit": limit}
        )
        rows = result.fetchall()

        personalized = len(rows) > 0

        # If no personalized results, fallback to top-rated products
        if not rows:
            logger.info(f"No personalized recommendations for user {user_id}, using top-rated fallback")
            result = db.execute(
                text("""
                    SELECT
                        id, name, description, image_url, price,
                        rating, review_count, category, brand,
                        promo_text, in_stock
                    FROM products
                    WHERE in_stock = true
                    ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

        products = []
        for row in rows:
            products.append({
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "imageUrl": row[3],
                "price": float(row[4]) if row[4] else 0.0,
                "rating": float(row[5]) if row[5] else None,
                "reviewCount": row[6] if row[6] else 0,
                "category": row[7],
                "brand": row[8],
                "promoText": row[9],
                "inStock": row[10]
            })

        logger.info(f"Returning {len(products)} recommendations (personalized={personalized})")
        return JSONResponse({
            "products": products,
            "count": len(products),
            "personalized": personalized
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Recommendations failed for user {user_id}: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recommendations: {str(e)}"
        )


@app.get("/api/coupons/wallet")
@limiter.limit("30/minute")
async def get_wallet_coupons(
    request: Request,
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get all active coupons assigned to the authenticated user.
    Returns coupons split by type (frontstore vs category/brand).
    """
    user_id = user["user_id"]

    try:
        # Query active coupons for this user
        query = text("""
            SELECT
                c.id,
                c.type,
                c.discount_details,
                c.category_or_brand,
                c.expiration_date,
                c.terms
            FROM coupons c
            JOIN user_coupons uc ON c.id = uc.coupon_id
            WHERE uc.user_id = :user_id
              AND uc.eligible_until > NOW()
              AND c.expiration_date > NOW()
            ORDER BY
                CASE c.type
                    WHEN 'frontstore' THEN 1
                    WHEN 'category' THEN 2
                    WHEN 'brand' THEN 3
                END,
                c.expiration_date ASC
        """)

        result = db.execute(query, {"user_id": user_id})
        rows = result.fetchall()

        # Transform to list of dicts
        all_coupons = [
            {
                "id": str(row.id),
                "type": row.type,
                "discount_details": row.discount_details,
                "category_or_brand": row.category_or_brand,
                "expiration_date": row.expiration_date.isoformat() if row.expiration_date else None,
                "terms": row.terms
            }
            for row in rows
        ]

        # Split by type
        frontstore = [c for c in all_coupons if c["type"] == "frontstore"]
        category_brand = [c for c in all_coupons if c["type"] in ("category", "brand")]

        logger.info(f"Wallet for user {user_id}: {len(frontstore)} frontstore, {len(category_brand)} category/brand")

        return JSONResponse({
            "frontstore": frontstore,
            "categoryBrand": category_brand,
            "total": len(all_coupons)
        })

    except Exception as e:
        logger.exception(f"Wallet fetch failed for user {user_id}: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch wallet coupons: {str(e)}"
        )


@app.post("/api/image-extract")
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP (increased for AR mode)
async def image_extract(
    request: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(verify_token)
) -> JSONResponse:
    """
    Image-based brand and category extraction using OpenAI Vision API (authenticated).
    - Accepts image upload (JPEG, PNG, WebP)
    - Extracts brand name, category, and confidence level
    - Returns: { "brand": "...", "category": "...", "confidence": "high|medium|low", "searchQuery": "..." }
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
            detail="No image file provided"
        )

    # Validate MIME type
    allowed_mimes = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    content_type = file.content_type or ""

    if content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type. Allowed: {', '.join(allowed_mimes)}"
        )

    logger.info(f"User {user_id} uploaded image: {file.filename}, content_type: {content_type}")

    # Read file content
    try:
        image_bytes = await file.read()
    except Exception as e:
        logger.exception("Failed to read uploaded image: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read image file"
        )

    # Validate file size (max 5MB for images)
    max_size_mb = 5
    if len(image_bytes) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image file too large. Max {max_size_mb}MB allowed."
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is empty"
        )

    # Convert image to base64 for OpenAI Vision API
    try:
        import base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Determine image format
        image_format = "jpeg"
        if content_type == "image/png":
            image_format = "png"
        elif content_type == "image/webp":
            image_format = "webp"

        data_url = f"data:{content_type};base64,{base64_image}"

    except Exception as e:
        logger.exception("Failed to encode image: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image"
        )

    # Call OpenAI Vision API
    try:
        logger.info(f"Initializing OpenAI client for image analysis (user {user_id})")
        client = OpenAI(
            api_key=api_key,
            default_headers={
                "X-Environment": ENV,
                "X-User-Agent": f"VoiceOffers/{app.version}/{ENV}"
            }
        )

        t_api_start = time.time()
        logger.info(f"Calling OpenAI Vision API for user {user_id}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this product image and extract DETAILED information. Focus on distinguishing product variants.

Return ONLY valid JSON:
{
  "product_name": "Specific Product Name with Variant" or null,
  "brand": "Brand Name" or null,
  "category": "Product Category" or null,
  "variant_details": {
    "form_factor": "gummies|tablets|capsules|liquid|powder|cream|etc" or null,
    "primary_ingredient": "B12|Vitamin C|Vitamin D|etc" or null,
    "dosage": "500mg|1000mcg|etc" or null,
    "flavor": "orange|cherry|etc" or null,
    "count": "60ct|120ct|etc" or null
  },
  "visible_text": ["All visible text on package"],
  "confidence": "high" or "medium" or "low"
}

CRITICAL INSTRUCTIONS:
1. product_name: Must include variant details. Examples:
   - "Vitamin B12 Gummies" (NOT just "Vitamin Gummies")
   - "Extra Strength Tylenol 500mg" (NOT just "Tylenol")
   - "Neutrogena Hydro Boost Gel Cream" (NOT just "Neutrogena Cream")

2. variant_details: Extract ALL visible variant identifiers:
   - form_factor: Physical form (gummies, tablets, capsules, liquid, etc.)
   - primary_ingredient: Main active ingredient or vitamin type (B12, Vitamin C, D3, etc.)
   - dosage: Strength/amount (500mg, 1000mcg, 50mg, etc.)
   - flavor: If visible (orange, cherry, strawberry, unflavored, etc.)
   - count: Package count if visible (60ct, 90ct, 120ct, etc.)

3. visible_text: Transcribe ALL readable text from the package as a list

4. confidence:
   - "high": Product name + brand + 2+ variant details clearly visible
   - "medium": Product name + brand visible, some variant details unclear
   - "low": Missing critical information or image unclear

5. If multiple products visible, focus on the most prominent/centered one

Return ONLY the JSON object, no additional text."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=400,  # Increased from 200 to allow detailed variant extraction
            temperature=0.0  # Fully deterministic (changed from 0.1)
        )

        t_api_end = time.time()

        # Extract response
        raw_content = response.choices[0].message.content.strip()
        logger.info(f"OpenAI Vision raw response: {raw_content}")

        # Parse JSON response
        try:
            # Robust JSON extraction: Find first '{' and last '}'
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = raw_content[start_idx:end_idx+1]
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(raw_content.strip())

            product_name = parsed.get("product_name")
            brand = parsed.get("brand")
            category = parsed.get("category")
            variant_details = parsed.get("variant_details", {})
            visible_text = parsed.get("visible_text", [])
            confidence = parsed.get("confidence", "low")

            # Validate confidence value
            if confidence not in ["high", "medium", "low"]:
                confidence = "low"

            # Create search query including variant details
            search_parts = []
            if brand:
                search_parts.append(str(brand))
            if product_name:
                search_parts.append(str(product_name))
            if category:
                search_parts.append(str(category))

            # Add variant details to search query for better matching
            if variant_details:
                if variant_details.get("primary_ingredient"):
                    search_parts.append(str(variant_details["primary_ingredient"]))
                if variant_details.get("form_factor"):
                    search_parts.append(str(variant_details["form_factor"]))

            search_query = " ".join(search_parts) if search_parts else ""

            logger.info(f"Extracted: product={product_name}, brand={brand}, category={category}, variant_details={variant_details}, confidence={confidence}, query={search_query}")

        except (json.JSONDecodeError, KeyError, AttributeError) as parse_error:
            logger.warning(f"Failed to parse Vision API response: {parse_error}. Raw: {raw_content}")
            # Return low confidence result
            product_name = None
            brand = None
            category = None
            variant_details = {}
            visible_text = []
            confidence = "low"
            search_query = ""

        t_total = time.time() - t0
        api_duration_ms = int((t_api_end - t_api_start) * 1000)
        total_duration_ms = int(t_total * 1000)

        if ENABLE_TIMING_LOGS:
            logger.info(f"Image extraction completed for user {user_id}: {total_duration_ms}ms total (API: {api_duration_ms}ms)")

        return JSONResponse({
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "variant_details": variant_details,
            "visible_text": visible_text,
            "confidence": confidence,
            "searchQuery": search_query,
            "duration_ms": total_duration_ms,
            "api_duration_ms": api_duration_ms
        }, status_code=200)

    except Exception as e:
        logger.exception("OpenAI Vision API error: %s", e)

        error_msg = str(e)
        error_type = type(e).__name__

        # Check for specific OpenAI API errors
        if "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
            detail = f"OpenAI quota exceeded. Error: {error_msg}"
        elif "rate_limit" in error_msg.lower():
            detail = f"Rate limit exceeded. Please try again later. Error: {error_msg}"
        elif "invalid_api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
            detail = f"Invalid OpenAI API key. Error: {error_msg}"
        elif "timeout" in error_msg.lower():
            detail = f"Request timeout. Please try with smaller image. Error: {error_msg}"
        else:
            detail = f"Image extraction failed ({error_type}): {error_msg}"

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
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
