export interface CategoryDistribution {
  name: string;
  count: number;
  pct: number;
}

export interface AnalysisResult {
  success: boolean;
  data: {
    center: { lat: number; lng: number };
    radius_m: number;
    total_stores: number;
    filtered_stores: number;
    category_filter: string | null;
    category_distribution: CategoryDistribution[];
    competition_score: number;
    competition_grade: string;
    density_per_km2: number;
    top_subcategories: { name: string; count: number }[];
    location_query: string;
    resolved_location: string;
    data_date: string;
  };
}

export interface ClosureResult {
  success: boolean;
  data: {
    total: number;
    active: number;
    closed: number;
    suspended: number;
    closure_rate_pct: number;
    risk_grade: string;
    city_average_closure_pct: number;
  };
}

export interface StartupScoreResult {
  success: boolean;
  data: {
    overall_score: number;
    grade: string;
    verdict: string;
    breakdown: Record<string, { score: number | null; weight: number }>;
    factors_available: number;
    factors_total: number;
    category: { code: string; name: string };
  };
}

export interface HotAreaItem {
  rank: number;
  name: string;
  lat: number;
  lng: number;
  total_stores: number;
  filtered_stores: number;
  competition_score: number;
  competition_grade: string;
  closure_rate_pct: number;
  risk_grade: string;
}

export interface HotAreasResult {
  success: boolean;
  data: {
    rankings: HotAreaItem[];
    category: { code: string; name: string };
    city_filter: string | null;
    total_candidates: number;
  };
}

export interface ReportResult {
  success: boolean;
  data: {
    markdown: string;
    summary: {
      location: string;
      category: string;
      total_stores: number;
      competition_score: number;
      closure_rate_pct: number;
      startup_score: number;
    };
  };
}
