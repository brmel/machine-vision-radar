import { type FC } from "react";
import type { MediaItem } from "../../../domain/views.ts";
import { DEFAULT_LANGUAGE, intlLocale } from "../../../domain/languages.ts";
import { Section, localized, localizedLang } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

const KILOBYTE = 1024;

export const ProductMedia: FC<{ media: readonly MediaItem[] }> = ({ media }) => {
  const { t, locale } = useI18n();
  if (media.length === 0) return null;
  const groups = [...new Map(media.map((m) => [m.kind.id, m.kind])).values()];
  const size = (bytes: number) => {
    const small = bytes < KILOBYTE;
    return new Intl.NumberFormat(intlLocale(locale), { style: "unit", unit: small ? "byte" : "kilobyte",
      unitDisplay: small ? "long" : "short", maximumFractionDigits: 0 }).format(small ? bytes : bytes / KILOBYTE);
  };
  const format = (mime: string) => {
    const [type, subtype] = mime.split("/");
    return (subtype === "plain" ? type : subtype).toUpperCase();
  };
  return (
    <Section title={t("mediaTitle")} className="media">
      {groups.map((kind) => (
        <div key={kind.id} className="space-y-1">
          <h3 className="text-caption font-heading text-fg-secondary">{localized(kind.label, locale)}</h3>
          <ul className="space-y-0.5">
            {media.filter((m) => m.kind.id === kind.id).map((m) => {
              const name = m.title ? localized(m.title, locale) : localized(m.kind.label, locale);
              return (
                <li key={m.id} className="flex flex-wrap items-center gap-2 text-caption text-fg-secondary">
                  {m.href ? (
                    <a href={m.href} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 underline hover:text-fg">
                      <span lang={m.title && localizedLang(m.title, locale) !== locale ? DEFAULT_LANGUAGE.code
                        : undefined}>{name}</span>
                    </a>
                  ) : (
                    <span>{name}</span>
                  )}
                  {m.version && <span className="font-mono text-muted">({m.version})</span>}
                  <span className="text-muted">{format(m.mime)} · {size(m.bytes)}</span>
                  <span className="text-muted">{localized(m.rights.label, locale)}</span>
                  {m.source_url && m.href !== m.source_url && (
                    <a href={m.source_url} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 underline text-muted hover:text-fg">
                      <span>{t("mediaSource")}</span>
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </Section>
  );
};
