"use client";

import { useState, Suspense } from "react";
import ReactMarkdown from "react-markdown";
import { fetchAnalysis } from "@/lib/mcp-client";

function ReportContent() {
  const [location, setLocation] = useState("강남역");
  const [category, setCategory] = useState("카페");
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const result = await fetchAnalysis("report", { location, category });
    const d = (result as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
    if (d?.markdown) {
      setMarkdown(d.markdown as string);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">종합 리포트</h1>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-8">
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
          className="px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white"
        >
          <option value="카페">카페</option>
          <option value="치킨">치킨</option>
          <option value="한식">한식</option>
          <option value="편의점">편의점</option>
        </select>
        <button type="submit" className="px-6 py-3 bg-violet-600 hover:bg-violet-500 rounded-lg text-white font-medium">
          생성
        </button>
      </form>

      {loading && (
        <div className="text-center py-20 text-zinc-500">
          <div className="animate-spin inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full mb-4" />
          <p>리포트 생성 중...</p>
        </div>
      )}

      {!loading && markdown && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">
          <div className="prose prose-invert prose-sm max-w-none
            prose-headings:text-white prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
            prose-p:text-zinc-300 prose-strong:text-white
            prose-table:text-sm prose-th:text-zinc-400 prose-td:text-zinc-300
            prose-th:border-zinc-700 prose-td:border-zinc-800
            prose-hr:border-zinc-800
            prose-li:text-zinc-300
          ">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-zinc-500">로딩 중...</div>}>
      <ReportContent />
    </Suspense>
  );
}
