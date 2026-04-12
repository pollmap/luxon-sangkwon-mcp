import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold text-white">
          Luxon <span className="text-violet-400">Sangkwon</span>
        </Link>
        <div className="flex gap-4 text-sm">
          <Link href="/analyze" className="text-zinc-400 hover:text-white transition-colors">
            분석
          </Link>
          <Link href="/compare" className="text-zinc-400 hover:text-white transition-colors">
            비교
          </Link>
          <Link href="/heatmap" className="text-zinc-400 hover:text-white transition-colors">
            히트맵
          </Link>
          <Link href="/report" className="text-zinc-400 hover:text-white transition-colors">
            리포트
          </Link>
        </div>
      </div>
    </nav>
  );
}
