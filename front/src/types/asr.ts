/** ASR WebSocket message types (Front ↔ Back /api/asr/ws). */

export type AsrTrack = "local" | "remote";

export type AsrClientMessage =
  | {
      type: "asr.start";
      scene: "call";
      track: AsrTrack;
      call_id?: string;
    }
  | {
      type: "asr.stop";
      track?: AsrTrack;
    }
  | {
      type: "asr.track";
      track: AsrTrack;
    };

export type AsrServerMessage =
  | { type: "connected"; user_id: string }
  | {
      type: "asr.partial";
      track: AsrTrack;
      text: string;
      start_time?: number;
      end_time?: number;
    }
  | {
      type: "asr.final";
      track: AsrTrack;
      text: string;
      start_time?: number;
      end_time?: number;
    }
  | { type: "asr.error"; code: string; message: string }
  | { type: "asr.ended"; track: AsrTrack };

export function isAsrServerMessage(value: unknown): value is AsrServerMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    typeof (value as { type: unknown }).type === "string"
  );
}

export type AsrTranscriptLine = {
  track: AsrTrack;
  text: string;
  startTime?: number;
  endTime?: number;
  seq: number;
};

export type AsrSensitiveAlert = {
  id: string;
  word: string;
  text: string;
  track: AsrTrack;
  seq: number;
};
