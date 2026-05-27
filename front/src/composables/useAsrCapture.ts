import type { AsrTrack } from "@/types/asr";

const TARGET_SAMPLE_RATE = 16_000;
const CHUNK_MS = 200;
const CHUNK_SAMPLES = (TARGET_SAMPLE_RATE * CHUNK_MS) / 1000;

export type AsrCaptureHandle = {
  stop: () => void;
};

function floatSamplesToInt16(samples: number[]): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i] ?? 0));
    const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(i * 2, int16, true);
  }
  return buffer;
}

/** Capture mono PCM at 16 kHz from a MediaStream (~200 ms chunks). */
export function startAsrCapture(
  stream: MediaStream,
  track: AsrTrack,
  onChunk: (track: AsrTrack, pcm: ArrayBuffer) => void,
): AsrCaptureHandle {
  const audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const muteGain = audioContext.createGain();
  muteGain.gain.value = 0;

  let sampleBuffer: number[] = [];
  let stopped = false;

  processor.onaudioprocess = (event) => {
    if (stopped) {
      return;
    }
    const input = event.inputBuffer.getChannelData(0);
    const ratio = audioContext.sampleRate / TARGET_SAMPLE_RATE;
    if (Math.abs(ratio - 1) < 0.01) {
      for (let i = 0; i < input.length; i += 1) {
        sampleBuffer.push(input[i] ?? 0);
      }
    } else {
      for (let i = 0; i < input.length; i += ratio) {
        const idx = Math.floor(i);
        sampleBuffer.push(input[idx] ?? 0);
      }
    }

    while (sampleBuffer.length >= CHUNK_SAMPLES) {
      const chunk = sampleBuffer.splice(0, CHUNK_SAMPLES);
      onChunk(track, floatSamplesToInt16(chunk));
    }
  };

  source.connect(processor);
  processor.connect(muteGain);
  muteGain.connect(audioContext.destination);

  return {
    stop: () => {
      if (stopped) {
        return;
      }
      stopped = true;
      processor.onaudioprocess = null;
      processor.disconnect();
      source.disconnect();
      muteGain.disconnect();
      void audioContext.close();
    },
  };
}
