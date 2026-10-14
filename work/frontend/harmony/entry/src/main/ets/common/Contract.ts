/**
 * 数据契约 v2.0 的 TypeScript 形状（docs/数据契约.md §二 routes / §四 vehicles）。
 * 字段名逐字对照契约，不改契约、不加字段。本单（#88）只用工程内 fixture 填充。
 */

/** routes.json 顶层信封（契约 §二） */
export interface RouteRecommend {
  request_id: string;
  session_id: string;
  driver_type: string;
  parking_mode: string;
  location: LocateResult;
  arrival_route: ArrivalRoute;
  departure_route: DepartureRoute;
  pickup_route: string | null;
  alternatives: Alternative[];
  reservation: Reservation;
  reroute: Reroute;
  factors_note: string | null;
  why: string;
  quota: QuotaItem[];
  is_simulated: boolean;
}

export interface LocateResult {
  segment_id: string;
  offset_m: number;
  match_confidence: number;
  source: string;
}

export interface ArrivalRoute {
  path_id: string;
  segments: string[];
  eta_min: number;
  dropoff_point: string;
  walk_min: number;
}

export interface DepartureRoute {
  path_id: string;
  segments: string[];
  eta_min: number;
}

export interface Alternative {
  path_id: string;
  eta_min: number;
  reason: string;
}

export interface Reservation {
  slots_reserved: number;
  lease_expire_s: number;
  harm_check: HarmCheck;
}

export interface HarmCheck {
  max_eta_increase_s: number;
  max_slot_x: number;
  passed: boolean;
}

export interface Reroute {
  count: number;
  reason: string | null;
}

/** quota v2.0 语义 = 各候选路径的「剩余可预约量」（契约 §2.1），数组表达避免把 id 当对象键 */
export interface QuotaItem {
  path_id: string;
  remaining: number;
}

/** vehicles.json 顶层信封（契约 §四） */
export interface VehiclesSnapshot {
  ts: string;
  is_simulated: boolean;
  vehicles: Vehicle[];
}

export interface Vehicle {
  vehicle_id: string;
  driver_type: string;
  segment_id: string;
  offset_m: number;
  lon: number;
  lat: number;
  state: string;
  guided: boolean;
  is_demo_bound: boolean;
}

/** 我的行程：一期本地会话记录（非契约字段，工程内展示口径） */
export interface TripRecord {
  session_id: string;
  time_label: string;
  path_id: string;
  adopted: boolean;
  note: string;
}
