import { isAxiosError } from "axios";
import { voiceApi } from "../api/endpoints";

let currentAudio: HTMLAudioElement | null = null;
let currentAudioUrl: string | null = null;
let currentUtterance: SpeechSynthesisUtterance | null = null;
let requestSequence = 0;

function emitSpeaking(active: boolean) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("assistant-speaking", { detail: { active } }));
  }
}

function stopCurrentPlayback() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.removeAttribute("src");
    currentAudio.load();
    currentAudio = null;
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  currentUtterance = null;
  emitSpeaking(false);
}

function speakWithBrowser(text: string): boolean {
  if (
    typeof window === "undefined" ||
    !("speechSynthesis" in window) ||
    !("SpeechSynthesisUtterance" in window)
  ) {
    return false;
  }

  stopCurrentPlayback();

  const synthesis = window.speechSynthesis;
  const utterance = new SpeechSynthesisUtterance(text);
  const voices = synthesis.getVoices();
  utterance.lang = "ru-RU";
  utterance.voice =
    voices.find((voice) => /^ru(?:-|_)/i.test(voice.lang)) ??
    voices.find((voice) => /russian|рус/i.test(voice.name)) ??
    null;
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onend = () => {
    if (currentUtterance === utterance) currentUtterance = null;
    emitSpeaking(false);
  };
  utterance.onerror = () => {
    if (currentUtterance === utterance) currentUtterance = null;
    emitSpeaking(false);
  };

  currentUtterance = utterance;
  emitSpeaking(true);
  synthesis.speak(utterance);
  return true;
}

function shouldUseBrowserFallback(error: unknown): boolean {
  if (!isAxiosError(error)) return true;
  return !error.response || error.response.status >= 500;
}

export async function speak(text: string): Promise<void> {
  const clean = text.trim();
  if (!clean) return;
  const sequence = ++requestSequence;

  try {
    const blob = await voiceApi.speak(clean);
    if (sequence !== requestSequence) return;

    const url = URL.createObjectURL(blob);
    stopCurrentPlayback();

    const audio = new Audio(url);
    currentAudio = audio;
    currentAudioUrl = url;
    const releaseAudio = () => {
      if (currentAudio === audio) currentAudio = null;
      if (currentAudioUrl === url) {
        URL.revokeObjectURL(url);
        currentAudioUrl = null;
      }
      emitSpeaking(false);
    };
    audio.onended = releaseAudio;
    audio.onerror = releaseAudio;
    emitSpeaking(true);
    await audio.play();
  } catch (error) {
    emitSpeaking(false);
    if (sequence === requestSequence && shouldUseBrowserFallback(error)) {
      speakWithBrowser(clean);
    }
  }
}
