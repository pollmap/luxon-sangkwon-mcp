"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { CategoryDistribution } from "@/types/analysis";

const COLORS = [
  "#8b5cf6", "#6366f1", "#3b82f6", "#06b6d4", "#14b8a6",
  "#22c55e", "#eab308", "#f97316", "#ef4444", "#ec4899",
];

export default function CategoryPieChart({
  data,
}: {
  data: CategoryDistribution[];
}) {
  const top = data.slice(0, 8);
  const others = data.slice(8);
  const othersTotal = others.reduce((s, d) => s + d.count, 0);

  const chartData = [
    ...top,
    ...(othersTotal > 0 ? [{ name: "기타", count: othersTotal, pct: 0 }] : []),
  ];

  return (
    <div className="w-full h-64">
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="count"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={80}
            label={false}
            labelLine={false}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: "8px" }}
            labelStyle={{ color: "#fff" }}
            formatter={(value) => [`${value}개`]}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
