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
        Specific method for summarizing transcripts via the Google GenAI SDK.
        """
        # Default to gemini-3.5-flash if none specified or if model is just 'gemini'
        actual_model = model if model != "gemini" else "gemini-3.5-flash"
        
        try:
            from google import genai
            from google.genai import types
            import pathlib
            
            client = genai.Client(api_key=self.api_key)
            
            transcript_path = pathlib.Path("transcript.txt")
            if transcript_path.exists():
                transcript_data = transcript_path.read_bytes()
            else:
                transcript_data = transcript.encode("utf-8")
                
            prompt = system_prompt
            if vocabulary:
                prompt = f"{system_prompt}\n\nContext/Vocabulary: {vocabulary}"
                
            response = client.models.generate_content(
                model=actual_model,
                contents=[
                    types.Part.from_bytes(
                        data=transcript_data,
                        mime_type='text/plain',
                    ),
                    prompt
                ]
            )
            return response.text
        except Exception as e:
            print(f"Error querying Gemini API via GenAI SDK: {e}", file=sys.stderr)
            return None

