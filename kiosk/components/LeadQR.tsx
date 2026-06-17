"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";

/** QR for lead capture — scan to get more info or book a test drive. */
export function LeadQR({ url, label }: { url: string; label: string }) {
  const [dataUrl, setDataUrl] = useState<string>("");

  useEffect(() => {
    let active = true;
    QRCode.toDataURL(url, { margin: 1, width: 160 })
      .then((d) => {
        if (active) setDataUrl(d);
      })
      .catch(() => setDataUrl(""));
    return () => {
      active = false;
    };
  }, [url]);

  if (!dataUrl) return null;
  return (
    <div className="lead-qr">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={dataUrl} alt="Lead capture QR code" width={120} height={120} />
      <span>{label}</span>
    </div>
  );
}
