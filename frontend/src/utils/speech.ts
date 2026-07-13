import { voiceApi } from "../api/endpoints";

let currentAudio: HTMLAudioElement | null = null;

export async function speak(text: string): Promise<void> {
  const clean = text.trim();
  if (!clean) return;

  try {
    const blob = await voiceApi.speak(clean);
    const url = URL.createObjectURL(blob);

    if (currentAudio) {
      currentAudio.pause();
      URL.revokeObjectURL(currentAudio.src);
    }

    const audio = new Audio(url);
    currentAudio = audio;
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play().catch(() => undefined);
  } catch {
    // TTS backend may still be downloading the model on first use; fail silently.
  }
}
