import { createContext, useContext, useEffect, useState } from "react";

export interface Read<T> {
  value: T | null;
  isLoading: boolean;
  error: boolean;
}

export interface PreparedReads {
  readonly values: ReadonlyMap<string, unknown>;
  ask: (key: string, read: () => Promise<unknown>) => void;
}

export const PreparedReadsContext = createContext<PreparedReads | null>(null);

export function useRead<T>(read: () => Promise<T>, key: string, onError: (err: unknown) => void): Read<T> {
  const prepared = useContext(PreparedReadsContext);
  if (prepared && !prepared.values.has(key)) prepared.ask(key, read);
  const [state, setState] = useState<Read<T>>(() =>
    prepared?.values.has(key)
      // Justification (typed boundary): a prepared value is what this key's own read resolved to on the server.
      ? { value: prepared.values.get(key) as T, isLoading: false, error: false }
      : { value: null, isLoading: true, error: false });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, isLoading: true, error: false }));
    read().then(
      (value) => live && setState({ value, isLoading: false, error: false }),
      (err: unknown) => {
        onError(err);
        if (live) setState((s) => ({ ...s, isLoading: false, error: true }));
      },
    );
    return () => {
      live = false;
    };
  }, [key]);
  return state;
}
