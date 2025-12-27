/**
 * Handles Text-to-Speech using the browser's native SpeechSynthesis API.
 * This removes the dependency on external APIs and works offline.
 */
export const speakText = (text: string) => {
    if (!('speechSynthesis' in window)) {
        console.warn("Browser does not support text-to-speech");
        return;
    }

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    
    // Attempt to select a friendly voice
    const voices = window.speechSynthesis.getVoices();
    // Prefer "Google US English" or similar if available, otherwise default
    const preferredVoice = voices.find(v => v.name.includes('Google US English')) || 
                           voices.find(v => v.lang.startsWith('en'));
    
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }

    utterance.rate = 0.9; // Slightly slower for children
    utterance.pitch = 1.1; // Slightly higher pitch often sounds friendlier

    window.speechSynthesis.speak(utterance);
};
