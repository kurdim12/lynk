"use client";

import { useEffect, useRef } from "react";
import { Strings } from "@/lib/i18n";
import { LeadQR } from "@/components/LeadQR";

/** The live session view: avatar video + audio, status, lead QR, and End. */
export function AvatarStage({
  stream,
  status,
  leadUrl,
  strings,
  onEnd,
}: {
  stream: MediaStream | null;
  status: string;
  leadUrl: string;
  strings: Strings;
  onEnd: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <div className="stage">
      <video ref={videoRef} className="avatar-video" autoPlay playsInline />
      <div className="stage-status" aria-live="polite">
        {status}
      </div>
      <LeadQR url={leadUrl} label={strings.scan} />
      <button className="end-btn" onClick={onEnd}>
        {strings.end}
      </button>
    </div>
  );
}
