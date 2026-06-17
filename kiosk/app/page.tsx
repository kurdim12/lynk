"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AttractLoop } from "@/components/AttractLoop";
import { AvatarStage } from "@/components/AvatarStage";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DIR, Lang, STRINGS } from "@/lib/i18n";
import { connectKiosk, KioskConnection } from "@/lib/webrtc";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const TENANT = process.env.NEXT_PUBLIC_TENANT ?? "lynk-and-co";
const LEAD_URL =
  process.env.NEXT_PUBLIC_LEAD_URL ?? `https://example.com/lead?ref=kiosk&tenant=${TENANT}`;

type Phase = "attract" | "connecting" | "live" | "error";

export default function Kiosk() {
  const [lang, setLang] = useState<Lang>("en");
  const [phase, setPhase] = useState<Phase>("attract");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const connRef = useRef<KioskConnection | null>(null);
  const t = STRINGS[lang];

  const teardown = useCallback(() => {
    connRef.current?.stop();
    connRef.current = null;
    setStream(null);
  }, []);

  const start = useCallback(async () => {
    setPhase("connecting");
    try {
      connRef.current = await connectKiosk({
        apiBase: API_BASE,
        tenant: TENANT,
        onRemoteStream: (s) => {
          setStream(s);
          setPhase("live");
        },
        onStateChange: (state) => {
          if (state === "failed" || state === "closed") setPhase("error");
        },
      });
    } catch {
      teardown();
      setPhase("error");
    }
  }, [teardown]);

  const end = useCallback(() => {
    teardown();
    setPhase("attract");
  }, [teardown]);

  // Stop media/peer connection if the component unmounts.
  useEffect(() => () => teardown(), [teardown]);

  return (
    <main className="kiosk" dir={DIR[lang]} data-lang={lang}>
      <div className="topbar">
        <LanguageToggle lang={lang} onChange={setLang} />
      </div>
      <div className="content">
        {phase === "attract" && <AttractLoop strings={t} onStart={start} />}
        {phase === "connecting" && <p className="status-center">{t.connecting}</p>}
        {phase === "live" && (
          <AvatarStage
            stream={stream}
            status={t.live}
            leadUrl={LEAD_URL}
            strings={t}
            onEnd={end}
          />
        )}
        {phase === "error" && (
          <p className="status-center error" role="button" onClick={start}>
            {t.error}
          </p>
        )}
      </div>
    </main>
  );
}
