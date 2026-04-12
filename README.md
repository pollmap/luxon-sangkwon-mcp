# Luxon Sangkwon MCP

**한국 상권 인텔리전스 MCP 서버** — 자연어로 물어보면 바로 답하는 AI 상권분석 인프라

```
"강남역 500m 카페 상권 분석해줘"
→ 점포 187개, 카페 15개, 경쟁점수 82/100 (높음), 업종분포 Top 10
```

## What is this?

소상공인시장진흥공단 상가정보 **250만 건** + 카카오 지오코딩을 결합한 MCP(Model Context Protocol) 서버.
AI 에이전트(Claude, Cursor 등)가 한국 상권 데이터를 자연어로 조회할 수 있는 인프라.

### Architecture

```
User (자연어)
  │
  ▼
AI Agent (Claude Code / Cursor / Claude Desktop)
  │ MCP (streamable-http)
  ▼
┌─────────────────────────────────────────┐
│       Luxon Sangkwon MCP Gateway        │
│       FastMCP 3.x / Port 8102          │
├─────────────┬───────────┬──────────────┤
│  sangkwon   │   maps    │  density     │
│  (3 tools)  │ (3 tools) │  (1 tool)    │
├─────────────┴───────────┴──────────────┤
│              status (1 tool)            │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
 SQLite+R-tree  Kakao API   Cache/RateLimiter
 (250만 점포)   (지오코딩)   (4-tier / TokenBucket)
```

## Tools (8)

| Tool | Description | Example |
|------|-------------|---------|
| `sangkwon_analyze` | 상권 종합 분석 (점포수, 업종분포, 경쟁점수) | `"홍대 500m 치킨 분석"` |
| `sangkwon_compare` | 복수 지역 비교 | `"강남역;홍대;합정 카페 비교"` |
| `sangkwon_nearby_similar` | 주변 동종 업종 검색 (거리순) | `"이태원 주변 카페 찾아줘"` |
| `sangkwon_density_map` | 격자 밀도 분석 | `"성수동 1km 카페 밀도"` |
| `geocode` | 주소/지명 → 좌표 변환 | `"강남역"` → `37.498, 127.028` |
| `reverse_geocode` | 좌표 → 주소 변환 | `37.498, 127.028` → `서울 강남구` |
| `poi_search` | POI 검색 (카카오) | `"강남역 주변 스타벅스"` |
| `maps_status` | 서버 상태 (DB 통계, API 가용성) | — |

## How it works

### Data Pipeline

```
data.go.kr (소상공인 상가정보 CSV, 분기별 갱신)
  │
  ▼ scripts/download_csv.py
  │
  ▼ scripts/build_db.py
  │  - pandas chunked read (50K rows/chunk, peak RAM ~200MB)
  │  - Filter: valid lat/lng + Korea bounds (33~39°N, 124~132°E)
  │  - SQLite + R-tree spatial index
  │
  ▼ data/sangkwon.db (~600MB, 250만 rows)
```

### Query Flow (sangkwon_analyze)

```
1. User: "강남역 500m 카페"
2. location="강남역" → Kakao geocode → (37.498, 127.028)
3. category="카페" → resolve_category → Q12 (커피점/카페)
4. bounding_box(37.498, 127.028, 500m) → (south, west, north, east)
5. R-tree query: SELECT stores WHERE rtree IN bbox AND category_m='Q12'
6. Haversine post-filter: exact distance ≤ 500m
7. Aggregate: count, category distribution, competition score
8. Return: success_response({total: 187, cafes: 15, score: 82, ...})
```

### Competition Score

```
area_km2 = π × (radius_m / 1000)²
density  = filtered_stores / area_km2
score    = min(100, density × category_weight × 10)

Category weights: 음식=1.2, 소매=1.0, 서비스=0.8, 숙박=1.1
Score grades: 0-20 거의없음 / 21-40 낮음 / 41-60 보통 / 61-80 높음 / 81-100 과포화
```

## Setup

### Prerequisites

- Python 3.10+
- Kakao REST API Key ([developers.kakao.com](https://developers.kakao.com))
- data.go.kr API Key ([data.go.kr](https://www.data.go.kr))

### Install

```bash
git clone https://github.com/luxon-ai/luxon-sangkwon-mcp.git
cd luxon-sangkwon-mcp
pip install -r requirements.txt

# Configure API keys
cp .env.template .env
# Edit .env: set KAKAO_REST_API_KEY and DATA_GO_KR_API_KEY
```

### Build Database

```bash
# Option 1: Download real data (250만 rows, ~3min)
python scripts/download_csv.py     # Download CSV from data.go.kr
python scripts/build_db.py          # Build SQLite + R-tree

# Option 2: Test with synthetic data (960 rows, instant)
python scripts/build_db.py --test
```

### Run

```bash
# Streamable HTTP (for AI agents)
python server.py --transport streamable-http --port 8102

# stdio (for local Claude Code)
python server.py --transport stdio

# With test DB
SANGKWON_DB_PATH=data/sangkwon_test.db python server.py --port 8102
```

### Deploy (systemd)

```bash
cp luxon-sangkwon-mcp.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now luxon-sangkwon-mcp
curl http://127.0.0.1:8102/mcp  # Health check
```

### Claude Code MCP Config

Add to your MCP settings:

```json
{
  "mcpServers": {
    "sangkwon": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8102/mcp"
    }
  }
}
```

## Project Structure

```
luxon-sangkwon-mcp/
├── server.py                    # Entry point (FastMCP 3.x)
├── requirements.txt             # Dependencies (minimal: no ML, no scipy)
├── .env.template                # API key template
│
├── mcp_servers/
│   ├── core/                    # Infrastructure (nexus-finance pattern)
│   │   ├── base_server.py       #   BaseMCPServer ABC
│   │   ├── cache_manager.py     #   4-tier cache (LRU→TTL→Disk)
│   │   ├── rate_limiter.py      #   Token bucket rate limiter
│   │   └── responses.py         #   success_response / error_response
│   ├── adapters/
│   │   ├── kakao_geocode_adapter.py   # Kakao Local API
│   │   └── sangkwon_db_adapter.py     # SQLite + R-tree engine
│   ├── gateway/
│   │   └── gateway_server.py    # Mount 4 servers into 1
│   └── servers/
│       ├── sangkwon_server.py   # analyze, compare, nearby_similar
│       ├── maps_server.py       # geocode, reverse_geocode, poi_search
│       ├── density_server.py    # density_map
│       └── status_server.py     # maps_status
│
├── utils/
│   ├── geo_utils.py             # Haversine, bounding box, grid
│   └── category_codes.py        # 업종코드 매핑 (~50 Korean aliases)
│
├── scripts/
│   ├── download_csv.py          # CSV download from data.go.kr
│   └── build_db.py              # CSV → SQLite + R-tree builder
│
└── data/                        # SQLite DB (gitignored)
```

## Tech Stack

- **MCP Framework**: FastMCP 3.x (streamable-http)
- **Database**: SQLite + R-tree (built-in module, zero extra deps)
- **Geocoding**: Kakao Local API (free, 300K calls/day)
- **Data**: 소상공인시장진흥공단 상가정보 (public, free, quarterly)
- **Caching**: 4-tier (LRU → TTL → DiskCache)
- **Pattern**: nexus-finance-mcp architecture (BaseMCPServer + Adapter + Gateway)

## Data Sources

| Source | Records | Coverage | Cost |
|--------|---------|----------|------|
| [소상공인 상가정보](https://www.data.go.kr/data/15083033/fileData.do) | ~250만 | 전국 | Free |
| [Kakao Local API](https://developers.kakao.com/docs/latest/ko/local/dev-guide) | Realtime | 전국 | Free |

## Roadmap

- [x] **Phase 1** (MVP): 8 tools, SQLite+R-tree, Kakao geocoding
- [ ] **Phase 2**: startup_score (AI 창업적합도), closure_risk, trend, report
- [ ] **Phase 3**: Web dashboard (Next.js + Kakao Map)
- [ ] **Phase 4**: SaaS (Kmong reports, Smithery, B2B API)

## Part of Luxon Maps Ecosystem

```
Luxon Sangkwon (this)     Luxon Guide (B2C 탐색)
    "창업해도 될까?"           "여기 가면 뭐 있어?"
         │                        │
         └──── luxon-geo-common ──┘
               (shared infra, Phase 3)
```

---

*Built by [Luxon AI](https://github.com/luxon-ai) — 상권 데이터의 접근 비용을 0으로 만드는 인프라*
