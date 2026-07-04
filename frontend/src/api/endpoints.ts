import { apiClient } from "./client";
import type {
  AppTab,
  CurrentOrderOut,
  EventTemplateOut,
  ExecutionPlanOut,
  FolderContentOut,
  FolderOut,
  IngredientOut,
  MePermissions,
  OrderLineHistoryOut,
  OrderLineOut,
  OrderUploadOut,
  PermissionDef,
  ProductDetailOut,
  ProductOut,
  RecipeStepOut,
  Role,
  RolePermissionEntry,
  RolePermissionOut,
  TokenResponse,
  UsedInProductOut,
  VoiceEventOut,
  UserListOut,
  UserOut,
} from "./types";

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<TokenResponse>("/auth/login", { email, password }).then((r) => r.data),
  logout: () => apiClient.post("/auth/logout").then((r) => r.data),
  me: () => apiClient.get<UserOut>("/me").then((r) => r.data),
  mePermissions: () => apiClient.get<MePermissions>("/me/permissions").then((r) => r.data),
};

export const tabsApi = {
  list: () => apiClient.get<AppTab[]>("/tabs").then((r) => r.data),
};

export const voiceApi = {
  events: (after = 0) => apiClient.get<VoiceEventOut[]>("/voice/events", { params: { after } }).then((r) => r.data),
};

export const rolesApi = {
  list: () => apiClient.get<Role[]>("/roles").then((r) => r.data),
  create: (name: string, description?: string, orderVisibilityAhead?: number | null) =>
    apiClient
      .post<Role>("/roles", { name, description, order_visibility_ahead: orderVisibilityAhead })
      .then((r) => r.data),
  update: (id: string, payload: Partial<Pick<Role, "name" | "description" | "order_visibility_ahead">>) =>
    apiClient.patch<Role>(`/roles/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/roles/${id}`).then((r) => r.data),
  permissionDefs: () => apiClient.get<PermissionDef[]>("/permission-defs").then((r) => r.data),
  getPermissions: (roleId: string) =>
    apiClient.get<RolePermissionOut[]>(`/roles/${roleId}/permissions`).then((r) => r.data),
  replacePermissions: (roleId: string, entries: RolePermissionEntry[]) =>
    apiClient.put<RolePermissionOut[]>(`/roles/${roleId}/permissions`, { entries }).then((r) => r.data),
};

export const usersApi = {
  list: () => apiClient.get<UserListOut[]>("/users").then((r) => r.data),
  create: (payload: { email: string; password: string; full_name: string; is_active?: boolean }) =>
    apiClient.post<UserListOut>("/users", payload).then((r) => r.data),
  update: (id: string, payload: Partial<{ full_name: string; is_active: boolean; password: string }>) =>
    apiClient.patch<UserListOut>(`/users/${id}`, payload).then((r) => r.data),
  setRoles: (id: string, roleIds: string[]) =>
    apiClient.put<UserListOut>(`/users/${id}/roles`, { role_ids: roleIds }).then((r) => r.data),
};

export const foldersApi = {
  tree: () => apiClient.get<FolderOut[]>("/folders/tree").then((r) => r.data),
  content: (folderId: string) =>
    apiClient.get<FolderContentOut>(`/folders/${folderId}/content`).then((r) => r.data),
  create: (name: string, parentId: string | null) =>
    apiClient.post<FolderOut>("/folders", { name, parent_id: parentId }).then((r) => r.data),
  rename: (folderId: string, name: string) =>
    apiClient.patch<FolderOut>(`/folders/${folderId}/rename`, { name }).then((r) => r.data),
  move: (folderId: string, parentId: string | null) =>
    apiClient.patch<FolderOut>(`/folders/${folderId}/move`, { parent_id: parentId }).then((r) => r.data),
  remove: (folderId: string) => apiClient.delete(`/folders/${folderId}`).then((r) => r.data),
};

export const ingredientsApi = {
  listInFolder: (folderId: string) =>
    apiClient.get<IngredientOut[]>(`/folders/${folderId}/ingredients`).then((r) => r.data),
  create: (folderId: string, payload: Omit<IngredientOut, "id" | "folder_id">) =>
    apiClient.post<IngredientOut>(`/folders/${folderId}/ingredients`, payload).then((r) => r.data),
  get: (id: string) => apiClient.get<IngredientOut>(`/ingredients/${id}`).then((r) => r.data),
  update: (id: string, payload: Partial<Omit<IngredientOut, "id" | "folder_id">>) =>
    apiClient.patch<IngredientOut>(`/ingredients/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/ingredients/${id}`).then((r) => r.data),
  usedIn: (id: string) => apiClient.get<UsedInProductOut[]>(`/ingredients/${id}/used-in`).then((r) => r.data),
};

export const eventsApi = {
  listInFolder: (folderId: string) =>
    apiClient.get<EventTemplateOut[]>(`/folders/${folderId}/events`).then((r) => r.data),
  create: (folderId: string, payload: Omit<EventTemplateOut, "id" | "folder_id">) =>
    apiClient.post<EventTemplateOut>(`/folders/${folderId}/events`, payload).then((r) => r.data),
  get: (id: string) => apiClient.get<EventTemplateOut>(`/events/${id}`).then((r) => r.data),
  update: (id: string, payload: Partial<Omit<EventTemplateOut, "id" | "folder_id">>) =>
    apiClient.patch<EventTemplateOut>(`/events/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/events/${id}`).then((r) => r.data),
};

export const productsApi = {
  listInFolder: (folderId: string) =>
    apiClient.get<ProductOut[]>(`/folders/${folderId}/products`).then((r) => r.data),
  search: (q: string) => apiClient.get<ProductOut[]>("/products/search", { params: { q } }).then((r) => r.data),
  create: (folderId: string, payload: { name: string; base_quantity: number }) =>
    apiClient.post<ProductOut>(`/folders/${folderId}/products`, payload).then((r) => r.data),
  get: (id: string) => apiClient.get<ProductDetailOut>(`/products/${id}`).then((r) => r.data),
  update: (id: string, payload: Partial<{ name: string; base_quantity: number; is_active: boolean }>) =>
    apiClient.patch<ProductOut>(`/products/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/products/${id}`).then((r) => r.data),
  createStep: (
    productId: string,
    payload: {
      step_type: "ingredient" | "event" | "ingredient_event";
      order_index: number;
      ingredient_id?: string;
      quantity_canonical?: number;
      event_template_id?: string;
      event_params?: Record<string, unknown>;
    },
  ) => apiClient.post<RecipeStepOut>(`/products/${productId}/steps`, payload).then((r) => r.data),
  updateStep: (
    productId: string,
    stepId: string,
    payload: { quantity_canonical?: number; event_params?: Record<string, unknown> },
  ) => apiClient.patch<RecipeStepOut>(`/products/${productId}/steps/${stepId}`, payload).then((r) => r.data),
  deleteStep: (productId: string, stepId: string) =>
    apiClient.delete(`/products/${productId}/steps/${stepId}`).then((r) => r.data),
  reorderSteps: (productId: string, stepIds: string[]) =>
    apiClient
      .patch<RecipeStepOut[]>(`/products/${productId}/steps/reorder`, { step_ids: stepIds })
      .then((r) => r.data),
};

export const ordersApi = {
  upload: (file: File, executionDate: string, workshopFolderId?: string | null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("execution_date", executionDate);
    if (workshopFolderId) form.append("workshop_folder_id", workshopFolderId);
    return apiClient
      .post<OrderUploadOut>("/orders/upload", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  current: () => apiClient.get<CurrentOrderOut>("/orders/current").then((r) => r.data),
  match: (lineId: string, productId: string) =>
    apiClient.patch<OrderLineOut>(`/order-lines/${lineId}/match`, { product_id: productId }).then((r) => r.data),
  updateLine: (lineId: string, payload: Partial<{ quantity: number; due_time: string; matched_product_id: string | null }>) =>
    apiClient.patch<OrderLineOut>(`/order-lines/${lineId}`, payload).then((r) => r.data),
  cancelLine: (lineId: string, reason: string) =>
    apiClient.post<OrderLineOut>(`/order-lines/${lineId}/cancel`, { reason }).then((r) => r.data),
  history: (lineId: string) =>
    apiClient.get<OrderLineHistoryOut[]>(`/order-lines/${lineId}/history`).then((r) => r.data),
};

export const executionApi = {
  getOrCreate: (orderLineId: string) =>
    apiClient.get<ExecutionPlanOut>(`/order-lines/${orderLineId}/execution-plan`).then((r) => r.data),
  advance: (planId: string) =>
    apiClient.post<ExecutionPlanOut>(`/execution-plans/${planId}/advance`).then((r) => r.data),
  rewind: (planId: string) =>
    apiClient.post<ExecutionPlanOut>(`/execution-plans/${planId}/rewind`).then((r) => r.data),
};
