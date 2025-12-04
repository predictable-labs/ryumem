"use client";

import { createContext, useContext, useRef, ReactNode } from "react";
import { MockMemoryStore } from "./mock-workflow";

interface MemoryStoreContextType {
  memoryStore: MockMemoryStore;
}

const MemoryStoreContext = createContext<MemoryStoreContextType | null>(null);

export function MemoryStoreProvider({ children }: { children: ReactNode }) {
  const memoryStore = useRef(new MockMemoryStore());

  return (
    <MemoryStoreContext.Provider value={{ memoryStore: memoryStore.current }}>
      {children}
    </MemoryStoreContext.Provider>
  );
}

export function useMemoryStore() {
  const context = useContext(MemoryStoreContext);
  if (!context) {
    throw new Error("useMemoryStore must be used within MemoryStoreProvider");
  }
  return context.memoryStore;
}
