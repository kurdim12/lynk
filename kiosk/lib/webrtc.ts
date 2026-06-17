/**
 * WebRTC client for the kiosk ↔ Pipecat bot.
 *
 * Mirrors the server's SmallWebRTC signaling (server/app.py `/offer`): send one
 * SDP offer with ICE already gathered, receive the answer (with `pc_id`). We
 * send the mic up and receive the avatar's audio + video back.
 */

export interface KioskConnection {
  pc: RTCPeerConnection;
  stop: () => void;
}

export interface ConnectOptions {
  apiBase: string;
  tenant: string;
  onRemoteStream: (stream: MediaStream) => void;
  onStateChange?: (state: RTCPeerConnectionState) => void;
}

const ICE_SERVERS: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];

/** Resolve once ICE gathering is complete (non-trickle signaling), with a cap. */
function waitForIceGathering(pc: RTCPeerConnection, timeoutMs = 3000): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    const check = () => {
      if (pc.iceGatheringState === "complete") done();
    };
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(done, timeoutMs);
  });
}

export async function connectKiosk(opts: ConnectOptions): Promise<KioskConnection> {
  const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

  const mic = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  for (const track of mic.getTracks()) pc.addTrack(track, mic);
  // Receive the avatar's lip-synced video (audio comes back on the mic's transceiver).
  pc.addTransceiver("video", { direction: "recvonly" });

  const remote = new MediaStream();
  pc.ontrack = (event) => {
    remote.addTrack(event.track);
    opts.onRemoteStream(remote);
  };
  pc.onconnectionstatechange = () => opts.onStateChange?.(pc.connectionState);

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitForIceGathering(pc);

  const res = await fetch(`${opts.apiBase}/tenants/${opts.tenant}/offer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sdp: pc.localDescription?.sdp,
      type: pc.localDescription?.type,
    }),
  });
  if (!res.ok) {
    pc.close();
    throw new Error(`offer rejected (${res.status}): ${await res.text()}`);
  }

  const answer = await res.json();
  await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });

  const stop = () => {
    for (const track of mic.getTracks()) track.stop();
    pc.close();
  };
  return { pc, stop };
}
