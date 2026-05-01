"""
Churchgate-AI Enterprise Invoice Processing Dashboard
Includes ERP Matching Engine (PO/WO/Abstract)
"""
import streamlit as st
import os, json, base64, requests, pandas as pd, time, re, numpy as np
from datetime import datetime
from pathlib import Path
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

# ============================================
# LOAD API KEY - Streamlit Cloud + Local .env
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
    
    .header-banner {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
        border-radius: 24px; padding: 2rem 3rem; margin-bottom: 2rem;
        display: flex; align-items: center; justify-content: center; gap: 32px;
        border: 1px solid #cbd5e1; box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }
    .header-title {
        font-size: 2.4rem; font-weight: 800;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e40af 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        letter-spacing: -1px; margin: 0; line-height: 1.2;
    }
    .header-subtitle { font-size: 1rem; color: #475569; font-weight: 500; margin: 6px 0 0 0; }
    .header-badge {
        display: inline-block; background: linear-gradient(135deg, #059669, #10b981);
        color: white; padding: 0.2rem 0.8rem; border-radius: 12px;
        font-size: 0.7rem; font-weight: 700; margin-left: 8px; vertical-align: middle;
    }
    .metric-box {
        background: white; border: 1px solid #e2e8f0; border-radius: 20px;
        padding: 1.5rem 1.2rem; text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04); transition: all 0.25s;
        position: relative; overflow: hidden;
    }
    .metric-box::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
        background: linear-gradient(90deg, #2563eb, #3b82f6, #60a5fa);
    }
    .metric-box:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
    .metric-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
    .metric-value { font-size: 2rem; font-weight: 800; color: #0f172a; }
    .metric-label { font-size: 0.85rem; color: #64748b; font-weight: 500; margin-top: 0.2rem; }
    
    .status-pass { background: #059669; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    .status-warn { background: #d97706; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    .status-fail { background: #dc2626; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    .status-approved { background: #7c3aed; color: white; padding: 0.4rem 1.4rem; border-radius: 24px; font-weight: 700; font-size: 0.85rem; display: inline-block; }
    
    div[data-testid="stFileUploader"] {
        border: 2px dashed #3b82f6; border-radius: 20px; padding: 2.5rem;
        background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 50%, #dbeafe 100%);
    }
    .stButton > button {
        border-radius: 14px; font-weight: 700; padding: 0.85rem 2.5rem; font-size: 1.05rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e40af 100%);
        color: white; border: none; transition: all 0.3s; width: 100%;
    }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(30,64,175,0.4); }
    
    .sidebar-header {
        text-align: center; padding: 1.5rem 0.5rem; border-bottom: 1px solid #e2e8f0;
        margin-bottom: 1.2rem; background: linear-gradient(180deg, #f8fafc 0%, transparent 100%);
        border-radius: 16px;
    }
    .sidebar-company { font-weight: 800; font-size: 1.2rem; color: #0f172a; margin-top: 0.6rem; }
    .sidebar-subtitle { font-size: 0.78rem; color: #64748b; font-weight: 500; }
    .section-divider { height: 1px; background: linear-gradient(90deg, transparent, #cbd5e1, transparent); margin: 2.5rem 0; }
    .chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
</style>
""", unsafe_allow_html=True)

# ============================================
# AI ENGINE
# ============================================
class Extractor:
    def __init__(self, key):
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    
    def extract(self, image_bytes):
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Extract ALL invoice data. Return ONLY valid JSON with: vendor_name, invoice_number, po_number (if visible), invoice_date, due_date, subtotal, tax_amount, total_amount, currency, line_items."
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
        d['_validation'] = {'confidence_score': max(0, conf), 'status': 'FAIL' if errors else ('WARN' if warnings else 'PASS'), 'errors': errors, 'warnings': warnings}
        return d

def pdf_to_bytes(b): 
    try:
        import fitz; doc=fitz.open(stream=b, filetype="pdf"); pix=doc[0].get_pixmap(dpi=200); img=pix.tobytes("jpg"); doc.close(); return img
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
        v = data.get('_validation', {}); cur = data.get('currency', 'NGN')
        pdf.set_fill_color(25,50,80); pdf.rect(0,0,210,40,'F')
        pdf.set_text_color(255,255,255); pdf.set_font('Arial','B',22)
        pdf.set_y(7); pdf.cell(0,11,'CHURCHGATE INVOICE REPORT',0,1,'C')
        pdf.set_font('Arial','',10); pdf.cell(0,7,'AI-Powered Extraction & Validation',0,1,'C')
        pdf.set_text_color(0,0,0); pdf.ln(12)
        sts, conf = v.get('status','?'), v.get('confidence_score',0)
        if sts == 'PASS': rc,gc,bc,tx = 39,174,96,'PASSED'
        elif sts == 'WARN': rc,gc,bc,tx = 243,156,18,'WARNINGS'
        else: rc,gc,bc,tx = 231,76,60,'REVIEW REQUIRED'
        pdf.set_fill_color(rc,gc,bc); pdf.set_text_color(255,255,255)
        pdf.set_font('Arial','B',13); pdf.cell(0,10,f'  STATUS: {tx}  |  Confidence: {conf}%',0,1,'L',True)
        pdf.set_text_color(0,0,0); pdf.ln(6)
        for section, items in [
            ('INVOICE DETAILS', [('Vendor:',clean(data.get('vendor_name','N/A'))),('Invoice #:',clean(data.get('invoice_number','N/A'))),('Date:',clean(data.get('invoice_date','N/A')))]),
            ('FINANCIAL', [('Subtotal:',f"{cur} {data.get('subtotal',0):,.2f}"),('Tax:',f"{cur} {data.get('tax_amount',0):,.2f}"),('TOTAL:',f"{cur} {data.get('total_amount',0):,.2f}")])
        ]:
            pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
            pdf.set_font('Arial','B',11); pdf.cell(0,8,f'  {section}',0,1,'L',True)
            pdf.set_text_color(0,0,0); pdf.ln(3)
            for l,vl in items:
                pdf.set_font('Arial','B',9); pdf.cell(35,6,l,0,0)
                pdf.set_font('Arial','',9); pdf.cell(0,6,vl,0,1)
            pdf.ln(3)
        items = data.get('line_items',[])
        if items:
            pdf.set_fill_color(52,73,94); pdf.set_text_color(255,255,255)
            pdf.set_font('Arial','B',11); pdf.cell(0,8,f'  LINE ITEMS',0,1,'L',True)
            pdf.set_text_color(0,0,0); pdf.ln(3)
            for item in items[:20]:
                pdf.set_font('Arial','',8)
                pdf.cell(0,5,f"  {clean(item.get('description',''))[:60]} - {item.get('line_total',0):,.2f}",0,1)
        pdf.ln(10); pdf.set_font('Arial','I',7); pdf.set_text_color(127,140,141)
        pdf.cell(0,5,'Churchgate-AI Enterprise | Gemini AI',0,1,'C')
        return pdf.output(dest='S').encode('latin-1')
    except: return None

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
    if LOGO_B64:
        st.markdown(f'<img src="data:image/png;base64,{LOGO_B64}" style="width:90px;height:90px;border-radius:18px;object-fit:contain;display:block;margin:0 auto 0.8rem;box-shadow:0 4px 12px rgba(0,0,0,0.1);">', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:3.5rem;text-align:center;">🏢</div>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-company">Churchgate Group</p>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-subtitle">Invoice Processing + ERP Matching</p>', unsafe_allow_html=True)
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
    
    if st.button("🗑️ Clear Session", use_container_width=True):
        st.session_state.count = 0; st.session_state.total_val = 0
        st.session_state.history = []; st.session_state.results = []
        st.rerun()
    st.markdown("---")
    st.caption("v3.0 Enterprise | Gemini AI")
    st.caption(f"© {datetime.now().year} Churchgate Group")

# ============================================
# HEADER
# ============================================
if LOGO_B64:
    logo_html = f'<img src="data:image/png;base64,{LOGO_B64}" style="width:100px;height:100px;border-radius:18px;object-fit:contain;background:white;padding:10px;box-shadow:0 4px 14px rgba(0,0,0,0.1);flex-shrink:0;">'
else:
    logo_html = '<div style="font-size:3.5rem;width:100px;height:100px;display:flex;align-items:center;justify-content:center;background:white;border-radius:18px;flex-shrink:0;">🏢</div>'

st.markdown(f"""
<div class="header-banner">
    {logo_html}
    <div>
        <h1 class="header-title">Churchgate Invoice Processing <span class="header-badge">ENTERPRISE</span></h1>
        <p class="header-subtitle">AI Extraction • Auto-Validation • ERP Matching • PDF & Excel Export</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================
# TABS: PROCESSING | ERP MATCHING
# ============================================
tab1, tab2 = st.tabs(["📄 Invoice Processing", "🔗 ERP Matching (PO/WO/Abstract)"])

# ============================================
# TAB 1: INVOICE PROCESSING
# ============================================
with tab1:
    # Metrics
    m1,m2,m3,m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-box"><div class="metric-icon">📄</div><div class="metric-value">{st.session_state.count}</div><div class="metric-label">Processed</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-box"><div class="metric-icon">💰</div><div class="metric-value">{"₦"+f"{st.session_state.total_val:,.0f}" if st.session_state.total_val > 0 else "—"}</div><div class="metric-label">Total Value</div></div>', unsafe_allow_html=True)
    with m3: st.markdown('<div class="metric-box"><div class="metric-icon">⚡</div><div class="metric-value">3-8s</div><div class="metric-label">Per Invoice</div></div>', unsafe_allow_html=True)
    with m4: st.markdown('<div class="metric-box"><div class="metric-icon">🎯</div><div class="metric-value">95%+</div><div class="metric-label">Accuracy</div></div>', unsafe_allow_html=True)
    
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
                fig = go.Figure(data=[go.Bar(x=vendors, y=totals, marker=dict(color=totals, colorscale=[[0,'#3b82f6'],[1,'#1e3a5f']]), text=[f"₦{t:,.0f}" for t in totals], textposition='outside')])
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
                img = None
                if suf == '.pdf': img = pdf_to_bytes(fb)
                elif suf in ['.xlsx','.xls']: img = excel_to_bytes(fb)
                else: img = fb
                res = extractor.extract(img) if img else {"error": f"Cannot process {file.name}"}
                if "error" in res: results.append({"file": file.name, "error": res["error"]})
                else:
                    res = validator.validate(res); res['_file'] = file.name; results.append(res)
                    st.session_state.count += 1; st.session_state.total_val += res.get('total_amount', 0) or 0
                    st.session_state.history.append({'status': res.get('_validation',{}).get('status','?'), 'currency': res.get('currency','NGN'), 'total': res.get('total_amount',0) or 0, 'vendor': res.get('vendor_name','N/A')})
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
            v = res.get('_validation', {}); sts = v.get('status', '?')
            badge = {'PASS':'<span class="status-pass">✅ PASSED</span>','WARN':'<span class="status-warn">⚠️ WARNINGS</span>'}.get(sts, '<span class="status-fail">❌ REVIEW</span>')
            with st.expander(f"{'✅' if sts=='PASS' else '⚠️'} {res.get('_file','')} — {res.get('vendor_name','N/A')[:30]} | {res.get('currency','')} {res.get('total_amount',0):,.2f}", expanded=(i==0)):
                c1,c2 = st.columns([2,1])
                with c1:
                    st.markdown(f"**Vendor:** {res.get('vendor_name','N/A')}")
                    st.markdown(f"**Invoice #:** {res.get('invoice_number','N/A')}")
                    st.markdown(f"**Date:** {res.get('invoice_date','N/A')}")
                    if res.get('po_number'): st.markdown(f"**PO #:** {res.get('po_number')}")
                    csub,ctax,ctot = st.columns(3)
                    csub.metric("Subtotal", f"{res.get('currency','')} {res.get('subtotal',0):,.2f}")
                    ctax.metric("Tax", f"{res.get('currency','')} {res.get('tax_amount',0):,.2f}")
                    ctot.metric("TOTAL", f"{res.get('currency','')} {res.get('total_amount',0):,.2f}")
                with c2:
                    st.markdown(badge, unsafe_allow_html=True)
                    st.progress(v.get('confidence_score',0)/100)
                items = res.get('line_items',[])
                if items: st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
                ex1,ex2 = st.columns(2)
                with ex1:
                    csv_d = pd.DataFrame([{'Vendor':res.get('vendor_name',''),'Invoice':res.get('invoice_number',''),'Total':res.get('total_amount',0),'Status':v.get('status','')}]).to_csv(index=False)
                    st.download_button("📊 CSV", csv_d, f"{res.get('invoice_number','invoice')}.csv", "text/csv", use_container_width=True, key=f"csv_{i}")
                with ex2:
                    pdf_b = generate_pdf_report(res)
                    if pdf_b: st.download_button("📕 PDF", pdf_b, f"{res.get('invoice_number','invoice')}.pdf", "application/pdf", use_container_width=True, key=f"pdf_{i}")

# ============================================
# TAB 2: ERP MATCHING
# ============================================
with tab2:
    st.markdown("### 🔗 ERP Matching Engine")
    st.markdown("Match extracted invoices against Purchase Orders, Work Orders, and Payment Abstracts")
    
    # Upload ERP data
    st.markdown("#### 📂 Load ERP Reference Data")
    erp_col1, erp_col2, erp_col3 = st.columns(3)
    with erp_col1:
        po_file = st.file_uploader("Purchase Orders (Excel)", type=['xlsx','xls'], key="po_upload")
    with erp_col2:
        wo_file = st.file_uploader("Work Orders (Excel)", type=['xlsx','xls'], key="wo_upload")
    with erp_col3:
        vendor_file = st.file_uploader("Vendor Master (Excel)", type=['xlsx','xls'], key="vendor_upload")
    
    # Load ERP data
    erp_loaded = False
    if po_file or vendor_file:
        if st.button("📥 Load ERP Data", use_container_width=True):
            try:
                from erp_matcher import ERPMatcher
                st.session_state.matcher = ERPMatcher()
                
                if po_file:
                    po_path = f"/tmp/po_{datetime.now().timestamp()}.xlsx"
                    with open(po_path, 'wb') as f: f.write(po_file.read())
                    st.session_state.matcher.load_erp_data(po_file=po_path)
                    st.success(f"✅ Loaded Purchase Orders")
                
                if vendor_file:
                    vendor_path = f"/tmp/vendor_{datetime.now().timestamp()}.xlsx"
                    with open(vendor_path, 'wb') as f: f.write(vendor_file.read())
                    st.session_state.matcher.load_erp_data(vendor_file=vendor_path)
                    st.success(f"✅ Loaded Vendor Master")
                
                erp_loaded = True
            except Exception as e:
                st.error(f"Error loading ERP data: {e}")
    
    # Run Matching
    if 'matcher' in st.session_state and 'results' in st.session_state:
        invoices = [r for r in st.session_state.results if 'error' not in r]
        
        if invoices:
            st.markdown("---")
            st.markdown(f"#### 🔍 Match {len(invoices)} Invoice(s) Against ERP")
            
            if st.button("🔍 Run ERP Matching", type="primary", use_container_width=True):
                with st.spinner("Matching invoices against ERP records..."):
                    match_results = st.session_state.matcher.match_batch(invoices)
                    st.session_state.match_results = match_results
                    
                    # Summary
                    summary = st.session_state.matcher.get_summary()
                    st.dataframe(summary, use_container_width=True, hide_index=True)
                    
                    # Detailed results
                    for i, r in enumerate(match_results):
                        status_color = {
                            'APPROVED_FOR_PAYMENT': 'status-pass',
                            'APPROVED_WITH_NOTES': 'status-warn',
                            'REVIEW_REQUIRED': 'status-fail'
                        }.get(r['status'], 'status-fail')
                        
                        with st.expander(f"{'✅' if 'APPROVED' in r['status'] else '❌'} {r.get('vendor_name','')} — {r.get('invoice_number','')} | Status: {r['status']}", expanded=(i==0)):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**Invoice:** {r.get('invoice_number','N/A')}")
                                st.markdown(f"**Vendor:** {r.get('vendor_name','N/A')}")
                                st.markdown(f"**Total:** {r.get('invoice_total',0):,.2f}")
                                if r.get('po_number'):
                                    st.markdown(f"**PO #:** {r['po_number']}")
                            with col_b:
                                st.markdown(f'<span class="{status_color}">{r["status"]}</span>', unsafe_allow_html=True)
                                st.metric("Match Confidence", f"{r.get('confidence',0)}%")
                            
                            if r.get('flags'):
                                st.markdown("**🚩 Flags:**")
                                for flag in r['flags']:
                                    sev_color = {'HIGH':'🔴','MEDIUM':'🟡','LOW':'🟢'}.get(flag['severity'],'⚪')
                                    st.markdown(f"{sev_color} [{flag['severity']}] {flag['message']}")
                    
                    # Export matching report
                    try:
                        report_path = st.session_state.matcher.export_report()
                        with open(report_path, 'rb') as f:
                            st.download_button("📊 Download Matching Report (Excel)", f.read(), Path(report_path).name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    except:
                        pass
        else:
            st.info("Process invoices in the 'Invoice Processing' tab first, then return here for ERP matching.")
    else:
        st.info("📤 Upload ERP data above and process invoices in the 'Invoice Processing' tab to enable matching.")