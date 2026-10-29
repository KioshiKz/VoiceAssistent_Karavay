export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  voice_assistant_enabled: boolean;
}

export interface TabPermission {
  view: boolean;
  edit: boolean;
}

export interface MePermissions {
  tabs: Record<string, TabPermission>;
  global: Record<string, boolean>;
  system_role: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserOut;
}

export interface AppTab {
  id: string;
  key: string;
  label: string;
  order_index: number;
}

export interface PermissionDef {
  code: string;
  label: string;
  scope_type: "tab" | "folder" | "global";
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  order_visibility_ahead: number | null;
}

export interface RolePermissionEntry {
  permission_code: string;
  tab_id?: string | null;
  folder_id?: string | null;
  granted: boolean;
}

export interface RolePermissionOut extends RolePermissionEntry {
  id: string;
}

export interface UserListOut {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  voice_assistant_enabled: boolean;
  role_names: string[];
}

export interface FolderOut {
  id: string;
  name: string;
  parent_id: string | null;
}

export interface BreadcrumbOut {
  id: string;
  name: string;
}

export interface FolderPermissions {
  view: boolean;
  create: boolean;
  edit: boolean;
}

export interface IngredientBrief {
  id: string;
  name: string;
  measure_type: MeasureType;
  is_active: boolean;
}

// Recipe output and order quantities: whole pieces or (possibly fractional) kilograms.
export type YieldUnit = "pcs" | "kg";

export interface ProductBrief {
  id: string;
  name: string;
  base_quantity: number;
  yield_unit: YieldUnit;
  is_active: boolean;
}

export interface EventBrief {
  id: string;
  name: string;
  event_type: EventType;
  is_active: boolean;
}

export interface FolderContentOut {
  folder: FolderOut;
  breadcrumbs: BreadcrumbOut[];
  permissions: FolderPermissions;
  subfolders: FolderOut[];
  ingredients: IngredientBrief[];
  products: ProductBrief[];
  events: EventBrief[];
}

export type MeasureType = "weight" | "volume" | "time" | "temperature" | "count";
export type EventType = "timer" | "weight_check" | "phrase_confirmation";

export interface WeightStatusOut {
  step_index: number;
  port: string | null;
  connected: boolean;
  weight_g: number | null;
  target_weight_g: number;
  tolerance_g: number;
  tolerance_below_g: number;
  tolerance_above_g: number;
  minimum_weight_g: number;
  maximum_weight_g: number;
  minimum_allowed_weight_g: number;
  minimum_weight_blocked: boolean;
  in_range: boolean;
  stable: boolean;
  held_seconds: number;
  required_seconds: number;
  ready: boolean;
  message: string;
}

export interface IngredientOut {
  id: string;
  folder_id: string;
  name: string;
  measure_type: MeasureType;
  description: string | null;
  allowed_container_weights_g: number[] | null;
  is_active: boolean;
}

export interface UsedInProductOut {
  product_id: string;
  product_name: string;
  folder_path: string;
}

export interface EventTemplateOut {
  id: string;
  folder_id: string;
  name: string;
  description: string | null;
  event_type: EventType;
  default_params: Record<string, unknown> | null;
  is_active: boolean;
}

export interface IngredientRef {
  id: string;
  name: string;
  measure_type: MeasureType;
}

export interface EventTemplateRef {
  id: string;
  name: string;
  event_type: EventType;
}

export interface RecipeStepOut {
  id: string;
  product_id: string;
  order_index: number;
  step_type: "ingredient" | "event" | "ingredient_event";
  ingredient: IngredientRef | null;
  quantity_canonical: number | null;
  quantity_display: string | null;
  event_template: EventTemplateRef | null;
  event_params: Record<string, unknown> | null;
}

export interface ProductOut {
  id: string;
  folder_id: string;
  name: string;
  base_quantity: number;
  yield_unit: YieldUnit;
  is_active: boolean;
}

export interface ProductDetailOut extends ProductOut {
  steps: RecipeStepOut[];
}

export interface OrderLineOut {
  id: string;
  order_id: string;
  product_name_raw: string;
  quantity: number;
  /** Matched product's unit; null while the line is unmatched. */
  unit: YieldUnit | null;
  due_time: string;
  match_status: "matched" | "unmatched";
  matched_product_id: string | null;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  cancellation_reason: string | null;
  cancelled_by: string | null;
  cancelled_by_name: string | null;
  cancelled_at: string | null;
  last_advanced_by: string | null;
  last_advanced_by_name: string | null;
  last_advanced_at: string | null;
  workshop_folder_id: string | null;
  workshop_folder_name: string | null;
  execution_plan_status: string | null;
  current_step_index: number | null;
  total_steps: number;
  current_step_name: string | null;
  is_emergency: boolean;
  emergency_action: "add" | "replace" | "remove" | null;
  emergency_source_line_id: string | null;
  emergency_schedule_id: string | null;
}

export interface OrderUploadOut {
  order_id: string;
  total_lines: number;
  matched: number;
  unmatched: number;
  lines: OrderLineOut[];
}

export interface CurrentOrderOut {
  order_id: string;
  execution_date: string;
  workshop_folder_id: string | null;
  workshop_folder_name: string | null;
  selection_mode: "automatic" | "manual";
  selected_at: string | null;
  selected_by_name: string | null;
  emergency_schedule_id: string | null;
  lines: OrderLineOut[];
}

export type OrderStatus = "pending" | "in_progress" | "completed";

export interface OrderDetailOut {
  order_id: string;
  execution_date: string;
  source_filename: string | null;
  uploaded_at: string;
  uploaded_by_name: string | null;
  workshop_folder_id: string | null;
  workshop_folder_name: string | null;
  force_completed_at: string | null;
  force_completed_by: string | null;
  force_completed_by_name: string | null;
  status: OrderStatus;
  emergency_schedule_id: string | null;
  lines: OrderLineOut[];
}

export interface OrderLineHistoryOut {
  id: string;
  order_line_id: string | null;
  actor_id: string | null;
  actor_name: string | null;
  event_type: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  note: string | null;
  created_at: string;
}

export interface OrderLineHistoryEntryOut extends OrderLineHistoryOut {
  order_id: string | null;
  product_name_raw: string | null;
  execution_date: string | null;
}

export interface OrderSummaryOut {
  id: string;
  execution_date: string;
  source_filename: string | null;
  uploaded_at: string;
  uploaded_by_name: string | null;
  workshop_folder_id: string | null;
  workshop_folder_name: string | null;
  total_lines: number;
  active_lines: number;
  status: OrderStatus;
}

export interface EmergencySourceLineOut {
  id: string;
  product_name_raw: string;
  quantity: number;
  unit: YieldUnit | null;
  due_time: string;
  matched_product_id: string | null;
  match_status: string;
  status: OrderLineOut["status"];
  overlaid_by_item_id: string | null;
  overlay_action: "replace" | "remove" | null;
}

export interface EmergencyItemOut {
  id: string;
  action: "add" | "replace" | "remove";
  source_line_id: string | null;
  product_name_raw: string;
  quantity: number;
  unit: YieldUnit | null;
  due_time: string;
  matched_product_id: string | null;
  match_status: string;
  status: OrderLineOut["status"];
  active: boolean;
}

export interface EmergencyScheduleOut {
  id: string;
  order_id: string;
  reason: string;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
  source_lines: EmergencySourceLineOut[];
  items: EmergencyItemOut[];
}

export interface StatisticsSummary {
  orders: number;
  positions: number;
  pending: number;
  in_progress: number;
  completed: number;
  cancelled: number;
  emergency_schedules: number;
  emergency_changes: number;
}

export interface ProductStatistics {
  product_name: string;
  unit: YieldUnit | null;
  positions: number;
  total_quantity: number;
  completed: number;
  cancelled: number;
  emergency_positions: number;
}

export interface AuditLogOut {
  id: string;
  source: "order" | "emergency";
  order_id: string | null;
  order_line_id: string | null;
  emergency_schedule_id: string | null;
  product_name_raw: string | null;
  execution_date: string | null;
  actor_id: string | null;
  actor_name: string | null;
  event_type: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  note: string | null;
  created_at: string;
}

export interface StatisticsOut {
  summary: StatisticsSummary;
  products: ProductStatistics[];
  logs: AuditLogOut[];
  logs_total: number;
}

export interface ExecutionPlanStepOut {
  order_index: number;
  step_type: "ingredient" | "event" | "ingredient_event";
  ingredient_name_snapshot: string | null;
  measure_type_snapshot: MeasureType | null;
  quantity_canonical_computed: number | null;
  quantity_display: string | null;
  event_name_snapshot: string | null;
  event_type_snapshot: EventType | null;
  event_params_snapshot: Record<string, unknown> | null;
  status: "pending" | "done";
  completed_at: string | null;
}

export interface ExecutionPlanOut {
  id: string;
  order_line_id: string;
  product_id: string;
  multiplier: number;
  status: "not_started" | "in_progress" | "completed";
  current_step_index: number;
  total_steps: number;
  can_view_full_recipe: boolean;
  steps: ExecutionPlanStepOut[];
}

export interface VoiceEventOut {
  id: number;
  text: string;
  source: string;
  created_at: string;
}
