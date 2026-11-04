import type { FC } from "react";
import { PageHeader } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useProblem } from "../../useLoad.tsx";
import { AskConsole } from "./AskConsole.tsx";
import { QueryConsole } from "./QueryConsole.tsx";

export const ConsoleView: FC = () => {
  const { t } = useI18n();
  const failure = useProblem("a console request");
  return (
    <section className="space-y-8 max-w-3xl">
      <PageHeader title={t("adminConsoleTitle")} />
      <QueryConsole onFail={failure.refuse} />
      <AskConsole onFail={failure.refuse} />
      {failure.alert}
    </section>
  );
};
