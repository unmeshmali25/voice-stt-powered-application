import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)

if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Coupons count:", conn.execute(text("SELECT count(*) FROM coupons")).scalar())
        print("Users count:", conn.execute(text("SELECT count(*) FROM users")).scalar())
        print("Agents count:", conn.execute(text("SELECT count(*) FROM agents")).scalar())
        print("Agents (active) count:", conn.execute(text("SELECT count(*) FROM agents WHERE is_active=true")).scalar())
        print("Offer Cycles count:", conn.execute(text("SELECT count(*) FROM offer_cycles")).scalar())
        print("User Offer Cycles count:", conn.execute(text("SELECT count(*) FROM user_offer_cycles")).scalar())
        
        sim_state = conn.execute(text("SELECT * FROM simulation_state")).fetchone()
        print("Simulation State:", sim_state)

except Exception as e:
    print(f"Error: {e}")
