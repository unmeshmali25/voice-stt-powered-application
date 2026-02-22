#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(
        text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'orders' 
        ORDER BY ordinal_position
    """)
    ).fetchall()
    print("Orders table columns:")
    for col in result:
        print(f"  - {col[0]}: {col[1]}")
