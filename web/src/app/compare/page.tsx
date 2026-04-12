"use client";

import { useState, Suspense } from "react";
import { fetchAnalysis } from "@/lib/mcp-client";
import AnalysisCard from "@/components/analysis/AnalysisCard";

function CompareContent() {
  const [locations, setLocations] = useState("강남역;홍대입구;합정역");
  const [category, setCategory] = useState("카페");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!locations.trim()) return;
    setLoading(true);
    const result = await fetchAnalysis("compare", { locations, category });
    setData(result);
    setLoading(false);
  };

  const d = (data as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
  const locs = d?.locations as Record<string, unknown>[] | undefined;
  const best = d?.best_for_entry as Record<string, unknown> | undefined;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">지역 비교</h1>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-8">
        <input
          type="text"
          value={locations}
          onChange={(e) => setLocations(e.target.value)}
          placeholder="지역명을 세미콜론(;)으로 구분 (예: 강남역;홍대;합정)"
          className="flex-1 px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
        >
          <option value="카페">카페</option>
          <option value="치킨">치킨</option>
          <option value="한식">한식</option>
          <option value="편의점">편의점</option>
        </select>
        <button type="submit" className="px-6 py-3 bg-violet-600 hover:bg-violet-500 rounded-lg text-white font-medium">
          비교
        </button>
      </form>

      {loading && (
        <div className="text-center py-20 text-zinc-500">
          <div className="animate-spin inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full mb-4" />
          <p>비교 분석 중...</p>
        </div>
      )}

      {!loading && locs && (
        <>
          {best && (
            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 mb-6">
              <span className="text-green-400 font-medium">
                추천: #{(best.index as number) + 1}번 지역 (경쟁 점수 {best.competition_score as number})
              </span>
              <span className="text-zinc-400 ml-2">— {best.reason as string}</span>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-3 px-4 text-zinc-500">항목</th>
                  {locs.map((loc, i) => (
                    <th key={i} className="text-center py-3 px-4 text-white">
                      {(loc.center as Record<string, number>)?.lat
                        ? `#${i + 1}`
                        : `지역 ${i + 1}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { key: "total_stores", label: "총 점포" },
                  { key: "filtered_stores", label: `${category} 점포` },
                  { key: "competition_score", label: "경쟁 점수" },
                  { key: "competition_grade", label: "경쟁 등급" },
                  { key: "density_per_km2", label: "km당 밀도" },
                ].map((row) => (
                  <tr key={row.key} className="border-b border-zinc-800/50">
                    <td className="py-3 px-4 text-zinc-400">{row.label}</td>
                    {locs.map((loc, i) => {
                      const val = loc[row.key];
                      const isBest = best && i === (best.index as number);
                      return (
                        <td
                          key={i}
                          className={`text-center py-3 px-4 ${isBest ? "text-green-400 font-medium" : "text-white"}`}
                        >
                          {typeof val === "number" ? val.toLocaleString() : String(val ?? "-")}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-zinc-500">로딩 중...</div>}>
      <CompareContent />
    </Suspense>
  );
}
