"""
Churchgate-AI Dual Free AI Engine
Primary: Mistral AI OCR (free tier)
Fallback: Google Gemini 2.5 Flash (free tier)
"""
import os
import json
import time
import requests
import base64
from datetime import datetime
from pathlib import Path

# ============================================
# CONFIGURATION
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# ============================================
# MISTRAL AI EXTRACTOR (FREE TIER)
# ============================================
class MistralExtractor:
    """Extract invoice data using Mistral AI OCR (free tier)"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or MISTRAL_API_KEY
        self.is_configured = bool(self.api_key)
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        
        if self.is_configured:
            print("✅ Mistral AI: Ready (free tier)")
        else:
            print("⚠️ Mistral AI not configured. Get free key at https://console.mistral.ai/")
    
    def extract(self, image_bytes):
        """Extract invoice data using Mistral's vision model"""
        if not self.is_configured:
            return {"error": "Mistral not configured", "_fallback": True}
        
        try:
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = """Extract ALL invoice data from this document. Return ONLY valid JSON with these exact fields:
{
    "vendor_name": "Company name on invoice",
    "invoice_number": "Invoice number",
    "invoice_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD or null",
    "subtotal": 0.00,
    "tax_amount": 0.00,
    "total_amount": 0.00,
    "currency": "NGN",
    "line_items": [
        {"description": "Item", "quantity": 1, "unit_price": 0.00, "line_total": 0.00}
    ]
}"""
            
            payload = {
                "model": "pixtral-12b-2409",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64}"}
                    ]
                }],
                "max_tokens": 2000
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=45)
            
            if response.status_code == 200:
                text = response.json()['choices'][0]['message']['content']
                text = text.replace('```json','').replace('```','').strip()
                s, e = text.find('{'), text.rfind('}')+1
                if s != -1 and e > s:
                    result = json.loads(text[s:e])
                    result['_source'] = 'mistral'
                    return result
            
            return {"error": f"Mistral failed: HTTP {response.status_code}", "_fallback": True}
            
        except Exception as e:
            return {"error": f"Mistral error: {str(e)[:100]}", "_fallback": True}


# ============================================
# DUAL FREE AI ENGINE
# ============================================
class DualAIEngine:
    """Primary: Mistral AI | Fallback: Google Gemini"""
    
    def __init__(self, mistral_extractor=None, gemini_extractor=None):
        self.mistral = mistral_extractor or MistralExtractor()
        self.gemini = gemini_extractor
        self.stats = {'mistral_calls': 0, 'gemini_calls': 0, 'mistral_success': 0, 'gemini_success': 0, 'fallback_triggered': 0}
    
    def extract(self, file_path=None, image_bytes=None):
        # Try Mistral first
        if self.mistral.is_configured and image_bytes:
            self.stats['mistral_calls'] += 1
            result = self.mistral.extract(image_bytes)
            if '_fallback' not in result:
                self.stats['mistral_success'] += 1
                return result
            else:
                self.stats['fallback_triggered'] += 1
        
        # Fall back to Gemini
        if self.gemini and image_bytes:
            self.stats['gemini_calls'] += 1
            result = self.gemini.extract(image_bytes, enhance=True)
            if 'error' not in result:
                self.stats['gemini_success'] += 1
                result['_source'] = 'gemini-fallback'
            return result
        
        return {"error": "No AI engine available"}
    
    def get_stats(self):
        return self.stats