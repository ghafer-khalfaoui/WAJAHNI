import urllib.request
import json
from app.core.config import settings

print("\n[*] Interrogating Google API for Generation Models...")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.GEMINI_API_KEY}"

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        print("\n[+] Text Generation Models explicitly allowed for your API Key:")
        
        found = False
        for model in data.get("models", []):
            if "generateContent" in model.get("supportedGenerationMethods", []):
                print(f"    -> {model['name']}")
                found = True
                
        if not found:
            print("    [-] ERROR: No generation models found.")
            
except Exception as e:
    print(f"[-] HTTP Request Failed: {e}")
