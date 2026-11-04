import { type FC, useEffect, useState } from "react";
import { SearchInput, prevented } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

interface CatalogSearchProps {
  value: string;
  onSearch: (words: string) => void;
}

export const CatalogSearch: FC<CatalogSearchProps> = ({ value, onSearch }) => {
  const { t } = useI18n();
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const clear = () => {
    setDraft("");
    if (value) onSearch("");
  };

  return (
    <form role="search" onSubmit={prevented(() => onSearch(draft.trim()))}>
      <SearchInput
        compact
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onClear={clear}
        placeholder={t("searchInputPlaceholder")}
        clearLabel={t("ariaClearInput")}
        className="sm:max-w-md"
      />
    </form>
  );
};
