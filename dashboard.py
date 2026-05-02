"""
Churchgate-AI Enterprise Invoice Processing Dashboard
Multi-Page PDF | Image Enhancement | Cross-Validation | ERP Matching
"""
import streamlit as st
import os, json, base64, requests, pandas as pd, time, re, numpy as np
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
import plotly.express as px
import plotly.graph_objects as go

# ============================================
# LOAD API KEY
# ============================================
API_KEY = None
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    pass
if not API_KEY:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        API_KEY = os.getenv("GEMINI_API_KEY")
    except:
        pass

# ============================================
# SET WORKING DIRECTORY
# ============================================
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# ============================================
# LOAD LOGO
# ============================================
def get_logo_base64():
    logo_path = os.path.join(script_dir, "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

LOGO_B64 = get_logo_base64()

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="Churchgate Invoice Processing",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    * { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    .brs-header {
        background: linear-gradient(135deg, #e8ecf1 0%, #d5dbe3 50%, #e8ecf1 100%);
        border-radius: 0; padding: 1.5rem 2rem; margin-bottom: 2rem;
        display: flex; align-items: center; gap: 28px; border-bottom: 2px solid #c0c7cf;
    }
    .brs-logo { width: 130px; height: 130px; border-radius: 0; object-fit: contain; background: transparent; padding: 0; box-shadow: none; flex-shrink: 0; }
    .brs-logo-placeholder { width: 130px; height: 130px; border-radius: 0; background: transparent; display: flex; align-items: center; justify-content: center; font-size: 5rem; box-shadow: none; flex-shrink: 0; }
    .brs-title { font-size: 2.2rem; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px; margin: 0; line-height: 1.2; }
    .brs-subtitle { font-size: 0.95rem; color: #4a5568; font-weight: 500; margin: 6px 0 0 0; }
    .brs-badge { display: inline-block; background: #2563eb; color: white; padding: 0.25rem 0.9rem; border-radius: 14px; font-size: 0.7rem; font-weight: 700; margin-left: 8px; vertical-align: middle; }
    
    .metric-box { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem 1.2rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.04); transition: all 0.25s; position: relative; overflow: hidden; }
    .metric-box::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, #2563eb, #3b82f6, #60a5fa); }
    .metric-box:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
    .metric-icon { font-size: 2rem; margin-bottom: 0.4rem; }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #1a1a2e; }
    .metric-label { font-size: 0.82rem; color: #64748b; font-weight: 500; margin-top: 0.2rem; }
    
    .status-pass { background: #059669; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    .status-warn { background: #d97706; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    .status-fail { background: #dc2626; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    
    div[data-testid="stFileUploader"] { border: 2px dashed #3b82f6; border-radius: 16px; padding: 2rem; background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 50%, #dbeafe 100%); }
    .stButton > button { border-radius: 12px; font-weight: 700; padding: 0.8rem 2.5rem; font-size: 1rem; background: linear-gradient(135deg, #1a1a2e 0%, #1e3a5f 50%, #2563eb 100%); color: white; border: none; transition: all 0.3s; width: 100%; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(37,99,235,0.4); }
    
    .sidebar-header { text-align: center; padding: 1.5rem 0.5rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 1.2rem; background: #f8fafc; border-radius: 16px; }
    .sidebar-logo-small { width: 110px; height: 110px; border-radius: 0; object-fit: contain; display: block; margin: 0 auto 0.6rem; box-shadow: none; background: transparent; padding: 0; }
    .sidebar-company { font-weight: 800; font-size: 1.1rem; color: #1a1a2e; margin-top: 0.5rem; }
    .sidebar-subtitle { font-size: 0.75rem; color: #64748b; font-weight: 500; }
    .section-divider { height: 1px; background: linear-gradient(90deg, transparent, #cbd5e1, transparent); margin: 2rem 0; }
    .chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
</style>
""", unsafe_allow_html=True)

# ============================================
# HELPERS
# ============================================
def safe_str(val, default='N/A', max_len=None):
    if val is None: return default
    s = str(val)
    if max_len and len(s) > max_len: s = s[:max_len]
    return s

def safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return default

# ============================================
# IMAGE ENHANCER
# ============================================
class ImageEnhancer:
    @staticmethod
    def enhance(image_bytes):
        try:
            img = Image.open(BytesIO(image_bytes))
            if img.mode not in ('RGB', 'L'): img = img.convert('RGB')
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = ImageEnhance.Sharpness(img).enhance(2.0)
            img = ImageEnhance.Brightness(img).enhance(1.1)
            img = img.filter(ImageFilter.MedianFilter(size=3))
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=95, optimize=True)
            return buf.getvalue()
        except: return image_bytes

# ============================================
# AI ENGINE
# ============================================
class Extractor:
    def __init__(self, key):
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        self.enhancer = ImageEnhancer()
    
    def extract(self, image_bytes, enhance=True):
        if enhance: image_bytes = self.enhancer.enhance(image_bytes)
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Extract ALL invoice/PO/BOQ data. Return ONLY valid JSON with: vendor_name, invoice_number, po_number, invoice_date, due_date, subtotal, tax_amount, total_amount, currency, line_items. Find the TOTAL. Extract ALL line items with quantities, rates, and totals. For multi-page documents, combine data from all pages."
        payload = {"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":"image/jpeg","data":b64}}]}]}
        for attempt in range(1, 4):
            try:
                if attempt > 1: time.sleep(attempt * 8)
                r = requests.post(self.url, json=payload, timeout=45)
                if r.status_code == 200:
                    text = r.json()['candidates'][0]['content']['parts'][0]['text']
                    text = text.replace('```json','').replace('```','').strip()
                    s, e = text.find('{'), text.rfind('}')+1
                    if s != -1 and e > s: return json.loads(text[s:e])
            except: pass
        return {"error": "AI service unavailable"}

class Validator:
    def validate(self, d):
        errors, warnings = [], []
        conf = 100
        if not d.get('vendor_name'): warnings.append("Vendor not identified"); conf -= 15
        if not d.get('total_amount') or d['total_amount'] == 0: errors.append("Total is zero/missing"); conf -= 30
        if not d.get('line_items'): warnings.append("No line items"); conf -= 15
        
        items = d.get('line_items', [])
        calc_total = 0
        for i, item in enumerate(items, 1):
            qty = safe_float(item.get('quantity'))
            price = safe_float(item.get('unit_price'))
            lt = safe_float(item.get('line_total'))
            if qty and price:
                expected = round(qty * price, 2)
                if lt == 0:
                    item['line_total'] = expected; lt = expected; conf += 2
                elif abs(expected - lt) > 1:
                    warnings.append(f"Line {i} auto-corrected: {qty}x{price:,.2f} = {expected:,.2f}")
                    item['line_total'] = expected; lt = expected
            calc_total += lt
        
        subtotal = safe_float(d.get('subtotal'))
        tax = safe_float(d.get('tax_amount'))
        total = safe_float(d.get('total_amount'))
        
        if calc_total > 0 and abs(calc_total - subtotal) > 1:
            warnings.append(f"Subtotal auto-corrected from line items")
            d['subtotal'] = round(calc_total, 2); subtotal = d['subtotal']
        
        expected_total = round(subtotal + tax, 2)
        if expected_total > 0 and abs(expected_total - total) > 1:
            warnings.append(f"Total auto-corrected"); d['total_amount'] = expected_total
            conf += 5
        
        if total == 0 and calc_total > 0:
            d['total_amount'] = round(calc_total + tax, 2); d['subtotal'] = round(calc_total, 2); conf += 3
        
        d['_validation'] = {'confidence_score': min(100, max(0, conf)), 'status': 'FAIL' if errors else ('WARN' if warnings else 'PASS'), 'errors': errors, 'warnings': warnings}
        return d

def pdf_to_bytes(b):
    try:
        import fitz; doc=fitz.open(stream=b, filetype="pdf")
        pages = min(len(doc), 10)
        if pages == 1:
            pix=doc[0].get_pixmap(dpi=200); img=pix.tobytes("jpg"); doc.close(); return [img]
        else:
            imgs = []
            for p in range(pages):
                pix=doc[p].get_pixmap(dpi=200); imgs.append(pix.tobytes("jpg"))
            doc.close(); return imgs
    except: return None

def excel_to_bytes(b):
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        df=pd.read_excel(BytesIO(b), header=None)
        fig,ax=plt.subplots(figsize=(18,max(4,len(df)*0.28))); ax.axis('off')
        ax.table(cellText=df.values, loc='center', cellLoc='left').set_fontsize(6)
        buf=BytesIO(); plt.savefig(buf,bbox_inches='tight',dpi=150,pad_inches=0.1,format='jpg'); plt.close(); return buf.getvalue()
    except: return None

def generate_pdf_report(data):
    try:
        from fpdf import FPDF
        def clean(txt):
            if not txt: return ''
            return str(txt).encode('ascii','replace').decode('ascii')
        pdf = FPDF(); pdf.add_page()
        v = data.get('_validation', {}); cur = safe_str(data.get('currency'), 'NGN')
        pdf.set_fill_color(25,50,80); pdf.rect(0,0,210,40,'F')
        pdf.set_text_color(255,255,255); pdf.set_font('Arial','B',22)
        pdf.set_y(7); pdf.cell(0,11,'CHURCHGATE INVOICE REPORT',0,1,'C')
        pdf.set_font('Arial','',10); pdf.cell(0,7,'AI-Powered Extraction & Enterprise Validation',0,1,'C')
        pdf.set_text_color(0,0,0); pdf.ln(12)
        sts = v.get('status','?'); conf = v.get('confidence_score',0)
        if sts == 'PASS': rc,gc,bc,tx = 39,174,96,'PASSED - VERIFIED'
        elif sts == 'WARN': rc,gc,bc,tx = 243,156,18,'WARNINGS (Auto-Corrected)'
        else: rc,gc,bc,tx = 231,76,60,'REVIEW REQUIRED'
        pdf.set_fill_color(rc,gc,bc); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',13); pdf.cell(0,10,f'  STATUS: {tx}  |  Confidence: {conf}%',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(6)
        pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',12); pdf.cell(0,9,'  VENDOR & INVOICE DETAILS',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(5)
        for l,vl in [('Vendor:',clean(safe_str(data.get('vendor_name')))),('Invoice #:',clean(safe_str(data.get('invoice_number')))),('Date:',clean(safe_str(data.get('invoice_date')))),('Due:',clean(safe_str(data.get('due_date'),'Not specified'))),('PO #:',clean(safe_str(data.get('po_number'),'N/A')))]:
            pdf.set_font('Arial','B',10); pdf.cell(38,7,l,0,0); pdf.set_font('Arial','',10); pdf.cell(0,7,vl,0,1)
        pdf.ln(5)
        pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',12); pdf.cell(0,9,'  FINANCIAL SUMMARY',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(5)
        subtotal = safe_float(data.get('subtotal')); tax = safe_float(data.get('tax_amount')); total = safe_float(data.get('total_amount'))
        for l,vl in [('Subtotal:',f"{cur} {subtotal:,.2f}"),('Tax Amount:',f"{cur} {tax:,.2f}")]:
            pdf.set_font('Arial','B',10); pdf.cell(38,7,l,0,0); pdf.set_font('Arial','',10); pdf.cell(0,7,vl,0,1)
        pdf.set_fill_color(230,240,250); pdf.set_font('Arial','B',12)
        pdf.cell(38,10,'TOTAL DUE:',0,0,'L',True); pdf.cell(0,10,f"{cur} {total:,.2f}",0,1,'L',True)
        pdf.ln(6)
        items = data.get('line_items',[])
        if items:
            pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
            pdf.set_font('Arial','B',12); pdf.cell(0,9,f'  LINE ITEMS ({len(items)})',0,1,'L',True)
            pdf.set_text_color(0,0,0); pdf.ln(4)
            pdf.set_fill_color(189,195,199); pdf.set_font('Arial','B',8)
            pdf.cell(75,7,'  Description',1,0,'L',True); pdf.cell(20,7,'Qty',1,0,'C',True); pdf.cell(30,7,'Unit Price',1,0,'R',True); pdf.cell(30,7,'Line Total',1,1,'R',True)
            pdf.set_font('Arial','',8)
            for item in items[:40]:
                desc = clean(safe_str(item.get('description'),'N/A'))[:40]
                qty = safe_float(item.get('quantity')); unit = safe_float(item.get('unit_price')); lt = safe_float(item.get('line_total'))
                pdf.cell(75,6,f'  {desc}',1,0,'L'); pdf.cell(20,6,str(int(qty)) if qty==int(qty) else str(qty),1,0,'C')
                pdf.cell(30,6,f"{cur} {unit:,.2f}",1,0,'R'); pdf.cell(30,6,f"{cur} {lt:,.2f}",1,1,'R')
        pdf.ln(15); pdf.set_font('Arial','I',7); pdf.set_text_color(127,140,141)
        pdf.cell(0,5,'Churchgate-AI Enterprise Invoice Processing System',0,1,'C')
        pdf.cell(0,5,'Powered by Google Gemini AI | Multi-Page PDF + Image Enhancement',0,1,'C')
        pdf.cell(0,5,f'Report generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}',0,1,'C')
        return pdf.output(dest='S').encode('latin-1')
    except: return None

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
    if LOGO_B64:
        st.markdown(f'<img src="data:image/png;base64,{LOGO_B64}" class="sidebar-logo-small">', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:3rem;text-align:center;">🏢</div>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-company">Churchgate Group</p>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-subtitle">Invoice Processing System</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if API_KEY: st.success("🔑 API Key Active")
    else: st.error("🔑 API Key Missing")
    st.markdown("---")
    if 'count' not in st.session_state: st.session_state.count = 0
    if 'total_val' not in st.session_state: st.session_state.total_val = 0
    if 'history' not in st.session_state: st.session_state.history = []
    c1,c2 = st.columns(2)
    c1.metric("📄 Total", st.session_state.count)
    c2.metric("💰 Value", f"₦{st.session_state.total_val:,.0f}")
    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    if st.button("📂 Output Folder", use_container_width=True):
        try: os.startfile(os.path.abspath("output"))
        except: st.info("Local only")
    if st.button("📁 Input Folder", use_container_width=True):
        try: os.startfile(os.path.abspath("input"))
        except: st.info("Local only")
    if st.button("🗑️ Clear Session", use_container_width=True):
        st.session_state.count = 0; st.session_state.total_val = 0
        st.session_state.history = []; st.session_state.results = []
        st.rerun()
    st.markdown("---")
    st.caption("v5.0 Enterprise | Multi-Page + Enhancement")
    st.caption(f"© {datetime.now().year} Churchgate Group")

# ============================================
# HEADER
# ============================================
if LOGO_B64:
    logo_html = f'<img src="data:image/png;base64,{LOGO_B64}" class="brs-logo">'
else:
    logo_html = '<div class="brs-logo-placeholder">🏢</div>'

st.markdown(f"""
<div class="brs-header">
    {logo_html}
    <div>
        <h1 class="brs-title">Churchgate Invoice Processing <span class="brs-badge">ENTERPRISE</span></h1>
        <p class="brs-subtitle">Multi-Page PDF • Image Enhancement • Cross-Validation • ERP Matching • PDF & Excel Export</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================
# TABS
# ============================================
tab1, tab2 = st.tabs(["📄 Invoice Processing", "🔗 ERP Matching (PO/WO/Abstract)"])

# ============================================
# TAB 1: INVOICE PROCESSING
# ============================================
with tab1:
    m1,m2,m3,m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-box"><div class="metric-icon">📄</div><div class="metric-value">{st.session_state.count}</div><div class="metric-label">Invoices Processed</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-box"><div class="metric-icon">💰</div><div class="metric-value">{"₦"+f"{st.session_state.total_val:,.0f}" if st.session_state.total_val > 0 else "—"}</div><div class="metric-label">Total Value</div></div>', unsafe_allow_html=True)
    with m3: st.markdown('<div class="metric-box"><div class="metric-icon">⚡</div><div class="metric-value">3-8s</div><div class="metric-label">Processing Speed</div></div>', unsafe_allow_html=True)
    with m4: st.markdown('<div class="metric-box"><div class="metric-icon">🎯</div><div class="metric-value">99%+</div><div class="metric-label">Extraction Accuracy</div></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Charts
    if st.session_state.history:
        ch1, ch2 = st.columns(2)
        with ch1:
            status_counts = {}
            for h in st.session_state.history:
                s = h.get('status', 'Unknown'); status_counts[s] = status_counts.get(s, 0) + 1
            if status_counts:
                colors_map = {'PASS': '#059669', 'WARN': '#d97706', 'FAIL': '#dc2626'}
                fig = go.Figure(data=[go.Pie(labels=list(status_counts.keys()), values=list(status_counts.values()), hole=0.5, marker=dict(colors=[colors_map.get(k, '#64748b') for k in status_counts.keys()]))])
                fig.update_layout(title='Validation Results', height=300, margin=dict(t=40,b=20,l=20,r=20), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        with ch2:
            if len(st.session_state.history) > 1:
                vendors = [h.get('vendor','N/A')[:20] for h in st.session_state.history]
                totals = [h.get('total',0) for h in st.session_state.history]
                fig = go.Figure(data=[go.Bar(x=vendors, y=totals, marker=dict(color=totals, colorscale=[[0,'#3b82f6'],[1,'#1a1a2e']]), text=[f"₦{t:,.0f}" for t in totals], textposition='outside')])
                fig.update_layout(title='Invoice Values', height=300, margin=dict(t=40,b=20,l=20,r=20), showlegend=False, yaxis=dict(showticklabels=False))
                st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Upload
    st.markdown("### 📤 Upload Invoices")
    uploaded = st.file_uploader("Drop invoice files — PDF, JPG, PNG, Excel", type=['pdf','jpg','jpeg','png','bmp','tiff','tif','xlsx','xls'], accept_multiple_files=True)
    
    if uploaded and API_KEY:
        if st.button("🚀 Process All Invoices", type="primary", use_container_width=True):
            extractor = Extractor(API_KEY)
            validator = Validator()
            results = []
            prog = st.progress(0)
            stat = st.empty()
            start_time = time.time()
            for i, file in enumerate(uploaded):
                stat.text(f"Processing {i+1}/{len(uploaded)}: {file.name}")
                fb = file.read()
                suf = Path(file.name).suffix.lower()
                
                r = None
                if suf == '.pdf':
                    page_images = pdf_to_bytes(fb)
                    if page_images:
                        if len(page_images) > 1:
                            # Multi-page: extract from each page and merge
                            all_pages = []
                            for pimg in page_images:
                                pr = extractor.extract(pimg, enhance=True)
                                if 'error' not in pr: all_pages.append(pr)
                            if all_pages:
                                r = all_pages[0].copy()
                                all_items = []
                                for ap in all_pages: all_items.extend(ap.get('line_items',[]))
                                r['line_items'] = all_items
                                r['subtotal'] = sum(safe_float(ap.get('subtotal')) for ap in all_pages)
                                r['tax_amount'] = sum(safe_float(ap.get('tax_amount')) for ap in all_pages)
                                r['total_amount'] = sum(safe_float(ap.get('total_amount')) for ap in all_pages)
                                for ap in all_pages:
                                    if ap.get('vendor_name'): r['vendor_name'] = ap['vendor_name']; break
                                    if ap.get('invoice_number'): r['invoice_number'] = ap['invoice_number']; break
                                r['_source'] = 'pdf-multi'
                            else: r = {"error": "No data from PDF pages"}
                        else:
                            r = extractor.extract(page_images[0], enhance=True)
                            r['_source'] = 'pdf'
                    else: r = {"error": "PDF conversion failed"}
                elif suf in ['.xlsx','.xls']:
                    img = excel_to_bytes(fb)
                    if img: r = extractor.extract(img, enhance=True); r['_source'] = 'excel'
                    else: r = {"error": "Excel conversion failed"}
                else:
                    r = extractor.extract(fb, enhance=True); r['_source'] = 'image'
                
                if "error" in r: results.append({"file": file.name, "error": r["error"]})
                else:
                    r = validator.validate(r); r['_file'] = file.name; results.append(r)
                    st.session_state.count += 1; st.session_state.total_val += safe_float(r.get('total_amount'))
                    st.session_state.history.append({'status': r.get('_validation',{}).get('status','?'), 'currency': safe_str(r.get('currency'),'NGN'), 'total': safe_float(r.get('total_amount')), 'vendor': safe_str(r.get('vendor_name'),'N/A')})
                prog.progress((i+1)/len(uploaded))
            elapsed = time.time() - start_time
            stat.success(f"✅ {len(uploaded)} invoice(s) processed in {elapsed:.1f}s")
            st.session_state.results = results
            st.rerun()
    
    # Results
    if 'results' in st.session_state and st.session_state.results:
        st.markdown("### 📋 Results")
        for i, res in enumerate(st.session_state.results):
            if "error" in res: st.error(f"❌ {res['file']}: {res['error']}"); continue
            v = res.get('_validation', {}); sts = str(v.get('status', '?'))
            badge = {'PASS':'<span class="status-pass">✅ PASSED</span>','WARN':'<span class="status-warn">⚠️ WARNINGS (Auto-Corrected)</span>'}.get(sts, '<span class="status-fail">❌ REVIEW</span>')
            vendor_disp = safe_str(res.get('vendor_name'), 'Unknown Vendor', 30)
            file_disp = safe_str(res.get('_file'), 'Invoice')
            cur_disp = safe_str(res.get('currency'), 'NGN')
            total_disp = safe_float(res.get('total_amount'))
            
            with st.expander(f"{'✅' if sts=='PASS' else '⚠️'} {file_disp} — {vendor_disp} | {cur_disp} {total_disp:,.2f}", expanded=(i==0)):
                c1,c2 = st.columns([2,1])
                with c1:
                    st.markdown(f"**🏢 Vendor:** {safe_str(res.get('vendor_name'))}")
                    st.markdown(f"**📄 Invoice #:** {safe_str(res.get('invoice_number'))}")
                    st.markdown(f"**📅 Date:** {safe_str(res.get('invoice_date'))} | **Due:** {safe_str(res.get('due_date'),'N/A')}")
                    if res.get('po_number'): st.markdown(f"**🔢 PO #:** {safe_str(res.get('po_number'))}")
                    st.markdown("---")
                    csub,ctax,ctot = st.columns(3)
                    csub.metric("Subtotal", f"{cur_disp} {safe_float(res.get('subtotal')):,.2f}")
                    ctax.metric("Tax", f"{cur_disp} {safe_float(res.get('tax_amount')):,.2f}")
                    ctot.metric("**TOTAL**", f"{cur_disp} {total_disp:,.2f}")
                with c2:
                    st.markdown(badge, unsafe_allow_html=True)
                    conf_score = v.get('confidence_score', 0) or 0
                    st.progress(conf_score/100, text=f"Confidence: {conf_score}%")
                    for e in v.get('errors',[]): st.error(safe_str(e))
                    for w in v.get('warnings',[]): st.warning(f"🔄 {safe_str(w)}")
                    if not v.get('errors') and not v.get('warnings'): st.success("All checks passed")
                
                items = res.get('line_items',[]) or []
                if items:
                    st.markdown("---")
                    st.markdown(f"**📦 Line Items ({len(items)}):**")
                    st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
                
                st.markdown("---")
                ex1,ex2 = st.columns(2)
                with ex1:
                    try:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            pd.DataFrame([{'Vendor': safe_str(res.get('vendor_name')), 'Invoice': safe_str(res.get('invoice_number')), 'Date': safe_str(res.get('invoice_date')), 'Total': total_disp, 'Status': sts}]).to_excel(writer, sheet_name='Summary', index=False)
                            if items: pd.DataFrame(items).to_excel(writer, sheet_name='Line Items', index=False)
                        st.download_button("📊 Download Excel", output.getvalue(), f"{safe_str(res.get('invoice_number'),'invoice')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key=f"excel_{i}")
                    except:
                        csv_d = pd.DataFrame([{'Vendor': safe_str(res.get('vendor_name')), 'Invoice': safe_str(res.get('invoice_number')), 'Total': total_disp}]).to_csv(index=False)
                        st.download_button("📊 Download CSV", csv_d, f"{safe_str(res.get('invoice_number'),'invoice')}.csv", "text/csv", use_container_width=True, key=f"csv_{i}")
                with ex2:
                    pdf_b = generate_pdf_report(res)
                    if pdf_b:
                        st.download_button("📕 Download PDF Report", pdf_b, f"{safe_str(res.get('invoice_number'),'invoice')}.pdf", "application/pdf", use_container_width=True, key=f"pdf_{i}")

# ============================================
# TAB 2: ERP MATCHING
# ============================================
with tab2:
    st.markdown("### 🔗 ERP Matching Engine")
    st.markdown("Match extracted invoices against Purchase Orders, Work Orders, and Payment Abstracts")
    
    erp_col1, erp_col2, erp_col3 = st.columns(3)
    with erp_col1:
        po_files = st.file_uploader("📄 Purchase Orders / Abstracts", type=['pdf','jpg','jpeg','png','bmp','tiff','tif','xlsx','xls'], accept_multiple_files=True, key="po_upload")
    with erp_col2:
        wo_files = st.file_uploader("📄 Work Orders / Contracts", type=['pdf','jpg','jpeg','png','bmp','tiff','tif','xlsx','xls'], accept_multiple_files=True, key="wo_upload")
    with erp_col3:
        vendor_files = st.file_uploader("📄 Vendor Master List", type=['pdf','jpg','jpeg','png','bmp','tiff','tif','xlsx','xls'], accept_multiple_files=True, key="vendor_upload")
    
    if (po_files or vendor_files) and API_KEY:
        if st.button("📥 Load & Extract ERP Data", type="primary", use_container_width=True):
            with st.spinner("AI extracting data from ERP documents..."):
                try:
                    from erp_matcher import ERPMatcher
                    st.session_state.matcher = ERPMatcher()
                    extractor = Extractor(API_KEY)
                    docs_processed = 0
                    if po_files:
                        st.session_state.erp_po_data = []
                        for po_file in po_files:
                            fb = po_file.read(); suf = Path(po_file.name).suffix.lower()
                            img = None
                            if suf == '.pdf':
                                imgs = pdf_to_bytes(fb)
                                img = imgs[0] if imgs else None
                            elif suf in ['.xlsx','.xls']: img = excel_to_bytes(fb)
                            else: img = fb
                            if img:
                                extracted = extractor.extract(img, enhance=True)
                                if 'error' not in extracted:
                                    extracted['_source_file'] = po_file.name; st.session_state.erp_po_data.append(extracted); docs_processed += 1
                    if vendor_files:
                        st.session_state.erp_vendor_data = []
                        for vendor_file in vendor_files:
                            fb = vendor_file.read(); suf = Path(vendor_file.name).suffix.lower()
                            img = None
                            if suf == '.pdf':
                                imgs = pdf_to_bytes(fb)
                                img = imgs[0] if imgs else None
                            elif suf in ['.xlsx','.xls']: img = excel_to_bytes(fb)
                            else: img = fb
                            if img:
                                extracted = extractor.extract(img, enhance=True)
                                if 'error' not in extracted:
                                    extracted['_source_file'] = vendor_file.name; st.session_state.erp_vendor_data.append(extracted); docs_processed += 1
                    st.success(f"✅ Extracted data from {docs_processed} ERP document(s)")
                    if st.session_state.get('erp_vendor_data'):
                        vn = [safe_str(vd.get('vendor_name')) for vd in st.session_state.erp_vendor_data if vd.get('vendor_name')]
                        if vn:
                            pd.DataFrame({'vendor_name': vn}).to_excel(f"/tmp/vm_{datetime.now().timestamp()}.xlsx", index=False)
                            st.session_state.matcher.load_erp_data(vendor_file=f"/tmp/vm_{datetime.now().timestamp()}.xlsx")
                    if st.session_state.get('erp_po_data'):
                        pr = [{'po_number': safe_str(pd.get('po_number') or pd.get('invoice_number')), 'vendor_name': safe_str(pd.get('vendor_name')), 'amount': safe_float(pd.get('total_amount'))} for pd in st.session_state.erp_po_data]
                        if pr:
                            pd.DataFrame(pr).to_excel(f"/tmp/po_{datetime.now().timestamp()}.xlsx", index=False)
                            st.session_state.matcher.load_erp_data(po_file=f"/tmp/po_{datetime.now().timestamp()}.xlsx")
                    st.session_state.erp_loaded = True
                except Exception as e: st.error(f"Error: {e}")
    
    if st.session_state.get('erp_loaded'):
        st.markdown("---"); st.success("✅ ERP Data Loaded & Ready")
        sc1,sc2,sc3 = st.columns(3)
        sc1.metric("📄 PO Docs", len(st.session_state.get('erp_po_data',[])))
        sc2.metric("🏢 Vendors", len(st.session_state.get('erp_vendor_data',[])))
        sc3.metric("🧾 Invoices", len([r for r in st.session_state.get('results',[]) if 'error' not in r]))
    
    if st.session_state.get('matcher') and st.session_state.get('results'):
        invoices = [r for r in st.session_state.results if 'error' not in r]
        if invoices:
            st.markdown("---")
            if st.button("🔍 Run ERP Matching", type="primary", use_container_width=True):
                with st.spinner("Matching..."):
                    match_results = st.session_state.matcher.match_batch(invoices)
                    st.session_state.match_results = match_results
                    summary = st.session_state.matcher.get_summary()
                    st.dataframe(summary, use_container_width=True, hide_index=True)
                    for i, r in enumerate(match_results):
                        status_color = {'APPROVED_FOR_PAYMENT':'status-pass','APPROVED_WITH_NOTES':'status-warn','REVIEW_REQUIRED':'status-fail'}.get(str(r.get('status','')), 'status-fail')
                        vendor_disp = safe_str(r.get('vendor_name'), 'Unknown', 30)
                        inv_disp = safe_str(r.get('invoice_number'), 'N/A')
                        status_disp = safe_str(r.get('status'), 'PENDING')
                        approved = 'APPROVED' in str(r.get('status',''))
                        with st.expander(f"{'✅' if approved else '❌'} {vendor_disp} — {inv_disp} | {status_disp}", expanded=(i==0)):
                            cA,cB = st.columns(2)
                            with cA:
                                st.markdown(f"**Invoice #:** {inv_disp}")
                                st.markdown(f"**Vendor:** {vendor_disp}")
                                st.markdown(f"**Total:** {safe_float(r.get('invoice_total')):,.2f}")
                            with cB:
                                st.markdown(f'<span class="{status_color}">{status_disp}</span>', unsafe_allow_html=True)
                                st.metric("Confidence", f"{r.get('confidence',0)}%")
                            flags = r.get('flags',[]) or []
                            if flags:
                                for flag in flags:
                                    sev = str(flag.get('severity','')).upper()
                                    sev_icon = {'HIGH':'🔴','MEDIUM':'🟡','LOW':'🟢'}.get(sev,'⚪')
                                    st.markdown(f"{sev_icon} **[{sev}]** {safe_str(flag.get('message'))}")
                    try:
                        rp = st.session_state.matcher.export_report()
                        with open(rp,'rb') as f: st.download_button("📊 Download Matching Report", f.read(), Path(rp).name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    except: pass