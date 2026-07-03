import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App.tsx";
import { AuthProvider } from "./auth/AuthContext";
import { DialogProvider } from "./components/DialogProvider";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DialogProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </DialogProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
