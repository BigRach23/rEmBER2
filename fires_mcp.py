# === fires_mcp.py (Shapefile-backed fire data with regional summaries) ===
import os, sqlite3, datetime
import geopandas as gpd
import pandas as pd

DB_PATH = "fires.db"
SHAPE_PATH = "MODIS_C6_1_USA_contiguous_and_Hawaii_48h.shp"
STATE_SHAPE_PATH = "cb_2018_us_state_500k.shp"  # optional

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fires (
            id TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            brightness REAL,
            confidence REAL,
            acq_date TEXT,
            satellite TEXT,
            updated_at TEXT
        )
    """)
    conn.commit(); conn.close()

def update_fire_data_from_local():
    if not os.path.exists(SHAPE_PATH):
        raise FileNotFoundError(f"Shapefile not found: {SHAPE_PATH}")
    gdf = gpd.read_file(SHAPE_PATH)
    gdf.columns = [c.upper() for c in gdf.columns]
    gdf = gdf.replace({pd.NA: None})

    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("DELETE FROM fires")
    inserted = 0
    for _, row in gdf.iterrows():
        try:
            lat = float(row.get("LATITUDE")); lon = float(row.get("LONGITUDE"))
            bright = float(row.get("BRIGHTNESS", 0) or 0)
        except Exception:
            continue
        conf = float(row.get("CONFIDENCE", 0) or 0)
        date = str(row.get("ACQ_DATE", "unknown"))
        sat = str(row.get("SATELLITE", "MODIS"))
        fid = f"{lat:.3f}_{lon:.3f}_{date}"
        cur.execute("""INSERT OR REPLACE INTO fires
            (id, latitude, longitude, brightness, confidence, acq_date, satellite, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fid, lat, lon, bright, conf, date, sat, datetime.datetime.utcnow().isoformat()))
        inserted += 1
    conn.commit(); conn.close()
    print(f"[FIRMS] Imported {inserted} fire records from shapefile.")

def get_fires_df(limit=None):
    init_db(); update_fire_data_from_local()
    conn = sqlite3.connect(DB_PATH)
    q = "SELECT latitude, longitude, brightness, confidence, acq_date, satellite FROM fires ORDER BY brightness DESC"
    if limit: q += f" LIMIT {int(limit)}"
    df = pd.read_sql_query(q, conn); conn.close(); return df

def get_fire_summary(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM fires")
    total = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT latitude, longitude, brightness, confidence, acq_date "
        "FROM fires ORDER BY brightness DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "No active fires found in the local MODIS database."

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"🔥 ({lat:.2f}, {lon:.2f}) brightness {b}, confidence {c}, date {d}"
        for (lat, lon, b, c, d) in rows
    ]
    return (
        f"As of {now}, there are approximately {total:,} active U.S. fires detected in the last 48 hours.\n"
        f"Here are {len(rows)} of the most intense sample fires:\n"
        + "\n".join(lines)
    )



def get_fire_summary_by_state(state_name: str):
    if not os.path.exists(STATE_SHAPE_PATH):
        return (f"State boundaries file not found ({STATE_SHAPE_PATH}). Upload Census 'cb_2018_us_state_500k' shapefile.")    
    states = gpd.read_file(STATE_SHAPE_PATH)
    name_col = 'NAME' if 'NAME' in states.columns else ('STATE_NAME' if 'STATE_NAME' in states.columns else None)
    if not name_col: return "Could not find a state name column in the state shapefile."
    states['NAME'] = states[name_col].astype(str).str.upper(); target = state_name.strip().upper()
    if target not in set(states['NAME'].values): return f"Unknown state '{state_name}'. Try a valid U.S. state name."
    conn = sqlite3.connect(DB_PATH); fires_df = pd.read_sql_query("SELECT latitude, longitude, brightness, confidence FROM fires", conn); conn.close()
    if fires_df.empty: return "No active fires found in the database."
    fire_gdf = gpd.GeoDataFrame(fires_df, geometry=gpd.points_from_xy(fires_df.longitude, fires_df.latitude), crs="EPSG:4326")
    state_geom = states[states['NAME']==target]
    try:
        joined = gpd.sjoin(fire_gdf, state_geom, how="inner", predicate="within")
    except TypeError:
        joined = gpd.sjoin(fire_gdf, state_geom, how="inner", op="within")
    if joined.empty: return f"No active fires currently detected in {state_name.title()}."
    count = len(joined); ab = joined['brightness'].mean(); ac = joined['confidence'].mean()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (f"As of {now}, {state_name.title()} has {count:,} active fires detected in the last 48 hours "
            f"(avg brightness {ab:.1f}, confidence {ac:.1f}%).")

def get_active_fires_cached(limit=10):
    init_db(); update_fire_data_from_local(); 
    return get_fire_summary(limit)
