"use client";

import { Lang } from "@/lib/i18n";

export function LanguageToggle({
  lang,
  onChange,
}: {
  lang: Lang;
  onChange: (lang: Lang) => void;
}) {
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        className={lang === "en" ? "active" : ""}
        onClick={() => onChange("en")}
        aria-pressed={lang === "en"}
      >
        EN
      </button>
      <button
        className={lang === "ar" ? "active" : ""}
        onClick={() => onChange("ar")}
        aria-pressed={lang === "ar"}
      >
        العربية
      </button>
    </div>
  );
}
