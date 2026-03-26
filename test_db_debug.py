import sqlite3
import datetime
import os

DB_PATH = "C:/Users/PIYUSH/.gemini/antigravity/scratch/smart_parking/data/smart_parking.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=== OCCUPANCY LOG TEST ===")
row = conn.execute("SELECT event_time FROM occupancy_log LIMIT 1").fetchone()
if row:
    print(f"Sample event_time format: {row['event_time']}")
else:
    print("NO EVENTS FOUND!")

print("\n=== DAILY SUMMARY TEST ===")
rows = conn.execute("SELECT * FROM daily_summary LIMIT 5").fetchall()
for r in rows:
    print(dict(r))

print("\n=== AGGREGATE TEST FOR '2026-03-25' ===")
zone_id = "LOC_HOSP_EM"
entries = conn.execute(
    "SELECT COUNT(*) as cnt FROM occupancy_log WHERE zone_id = ? AND event_time LIKE '2026-03-25%'",
    (zone_id,)
).fetchone()["cnt"]
print(f"Count for 2026-03-25 LIKE query: {entries}")

conn.close()
