import { create } from "zustand";

interface ShellState {
  // Mirror of the optional_outputs flag map plus required/conditional state.
  // True means "should be in the output set". The backend distinguishes
  // required (always true) and conditional (auto-resolved) — this store
  // only tracks the user-modifiable optional flags.
  selections: Record<string, boolean>;
  pendingChanges: { shell_id: string; action: "add" | "remove"; reason: string }[];
  setSelections: (sel: Record<string, boolean>) => void;
  toggle: (shellId: string) => void;
  setPendingChanges: (changes: ShellState["pendingChanges"]) => void;
  applyPending: () => void;
  clearPending: () => void;
}

export const useShellStore = create<ShellState>((set) => ({
  selections: {},
  pendingChanges: [],
  setSelections: (sel) => set({ selections: sel }),
  toggle: (id) =>
    set((s) => ({
      selections: { ...s.selections, [id]: !s.selections[id] },
    })),
  setPendingChanges: (changes) => set({ pendingChanges: changes }),
  applyPending: () =>
    set((s) => {
      const next = { ...s.selections };
      for (const c of s.pendingChanges) {
        next[c.shell_id] = c.action === "add";
      }
      return { selections: next, pendingChanges: [] };
    }),
  clearPending: () => set({ pendingChanges: [] }),
}));
