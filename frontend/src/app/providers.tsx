"use client";

import { useState } from "react";
import { ThemeProvider } from "next-themes";
import { Provider } from "react-redux";

import { ClientErrorReporter } from "@/components/client-error-reporter";
import { OfflineBanner } from "@/components/offline-banner";
import { Toaster } from "@/components/ui/sonner";
import { makeStore } from "@/store";

export function Providers({ children }: { children: React.ReactNode }) {
  // Create the store once per client (stable across re-renders).
  const [store] = useState(makeStore);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <Provider store={store}>
        <OfflineBanner />
        {children}
        <ClientErrorReporter />
        {/* visibleToasts caps the stack; toastError() de-dupes identical messages. */}
        <Toaster richColors position="top-right" visibleToasts={3} />
      </Provider>
    </ThemeProvider>
  );
}
