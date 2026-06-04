"""
Churchgate-AI Email Integration Engine
Fetches invoices from invoices@churchgate.com via Microsoft Graph API
Auto-routes to subsidiary based on email/invoice content
"""
import os
import json
import base64
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
import re

# ============================================
# CONFIGURATION
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# Azure AD App Registration details
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
INVOICE_EMAIL = os.getenv("INVOICE_EMAIL", "invoices@churchgate.com")

# ============================================
# 14 SUBSIDIARIES
# ============================================
SUBSIDIARIES = {
    "first_continental": {
        "name": "First Continental Properties Limited",
        "keywords": ["first continental", "fcpl", "continental properties"],
        "email_domains": ["fcpl.com", "firstcontinental.com"],
        "erp_code": "FCPL",
        "tax_id": ""
    },
    "agroline": {
        "name": "Agroline Ventures",
        "keywords": ["agroline", "agro ventures"],
        "email_domains": ["agroline.com"],
        "erp_code": "AGRO",
        "tax_id": ""
    },
    "rb_properties": {
        "name": "RB Properties Limited",
        "keywords": ["rb properties", "rb properties ltd"],
        "email_domains": ["rbproperties.com"],
        "erp_code": "RBPL",
        "tax_id": ""
    },
    "churchgate": {
        "name": "Churchgate Group",
        "keywords": ["churchgate", "churchgate group"],
        "email_domains": ["churchgate.com"],
        "erp_code": "CHGT",
        "tax_id": ""
    },
    # Add remaining 10 subsidiaries here
    "primeland": {
        "name": "Primeland Developments",
        "keywords": ["primeland", "prime land"],
        "email_domains": ["primeland.com"],
        "erp_code": "PRML",
        "tax_id": ""
    },
    "metro_homes": {
        "name": "Metro Homes Limited",
        "keywords": ["metro homes", "metrohomes"],
        "email_domains": ["metrohomes.com"],
        "erp_code": "MHL",
        "tax_id": ""
    },
    "urban_estates": {
        "name": "Urban Estates Nigeria",
        "keywords": ["urban estates", "urbanestates"],
        "email_domains": ["urbanestates.com"],
        "erp_code": "UEN",
        "tax_id": ""
    },
    "greenfield": {
        "name": "Greenfield Properties",
        "keywords": ["greenfield", "green field"],
        "email_domains": ["greenfield.com"],
        "erp_code": "GFP",
        "tax_id": ""
    },
    "skyline": {
        "name": "Skyline Construction Ltd",
        "keywords": ["skyline", "skyline construction"],
        "email_domains": ["skyline.com"],
        "erp_code": "SKY",
        "tax_id": ""
    },
    "atlantic": {
        "name": "Atlantic Ventures",
        "keywords": ["atlantic", "atlantic ventures"],
        "email_domains": ["atlantic.com"],
        "erp_code": "ATL",
        "tax_id": ""
    },
    "capital": {
        "name": "Capital Development Co",
        "keywords": ["capital development", "capitaldev"],
        "email_domains": ["capitaldev.com"],
        "erp_code": "CDC",
        "tax_id": ""
    },
    "heritage": {
        "name": "Heritage Homes",
        "keywords": ["heritage", "heritage homes"],
        "email_domains": ["heritagehomes.com"],
        "erp_code": "HH",
        "tax_id": ""
    },
    "premium": {
        "name": "Premium Estates Ltd",
        "keywords": ["premium estates", "premiumestates"],
        "email_domains": ["premiumestates.com"],
        "erp_code": "PEL",
        "tax_id": ""
    },
    "united": {
        "name": "United Property Group",
        "keywords": ["united property", "unitedproperty"],
        "email_domains": ["unitedproperty.com"],
        "erp_code": "UPG",
        "tax_id": ""
    }
}

# ============================================
# MICROSOFT GRAPH AUTHENTICATION
# ============================================
class MicrosoftGraphAuth:
    """Authenticate with Microsoft Graph API using client credentials"""
    
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = None
    
    def get_token(self):
        """Get OAuth2 access token"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
        
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }
        
        response = requests.post(url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expiry = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
            return self.access_token
        else:
            raise Exception(f"Auth failed: {response.status_code} - {response.text}")
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.get_token()}", "Content-Type": "application/json"}


# ============================================
# EMAIL FETCHER
# ============================================
class InvoiceEmailFetcher:
    """Fetch invoices from inbox via Microsoft Graph API"""
    
    def __init__(self, auth, email_address=INVOICE_EMAIL):
        self.auth = auth
        self.email_address = email_address
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.download_folder = Path("input/email_fetched")
        self.download_folder.mkdir(parents=True, exist_ok=True)
    
    def fetch_unread_invoices(self, minutes_back=60):
        """Fetch unread emails with invoice attachments from the last N minutes"""
        headers = self.auth.get_headers()
        
        # Calculate time window
        time_filter = (datetime.utcnow() - timedelta(minutes=minutes_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Search for invoice-related emails
        url = f"{self.graph_url}/users/{self.email_address}/messages"
        params = {
            "$filter": f"receivedDateTime ge {time_filter} and hasAttachments eq true",
            "$orderby": "receivedDateTime desc",
            "$top": 50,
            "$select": "id,subject,from,receivedDateTime,hasAttachments,bodyPreview"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching emails: {response.status_code} - {response.text}")
            return []
        
        emails = response.json().get("value", [])
        invoice_emails = []
        
        for email in emails:
            subject = (email.get("subject", "") or "").lower()
            body = (email.get("bodyPreview", "") or "").lower()
            
            # Check if this is an invoice email
            invoice_keywords = ["invoice", "bill", "payment", "due", "receipt", "quote", "po", "purchase order"]
            is_invoice = any(kw in subject or kw in body for kw in invoice_keywords)
            
            if is_invoice:
                invoice_emails.append(email)
                print(f"  📧 Found: {email['subject'][:80]} from {email['from']['emailAddress']['address']}")
        
        return invoice_emails
    
    def download_attachments(self, email_id, email_subject=""):
        """Download attachments from a specific email"""
        headers = self.auth.get_headers()
        url = f"{self.graph_url}/users/{self.email_address}/messages/{email_id}/attachments"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"  Error fetching attachments: {response.status_code}")
            return []
        
        attachments = response.json().get("value", [])
        downloaded_files = []
        
        for attachment in attachments:
            filename = attachment.get("name", "unknown")
            content_type = attachment.get("contentType", "")
            
            # Only download invoice-relevant files
            invoice_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls", ".docx", ".doc"]
            is_invoice_file = any(filename.lower().endswith(ext) for ext in invoice_extensions)
            
            if not is_invoice_file:
                continue
            
            # Generate safe filename
            safe_name = re.sub(r'[^\w\-.]', '_', filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = self.download_folder / f"{timestamp}_{safe_name}"
            
            # Handle different attachment types
            if "@microsoft.graph.temporaryId" in str(attachment):
                # File attachment - may be large, use contentBytes
                content_bytes = attachment.get("contentBytes", "")
                if content_bytes:
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(content_bytes))
            elif "contentBytes" in attachment:
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(attachment["contentBytes"]))
            elif "size" in attachment and attachment.get("size", 0) < 5000000:
                # Small inline attachment
                content_url = f"{url}/{attachment['id']}/$value"
                att_response = requests.get(content_url, headers=headers)
                if att_response.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(att_response.content)
            
            if save_path.exists() and save_path.stat().st_size > 0:
                downloaded_files.append(str(save_path))
                print(f"  📎 Downloaded: {filename} ({save_path.stat().st_size/1024:.0f}KB)")
        
        return downloaded_files
    
    def mark_as_read(self, email_id):
        """Mark email as read after processing"""
        headers = self.auth.get_headers()
        url = f"{self.graph_url}/users/{self.email_address}/messages/{email_id}"
        data = {"isRead": True}
        requests.patch(url, headers=headers, json=data)
    
    def move_to_folder(self, email_id, folder_name="Processed Invoices"):
        """Move processed email to a folder"""
        headers = self.auth.get_headers()
        
        # Find folder ID
        folders_url = f"{self.graph_url}/users/{self.email_address}/mailFolders"
        folders_response = requests.get(folders_url, headers=headers)
        
        folder_id = None
        if folders_response.status_code == 200:
            for folder in folders_response.json().get("value", []):
                if folder.get("displayName", "").lower() == folder_name.lower():
                    folder_id = folder["id"]
                    break
        
        if folder_id:
            move_url = f"{self.graph_url}/users/{self.email_address}/messages/{email_id}/move"
            data = {"destinationId": folder_id}
            requests.post(move_url, headers=headers, json=data)


# ============================================
# SUBSIDIARY ROUTER
# ============================================
class SubsidiaryRouter:
    """Route invoices to the correct subsidiary"""
    
    def detect_subsidiary(self, email_data=None, invoice_text=""):
        """Detect which subsidiary an invoice belongs to"""
        text = (invoice_text or "").lower()
        
        if email_data:
            subject = (email_data.get("subject", "") or "").lower()
            body = (email_data.get("bodyPreview", "") or "").lower()
            sender = (email_data.get("from", {}).get("emailAddress", {}).get("address", "") or "").lower()
            text = f"{subject} {body} {sender}"
        
        scores = {}
        for key, sub in SUBSIDIARIES.items():
            score = 0
            for keyword in sub["keywords"]:
                if keyword.lower() in text:
                    score += 3
            for domain in sub["email_domains"]:
                if domain.lower() in text:
                    score += 5
            if score > 0:
                scores[key] = score
        
        if scores:
            # Return the highest scoring subsidiary
            best = max(scores, key=scores.get)
            return SUBSIDIARIES[best]
        
        # Default to Churchgate Group
        return SUBSIDIARIES["churchgate"]
    
    def get_subsidiary_by_name(self, name):
        """Find subsidiary by partial name match"""
        name_lower = name.lower()
        for key, sub in SUBSIDIARIES.items():
            if name_lower in sub["name"].lower():
                return sub
            for keyword in sub["keywords"]:
                if keyword in name_lower:
                    return sub
        return None


# ============================================
# SIMULATED MODE (for testing without Azure)
# ============================================
class SimulatedEmailFetcher:
    """Simulates email fetching when Azure credentials aren't configured"""
    
    def __init__(self):
        self.download_folder = Path("input/email_fetched")
        self.download_folder.mkdir(parents=True, exist_ok=True)
    
    def fetch_unread_invoices(self, minutes_back=60):
        """Check local input folder for test files"""
        print("  ⚠️  Running in SIMULATED mode — checking input folder for files")
        
        # Look for files in input folder
        input_folder = Path("input")
        files = []
        for ext in ["*.pdf", "*.jpg", "*.jpeg", "*.png", "*.xlsx", "*.xls"]:
            files.extend(input_folder.glob(ext))
        
        simulated_emails = []
        for f in files:
            simulated_emails.append({
                "id": f"sim_{f.stem}",
                "subject": f"Invoice: {f.name}",
                "from": {"emailAddress": {"address": "vendor@example.com"}},
                "receivedDateTime": datetime.utcnow().isoformat(),
                "bodyPreview": f"Please process attached invoice for {f.stem}",
                "_local_file": str(f)
            })
        
        return simulated_emails
    
    def download_attachments(self, email_id, email_subject=""):
        """Return existing file path for simulated emails"""
        if "_local_file" in email_id if isinstance(email_id, dict) else False:
            return [email_id["_local_file"]]
        return []


# ============================================
# MAIN EMAIL PROCESSING PIPELINE
# ============================================
def run_email_pipeline():
    """Main function: Fetch emails → Download → Route → Process"""
    print("\n" + "="*60)
    print("  📧 CHURCHGATE-AI EMAIL INVOICE PIPELINE")
    print("="*60)
    
    # Initialize auth
    if AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
        print("\n  🔑 Authenticating with Microsoft Graph...")
        try:
            auth = MicrosoftGraphAuth(AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)
            fetcher = InvoiceEmailFetcher(auth)
            print("  ✅ Connected to Microsoft 365")
        except Exception as e:
            print(f"  ❌ Azure auth failed: {e}")
            print("  ⚠️  Switching to simulated mode")
            fetcher = SimulatedEmailFetcher()
    else:
        print("\n  ⚠️  Azure credentials not configured")
        print("  💡 Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET in .env")
        print("  🔄 Running in SIMULATED mode\n")
        fetcher = SimulatedEmailFetcher()
    
    router = SubsidiaryRouter()
    
    # Fetch invoice emails
    print("\n  📥 Checking for new invoice emails...")
    invoice_emails = fetcher.fetch_unread_invoices(minutes_back=1440)  # Last 24 hours
    
    if not invoice_emails:
        print("  📭 No new invoice emails found")
        return []
    
    print(f"\n  📧 Found {len(invoice_emails)} invoice email(s)")
    
    processed_files = []
    
    for i, email in enumerate(invoice_emails, 1):
        print(f"\n  {'─'*50}")
        print(f"  [{i}/{len(invoice_emails)}] Processing email...")
        
        # Get email details
        email_id = email.get("id", "")
        subject = email.get("subject", "No Subject")
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "unknown")
        
        print(f"  From: {sender}")
        print(f"  Subject: {subject[:100]}")
        
        # Detect subsidiary
        subsidiary = router.detect_subsidiary(email_data=email)
        print(f"  🏢 Routed to: {subsidiary['name']} ({subsidiary['erp_code']})")
        
        # Download attachments
        attachments = []
        if isinstance(fetcher, SimulatedEmailFetcher) and "_local_file" in email:
            attachments = [email["_local_file"]]
        else:
            attachments = fetcher.download_attachments(email_id, subject)
        
        if attachments:
            print(f"  📎 {len(attachments)} attachment(s) saved")
            for att in attachments:
                processed_files.append({
                    "file_path": att,
                    "subsidiary": subsidiary,
                    "email_from": sender,
                    "email_subject": subject,
                    "processed_at": datetime.now().isoformat()
                })
        else:
            print("  ⚠️  No invoice attachments found")
        
        # Mark as read (only for real mode)
        if not isinstance(fetcher, SimulatedEmailFetcher):
            try:
                fetcher.mark_as_read(email_id)
            except:
                pass
    
    print(f"\n  {'='*60}")
    print(f"  ✅ Pipeline complete: {len(processed_files)} files ready for processing")
    print(f"  {'='*60}")
    
    return processed_files


# ============================================
# STANDALONE TEST
# ============================================
if __name__ == "__main__":
    results = run_email_pipeline()
    
    if results:
        print("\n  📋 Files ready for invoice processing:")
        for r in results:
            print(f"    📄 {Path(r['file_path']).name}")
            print(f"       Subsidiary: {r['subsidiary']['name']} ({r['subsidiary']['erp_code']})")
            print(f"       From: {r['email_from']}")
    
    print("\n  ✅ Done")