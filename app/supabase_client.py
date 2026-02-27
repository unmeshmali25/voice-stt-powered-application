"""
Supabase client for backend Python scripts.
Used by scripts for database operations and storage uploads.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Optional[Client] = None

if SUPABASE_URL:
    # Use service key if available for backend operations (bypasses RLS)
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if key:
        supabase = create_client(SUPABASE_URL, key)
    else:
        print("Warning: Neither SUPABASE_SERVICE_KEY nor SUPABASE_KEY set.")
else:
    print("Warning: SUPABASE_URL not set. Supabase client not initialized.")
