"use client";

import { useState } from "react";
import { Provider } from "react-redux";

import { Toaster } from "@/components/ui/sonner";
import { makeStore } from "@/store";

export function Providers({ children }: { children: React.ReactNode }) {
  // Create the store once per client (stable across re-renders).
  const [store] = useState(makeStore);

  return (
    <Provider store={store}>
      {children}
      <Toaster richColors position="top-right" />
    </Provider>
  );
}
