/**
 * Number formatting utilities for Korean display.
 */

export function formatNumber(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}천`;
  return n.toLocaleString();
}

export function scoreColor(score: number): string {
  if (score >= 80) return "text-green-400";
  if (score >= 60) return "text-blue-400";
  if (score >= 40) return "text-yellow-400";
  if (score >= 20) return "text-orange-400";
  return "text-red-400";
}

export function gradeColor(grade: string): string {
  const map: Record<string, string> = {
    "매우적합": "bg-green-500/20 text-green-400",
    "적합": "bg-blue-500/20 text-blue-400",
    "보통": "bg-yellow-500/20 text-yellow-400",
    "부적합": "bg-orange-500/20 text-orange-400",
    "매우부적합": "bg-red-500/20 text-red-400",
    "안정": "bg-green-500/20 text-green-400",
    "주의": "bg-orange-500/20 text-orange-400",
    "위험": "bg-red-500/20 text-red-400",
    "거의 없음": "bg-green-500/20 text-green-400",
    "낮음": "bg-blue-500/20 text-blue-400",
    "높음": "bg-orange-500/20 text-orange-400",
    "과포화": "bg-red-500/20 text-red-400",
  };
  return map[grade] || "bg-gray-500/20 text-gray-400";
}
