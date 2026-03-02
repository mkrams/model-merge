/* ── Safety Traceability Graph Model ── */

// Item types in the graph
export type ItemType = 'hazard' | 'hazardous_event' | 'safety_goal' | 'fsr' | 'tsr' | 'verification';
export type VerificationMethod = 'test' | 'analysis' | 'review';
export type ItemStatus = 'gap' | 'draft' | 'review' | 'approved';
export type LinkType = 'hazard_to_event' | 'event_to_goal' | 'goal_to_fsr' | 'fsr_to_tsr' | 'tsr_to_verification' | 'fsr_to_verification';
export type Perspective = 'safety_engineer' | 'test_engineer' | 'req_engineer' | 'manager';

/**
 * Version history for audit trail
 */
export interface ItemVersion {
  version: number;
  text: string;
  author: string;
  timestamp: string;
  fields: Record<string, string>;
}

/**
 * Extensible attributes for different item types
 */
export interface ItemAttributes {
  // Hazardous Event
  severity?: string;
  exposure?: string;
  controllability?: string;
  asil_level?: string;
  operating_situation?: string;

  // Safety Goal
  safe_state?: string;

  // FSR / TSR
  testable_criterion?: string;

  // TSR only
  allocated_to?: string;

  // Verification
  method?: VerificationMethod;
  steps?: string;
  expected_result?: string;
  pass_criteria?: string;

  // Allow custom fields
  [key: string]: any;
}

/**
 * A node in the traceability graph
 */
export interface SafetyItem {
  item_id: string;
  item_type: ItemType;
  name: string;
  description: string;
  status: ItemStatus;
  attributes: ItemAttributes;
  versions: ItemVersion[];
}

/**
 * A directed edge in the traceability graph
 */
export interface TraceLink {
  link_id: string;
  source_id: string;
  target_id: string;
  link_type: LinkType;
  rationale: string;
}

/**
 * Complete safety project with graph structure
 */
export interface SafetyProject {
  project_id: string;
  name: string;
  items: SafetyItem[];
  links: TraceLink[];
}

/**
 * Draft response from AI assistant
 */
export interface DraftResponse {
  name: string;
  text: string;
  rationale: string;
  steps?: string;
  expected_result?: string;
  pass_criteria?: string;
  safe_state?: string;
  testable_criterion?: string;
  operating_situation?: string;
  allocated_to?: string;
  method?: string;
}

/**
 * Coverage metrics for the traceability graph
 */
export interface CoverageMetrics {
  total_items: number;
  items_by_type: Record<string, { total: number; approved: number; draft: number; gap: number }>;
  total_links: number;
  fully_traced_chains: number;
  coverage_pct: number;
  gaps: GapInfo[];
}

/**
 * Information about gaps in the traceability graph
 */
export interface GapInfo {
  item_id: string;
  item_type: ItemType;
  gap_type: string;
  message: string;
}

/**
 * Tree representation of traceability from/to an item
 */
export interface TraceTree {
  item: SafetyItem;
  parents: TraceTree[];
  children: TraceTree[];
}

/**
 * Cell in a traceability matrix
 */
export interface MatrixCell {
  source_id: string;
  target_id: string;
  linked: boolean;
  link_id?: string;
}

/**
 * Traceability matrix between two item types
 */
export interface TraceMatrix {
  source_type: ItemType;
  target_type: ItemType;
  sources: SafetyItem[];
  targets: SafetyItem[];
  cells: MatrixCell[];
}

/**
 * Backward compatibility alias for migration
 */
export type ChainLevel = ItemType | 'asil_determination';
