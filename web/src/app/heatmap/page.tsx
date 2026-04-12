"use client";

import { useState, Suspense } from "react";
import { fetchAnalysis } from "@/lib/mcp-client";

function HeatmapContent() {
  const [location, setLocation] = useState("강남역");
  const [category, setCategory] = useState("카페");
  const [radiusM, setRadiusM] = useState(1000);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const result = await fetchAnalysis("density", {
      location,
      category: category || null,
      radius_m: radiusM,
      cell_size_m: 100,
    });
    setData(result);
    setLoading(false);
  };

  const d = (data as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
  const cells = d?.cells as { lat: number; lng: number; store_count: number; row: number; col: number }[] | undefined;
  const maxDensity = (d?.max_density as number) || 1;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">밀도 히트맵</h1>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
        <input
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="위치 (예: 강남역)"
          className="flex-1 px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
        >
          <option value="카페">카페</option>
          <option value="치킨">치킨</option>
          <option value="한식">한식</option>
          <option value="">전체</option>
        </select>
        <select
          value={radiusM}
          onChange={(e) => setRadiusM(Number(e.target.value))}
          className="px-3 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
        >
          <option value={500}>500m</option>
          <option value={1000}>1km</option>
          <option value={2000}>2km</option>
        </select>
        <button type="submit" className="px-6 py-3 bg-violet-600 hover:bg-violet-500 rounded-lg text-white font-medium">
          생성
        </button>
      </form>

      {loading && (
        <div className="text-center py-20 text-zinc-500">
          <div className="animate-spin inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full mb-4" />
          <p>밀도 계산 중...</p>
        </div>
      )}

      {!loading && cells && (
        <>
          <div className="mb-4 flex gap-4 text-sm text-zinc-400">
            <span>총 {d?.total_stores as number}개 점포</span>
            <span>|</span>
            <span>{d?.total_cells as number}개 셀</span>
            <span>|</span>
            <span>최대 밀도: {maxDensity}개/셀</span>
          </div>

          {/* Grid heatmap visualization */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 overflow-auto">
            <div
              className="inline-grid gap-px"
              style={{
                gridTemplateColumns: `repeat(${Math.max(...cells.map((c) => c.col)) - Math.min(...cells.map((c) => c.col)) + 1}, 1fr)`,
              }}
            >
              {cells
                .sort((a, b) => a.row - b.row || a.col - b.col)
                .map((cell, i) => {
                  const intensity = cell.store_count / maxDensity;
                  const bg =
                    intensity === 0
                      ? "bg-zinc-800"
                      : intensity < 0.25
                        ? "bg-green-900"
                        : intensity < 0.5
                          ? "bg-yellow-900"
                          : intensity < 0.75
                            ? "bg-orange-900"
                            : "bg-red-900";
                  return (
                    <div
                      key={i}
                      className={`w-6 h-6 ${bg} rounded-sm flex items-center justify-center`}
                      title={`(${cell.lat.toFixed(4)}, ${cell.lng.toFixed(4)}) — ${cell.store_count}개`}
                    >
                      {cell.store_count > 0 && (
                        <span className="text-[8px] text-white/70">{cell.store_count}</span>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>

          <div className="mt-4 flex gap-2 items-center text-xs text-zinc-500">
            <span>밀도:</span>
            <div className="w-4 h-4 bg-zinc-800 rounded-sm" /> 0
            <div className="w-4 h-4 bg-green-900 rounded-sm" /> 낮음
            <div className="w-4 h-4 bg-yellow-900 rounded-sm" /> 중간
            <div className="w-4 h-4 bg-orange-900 rounded-sm" /> 높음
            <div className="w-4 h-4 bg-red-900 rounded-sm" /> 매우 높음
          </div>
        </>
      )}
    </div>
  );
}

export default function HeatmapPage() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-zinc-500">로딩 중...</div>}>
      <HeatmapContent />
    </Suspense>
  );
}
