/** ICE servers for RTCPeerConnection (STUN only in task 113). */
export function getIceServers(): RTCIceServer[] {
  const url =
    import.meta.env.VITE_WEBRTC_STUN_URL ?? "stun:stun.l.google.com:19302";
  return [{ urls: url }];
}
