export interface UserOut {
  id: string;
  email: string;
  full_name: string;
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

export interface ProductBrief {
  id: string;
  name: string;
  base_quantity: number;
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
  lines: OrderLineOut[];
}

export interface OrderLineHistoryOut {
  id: string;
  order_line_id: string;
  actor_id: string | null;
  actor_name: string | null;
  event_type: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  note: string | null;
  created_at: string;
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
