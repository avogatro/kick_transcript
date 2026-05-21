import sys
import requests

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def generate(self, model, prompt, stream=False):
        """
        Calls the Ollama generate API.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Ollama API: {e}", file=sys.stderr)
            return None

    def summarize(self, model, transcript, system_prompt, vocabulary=""):
        """
        Specific method for summarizing transcripts.
        """
        full_prompt = f"{system_prompt}\n\nContext/Vocabulary: {vocabulary}\n\n[Transcript]:\n{transcript}"
        result = self.generate(model, full_prompt)
        if result:
            return result.get("response", "")
        return ""

    def translate_subtitle(self, model, text, target_lang):
        """
        Specific method for translating subtitle text.
        """
        prompt = f"Translate the following subtitle text to {target_lang}. Output ONLY the raw translated text, nothing else.\n\nText: {text}"
        result = self.generate(model, prompt)
        if result:
            return result.get("response", "").strip()
        return text

class GeminiClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def summarize(self, model, transcript, system_prompt, vocabulary=""):
        """
        Specific method for summarizing transcripts via the free Google AI Studio Gemini API.
        """
        # Default to gemini-3.5-flash if none specified or if model is just 'gemini'
        actual_model = model if model != "gemini" else "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1/models/{actual_model}:generateContent?key={self.api_key}"
        
        full_prompt = f"{system_prompt}\n\nContext/Vocabulary: {vocabulary}\n\n[Transcript]:\n{transcript}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }]
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            res_json = response.json()
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error querying Gemini API: {e}", file=sys.stderr)
            if 'response' in locals() and response is not None:
                try:
                    print(f"API Error Response: {response.text}", file=sys.stderr)
                except Exception:
                    pass
            return None

