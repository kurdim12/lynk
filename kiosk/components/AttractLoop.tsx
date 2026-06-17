"use client";

import { Strings } from "@/lib/i18n";

/** The idle screen — a looping invitation to start a conversation. */
export function AttractLoop({ strings, onStart }: { strings: Strings; onStart: () => void }) {
  return (
    <button className="attract" onClick={onStart} aria-label={strings.tapToTalk}>
      <div className="attract-orb" aria-hidden />
      <h1 className="attract-title">{strings.attractTitle}</h1>
      <p className="attract-subtitle">{strings.subtitle}</p>
      <span className="attract-cta">{strings.tapToTalk}</span>
    </button>
  );
}
