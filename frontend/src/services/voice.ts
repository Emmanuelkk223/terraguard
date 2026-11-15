/**
 * Voice for TerraGuide, using the browser's built-in Web Speech API (no extra service, no key).
 * Speaking works in all major browsers. Listening works in Chrome, Edge and Safari; those browsers send the recording to their own
 * speech service (Google, Microsoft or Apple) to turn it into text. Firefox has no listening, so the microphone button is hidden there.
 */

/* Minimal typings: SpeechRecognition is not in TypeScript's DOM library. */
interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
export interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}
type RecognitionCtor = new () => Recognition;

const Ctor: RecognitionCtor | undefined = typeof window !== "undefined"
  ? ((window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }).SpeechRecognition
    ?? (window as unknown as { webkitSpeechRecognition?: RecognitionCtor }).webkitSpeechRecognition)
  : undefined;

export const canListen = Boolean(Ctor);
export const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

/** Start listening once; calls back with words as they are heard and once with the final text. Returns a stop function. */
export function listen(handlers: {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
  onEnd: () => void;
}): () => void {
  if (!Ctor) {
    handlers.onError("This browser cannot listen. Try Chrome or Edge, or type instead.");
    handlers.onEnd();
    return () => undefined;
  }
  const rec = new Ctor();
  rec.lang = navigator.language?.startsWith("en") ? navigator.language : "en-GB";
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  let final = "";
  rec.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i += 1) {
      const r = e.results[i];
      if (r.isFinal) final += r[0].transcript;
      else interim += r[0].transcript;
    }
    handlers.onInterim((final + interim).trim());
  };
  rec.onerror = (e) => {
    const messages: Record<string, string> = {
      "not-allowed": "I can't use the microphone: please allow it in the browser (the icon in the address bar), or type instead.",
      "service-not-allowed": "Voice input is turned off in this browser. You can type instead.",
      "no-speech": "I didn't hear anything. Press the microphone and try again.",
      "audio-capture": "No microphone was found. You can type instead.",
      network: "Voice input needs an internet connection to the browser's speech service.",
    };
    if (e.error !== "aborted") handlers.onError(messages[e.error] ?? "Voice input stopped. You can try again or type.");
  };
  rec.onend = () => {
    if (final.trim()) handlers.onFinal(final.trim());
    handlers.onEnd();
  };
  stopSpeaking(); // do not let the robot hear itself
  rec.start();
  return () => rec.stop();
}

let chosenVoice: SpeechSynthesisVoice | null | undefined;

/** A clear English voice: prefer natural or neural voices, then Google and Microsoft voices, then any English voice. */
function pickVoice(): SpeechSynthesisVoice | null {
  if (chosenVoice !== undefined && chosenVoice !== null) return chosenVoice;
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"));
  if (!voices.length) return null;
  const score = (v: SpeechSynthesisVoice) =>
    (/natural|neural|online/i.test(v.name) ? 8 : 0) + (/google|microsoft|samantha|daniel/i.test(v.name) ? 4 : 0)
    + (/en-(gb|ng|gh|za)/i.test(v.lang) ? 2 : 0) + (v.localService ? 0 : 1);
  chosenVoice = [...voices].sort((a, b) => score(b) - score(a))[0];
  return chosenVoice;
}
if (canSpeak) window.speechSynthesis.addEventListener?.("voiceschanged", () => { chosenVoice = undefined; });

/** Say a line aloud (queued after anything already being said). Calls onStart/onEnd so the robot can move its mouth. */
export function speak(text: string, onStart?: () => void, onEnd?: () => void): void {
  if (!canSpeak) return;
  const clean = text
    .replace(/^•\s*/, "")
    .replace(/[“”"]/g, "")
    .replace(/\bkm\b/g, "kilometres")
    .replace(/\bMODIS\b/g, "Moe-diss")
    .replace(/\bVIIRS\b/g, "veers")
    .replace(/\bCSV\b/g, "C S V")
    .replace(/\bFIRMS\b/g, "firms")
    .replace(/(\d{4})–(\d{4})/g, "$1 to $2");
  const u = new SpeechSynthesisUtterance(clean);
  const voice = pickVoice();
  if (voice) { u.voice = voice; u.lang = voice.lang; }
  u.rate = 1.03;
  u.pitch = 1.08;
  u.onstart = () => onStart?.();
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export function stopSpeaking(): void {
  if (canSpeak) window.speechSynthesis.cancel();
}

/** Pick the choice whose label best matches what was said (most shared words); null when nothing matches well enough. */
export function matchChoice(said: string, labels: string[]): number | null {
  const words = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter((w) => w.length > 2);
  const heard = new Set(words(said));
  const skip = new Set(["the", "and", "for", "what", "how", "are", "was", "were", "which", "this", "that", "with", "from", "show", "want", "about"]);
  let best: number | null = null;
  let bestScore = 0;
  labels.forEach((label, i) => {
    const own = words(label).filter((w) => !skip.has(w));
    if (!own.length) return;
    const hits = own.filter((w) => heard.has(w) || [...heard].some((h) => sameStem(h, w))).length;
    const score = hits / Math.sqrt(own.length) + (said.toLowerCase().trim() === label.toLowerCase().trim() ? 5 : 0);
    if (hits && score > bestScore) { bestScore = score; best = i; }
  });
  return bestScore >= 0.55 ? best : null;
}

/** Words that share a stem of at least five letters (firefighter / firefighting, scientist / science is not, research / researcher is). */
function sameStem(a: string, b: string): boolean {
  if (a.length < 5 || b.length < 5) return false;
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  return i >= 5 || (i >= 4 && Math.min(a.length, b.length) <= 6);
}
