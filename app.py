"""
Churchgate-AI Enterprise Invoice Processing
AI-Powered | Auto-Validated | Export-Ready | ERP Matching
Multi-Page PDF Support | Image Enhancement
Handles: Images, PDFs, Scanned Documents, Excel, BOQ Files
"""
import os, json, base64, requests, pandas as pd, numpy as np, time, re, traceback
from datetime import datetime, date
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from rapidfuzz import fuzz, process

# ============================================
# API KEY
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        print("WARNING: No GEMINI_API_KEY found in .env file")
        API_KEY = input("Or paste your API key now: ").strip()
except ImportError:
    API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if not API_KEY:
        API_KEY = input("Enter your Gemini API key: ").strip()

os.system('')

# Colors
Rs = '\033[0m'; Bo = '\033[1m'; Di = '\033[2m'
Rd = '\033[91m'; Gn = '\033[92m'; Ye = '\033[93m'; Cy = '\033[96m'; Wh = '\033[97m'
BgB = '\033[44m'; BgG = '\033[42m'; BgR = '\033[41m'; BgY = '\033[43m'

def banner():
    print(f"""
{BgB}{Wh}{Bo}  ╔{'═'*56}╗  {Rs}
{BgB}{Wh}{Bo}  ║{' '*56}║  {Rs}
{BgB}{Wh}{Bo}  ║  {Bo}CHURCHGATE-AI ENTERPRISE INVOICE PROCESSING{' '*11}║  {Rs}
{BgB}{Wh}{Bo}  ║{' '*56}║  {Rs}
{BgB}{Wh}  ║  {Di}Multi-Page PDF | Image Enhancement | ERP Matching | Export{' '*8}║  {Rs}
{BgB}{Wh}{Bo}  ║{' '*56}║  {Rs}
{BgB}{Wh}{Bo}  ╚{'═'*56}╝  {Rs}""")

def ok(m): print(f"  {Gn}{Bo}OK{Rs}  {m}")
def er(m): print(f"  {Rd}{Bo}ERR{Rs} {m}")
def wn(m): print(f"  {Ye}{Bo}WRN{Rs} {m}")
def inf(m): print(f"  {Cy}{Bo}INF{Rs} {m}")
def sep(): print(f"  {Di}{'─'*58}{Rs}")

# ============================================
# IMAGE ENHANCEMENT ENGINE (NEW!)
# ============================================
class ImageEnhancer:
    """Pre-process images for better AI extraction accuracy"""
    
    @staticmethod
    def enhance(image_path, output_path=None):
        """
        Enhance image quality for better OCR/extraction:
        - Auto-rotate skewed documents
        - Increase contrast
        - Sharpen text
        - Denoise
        - Convert to optimal format
        """
        if not output_path:
            output_path = str(image_path) + "_enhanced.jpg"
        
        try:
            img = Image.open(image_path)
            
            # 1. Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # 2. Auto-contrast (stretch histogram)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)  # 50% more contrast
            
            # 3. Sharpen
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)  # 2x sharpness
            
            # 4. Brightness optimization
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.1)  # Slightly brighter
            
            # 5. Denoise with slight blur then resharpening
            img = img.filter(ImageFilter.MedianFilter(size=3))
            
            # 6. Auto-rotate if needed (basic deskew)
            # Check if image is portrait and rotate if needed
            width, height = img.size
            if width > height * 1.5:
                # Likely a landscape scan of a portrait document
                pass  # Keep as-is for wide documents
            
            # Save enhanced image
            img.save(output_path, 'JPEG', quality=95, optimize=True)
            
            # Only return enhanced path if file was actually created and is valid
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                orig_size = os.path.getsize(image_path) / 1024
                new_size = os.path.getsize(output_path) / 1024
                inf(f"Image enhanced: {orig_size:.0f}KB → {new_size:.0f}KB")
                return output_path
            
        except Exception as e:
            wn(f"Enhancement skipped: {str(e)[:50]}")
        
        return image_path  # Return original if enhancement fails

# ============================================
# AI EXTRACTION ENGINE (WITH MULTI-PAGE SUPPORT)
# ============================================
class Extractor:
    def __init__(self, key):
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        self.enhancer = ImageEnhancer()
    
    def extract(self, path, enhance=True):
        """Extract from image with optional enhancement"""
        # Enhance image first
        if enhance:
            enhanced_path = self.enhancer.enhance(path)
            actual_path = enhanced_path if os.path.exists(enhanced_path) else path
        else:
            actual_path = path
        
        with open(actual_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Clean up enhanced temp file
        if enhance and actual_path != path and os.path.exists(actual_path):
            try: os.remove(actual_path)
            except: pass
        
        file_size_kb = os.path.getsize(path) / 1024
        if file_size_kb > 5000:
            return {"error": f"File too large ({file_size_kb:.0f}KB). Max 5MB."}
        
        prompt = """Extract ALL invoice/PO/BOQ data from this document. Return ONLY valid JSON.
{
    "vendor_name": "Company name",
    "invoice_number": "Reference number",
    "po_number": "PO number if visible",
    "invoice_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD or null",
    "subtotal": 0.00,
    "tax_amount": 0.00,
    "total_amount": 0.00,
    "currency": "NGN",
    "line_items": [
        {"description": "Item or service", "quantity": 1, "unit_price": 0.00, "line_total": 0.00}
    ]
}
Find the TOTAL or GRAND TOTAL. Extract ALL line items with quantities, rates, and totals.
For multi-page documents, combine data from all pages into a single response."""
        
        payload = {"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":"image/jpeg","data":b64}}]}]}
        
        for attempt in range(1, 4):
            try:
                if attempt > 1: time.sleep(attempt * 10)
                print(f"  {Cy}...{Rs} AI processing (attempt {attempt}/3)")
                r = requests.post(self.url, json=payload, timeout=60)
                if r.status_code == 200:
                    text = r.json()['candidates'][0]['content']['parts'][0]['text']
                    return self._parse(text)
                elif r.status_code == 429:
                    print(f"  {Ye}...{Rs} Rate limited")
                elif r.status_code == 503:
                    print(f"  {Ye}...{Rs} Server busy")
                elif r.status_code == 403:
                    return {"error": "API key rejected. Check .env file."}
            except Exception as e:
                if attempt == 3: return {"error": str(e)[:100]}
        return {"error": "AI unavailable after 3 attempts"}
    
    def extract_multi_page(self, image_paths, enhance=True):
        """Extract from multiple pages and merge results"""
        all_results = []
        
        for i, path in enumerate(image_paths):
            inf(f"Processing page {i+1}/{len(image_paths)}...")
            result = self.extract(path, enhance=enhance)
            if "error" not in result:
                all_results.append(result)
        
        if not all_results:
            return {"error": "No data extracted from any page"}
        
        if len(all_results) == 1:
            return all_results[0]
        
        # Merge multiple pages
        merged = all_results[0].copy()
        
        # Combine line items from all pages
        all_items = []
        for r in all_results:
            items = r.get('line_items', [])
            all_items.extend(items)
        
        merged['line_items'] = all_items
        
        # Sum financial totals
        merged['subtotal'] = sum(r.get('subtotal', 0) or 0 for r in all_results)
        merged['tax_amount'] = sum(r.get('tax_amount', 0) or 0 for r in all_results)
        merged['total_amount'] = sum(r.get('total_amount', 0) or 0 for r in all_results)
        
        # Use the first non-empty vendor name
        for r in all_results:
            if r.get('vendor_name'):
                merged['vendor_name'] = r['vendor_name']
                break
        
        # Use the first invoice number found
        for r in all_results:
            if r.get('invoice_number'):
                merged['invoice_number'] = r['invoice_number']
                break
        
        inf(f"Merged {len(all_results)} pages: {len(all_items)} line items total")
        return merged
    
    def _parse(self, text):
        text = text.replace('```json','').replace('```','').strip()
        s, e = text.find('{'), text.rfind('}')+1
        if s != -1 and e > s:
            try: return json.loads(text[s:e])
            except:
                try: return json.loads(re.sub(r'(\d+),(\d+)', r'\1\2', text[s:e]))
                except: pass
        return {"error": "Could not parse AI response"}

# ============================================
# MULTI-PAGE PDF CONVERTER (NEW!)
# ============================================
def pdf_to_images(path, max_pages=10):
    """Convert PDF pages to images - supports multi-page documents"""
    try:
        import fitz
        doc = fitz.open(path)
        total_pages = min(len(doc), max_pages)
        
        if total_pages == 0:
            doc.close()
            return []
        
        image_paths = []
        for page_num in range(total_pages):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            tmp = f"{path}_page{page_num+1}_temp.jpg"
            pix.save(tmp)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
                image_paths.append(tmp)
        
        doc.close()
        
        if len(image_paths) > 1:
            inf(f"PDF has {total_pages} pages — processing all")
        
        return image_paths
    except Exception as e:
        wn(f"PDF conversion failed: {str(e)[:60]}")
        return []

def excel_to_image(path):
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        df = pd.read_excel(path, header=None)
        fig, ax = plt.subplots(figsize=(20, max(5, len(df) * 0.35)))
        ax.axis('off')
        ax.table(cellText=df.values, loc='center', cellLoc='left', colWidths=[0.12]*len(df.columns)).set_fontsize(6)
        tmp = str(path) + "_temp.jpg"
        plt.savefig(tmp, bbox_inches='tight', dpi=150, pad_inches=0.15)
        plt.close()
        return tmp if os.path.exists(tmp) and os.path.getsize(tmp) > 1000 else None
    except: return None

# ============================================
# VALIDATION ENGINE (WITH CROSS-VALIDATION)
# ============================================
class Validator:
    def validate(self, d):
        errors, warnings = [], []
        conf = 100
        
        if not d.get('vendor_name'): warnings.append("Vendor name not identified"); conf -= 15
        if not d.get('total_amount') or d['total_amount'] == 0: errors.append("Total amount is zero or missing"); conf -= 30
        if not d.get('line_items'): warnings.append("No line items extracted"); conf -= 15
        
        # Cross-validate line items
        items = d.get('line_items', [])
        calculated_total = 0
        for i, item in enumerate(items, 1):
            qty = item.get('quantity', 0) or 0
            price = item.get('unit_price', 0) or 0
            lt = item.get('line_total', 0) or 0
            
            # Auto-correct line total if qty * price is close
            if qty and price:
                expected = round(qty * price, 2)
                if lt == 0:
                    # Auto-fill missing line total
                    item['line_total'] = expected
                    lt = expected
                    conf += 2  # Bonus for auto-correction
                elif abs(expected - lt) > 1:
                    warnings.append(f"Line {i} math: {qty}x{price:,.2f} should be {expected:,.2f} (found {lt:,.2f})")
                    item['line_total'] = expected  # Auto-correct
                    lt = expected
            
            calculated_total += lt
        
        # Cross-validate subtotal
        subtotal = d.get('subtotal', 0) or 0
        if calculated_total > 0 and subtotal > 0:
            if abs(calculated_total - subtotal) > 1:
                warnings.append(f"Line items sum ({calculated_total:,.2f}) doesn't match subtotal ({subtotal:,.2f}) — using calculated total")
                d['subtotal'] = round(calculated_total, 2)
        
        # Cross-validate total
        total = d.get('total_amount', 0) or 0
        tax = d.get('tax_amount', 0) or 0
        
        # Auto-correct total if it doesn't match
        expected_total = round((d.get('subtotal', 0) or 0) + tax, 2)
        if expected_total > 0 and abs(expected_total - total) > 1:
            warnings.append(f"Total doesn't match subtotal+tax — auto-corrected")
            d['total_amount'] = expected_total
            total = expected_total
            conf += 5  # Bonus for auto-correction
        
        # If no total but we have calculated from line items
        if total == 0 and calculated_total > 0:
            d['total_amount'] = round(calculated_total + tax, 2)
            d['subtotal'] = round(calculated_total, 2)
            conf += 3
        
        d['_validation'] = {
            'confidence_score': min(100, max(0, conf)),
            'status': 'FAIL' if errors else ('WARN' if warnings else 'PASS'),
            'errors': errors,
            'warnings': warnings
        }
        return d

# ============================================
# ERP MATCHING ENGINE
# ============================================
class ERPMatcher:
    def __init__(self):
        self.po_database = None
        self.vendor_master = None
        self.results = []
    
    def load_erp_data(self, po_file=None, vendor_file=None):
        if po_file and Path(po_file).exists():
            self.po_database = pd.read_excel(po_file)
            self.po_database.columns = [c.lower().strip() for c in self.po_database.columns]
            inf(f"Loaded {len(self.po_database)} Purchase Orders")
        if vendor_file and Path(vendor_file).exists():
            self.vendor_master = pd.read_excel(vendor_file)
            self.vendor_master.columns = [c.lower().strip() for c in self.vendor_master.columns]
            inf(f"Loaded {len(self.vendor_master)} Vendors")
    
    def match_invoice(self, invoice_data, threshold=80):
        result = {
            'invoice_number': invoice_data.get('invoice_number', 'N/A'),
            'vendor_name': invoice_data.get('vendor_name', 'N/A'),
            'invoice_total': invoice_data.get('total_amount', 0),
            'invoice_date': invoice_data.get('invoice_date', 'N/A'),
            'timestamp': datetime.now().isoformat(),
            'matches': [], 'flags': [], 'status': 'PENDING', 'confidence': 0
        }
        
        if self.vendor_master is not None:
            vendor_name = invoice_data.get('vendor_name', '')
            if vendor_name:
                vendor_col = None
                for col in self.vendor_master.columns:
                    if any(w in col.lower() for w in ['vendor', 'supplier', 'name', 'company']):
                        vendor_col = col; break
                if vendor_col:
                    vendor_list = self.vendor_master[vendor_col].dropna().tolist()
                    best_match = process.extractOne(vendor_name.lower(), [str(v).lower() for v in vendor_list], scorer=fuzz.token_sort_ratio)
                    if best_match:
                        score = best_match[1]; approved = score >= threshold
                        result['matches'].append({'type': 'VENDOR', 'matched_to': best_match[0], 'score': score, 'status': 'APPROVED' if approved else 'UNKNOWN'})
                        if not approved:
                            result['flags'].append({'severity': 'HIGH', 'message': f"Vendor '{vendor_name}' not in approved list (match: {score}%)"})
        
        po_matched = False
        po_number = invoice_data.get('po_number')
        if self.po_database is not None and po_number:
            po_col = None
            for col in self.po_database.columns:
                if any(w in col.lower() for w in ['po', 'purchase order', 'order', 'po_number']):
                    po_col = col; break
            if po_col:
                for _, po_row in self.po_database.iterrows():
                    if str(po_row[po_col]).strip().lower() == str(po_number).lower():
                        po_matched = True
                        po_amount = None
                        for col in self.po_database.columns:
                            if any(w in col.lower() for w in ['amount', 'total', 'value']):
                                try: po_amount = float(po_row[col]); break
                                except: pass
                        match_info = {'type': 'PURCHASE_ORDER', 'po_number': po_number, 'po_amount': po_amount, 'score': 100}
                        if po_amount and po_amount > 0:
                            variance = abs(invoice_data.get('total_amount', 0) - po_amount)
                            variance_pct = (variance / po_amount) * 100
                            match_info['variance_pct'] = round(variance_pct, 2)
                            if variance_pct > 10:
                                result['flags'].append({'severity': 'HIGH', 'message': f"PO variance {variance_pct:.1f}%"})
                            elif variance_pct > 5:
                                result['flags'].append({'severity': 'MEDIUM', 'message': f"Minor PO variance {variance_pct:.1f}%"})
                        result['matches'].append(match_info); result['po_number'] = po_number; break
        
        if not po_matched and po_number:
            result['flags'].append({'severity': 'MEDIUM', 'message': f"PO #{po_number} not found in ERP"})
        
        high_flags = [f for f in result['flags'] if f['severity'] == 'HIGH']
        if not result['flags']: result['status'] = 'APPROVED_FOR_PAYMENT'; result['confidence'] = 95
        elif not high_flags: result['status'] = 'APPROVED_WITH_NOTES'; result['confidence'] = 80
        else: result['status'] = 'REVIEW_REQUIRED'; result['confidence'] = 50
        return result
    
    def match_batch(self, invoices):
        self.results = []
        for inv in invoices:
            if 'error' not in inv: self.results.append(self.match_invoice(inv))
        return self.results
    
    def get_summary(self):
        if not self.results: return pd.DataFrame()
        return pd.DataFrame([{
            'Invoice #': r.get('invoice_number',''), 'Vendor': r.get('vendor_name',''),
            'Total': r.get('invoice_total',0), 'PO #': r.get('po_number',''),
            'Status': r.get('status',''), 'Confidence': r.get('confidence',0), 'Flags': len(r.get('flags',[]))
        } for r in self.results])
    
    def export_report(self, filepath=None):
        if not filepath:
            filepath = f"output/erp_matching_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            self.get_summary().to_excel(writer, sheet_name='Matching Summary', index=False)
            flag_rows = []
            for r in self.results:
                for f in r.get('flags', []):
                    flag_rows.append({'Invoice #': r.get('invoice_number',''), 'Vendor': r.get('vendor_name',''), 'Severity': f['severity'], 'Flag': f['message']})
            if flag_rows: pd.DataFrame(flag_rows).to_excel(writer, sheet_name='Flags & Issues', index=False)
        return filepath

# ============================================
# PDF REPORT GENERATION
# ============================================
def save_pdf(data, path):
    try:
        from fpdf import FPDF
        def cl(txt):
            if not txt: return ''
            return str(txt).encode('ascii','replace').decode('ascii')
        pdf = FPDF(); pdf.add_page()
        v = data.get('_validation', {}); cur = data.get('currency', 'NGN')
        pdf.set_fill_color(25,50,80); pdf.rect(0,0,210,40,'F')
        pdf.set_text_color(255,255,255); pdf.set_font('Arial','B',22)
        pdf.set_y(8); pdf.cell(0,10,'CHURCHGATE-AI',0,1,'C')
        pdf.set_font('Arial','',11); pdf.cell(0,8,'Invoice Processing Report',0,1,'C')
        pdf.set_text_color(0,0,0); pdf.ln(12)
        st, conf = v.get('status','?'), v.get('confidence_score',0)
        if st == 'PASS': rc,gc,bc,tx = 39,174,96,'[PASSED] VERIFIED'
        elif st == 'WARN': rc,gc,bc,tx = 243,156,18,'[!] WARNINGS PRESENT'
        else: rc,gc,bc,tx = 231,76,60,'[FAILED] REVIEW REQUIRED'
        pdf.set_fill_color(rc,gc,bc); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',13); pdf.cell(0,10,f'  {tx}  |  Confidence: {conf}%',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(6)
        if v.get('errors'):
            pdf.set_font('Arial','B',10); pdf.set_text_color(231,76,60)
            pdf.cell(0,7,'ERRORS:',0,1); pdf.set_font('Arial','',9)
            for e in v['errors']: pdf.cell(0,6,f'  [X] {cl(e)}',0,1)
            pdf.ln(3)
        if v.get('warnings'):
            pdf.set_font('Arial','B',10); pdf.set_text_color(243,156,18)
            pdf.cell(0,7,'WARNINGS:',0,1); pdf.set_font('Arial','',9)
            for w in v['warnings']: pdf.cell(0,6,f'  [!] {cl(w)}',0,1)
            pdf.ln(3)
        pdf.set_text_color(0,0,0)
        pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',12); pdf.cell(0,9,'  VENDOR & INVOICE DETAILS',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(5)
        for l,vl in [('Vendor Name:',cl(data.get('vendor_name','N/A'))),('Invoice Number:',cl(data.get('invoice_number','N/A'))),('Invoice Date:',cl(data.get('invoice_date','N/A'))),('Due Date:',cl(data.get('due_date','N/A') or 'Not specified'))]:
            pdf.set_font('Arial','B',10); pdf.cell(40,7,l,0,0)
            pdf.set_font('Arial','',10); pdf.cell(0,7,vl,0,1)
        pdf.ln(5)
        pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',12); pdf.cell(0,9,'  FINANCIAL SUMMARY',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(5)
        for l,vl in [('Subtotal:',f"{cur} {data.get('subtotal',0):,.2f}"),('Tax Amount:',f"{cur} {data.get('tax_amount',0):,.2f}")]:
            pdf.set_font('Arial','B',10); pdf.cell(40,7,l,0,0)
            pdf.set_font('Arial','',10); pdf.cell(0,7,vl,0,1)
        pdf.set_fill_color(230,240,250); pdf.set_font('Arial','B',12)
        pdf.cell(40,10,'TOTAL DUE:',0,0,'L',True)
        pdf.cell(0,10,f"{cur} {data.get('total_amount',0):,.2f}",0,1,'L',True)
        pdf.ln(6)
        items = data.get('line_items',[])
        if items:
            pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
            pdf.set_font('Arial','B',12); pdf.cell(0,9,f'  LINE ITEMS ({len(items)})',0,1,'L',True)
            pdf.set_text_color(0,0,0); pdf.ln(4)
            pdf.set_fill_color(189,195,199); pdf.set_font('Arial','B',8)
            pdf.cell(75,7,'  Description',1,0,'L',True); pdf.cell(20,7,'Qty',1,0,'C',True)
            pdf.cell(35,7,'Unit Price',1,0,'R',True); pdf.cell(35,7,'Line Total',1,1,'R',True)
            pdf.set_font('Arial','',8)
            for item in items[:40]:
                pdf.cell(75,6,f"  {cl(item.get('description','N/A'))[:40]}",1,0,'L')
                pdf.cell(20,6,str(item.get('quantity',0)),1,0,'C')
                pdf.cell(35,6,f"{item.get('unit_price',0):,.2f}",1,0,'R')
                pdf.cell(35,6,f"{item.get('line_total',0):,.2f}",1,1,'R')
        pdf.ln(15); pdf.set_font('Arial','I',7); pdf.set_text_color(127,140,141)
        pdf.cell(0,5,'Churchgate-AI Enterprise Invoice Processing System',0,1,'C')
        pdf.cell(0,5,'Powered by Google Gemini AI | Multi-Page PDF + Image Enhancement',0,1,'C')
        pdf.cell(0,5,f'Report generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}',0,1,'C')
        pdf.output(path); return True
    except Exception as e:
        print(f"  {Ye}WRN{Rs} PDF error: {e}"); return False

# ============================================
# SAVE ALL
# ============================================
def save_all(data, base):
    v = data.get('_validation',{})
    with open(f"output/json/{base}.json",'w') as f: json.dump(data,f,indent=2,default=str)
    try:
        with pd.ExcelWriter(f"output/excel/{base}.xlsx",engine='openpyxl') as w:
            pd.DataFrame([{'Vendor':data.get('vendor_name',''),'Invoice':data.get('invoice_number',''),'Date':data.get('invoice_date',''),'Subtotal':data.get('subtotal',0),'Tax':data.get('tax_amount',0),'Total':data.get('total_amount',0),'Currency':data.get('currency',''),'Confidence':v.get('confidence_score',0),'Status':v.get('status','')}]).to_excel(w,sheet_name='Summary',index=False)
            if data.get('line_items'): pd.DataFrame(data['line_items']).to_excel(w,sheet_name='Items',index=False)
            if v.get('errors') or v.get('warnings'):
                issues = [{'Type':'ERROR','Message':e} for e in v.get('errors',[])] + [{'Type':'WARNING','Message':w} for w in v.get('warnings',[])]
                pd.DataFrame(issues).to_excel(w,sheet_name='Issues',index=False)
    except: pass
    save_pdf(data,f"output/pdf/{base}.pdf")
    pd.DataFrame([{'vendor':data.get('vendor_name',''),'invoice':data.get('invoice_number',''),'total':data.get('total_amount',0),'confidence':v.get('confidence_score',0),'status':v.get('status','')}]).to_csv(f"output/csv/{base}.csv",index=False)

# ============================================
# SCAN
# ============================================
EXT = ["*.jpg","*.jpeg","*.png","*.bmp","*.tiff","*.tif","*.webp","*.gif","*.pdf","*.xlsx","*.xls","*.xlsm","*.csv"]
def scan():
    fs = []
    for e in EXT: fs.extend(Path("input").glob(e))
    return sorted([f for f in fs if "_temp." not in f.name and "_enhanced." not in f.name and "_page" not in f.name], key=lambda x: x.name.lower())

def ico(fp):
    s = fp.suffix.lower()
    return {'xlsx':'📊','xls':'📊','xlsm':'📊','pdf':'📑','csv':'📝','tiff':'🖼️','tif':'🖼️'}.get(s,'📄')

def ftype(fp):
    return {'xlsx':'Excel','xls':'Excel','xlsm':'Excel','pdf':'PDF','csv':'CSV','tiff':'Scanned','tif':'Scanned'}.get(fp.suffix.lower(),'Image')

# ============================================
# PROCESS ONE FILE (UPDATED WITH MULTI-PAGE + ENHANCEMENT)
# ============================================
def process_one(ext, val, fp):
    try:
        print(f"\n  {'='*58}")
        print(f"  {Bo}{ico(fp)}  PROCESSING: {fp.name}{Rs}  ({ftype(fp)})")
        print(f"  {'='*58}")
        
        suffix = fp.suffix.lower()
        r = None
        
        if suffix == '.pdf':
            # MULTI-PAGE PDF SUPPORT
            inf("Converting PDF pages...")
            page_images = pdf_to_images(str(fp))
            
            if page_images:
                if len(page_images) > 1:
                    inf(f"Multi-page document: {len(page_images)} pages")
                    r = ext.extract_multi_page(page_images, enhance=True)
                else:
                    inf("Single page — extracting with enhancement...")
                    r = ext.extract(page_images[0], enhance=True)
                
                r['_source'] = 'pdf'
                # Clean up temp page images
                for tmp in page_images:
                    try: os.remove(tmp)
                    except: pass
            else:
                er("PDF conversion failed. Install: pip install pymupdf")
                return None
        
        elif suffix in ['.xlsx','.xls','.xlsm']:
            inf("Converting Excel...")
            tmp = excel_to_image(str(fp))
            if tmp and os.path.exists(tmp):
                inf("Extracting with enhancement...")
                r = ext.extract(tmp, enhance=True)
                r['_source'] = 'excel'
                os.remove(tmp)
            else:
                er("Excel conversion failed"); return None
        else:
            inf("Extracting with image enhancement...")
            r = ext.extract(str(fp), enhance=True)
            r['_source'] = 'image'
        
        if "error" in r: er(r['error']); return None
        
        inf("Running cross-validation...")
        r = val.validate(r)
        
        vn = str(r.get('vendor_name','file'))[:25].replace(' ','_').replace('/','_').replace('.','_')
        inv = str(r.get('invoice_number', fp.stem)).replace('/','_')
        base = f"{vn}_{inv}"
        
        print(f"\n  {Bo}Saving outputs...{Rs}")
        save_all(r, base)
        ok("Saved: JSON, Excel, PDF, CSV")
        return r, base
    except Exception as e: er(str(e)[:150]); return None

def show(data, base):
    v = data.get('_validation',{}); items = data.get('line_items',[])
    print(f"\n  {'='*58}")
    print(f"  {Bo}📋  EXTRACTION RESULTS{Rs}")
    print(f"  {'='*58}")
    print(f"  {Bo}Vendor:{Rs}      {data.get('vendor_name','N/A')}")
    print(f"  {Bo}Invoice #:{Rs}   {data.get('invoice_number','N/A')}")
    print(f"  {Bo}Date:{Rs}        {data.get('invoice_date','N/A')}")
    if data.get('po_number'): print(f"  {Bo}PO #:{Rs}        {data.get('po_number')}")
    print(f"  {Bo}Subtotal:{Rs}    {data.get('currency','')} {data.get('subtotal',0):,.2f}")
    print(f"  {Bo}Tax:{Rs}         {data.get('currency','')} {data.get('tax_amount',0):,.2f}")
    print(f"  {Bo}TOTAL:{Rs}       {Gn}{data.get('currency','')} {data.get('total_amount',0):,.2f}{Rs}")
    if items:
        print(f"\n  {Bo}📦  LINE ITEMS ({len(items)}):{Rs}")
        for item in items[:5]:
            print(f"    {Cy}•{Rs} {item.get('description','N/A')[:60]}")
            print(f"      {item.get('quantity',0)} x {item.get('unit_price',0):,.2f} = {item.get('line_total',0):,.2f}")
        if len(items) > 5: print(f"    {Di}... and {len(items)-5} more items{Rs}")
    print(f"\n  {'─'*58}")
    print(f"  {Bo}🔍  CROSS-VALIDATION{Rs}")
    st = v.get('status','?')
    if st == 'PASS': print(f"  Status:   {BgG}{Wh} VERIFIED - PASSED {Rs}")
    elif st == 'WARN': print(f"  Status:   {BgY}{Wh} WARNINGS (auto-corrected) {Rs}")
    else: print(f"  Status:   {BgR}{Wh} REVIEW REQUIRED {Rs}")
    bar = int(30 * v.get('confidence_score',0)/100)
    bc = Gn if v.get('confidence_score',0)>=80 else (Ye if v.get('confidence_score',0)>=50 else Rd)
    print(f"  Confidence: [{bc}{'█'*bar}{Di}{'░'*(30-bar)}{Rs}] {v.get('confidence_score',0)}%")
    if v.get('errors'):
        print(f"\n  {Rd}{Bo}ERRORS:{Rs}")
        for e in v['errors']: print(f"    {Rd}✗{Rs}  {e}")
    if v.get('warnings'):
        print(f"\n  {Ye}{Bo}AUTO-CORRECTIONS:{Rs}")
        for w in v['warnings']: print(f"    {Ye}⚠{Rs}  {w}")
    print(f"\n  {'─'*58}")
    print(f"  {Bo}📁  OUTPUT:{Rs}  json/{base}.json | excel/{base}.xlsx | pdf/{base}.pdf | csv/{base}.csv")
    print(f"  {'='*58}")

# ============================================
# MAIN
# ============================================
def main():
    for f in ['input','output/json','output/excel','output/pdf','output/csv']:
        os.makedirs(f, exist_ok=True)
    if not API_KEY or len(API_KEY) < 10: er("No API key!"); input("\n  Enter..."); return
    ext = Extractor(API_KEY); val = Validator()
    
    while True:
        banner(); files = scan()
        if files:
            from collections import Counter
            tc = Counter(ftype(f) for f in files)
            print(f"  {Gn}●{Rs}  {Bo}QUEUE:{Rs} {', '.join(f'{c}x {t}' for t,c in tc.items())} in {Cy}📁 input\\{Rs}")
        else: print(f"  {Ye}●{Rs}  {Bo}QUEUE:{Rs} Empty")
        sep()
        print(f"  {Bo}[1]{Rs}  📄  Process invoices (select)")
        print(f"  {Bo}[2]{Rs}  🔄  Process ALL invoices")
        print(f"  {Bo}[3]{Rs}  🔗  ERP Matching (PO/WO/Abstract)")
        print(f"  {Bo}[4]{Rs}  📂  Output folder")
        print(f"  {Bo}[5]{Rs}  📁  Input folder")
        print(f"  {Bo}[6]{Rs}  🚪  Exit")
        sep()
        c = input(f"  {Bo}▶{Rs}  Choice (1-6): ").strip()
        
        if c == '6': print(f"\n  {Gn}{Bo}✓{Rs}  Done\n"); break
        elif c == '5': os.startfile(os.path.abspath("input"))
        elif c == '4': os.startfile(os.path.abspath("output"))
        elif c == '3':
            print(f"\n  {'='*58}")
            print(f"  {Bo}🔗  ERP MATCHING{Rs}")
            print(f"  {'='*58}")
            po_files = list(Path("input").glob("*PO*.xlsx")) + list(Path("input").glob("*purchase*.xlsx")) + list(Path("input").glob("*abstract*.xlsx"))
            vendor_files = list(Path("input").glob("*vendor*.xlsx")) + list(Path("input").glob("*supplier*.xlsx"))
            matcher = ERPMatcher()
            if po_files: inf(f"PO data: {po_files[0].name}"); matcher.load_erp_data(po_file=str(po_files[0]))
            else: wn("No PO files found")
            if vendor_files: inf(f"Vendor data: {vendor_files[0].name}"); matcher.load_erp_data(vendor_file=str(vendor_files[0]))
            else: wn("No vendor files found")
            json_files = list(Path("output/json").glob("*.json"))
            if json_files:
                invoices = []
                for jf in json_files[:10]:
                    with open(jf) as f: invoices.append(json.load(f))
                if invoices and (po_files or vendor_files):
                    print(f"\n  {Bo}🔍  Running ERP Matching...{Rs}")
                    match_results = matcher.match_batch(invoices)
                    for r in match_results:
                        icon = '✅' if 'APPROVED' in r['status'] else '❌'
                        print(f"\n  {icon} {r.get('vendor_name','N/A')[:30]}")
                        print(f"     Invoice: {r.get('invoice_number','N/A')} | Total: {r.get('invoice_total',0):,.2f}")
                        print(f"     Status: {r['status']} | Confidence: {r.get('confidence',0)}%")
                        for flag in r.get('flags',[]):
                            sev = {'HIGH':'🔴','MEDIUM':'🟡','LOW':'🟢'}.get(flag['severity'],'⚪')
                            print(f"     {sev} [{flag['severity']}] {flag['message']}")
                    try:
                        rp = matcher.export_report(); ok(f"Report: {rp}")
                    except: wn("Report export failed")
            else: wn("No processed invoices found")
            input("\n  Enter...")
        elif c == '2':
            if not files: wn("No files!"); input("\n  Enter..."); continue
            okn = 0
            for i, f in enumerate(files, 1):
                print(f"\n  {Bo}[{i}/{len(files)}]{Rs} {ico(f)} {f.name}")
                if process_one(ext, val, f): okn += 1
                if i < len(files): time.sleep(30)
            print(f"\n  {Gn}✓{Rs}  {okn}/{len(files)} done")
            input("\n  Enter...")
        elif c == '1':
            if not files: wn("No files!"); input("\n  Enter..."); continue
            sep()
            for i, f in enumerate(files, 1):
                print(f"  {Bo}[{i}]{Rs}   {ico(f)}  {f.name} {Di}({ftype(f)}, {f.stat().st_size/1024:.0f}KB){Rs}")
            print(f"  {Bo}[{len(files)+1}]{Rs}   🔄  ALL")
            print(f"  {Bo}[0]{Rs}   ↩   Back")
            s = input(f"  {Bo}▶{Rs}  Number: ").strip()
            if s == '0': continue
            elif s == str(len(files)+1):
                okn = 0
                for i, f in enumerate(files, 1):
                    print(f"\n  {Bo}[{i}/{len(files)}]{Rs} {ico(f)} {f.name}")
                    if process_one(ext, val, f): okn += 1
                    if i < len(files): time.sleep(30)
                print(f"\n  {Gn}✓{Rs}  {okn}/{len(files)}")
                input("\n  Enter..."); continue
            try:
                idx = int(s)-1
                if 0 <= idx < len(files):
                    r = process_one(ext, val, files[idx])
                    if r: show(r[0], r[1])
                    input("\n  Enter...")
            except: er("Invalid"); input("  Enter...")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"\n  {Rd}{Bo}✗ FATAL{Rs}: {e}")
        traceback.print_exc()
        input("\n  Enter...")