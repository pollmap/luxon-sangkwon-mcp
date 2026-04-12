import SearchBar from "@/components/layout/SearchBar";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] px-4">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-2">
          <span className="text-violet-400">상권</span> 인텔리전스
        </h1>
        <p className="text-zinc-500 text-lg">
          자연어로 물어보면 바로 답하는 AI 상권분석
        </p>
      </div>

      <SearchBar />

      <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-sm">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-violet-400">13</div>
          <div className="text-zinc-500">분석 도구</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-violet-400">250만</div>
          <div className="text-zinc-500">점포 데이터</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-violet-400">100</div>
          <div className="text-zinc-500">주요 상권</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-violet-400">0원</div>
          <div className="text-zinc-500">이용 비용</div>
        </div>
      </div>

      <div className="mt-8 text-zinc-600 text-xs">
        소상공인시장진흥공단 상가정보 + 카카오 지오코딩 기반
      </div>
    </div>
  );
}
