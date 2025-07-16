
/**
 * Speaks the given text using the browser's Web Speech API.
 * @param {string} text The text to be spoken.
 */
export const speak = (text) => {
  if (!window.speechSynthesis) {
    console.warn("Browser does not support speech synthesis.");
    return;
  }

  // Cancel any ongoing speech to prevent overlap
  window.speechSynthesis.cancel();

  // Clean the text by removing Markdown asterisks for bold/italics
  const cleanedText = text.replace(/\*/g, '');

  const utterance = new SpeechSynthesisUtterance(cleanedText);
  
  // Optional: Configure voice, rate, pitch, etc.
  utterance.voice = speechSynthesis.getVoices().find(voice => voice.name === 'Google UK English Male');
  // utterance.rate = 1;
  // utterance.pitch = 1;

  window.speechSynthesis.speak(utterance);
};
