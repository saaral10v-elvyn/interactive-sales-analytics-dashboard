/**
 * Wire types for the FastAPI contract.
 *
 * Every number that reaches the screen comes from these payloads; the domain
 * rules stay in Python. Shapes mirror `tests/golden/demo.json`.
 */

export type Granularity = "daily" | "weekly" | "monthly";

export type FilterField = "category" | "region" | "product" | "status";

export type DatePreset =
  | "all_time"
  | "last_7_days"
  | "last_30_days"
  | "last_90_days"
  | "this_month"
  | "this_year"
  | "custom";

export type DateFormatDecision = "auto" | "DMY" | "MDY";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface AppMeta {
  name: string;
  short_name: string;
  tagline: string;
  version: string;
}

export interface FieldGuide {
  column: string;
  requirement: string;
  description: string;
  example: string;
}

export interface PresetOption {
  key: DatePreset;
  label: string;
}

export interface MetaResponse {
  app: AppMeta;
  currency: { code: string; symbol: string };
  limits: {
    max_upload_mb: number;
    max_rows: number;
    large_dataset_rows: number;
  };
  uploads: {
    extensions: string[];
    encodings: string[];
    delimiters: string[];
  };
  fields: FieldGuide[];
  field_labels: Record<string, string>;
  field_order: string[];
  required_fields: string[];
  price_fields: string[];
  filters: {
    fields: FilterField[];
    default_preset: DatePreset;
    presets: PresetOption[];
  };
}

export interface MappingTableRow {
  Field: string;
  "Source column": string;
  Method: string;
  Confidence: string;
  Status: string;
}

export interface ColumnMapping {
  fields: Record<string, string>;
  confidence: Record<string, number>;
  methods: Record<string, string>;
  low_confidence_fields: string[];
  missing_required: string[];
  is_complete: boolean;
  requires_review: boolean;
  table: MappingTableRow[];
}

export interface DatasetProfile {
  row_count: number;
  column_count: number;
  missing_cells: number;
  duplicate_rows: number;
  date_min: string | null;
  date_max: string | null;
  net_revenue: number;
  order_count: number;
  product_count: number;
  region_count: number;
  category_count: number;
}

export type Row = Record<string, string | number | null>;

export interface DatasetSummary {
  filename: string;
  source: string;
  size_bytes: number;
  encoding: string;
  delimiter: string;
  row_count: number;
  column_count: number;
  columns: string[];
  dtypes: Record<string, string>;
  profile: DatasetProfile;
  mapping: ColumnMapping;
  preview: Row[];
  warnings: string[];
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  description: string;
  affected_rows: number;
  affected_label: string;
  example_text: string;
  examples: string[];
  action_taken: string;
}

export interface ValidationReport {
  rows_input: number;
  rows_output: number;
  rows_dropped: number;
  dropped_ratio: number;
  blocked: boolean;
  block_reason: string | null;
  date_format_used: string | null;
  should_warn_about_drops: boolean;
  issue_counts: { error: number; warning: number; info: number };
  issues: ValidationIssue[];
}

export interface CleaningSummary {
  rows: number;
  columns: string[];
  dtypes: Record<string, string>;
  revenue_source: string;
  order_id_available: boolean;
  date_format_used: string | null;
  returns_kept: number;
  report: ValidationReport;
  preview: Row[];
}

export interface SessionResponse {
  session_id: string;
  dataset: DatasetSummary;
  cleaned: CleaningSummary | null;
  mapping_override: Record<string, string>;
  revision: number;
}

export interface CleaningResponse {
  session_id: string;
  cleaned: CleaningSummary;
  date_format_used: string | null;
  revision: number;
}

export interface DateInspection {
  total_values: number;
  parseable_count: number;
  invalid_count: number;
  ambiguous_count: number;
  ambiguous_examples: string[];
  day_first_hint_count: number;
  month_first_hint_count: number;
  suggested_format: string | null;
}

export interface DateInspectionResponse {
  session_id: string;
  inspection: DateInspection | null;
}

export interface FilterState {
  start_date: string;
  end_date: string;
  preset: DatePreset;
  categories: string[];
  regions: string[];
  products: string[];
  statuses: string[];
}

export interface FilterRequest {
  start_date?: string | null;
  end_date?: string | null;
  preset?: DatePreset | null;
  categories?: string[];
  regions?: string[];
  products?: string[];
  statuses?: string[];
}

export interface ResolvedFilters {
  session_id: string;
  state: FilterState;
  summary: string;
  filtered_rows: number;
  total_rows: number;
}

export interface FiltersResponse extends ResolvedFilters {
  bounds: [string, string];
  options: Record<FilterField, string[]>;
  presets: Record<string, [string, string]>;
}

export interface PageContext {
  filters: FilterState;
  summary: string;
  filtered_rows: number;
  total_rows: number;
  current_period: [string, string];
  previous_period: [string, string];
  previous_rows: number;
  order_id_available: boolean;
}

export interface KpiValues {
  total_revenue: number;
  total_orders: number;
  average_order_value: number;
  total_units: number;
  total_products: number;
  rows: number;
}

export interface KpiComparison {
  key: string;
  current: number;
  previous: number;
  absolute_change: number;
  percent_change: number | null;
  previous_available: boolean;
}

export interface TrendPoint {
  period: string;
  revenue: number;
  orders: number;
  units: number;
}

export interface CategoryRevenue {
  category: string;
  revenue: number;
  units: number;
  share: number;
}

export interface TopProduct {
  product: string;
  revenue: number;
  units: number;
}

export interface Insight {
  kind: string;
  title: string;
  body: string;
}

export interface OverviewPayload {
  context: PageContext;
  kpis: {
    current: KpiValues;
    previous: KpiValues;
    comparisons: KpiComparison[];
  };
  trend: Record<Granularity, TrendPoint[]>;
  categories: CategoryRevenue[];
  top_products: TopProduct[];
  insights: Insight[];
  capabilities: {
    has_category: boolean;
    has_region: boolean;
    has_dates: boolean;
    order_id_available: boolean;
  };
}

export interface ProductPerformanceRow {
  product: string;
  revenue: number;
  units: number;
  orders: number;
  average_order_value: number;
  share: number | null;
}

export interface ParetoRow {
  rank: number;
  product: string;
  revenue: number;
  cumulative_revenue: number;
  cumulative_share: number;
}

export interface ParetoThreshold {
  rank: number;
  product: string;
  cumulative_share: number;
}

export interface ProductSnapshot {
  total_revenue: number;
  total_orders: number;
  total_units: number;
  average_order_value: number;
  rows: number;
}

export interface ProductDrilldown {
  product: string;
  snapshot: ProductSnapshot;
  trend: Record<Granularity, TrendPoint[]>;
}

export interface ProductsPayload {
  context: PageContext;
  performance: ProductPerformanceRow[];
  top_products: TopProduct[];
  pareto: ParetoRow[];
  threshold: ParetoThreshold | null;
  drilldown: ProductDrilldown | null;
  notes: {
    share_unavailable: boolean;
    pareto_unavailable: string | null;
  };
}

export interface RegionPerformanceRow {
  region: string;
  revenue: number;
  units: number;
  orders: number;
  average_order_value: number;
  share: number | null;
}

export interface RegionCategoryRow {
  region: string;
  category: string;
  revenue: number;
}

export interface RegionTrendPoint {
  period: string;
  region: string;
  revenue: number;
}

export interface RegionsPayload {
  context: PageContext;
  available: boolean;
  has_category: boolean;
  performance: RegionPerformanceRow[];
  category_mix: RegionCategoryRow[];
  trend: Record<Granularity, RegionTrendPoint[]>;
  blank_region_rows: number;
}

export interface ExplorerRequest extends FilterRequest {
  search?: string;
  limit?: number;
}

export interface ExplorerPayload {
  context: PageContext;
  columns: string[];
  search_term: string;
  filtered_rows: number;
  matching_rows: number;
  rows_shown: number;
  filtered_revenue: number;
  preview: Row[];
}

export type PageName = "overview" | "products" | "regions" | "explorer";

export type ExportKind = "cleaned" | "filtered" | "quality-report";
