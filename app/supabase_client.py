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

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set. Supabase client not initialized.")

