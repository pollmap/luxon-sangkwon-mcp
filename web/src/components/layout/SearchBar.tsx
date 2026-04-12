"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SearchBar() {
  const [location, setLocation] = useState("");
  const [category, setCategory] = useState("카페");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!location.trim()) return;
    router.push(
      `/analyze?location=${encodeURIComponent(location)}&category=${encodeURIComponent(category)}`
    );
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 w-full max-w-2xl">
      <input
        type="text"
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder="위치 입력 (예: 강남역, 홍대입구)"
        className="flex-1 px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
      />
      <select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        className="px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-500"
      >
        <option value="카페">카페</option>
        <option value="치킨">치킨</option>
        <option value="한식">한식</option>
        <option value="분식">분식</option>
        <option value="편의점">편의점</option>
        <option value="미용실">미용실</option>
        <option value="헬스">헬스</option>
        <option value="">전체 업종</option>
      </select>
      <button
        type="submit"
        className="px-6 py-3 bg-violet-600 hover:bg-violet-500 rounded-lg text-white font-medium transition-colors"
      >
        분석
      </button>
    </form>
  );
}
