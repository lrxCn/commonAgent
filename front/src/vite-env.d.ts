/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CALL_WS_PATH?: string;
  readonly VITE_WEBRTC_STUN_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
