#!/usr/bin/env python3
"""
소상공인 상가정보 CSV → SQLite + R-tree 빌드 스크립트.

Usage:
    python scripts/build_db.py                    # Build from CSV files
    python scripts/build_db.py --test              # Build test DB with synthetic data
    python scripts/build_db.py --csv path/to.csv   # Build from specific CSV

Output:
    data/sangkwon.db (production)
    data/sangkwon_test.db (test mode)
"""
import argparse
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

# 소상공인 CSV 컬럼 매핑 (한글 → 영문)
COLUMN_MAP = {
    "상가업소번호": "store_id",
    "상호명": "name",
    "지점명": "branch_name",
    "상권업종대분류코드": "category_l",
    "상권업종대분류명": "category_l_name",
    "상권업종중분류코드": "category_m",
    "상권업종중분류명": "category_m_name",
    "상권업종소분류코드": "category_s",
    "상권업종소분류명": "category_s_name",
    "시도코드": "sido_code",
    "시도명": "sido",
    "시군구코드": "sigungu_code",
    "시군구명": "sigungu",
    "행정동코드": "dong_code",
    "행정동명": "dong",
    "법정동코드": "legal_dong_code",
    "법정동명": "legal_dong",
    "지번코드": "jibun_code",
    "도로명코드": "road_code",
    "도로명": "road_name",
    "건물본번지": "building_main",
    "건물부번지": "building_sub",
    "건물관리번호": "building_mgmt_no",
    "건물명": "building_name",
    "도로명주소": "road_address",
    "구주소": "old_address",
    "신우편번호": "zipcode",
    "경도": "lng",
    "위도": "lat",
    "층정보": "floor_info",
    "영업상태코드": "business_status",
    "영업상태명": "business_status_name",
}

# SQLite 테이블 스키마
CREATE_STORES_SQL = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT,
    name TEXT,
    branch_name TEXT,
    category_l TEXT,
    category_l_name TEXT,
    category_m TEXT,
    category_m_name TEXT,
    category_s TEXT,
    category_s_name TEXT,
    sido TEXT,
    sigungu TEXT,
    dong TEXT,
    road_address TEXT,
    old_address TEXT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    floor_info TEXT,
    business_status TEXT,
    business_status_name TEXT
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_category_l ON stores(category_l);",
    "CREATE INDEX IF NOT EXISTS idx_category_m ON stores(category_m);",
    "CREATE INDEX IF NOT EXISTS idx_sido ON stores(sido);",
    "CREATE INDEX IF NOT EXISTS idx_sigungu ON stores(sigungu);",
    "CREATE INDEX IF NOT EXISTS idx_dong ON stores(dong);",
    "CREATE INDEX IF NOT EXISTS idx_lat_lng ON stores(lat, lng);",
    "CREATE INDEX IF NOT EXISTS idx_business_status ON stores(business_status);",
]

CREATE_RTREE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS store_rtree USING rtree(
    id,
    min_lat, max_lat,
    min_lng, max_lng
);
"""

CREATE_CATEGORIES_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    code TEXT PRIMARY KEY,
    name TEXT,
    level TEXT,
    parent_code TEXT,
    count INTEGER DEFAULT 0
);
"""

CREATE_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS store_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    business_status TEXT,
    quarter TEXT NOT NULL,
    category_m TEXT,
    lat REAL,
    lng REAL,
    UNIQUE(store_id, quarter)
);
"""

CREATE_META_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

# Keep columns we actually use
KEEP_COLUMNS = [
    "store_id", "name", "branch_name",
    "category_l", "category_l_name",
    "category_m", "category_m_name",
    "category_s", "category_s_name",
    "sido", "sigungu", "dong",
    "road_address", "old_address",
    "lat", "lng", "floor_info",
    "business_status", "business_status_name",
]


def detect_encoding(csv_path: Path) -> str:
    """Detect CSV encoding (UTF-8 or CP949)."""
    for enc in ["utf-8", "cp949", "euc-kr"]:
        try:
            with open(csv_path, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def build_from_csvs(db_path: Path, csv_files: list, chunk_size: int = 50000):
    """Build SQLite DB from CSV files."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")  # Speed up bulk insert
    conn.execute("PRAGMA cache_size=-200000;")  # 200MB cache

    # Create tables
    conn.execute(CREATE_STORES_SQL)
    conn.execute(CREATE_RTREE_SQL)
    conn.execute(CREATE_SNAPSHOTS_SQL)
    conn.execute(CREATE_CATEGORIES_SQL)
    conn.execute(CREATE_META_SQL)
    conn.commit()

    total_inserted = 0
    total_skipped = 0
    start_time = time.time()

    for csv_path in csv_files:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"  SKIP: {csv_path} not found")
            continue

        encoding = detect_encoding(csv_path)
        print(f"  Processing: {csv_path.name} (encoding={encoding})")

        for chunk_idx, chunk in enumerate(pd.read_csv(
            csv_path,
            encoding=encoding,
            chunksize=chunk_size,
            dtype=str,
            low_memory=False,
            on_bad_lines="skip",
        )):
            # Rename columns
            chunk = chunk.rename(columns={
                k: v for k, v in COLUMN_MAP.items() if k in chunk.columns
            })

            # Keep only needed columns that exist
            available = [c for c in KEEP_COLUMNS if c in chunk.columns]
            chunk = chunk[available]

            # Convert lat/lng to float
            if "lat" in chunk.columns and "lng" in chunk.columns:
                chunk["lat"] = pd.to_numeric(chunk["lat"], errors="coerce")
                chunk["lng"] = pd.to_numeric(chunk["lng"], errors="coerce")
            else:
                print(f"    WARNING: lat/lng columns missing in chunk {chunk_idx}")
                continue

            # Filter: valid coordinates + not null
            before = len(chunk)
            chunk = chunk.dropna(subset=["lat", "lng"])
            chunk = chunk[(chunk["lat"] > 33) & (chunk["lat"] < 39)]  # Korea bounds
            chunk = chunk[(chunk["lng"] > 124) & (chunk["lng"] < 132)]
            after = len(chunk)
            total_skipped += before - after

            if after == 0:
                continue

            # Insert into stores table
            chunk.to_sql("stores", conn, if_exists="append", index=False)
            total_inserted += after

            if (chunk_idx + 1) % 5 == 0:
                elapsed = time.time() - start_time
                print(f"    Chunk {chunk_idx + 1}: {total_inserted:,} rows inserted ({elapsed:.1f}s)")

    # Build R-tree index
    print("  Building R-tree spatial index...")
    conn.execute("""
        INSERT INTO store_rtree (id, min_lat, max_lat, min_lng, max_lng)
        SELECT id, lat, lat, lng, lng FROM stores;
    """)

    # Build regular indexes
    print("  Building standard indexes...")
    for sql in CREATE_INDEXES_SQL:
        conn.execute(sql)

    # Build categories table
    print("  Building categories table...")
    conn.execute("""
        INSERT OR REPLACE INTO categories (code, name, level, parent_code, count)
        SELECT category_m, category_m_name, '중분류', category_l, COUNT(*)
        FROM stores
        WHERE category_m IS NOT NULL
        GROUP BY category_m, category_m_name, category_l;
    """)
    conn.execute("""
        INSERT OR REPLACE INTO categories (code, name, level, parent_code, count)
        SELECT category_l, category_l_name, '대분류', NULL, COUNT(*)
        FROM stores
        WHERE category_l IS NOT NULL
        GROUP BY category_l, category_l_name;
    """)

    # Build snapshots for quarterly tracking
    import datetime
    current_quarter = f"{datetime.date.today().year}Q{(datetime.date.today().month - 1) // 3 + 1}"
    print(f"  Building store snapshots ({current_quarter})...")
    conn.execute("""
        INSERT OR IGNORE INTO store_snapshots (store_id, business_status, quarter, category_m, lat, lng)
        SELECT store_id, business_status, ?, category_m, lat, lng
        FROM stores WHERE store_id IS NOT NULL;
    """, (current_quarter,))

    # Save metadata (parameterized queries)
    elapsed = time.time() - start_time
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('build_date', datetime('now'));")
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("total_stores", str(total_inserted)))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("total_skipped", str(total_skipped)))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("build_time_sec", f"{elapsed:.1f}"))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("source", "data.go.kr/15083033"))

    # Reset PRAGMA
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.commit()
    conn.close()

    db_size_mb = db_path.stat().st_size / 1_000_000
    print(f"\n  Done!")
    print(f"  Total inserted: {total_inserted:,}")
    print(f"  Total skipped: {total_skipped:,}")
    print(f"  DB size: {db_size_mb:.1f} MB")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Path: {db_path}")


def build_test_db(db_path: Path):
    """Build a small test DB with synthetic data around major Korean locations."""
    import random
    random.seed(42)

    locations = [
        # (name, lat, lng, concentration)
        ("강남역", 37.4980, 127.0276, 200),
        ("홍대입구", 37.5563, 126.9236, 150),
        ("종로", 37.5700, 126.9920, 120),
        ("이태원", 37.5345, 126.9940, 80),
        ("합정", 37.5496, 126.9139, 60),
        ("성수", 37.5445, 127.0567, 90),
        ("여의도", 37.5216, 126.9241, 70),
        ("건대입구", 37.5402, 127.0690, 80),
        ("대전둔산", 36.3551, 127.3837, 50),
        ("부산서면", 35.1576, 129.0596, 60),
    ]

    categories_m = [
        ("Q01", "한식", "Q", "음식"),
        ("Q02", "중식", "Q", "음식"),
        ("Q03", "일식", "Q", "음식"),
        ("Q04", "양식", "Q", "음식"),
        ("Q05", "제과점/베이커리", "Q", "음식"),
        ("Q07", "치킨", "Q", "음식"),
        ("Q08", "분식", "Q", "음식"),
        ("Q09", "호프/주점", "Q", "음식"),
        ("Q12", "커피점/카페", "Q", "음식"),
        ("D01", "편의점", "D", "소매"),
        ("D02", "슈퍼마켓", "D", "소매"),
        ("D03", "의류", "D", "소매"),
        ("D04", "화장품", "D", "소매"),
        ("F01", "미용실", "F", "생활서비스"),
        ("F02", "세탁소", "F", "생활서비스"),
        ("F06", "헬스/피트니스", "F", "생활서비스"),
        ("N01", "학원", "N", "학문/교육"),
    ]

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(CREATE_STORES_SQL)
    conn.execute(CREATE_RTREE_SQL)
    conn.execute(CREATE_SNAPSHOTS_SQL)
    conn.execute(CREATE_CATEGORIES_SQL)
    conn.execute(CREATE_META_SQL)

    # Business status distribution: 80% active, 10% closed, 10% suspended
    statuses = [
        ("01", "영업/정상", 80),
        ("03", "폐업", 10),
        ("02", "휴업", 10),
    ]
    status_pool = []
    for code, name, weight in statuses:
        status_pool.extend([(code, name)] * weight)

    store_id = 0
    rows = []

    for loc_name, center_lat, center_lng, count in locations:
        for _ in range(count):
            store_id += 1
            cat = random.choice(categories_m)
            status = random.choice(status_pool)
            # Random offset within ~500m
            lat = center_lat + random.gauss(0, 0.002)
            lng = center_lng + random.gauss(0, 0.002)
            rows.append((
                store_id,
                f"SYN{store_id:06d}",
                f"{loc_name} {cat[1]} {store_id}",
                None,
                cat[2], cat[3],
                cat[0], cat[1],
                None, None,
                "서울특별시" if center_lat > 37 else "대전광역시" if center_lat > 36 else "부산광역시",
                loc_name,
                loc_name,
                f"서울시 {loc_name} {store_id}번지",
                None,
                round(lat, 6),
                round(lng, 6),
                None,
                status[0], status[1],
            ))

    conn.executemany("""
        INSERT INTO stores (
            id, store_id, name, branch_name,
            category_l, category_l_name,
            category_m, category_m_name,
            category_s, category_s_name,
            sido, sigungu, dong,
            road_address, old_address,
            lat, lng, floor_info,
            business_status, business_status_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    # Build R-tree
    conn.execute("""
        INSERT INTO store_rtree (id, min_lat, max_lat, min_lng, max_lng)
        SELECT id, lat, lat, lng, lng FROM stores;
    """)

    # Build indexes
    for sql in CREATE_INDEXES_SQL:
        conn.execute(sql)

    # Build categories
    conn.execute("""
        INSERT OR REPLACE INTO categories (code, name, level, parent_code, count)
        SELECT category_m, category_m_name, '중분류', category_l, COUNT(*)
        FROM stores WHERE category_m IS NOT NULL
        GROUP BY category_m, category_m_name, category_l;
    """)

    # Build snapshots
    import datetime
    current_quarter = f"{datetime.date.today().year}Q{(datetime.date.today().month - 1) // 3 + 1}"
    conn.execute("""
        INSERT OR IGNORE INTO store_snapshots (store_id, business_status, quarter, category_m, lat, lng)
        SELECT store_id, business_status, ?, category_m, lat, lng
        FROM stores WHERE store_id IS NOT NULL;
    """, (current_quarter,))

    # Metadata (parameterized)
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('build_date', datetime('now'));")
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("total_stores", str(store_id)))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("source", "synthetic_test_data"))

    conn.commit()
    conn.close()

    print(f"Test DB built: {db_path}")
    print(f"  Total stores: {store_id}")
    print(f"  Locations: {len(locations)}")
    print(f"  Categories: {len(categories_m)}")


def main():
    parser = argparse.ArgumentParser(description="Build Sangkwon SQLite DB")
    parser.add_argument("--test", action="store_true", help="Build test DB with synthetic data")
    parser.add_argument("--csv", type=str, help="Specific CSV file to process")
    parser.add_argument("--output", type=str, help="Output DB path")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.test:
        db_path = Path(args.output) if args.output else DATA_DIR / "sangkwon_test.db"
        if db_path.exists():
            db_path.unlink()
        build_test_db(db_path)
        return

    # Production build
    db_path = Path(args.output) if args.output else DATA_DIR / "sangkwon.db"

    if args.csv:
        csv_files = [Path(args.csv)]
    else:
        csv_files = sorted(RAW_DIR.glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {RAW_DIR}")
        print("Run: python scripts/download_csv.py first")
        print("Or use: python scripts/build_db.py --test for synthetic data")
        sys.exit(1)

    print(f"Building DB from {len(csv_files)} CSV files...")
    if db_path.exists():
        db_path.unlink()
    build_from_csvs(db_path, csv_files)


if __name__ == "__main__":
    main()
