"use client";

import { gradeColor, formatNumber } from "@/lib/format";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  grade?: string;
}

export default function AnalysisCard({ label, value, sub, grade }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white">
        {typeof value === "number" ? formatNumber(value) : value}
      </div>
      {grade && (
        <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${gradeColor(grade)}`}>
          {grade}
        </span>
      )}
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}
