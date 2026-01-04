#!/usr/bin/env python3
"""Quick database query script using .env credentials"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def query_db(query: str):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set in .env")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        if result.returns_rows:
            columns = result.keys()
            print("\t".join(columns))
            print("-" * 100)
            for row in result:
                print("\t".join(str(v) for v in row))
        else:
            print(f"Query executed. {result.rowcount} rows affected.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python query_db.py "YOUR SQL QUERY"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    query_db(query)
