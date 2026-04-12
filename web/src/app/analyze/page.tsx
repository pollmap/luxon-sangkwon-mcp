"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { fetchAnalysis } from "@/lib/mcp-client";
import AnalysisCard from "@/components/analysis/AnalysisCard";
import CompetitionGauge from "@/components/charts/CompetitionGauge";
import CategoryPieChart from "@/components/charts/CategoryPieChart";
import SearchBar from "@/components/layout/SearchBar";

function AnalyzeContent() {
  const params = useSearchParams();
  const location = params.get("location") || "";
  const category = params.get("category") || "";
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [closure, setClosure] = useState<Record<string, unknown> | null>(null);
  const [startup, setStartup] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!location) return;
    setLoading(true);

    Promise.all([
      fetchAnalysis("analyze", { location, category: category || null, radius_m: 500 }),
      fetchAnalysis("closure", { location, category: category || null, radius_m: 500 }),
      fetchAnalysis("startup-score", { location, category: category || "카페" }),
    ]).then(([a, c, s]) => {
      setData(a);
      setClosure(c);
      setStartup(s);
      setLoading(false);
    });
  }, [location, category]);

  const d = (data as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
  const cl = (closure as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
  const st = (startup as Record<string, unknown>)?.data as Record<string, unknown> | undefined;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8 flex justify-center">
        <SearchBar />
      </div>

      {loading && (
        <div className="text-center py-20 text-zinc-500">
          <div className="animate-spin inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full mb-4" />
          <p>분석 중...</p>
        </div>
      )}

      {!loading && d && (
        <>
          <h2 className="text-xl font-bold mb-1">
            {d.resolved_location as string || location} 상권 분석
          </h2>
          <p className="text-zinc-500 text-sm mb-6">
            반경 {d.radius_m as number}m | {category || "전체 업종"}
          </p>

          {/* Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
            <AnalysisCard label="총 점포" value={d.total_stores as number} />
            <AnalysisCard
              label={category || "필터 점포"}
              value={d.filtered_stores as number}
            />
            <AnalysisCard
              label="경쟁 점수"
              value={`${d.competition_score}/100`}
              grade={d.competition_grade as string}
            />
            <AnalysisCard
              label="폐업률"
              value={cl ? `${cl.closure_rate_pct}%` : "-"}
              grade={cl?.risk_grade as string}
            />
            <AnalysisCard
              label="창업 적합도"
              value={st ? `${st.overall_score}/100` : "-"}
              grade={st?.grade as string}
            />
          </div>

          {/* Charts Row */}
          <div className="grid md:grid-cols-2 gap-6 mb-8">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-sm font-medium text-zinc-400 mb-4">업종 분포</h3>
              <CategoryPieChart data={d.category_distribution as { name: string; count: number; pct: number }[]} />
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex items-center justify-center">
              <CompetitionGauge
                score={d.competition_score as number}
                grade={d.competition_grade as string}
              />
            </div>
          </div>

          {/* Startup Score Breakdown */}
          {st && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
              <h3 className="text-sm font-medium text-zinc-400 mb-4">창업 적합도 상세</h3>
              <p className="text-zinc-300 mb-4">{st.verdict as string}</p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(st.breakdown as Record<string, { score: number | null; weight: number }>).map(
                  ([key, val]) => (
                    <div key={key} className="text-center">
                      <div className="text-xs text-zinc-500 mb-1">{key}</div>
                      <div className="text-lg font-bold text-white">
                        {val.score !== null ? Math.round(val.score) : "N/A"}
                      </div>
                      <div className="text-xs text-zinc-600">weight {val.weight}</div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Top Subcategories */}
          {(d.top_subcategories as { name: string; count: number }[])?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-sm font-medium text-zinc-400 mb-4">세부 업종 Top 10</h3>
              <div className="space-y-2">
                {(d.top_subcategories as { name: string; count: number }[]).map((sub, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs text-zinc-600 w-4">{i + 1}</span>
                    <div className="flex-1 bg-zinc-800 rounded-full h-6 overflow-hidden">
                      <div
                        className="bg-violet-600 h-full rounded-full flex items-center pl-3"
                        style={{
                          width: `${Math.max(
                            10,
                            (sub.count / (d.top_subcategories as { name: string; count: number }[])[0].count) * 100
                          )}%`,
                        }}
                      >
                        <span className="text-xs text-white whitespace-nowrap">
                          {sub.name}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm text-zinc-400 w-12 text-right">
                      {sub.count}개
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!loading && !location && (
        <div className="text-center py-20 text-zinc-500">
          위치를 입력하면 상권 분석 결과가 여기에 표시됩니다.
        </div>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-zinc-500">로딩 중...</div>}>
      <AnalyzeContent />
    </Suspense>
  );
}
