"""
Churchgate-AI Azure Document Intelligence Extractor
Enterprise-grade invoice extraction using Azure Form Recognizer
Falls back to Gemini AI when Azure is unavailable
"""
import os
import json
import time
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

AZURE_FORM_ENDPOINT = os.getenv("AZURE_FORM_ENDPOINT", "")
AZURE_FORM_KEY = os.getenv("AZURE_FORM_KEY", "")

# ============================================
# AZURE DOCUMENT INTELLIGENCE EXTRACTOR
# ============================================
class AzureInvoiceExtractor:
    """Extract invoice data using Azure Document Intelligence prebuilt-invoice model"""
    
    def __init__(self, endpoint=None, api_key=None):
        self.endpoint = endpoint or AZURE_FORM_ENDPOINT
        self.api_key = api_key or AZURE_FORM_KEY
        self.is_configured = bool(self.endpoint and self.api_key)
        
        if self.is_configured:
            try:
                from azure.ai.formrecognizer import DocumentAnalysisClient
                from azure.core.credentials import AzureKeyCredential
                self.client = DocumentAnalysisClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.api_key)
                )
                print("✅ Azure Document Intelligence connected")
            except ImportError:
                print("⚠️ Azure SDK not installed. Run: pip install azure-ai-formrecognizer")
                self.is_configured = False
            except Exception as e:
                print(f"⚠️ Azure connection failed: {e}")
                self.is_configured = False
        else:
            print("⚠️ Azure credentials not configured. Set AZURE_FORM_ENDPOINT and AZURE_FORM_KEY in .env")
    
    def extract(self, file_path):
        """Extract invoice data from a file using Azure prebuilt-invoice model"""
        if not self.is_configured:
            return {"error": "Azure not configured", "_fallback": True}
        
        try:
            with open(file_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    model_id="prebuilt-invoice",
                    document=f
                )
            
            result = poller.result()
            
            # Parse Azure response into our standard format
            extracted = self._parse_azure_response(result)
            extracted['_source'] = 'azure'
            extracted['_azure_confidence'] = self._get_confidence(result)
            
            return extracted
            
        except Exception as e:
            return {"error": f"Azure extraction failed: {str(e)[:100]}", "_fallback": True}
    
    def _parse_azure_response(self, result):
        """Convert Azure Document Intelligence response to our standard format"""
        data = {
            'vendor_name': None,
            'invoice_number': None,
            'invoice_date': None,
            'due_date': None,
            'subtotal': 0.0,
            'tax_amount': 0.0,
            'total_amount': 0.0,
            'currency': 'NGN',
            'line_items': [],
            '_azure_fields': {}
        }
        
        # Extract top-level fields
        for field_name, field in result.documents[0].fields.items():
            if field_name == "VendorName":
                data['vendor_name'] = field.value if field.value else None
            elif field_name == "InvoiceId":
                data['invoice_number'] = field.value if field.value else None
            elif field_name == "InvoiceDate":
                data['invoice_date'] = str(field.value) if field.value else None
            elif field_name == "DueDate":
                data['due_date'] = str(field.value) if field.value else None
            elif field_name == "SubTotal":
                data['subtotal'] = float(field.value) if field.value else 0.0
            elif field_name == "TotalTax":
                data['tax_amount'] = float(field.value) if field.value else 0.0
            elif field_name == "InvoiceTotal":
                data['total_amount'] = float(field.value) if field.value else 0.0
            elif field_name == "CurrencyCode":
                data['currency'] = str(field.value) if field.value else 'NGN'
            
            # Store all Azure fields for reference
            data['_azure_fields'][field_name] = {
                'value': str(field.value) if field.value else None,
                'confidence': field.confidence if hasattr(field, 'confidence') else None
            }
        
        # Extract line items
        if hasattr(result.documents[0].fields.get("Items"), "value"):
            items = result.documents[0].fields.get("Items")
            if items and items.value:
                for item in items.value:
                    line_item = {
                        'description': None,
                        'quantity': 0,
                        'unit_price': 0.0,
                        'line_total': 0.0
                    }
                    
                    for item_field_name, item_field in item.value.items():
                        if item_field_name == "Description":
                            line_item['description'] = item_field.value if item_field.value else None
                        elif item_field_name == "Quantity":
                            line_item['quantity'] = float(item_field.value) if item_field.value else 0
                        elif item_field_name == "UnitPrice":
                            line_item['unit_price'] = float(item_field.value) if item_field.value else 0.0
                        elif item_field_name == "Amount":
                            line_item['line_total'] = float(item_field.value) if item_field.value else 0.0
                    
                    data['line_items'].append(line_item)
        
        return data
    
    def _get_confidence(self, result):
        """Calculate average confidence across all fields"""
        confidences = []
        for field in result.documents[0].fields.values():
            if hasattr(field, 'confidence') and field.confidence is not None:
                confidences.append(field.confidence)
        
        if confidences:
            return round(sum(confidences) / len(confidences) * 100, 1)
        return 0


# ============================================
# DUAL AI ENGINE (Azure + Gemini Fallback)
# ============================================
class DualAIEngine:
    """
    Primary: Azure Document Intelligence (enterprise-grade)
    Fallback: Google Gemini 2.5 Flash
    """
    
    def __init__(self, azure_extractor=None, gemini_extractor=None):
        self.azure = azure_extractor or AzureInvoiceExtractor()
        self.gemini = gemini_extractor  # Will be set from dashboard/app
        self.stats = {
            'azure_calls': 0,
            'gemini_calls': 0,
            'azure_success': 0,
            'gemini_success': 0,
            'fallback_triggered': 0
        }
    
    def extract(self, file_path, image_bytes=None):
        """Extract with Azure first, fall back to Gemini"""
        
        # Try Azure first
        if self.azure.is_configured:
            self.stats['azure_calls'] += 1
            result = self.azure.extract(file_path)
            
            if '_fallback' not in result:
                self.stats['azure_success'] += 1
                return result
            else:
                self.stats['fallback_triggered'] += 1
                print(f"  ⚠️ Azure unavailable, falling back to Gemini...")
        
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
        """Return engine usage statistics"""
        return self.stats


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("  Churchgate-AI Dual AI Engine Test")
    print("="*60)
    
    engine = DualAIEngine()
    
    if engine.azure.is_configured:
        print("\n✅ Azure Document Intelligence: READY")
    else:
        print("\n⚠️ Azure: NOT CONFIGURED")
        print("  Set AZURE_FORM_ENDPOINT and AZURE_FORM_KEY in .env")
    
    print("\n📊 Engine Stats:")
    print(f"  Azure: {engine.stats['azure_success']}/{engine.stats['azure_calls']} successful")
    print(f"  Gemini (fallback): {engine.stats['gemini_success']}/{engine.stats['gemini_calls']} successful")
    print(f"  Fallbacks triggered: {engine.stats['fallback_triggered']}")