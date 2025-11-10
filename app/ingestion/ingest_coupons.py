"""
Coupon Data Ingestion Script

Loads coupon data from JSON file and ingests into PostgreSQL database.
Optionally generates embeddings and builds FAISS index.

Usage:
    python -m app.ingestion.ingest_coupons --rebuild
    python -m app.ingestion.ingest_coupons --no-embed
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev@localhost:5432/voiceoffers")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
COUPONS_JSON_PATH = DATA_DIR / "coupons.json"
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", "./data/index/faiss.index")).resolve()
FAISS_META_PATH = Path(os.getenv("FAISS_META_PATH", "./data/index/meta.json")).resolve()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Database setup
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def load_coupons_data() -> Dict[str, Any]:
    """Load coupon data from JSON file."""
    if not COUPONS_JSON_PATH.exists():
        print(f"Error: Coupons JSON file not found at {COUPONS_JSON_PATH}")
        sys.exit(1)

    with open(COUPONS_JSON_PATH, 'r') as f:
        data = json.load(f)

    print(f"Loaded {len(data.get('coupons', []))} coupons from {COUPONS_JSON_PATH}")
    return data


def clear_database(session):
    """Clear existing coupon data."""
    print("Clearing existing coupon data...")
    session.execute(text("DELETE FROM coupon_usage"))
    session.execute(text("DELETE FROM user_coupons"))
    session.execute(text("DELETE FROM coupons"))
    session.execute(text("DELETE FROM user_attributes"))
    session.execute(text("DELETE FROM users"))
    session.commit()
    print("Database cleared.")


def ingest_users(session, users_data: List[Dict[str, Any]]):
    """Insert users into database."""
    print(f"Ingesting {len(users_data)} users...")

    for user in users_data:
        session.execute(
            text("""
                INSERT INTO users (id, email, full_name)
                VALUES (:id, :email, :full_name)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "id": user["id"],
                "email": user["email"],
                "full_name": user.get("full_name")
            }
        )

        # Insert user attributes if provided
        for attr_key, attr_value in user.get("attributes", {}).items():
            session.execute(
                text("""
                    INSERT INTO user_attributes (user_id, attribute_key, attribute_value)
                    VALUES (:user_id, :attribute_key, :attribute_value)
                    ON CONFLICT (user_id, attribute_key) DO UPDATE SET
                        attribute_value = EXCLUDED.attribute_value
                """),
                {
                    "user_id": user["id"],
                    "attribute_key": attr_key,
                    "attribute_value": attr_value
                }
            )

    session.commit()
    print(f"Ingested {len(users_data)} users.")


def ingest_coupons(session, coupons_data: List[Dict[str, Any]]) -> List[str]:
    """Insert coupons into database. Returns list of coupon IDs."""
    print(f"Ingesting {len(coupons_data)} coupons...")

    coupon_ids = []

    for coupon in coupons_data:
        result = session.execute(
            text("""
                INSERT INTO coupons (id, type, discount_details, category_or_brand,
                                     expiration_date, terms)
                VALUES (uuid_generate_v4()::text::uuid, :type, :discount_details,
                        :category_or_brand, :expiration_date, :terms)
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    discount_details = EXCLUDED.discount_details,
                    category_or_brand = EXCLUDED.category_or_brand,
                    expiration_date = EXCLUDED.expiration_date,
                    terms = EXCLUDED.terms,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """),
            {
                "type": coupon["type"],
                "discount_details": coupon["discount_details"],
                "category_or_brand": coupon.get("category_or_brand"),
                "expiration_date": coupon["expiration_date"],
                "terms": coupon.get("terms")
            }
        )
        coupon_id = result.scalar()
        coupon_ids.append(str(coupon_id))

    session.commit()
    print(f"Ingested {len(coupons_data)} coupons.")
    return coupon_ids


def assign_coupons_to_users(session, assignments: Dict[str, List[str]], coupon_map: Dict[int, str]):
    """
    Assign coupons to users.
    assignments: { user_id: [coupon_index, ...] }
    coupon_map: { coupon_index: coupon_id }
    """
    print(f"Assigning coupons to {len(assignments)} users...")

    total_assignments = 0
    for user_id, coupon_indices in assignments.items():
        for idx in coupon_indices:
            coupon_id = coupon_map.get(idx)
            if not coupon_id:
                print(f"Warning: Coupon index {idx} not found in coupon_map")
                continue

            session.execute(
                text("""
                    INSERT INTO user_coupons (user_id, coupon_id)
                    VALUES (:user_id, :coupon_id)
                    ON CONFLICT (user_id, coupon_id) DO NOTHING
                """),
                {
                    "user_id": user_id,
                    "coupon_id": coupon_id
                }
            )
            total_assignments += 1

    session.commit()
    print(f"Created {total_assignments} user-coupon assignments.")


def generate_embeddings(session, skip_embeddings: bool):
    """Generate embeddings for all coupons."""
    if skip_embeddings:
        print("Skipping embedding generation (--no-embed flag).")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not configured. Skipping embeddings.")
        return

    print("Generating embeddings for coupons...")

    # Fetch all coupons
    result = session.execute(
        text("SELECT id, discount_details, category_or_brand, terms FROM coupons ORDER BY created_at")
    )
    coupons = result.fetchall()

    if not coupons:
        print("No coupons found. Skipping embeddings.")
        return

    # Prepare texts for embedding
    texts = [
        f"{coupon[1]} {coupon[2] or ''} {coupon[3] or ''}".strip()
        for coupon in coupons
    ]

    # Generate embeddings in batches
    batch_size = 64
    all_embeddings = []
    client = OpenAI(api_key=api_key)

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}...")

        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"Error generating embeddings for batch {i//batch_size + 1}: {e}")
            sys.exit(1)

    # L2 normalize embeddings
    embeddings = np.array(all_embeddings, dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
    embeddings = embeddings / norms

    print(f"Generated {len(embeddings)} embeddings with dimension {embeddings.shape[1]}")

    # Build FAISS index
    try:
        import faiss

        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity on normalized vectors)
        index.add(embeddings)

        # Save index
        FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(FAISS_INDEX_PATH))
        print(f"FAISS index saved to {FAISS_INDEX_PATH}")

        # Save metadata
        metadata = [
            {"coupon_id": str(coupon[0])}
            for coupon in coupons
        ]
        with open(FAISS_META_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata saved to {FAISS_META_PATH}")

    except ImportError:
        print("Warning: FAISS not installed. Skipping index creation.")
    except Exception as e:
        print(f"Error creating FAISS index: {e}")


def main():
    parser = argparse.ArgumentParser(description="Ingest coupon data into database")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing data before ingestion")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()

    print("=" * 60)
    print("Coupon Data Ingestion Script")
    print("=" * 60)

    # Load data
    data = load_coupons_data()

    session = SessionLocal()

    try:
        if args.rebuild:
            clear_database(session)

        # Ingest users
        if "users" in data:
            ingest_users(session, data["users"])

        # Ingest coupons
        coupon_ids = ingest_coupons(session, data["coupons"])

        # Create coupon index mapping
        coupon_map = {i: coupon_id for i, coupon_id in enumerate(coupon_ids)}

        # Assign coupons to users
        if "user_assignments" in data:
            assign_coupons_to_users(session, data["user_assignments"], coupon_map)

        # Generate embeddings
        generate_embeddings(session, args.no_embed)

        print("\n" + "=" * 60)
        print("Ingestion complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during ingestion: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
