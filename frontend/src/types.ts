export interface BusInput {
  id: string;
  channels: string;
}

export interface SentinelInput {
  id: string;
  cost: string;
  bus: string;
  readings: Record<string, string>; // modeId -> "" | "0" | "1"
}

export interface ValidationErrorItem {
  loc: string;
  msg: string;
}

export interface EvidenceItem {
  mode_a: string;
  mode_b: string;
  witness: string;
  reading_a: number;
  reading_b: number;
}

export interface IndistinguishablePair {
  mode_a: string;
  mode_b: string;
}

export interface BusUsage {
  bus: string;
  selected: string[];
  used: number;
  capacity: number;
}

export interface SolveResult {
  feasible: boolean;
  reason?: string;
  indistinguishable_pairs?: IndistinguishablePair[];
  selection?: string[];
  total_cost?: number;
  sentinel_count?: number;
  evidence?: EvidenceItem[];
  bus_usage?: BusUsage[];
  combinations_evaluated: number;
  total_combinations: number;
}

export interface SolveResponse {
  ok: boolean;
  result?: SolveResult;
  errors?: ValidationErrorItem[];
}

export interface FormState {
  modes: string[];
  buses: BusInput[];
  sentinels: SentinelInput[];
}
