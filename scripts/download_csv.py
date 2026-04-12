#!/usr/bin/env python3
"""
소상공인 상가정보 CSV 다운로드 스크립트.

data.go.kr 소상공인시장진흥공단_상가(상권)정보 파일데이터
https://www.data.go.kr/data/15083033/fileData.do

Usage:
    python scripts/download_csv.py
"""
import os
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

# 소상공인 상가정보 파일 다운로드 URL
# NOTE: data.go.kr의 파일데이터 다운로드 URL은 변경될 수 있음
# 최신 URL은 https://www.data.go.kr/data/15083033/fileData.do 에서 확인
DOWNLOAD_URLS = [
    # 시도별 분할 파일 (각 ~50MB)
    # 2025년 1분기 기준 - URL 업데이트 필요시 data.go.kr에서 확인
]


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> Path:
    """Stream download a file with progress."""
    print(f"Downloading: {url}")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded / total * 100
                print(f"\r  {downloaded / 1_000_000:.1f}MB / {total / 1_000_000:.1f}MB ({pct:.1f}%)", end="", flush=True)
    print()
    return dest


def extract_zip(zip_path: Path, dest_dir: Path) -> list:
    """Extract ZIP and return list of extracted CSV files."""
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                zf.extract(name, dest_dir)
                extracted.append(dest_dir / name)
                print(f"  Extracted: {name}")
    return extracted


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if CSV files already exist
    existing_csvs = list(RAW_DIR.glob("*.csv"))
    if existing_csvs:
        print(f"Found {len(existing_csvs)} existing CSV files in {RAW_DIR}")
        ans = input("Re-download? [y/N] ").strip().lower()
        if ans != "y":
            print("Using existing files.")
            return

    if not DOWNLOAD_URLS:
        print("=" * 60)
        print("자동 다운로드 URL이 설정되지 않았습니다.")
        print()
        print("수동 다운로드 방법:")
        print("1. https://www.data.go.kr/data/15083033/fileData.do 접속")
        print("2. 최신 분기 파일 다운로드 (CSV)")
        print(f"3. 다운로드한 파일을 {RAW_DIR}/ 에 배치")
        print("4. python scripts/build_db.py 실행")
        print()
        print("또는 API를 사용하려면:")
        print("  DATA_GO_KR_API_KEY를 .env에 설정 후")
        print("  python scripts/download_csv.py --api 로 실행")
        print("=" * 60)

        # API fallback
        if "--api" in sys.argv:
            api_key = os.getenv("DATA_GO_KR_API_KEY")
            if not api_key:
                print("ERROR: DATA_GO_KR_API_KEY not set in .env")
                sys.exit(1)
            download_via_api(api_key)
        return

    for url in DOWNLOAD_URLS:
        filename = url.split("/")[-1]
        dest = RAW_DIR / filename
        download_file(url, dest)

        if filename.endswith(".zip"):
            extract_zip(dest, RAW_DIR)
            dest.unlink()  # Remove ZIP after extraction

    print(f"\nDone. CSV files are in {RAW_DIR}")
    print("Next: python scripts/build_db.py")


def download_via_api(api_key: str):
    """Download store data via 소상공인 API (slower but always available)."""
    print("API download not yet implemented for bulk data.")
    print("The API returns 1000 rows per request — use file download for bulk data.")
    sys.exit(1)


if __name__ == "__main__":
    main()
