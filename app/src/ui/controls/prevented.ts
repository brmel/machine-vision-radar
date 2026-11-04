import type { SyntheticEvent } from "react";

export const prevented = (run: () => unknown) => (event: SyntheticEvent): void => {
  event.preventDefault();
  void run();
};
