"use client";

import { scoreColor } from "@/lib/format";

export default function CompetitionGauge({
  score,
  grade,
}: {
  score: number;
  grade: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle
            cx="50" cy="50" r="40"
            fill="none" stroke="#27272a" strokeWidth="8"
          />
          <circle
            cx="50" cy="50" r="40"
            fill="none"
            stroke={score >= 80 ? "#ef4444" : score >= 60 ? "#f97316" : score >= 40 ? "#eab308" : "#22c55e"}
            strokeWidth="8"
            strokeDasharray={`${score * 2.51} 251`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${scoreColor(score)}`}>
            {score}
          </span>
          <span className="text-xs text-zinc-500">/100</span>
        </div>
      </div>
      <span className="text-sm text-zinc-400">경쟁 강도: {grade}</span>
    </div>
  );
}
