// Tactical Web Audio Synthesizer (No external audio files required)
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx && typeof window !== "undefined") {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      audioCtx = new AudioContext();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

export function playAlertSound(threatLevel = "CRITICAL") {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    if (threatLevel === "CRITICAL") {
      // Urgent warble/siren alarm
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.linearRampToValueAtTime(440, now + 0.15);
      osc.frequency.linearRampToValueAtTime(880, now + 0.3);
      osc.frequency.linearRampToValueAtTime(440, now + 0.45);

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

      osc.start(now);
      osc.stop(now + 0.5);
    } else if (threatLevel === "HIGH") {
      // High caution chime
      osc.type = "sine";
      osc.frequency.setValueAtTime(659.25, now);
      osc.frequency.setValueAtTime(880, now + 0.1);

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);

      osc.start(now);
      osc.stop(now + 0.35);
    } else {
      // Subtle info pip
      osc.type = "triangle";
      osc.frequency.setValueAtTime(523.25, now);

      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

      osc.start(now);
      osc.stop(now + 0.15);
    }
  } catch (e) {
    // Audio may be blocked until first user interaction
  }
}