import { Routes, Route } from "react-router-dom";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { FileManager } from "./pages/FileManager";
import { IngredientEditor } from "./pages/IngredientEditor";
import { ProductEditor } from "./pages/ProductEditor";
import { EventEditor } from "./pages/EventEditor";
import { RolesPermissions } from "./pages/RolesPermissions";
import { Users } from "./pages/Users";
import { UploadOrder } from "./pages/UploadOrder";
import { CurrentOrder } from "./pages/CurrentOrder";
import { ExecutionView } from "./pages/ExecutionView";
import { ExecutionQueue } from "./pages/ExecutionQueue";
import { ProtectedRoute } from "./auth/ProtectedRoute";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/files"
        element={
          <ProtectedRoute tabView="file_manager">
            <FileManager />
          </ProtectedRoute>
        }
      />
      <Route
        path="/files/:folderId"
        element={
          <ProtectedRoute tabView="file_manager">
            <FileManager />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ingredients/:ingredientId"
        element={
          <ProtectedRoute tabView="file_manager">
            <IngredientEditor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/products/:productId"
        element={
          <ProtectedRoute tabView="file_manager">
            <ProductEditor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/events/:eventId"
        element={
          <ProtectedRoute tabView="file_manager">
            <EventEditor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/roles"
        element={
          <ProtectedRoute globalCode="admin.manage">
            <RolesPermissions />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute globalCode="admin.manage">
            <Users />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders/upload"
        element={
          <ProtectedRoute tabView="upload_order">
            <UploadOrder />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders/current"
        element={
          <ProtectedRoute tabView="current_order">
            <CurrentOrder />
          </ProtectedRoute>
        }
      />
      <Route
        path="/execution"
        element={
          <ProtectedRoute tabView="execution_queue" globalCode="order.execute">
            <ExecutionQueue />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders/current/:orderLineId/execute"
        element={
          <ProtectedRoute globalCode="order.execute">
            <ExecutionView />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
