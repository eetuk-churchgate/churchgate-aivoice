"""
Churchgate-AI ERP Matching Engine
Matches extracted invoices against Work Orders / Purchase Orders / Abstracts
"""
import pandas as pd
import numpy as np
from pathlib import Path
from rapidfuzz import fuzz, process
from datetime import datetime
import json

class ERPMatcher:
    """
    Matches AI-extracted invoices against ERP records
    Supports: Purchase Orders (PO), Work Orders (WO), Payment Abstracts
    """
    
    def __init__(self):
        self.po_database = None
        self.wo_database = None
        self.vendor_master = None
        self.results = []
    
    def load_erp_data(self, po_file=None, wo_file=None, vendor_file=None):
        """Load ERP reference data from Excel files"""
        if po_file and Path(po_file).exists():
            self.po_database = pd.read_excel(po_file)
            self.po_database.columns = [c.lower().strip() for c in self.po_database.columns]
            print(f"✅ Loaded {len(self.po_database)} Purchase Orders")
        
        if wo_file and Path(wo_file).exists():
            self.wo_database = pd.read_excel(wo_file)
            self.wo_database.columns = [c.lower().strip() for c in self.wo_database.columns]
            print(f"✅ Loaded {len(self.wo_database)} Work Orders")
        
        if vendor_file and Path(vendor_file).exists():
            self.vendor_master = pd.read_excel(vendor_file)
            self.vendor_master.columns = [c.lower().strip() for c in self.vendor_master.columns]
            print(f"✅ Loaded {len(self.vendor_master)} Vendors")
    
    def match_invoice(self, invoice_data, threshold=80):
        """
        Match a single extracted invoice against ERP records
        
        Args:
            invoice_data: Dict with extracted invoice fields
            threshold: Matching confidence threshold (0-100)
        
        Returns:
            Dict with matching results and flags
        """
        result = {
            'invoice_number': invoice_data.get('invoice_number', 'N/A'),
            'vendor_name': invoice_data.get('vendor_name', 'N/A'),
            'invoice_total': invoice_data.get('total_amount', 0),
            'invoice_date': invoice_data.get('invoice_date', 'N/A'),
            'timestamp': datetime.now().isoformat(),
            'matches': [],
            'flags': [],
            'status': 'PENDING',
            'confidence': 0
        }
        
        # ============================================
        # 1. VENDOR VERIFICATION
        # ============================================
        vendor_match_score = 0
        vendor_approved = False
        
        if self.vendor_master is not None:
            vendor_name = invoice_data.get('vendor_name', '')
            if vendor_name:
                # Find vendor name column
                vendor_col = None
                for col in self.vendor_master.columns:
                    if any(w in col.lower() for w in ['vendor', 'supplier', 'name', 'company']):
                        vendor_col = col
                        break
                
                if vendor_col:
                    vendor_list = self.vendor_master[vendor_col].dropna().tolist()
                    best_match = process.extractOne(
                        vendor_name.lower(),
                        [str(v).lower() for v in vendor_list],
                        scorer=fuzz.token_sort_ratio
                    )
                    
                    if best_match:
                        vendor_match_score = best_match[1]
                        vendor_approved = vendor_match_score >= threshold
                        
                        result['matches'].append({
                            'type': 'VENDOR',
                            'matched_to': best_match[0],
                            'score': vendor_match_score,
                            'status': 'APPROVED' if vendor_approved else 'UNKNOWN'
                        })
                        
                        if not vendor_approved:
                            result['flags'].append({
                                'severity': 'HIGH',
                                'message': f"Vendor '{vendor_name}' not found in approved vendor list (match: {vendor_match_score}%)"
                            })
                    else:
                        result['flags'].append({
                            'severity': 'HIGH',
                            'message': f"Vendor '{vendor_name}' not in vendor database"
                        })
        
        # ============================================
        # 2. PO MATCHING
        # ============================================
        po_matched = False
        po_number = invoice_data.get('po_number') or self._extract_po_from_invoice(invoice_data)
        
        if self.po_database is not None and po_number:
            po_col = None
            for col in self.po_database.columns:
                if any(w in col.lower() for w in ['po', 'purchase order', 'order', 'po_number', 'ponumber']):
                    po_col = col
                    break
            
            if po_col:
                # Find matching PO
                for _, po_row in self.po_database.iterrows():
                    po_id = str(po_row[po_col]).strip()
                    if po_id.lower() == po_number.lower():
                        po_matched = True
                        
                        # Get PO amount
                        po_amount = None
                        for col in self.po_database.columns:
                            if any(w in col.lower() for w in ['amount', 'total', 'value', 'sum']):
                                try:
                                    po_amount = float(po_row[col])
                                    break
                                except:
                                    pass
                        
                        match_info = {
                            'type': 'PURCHASE_ORDER',
                            'po_number': po_id,
                            'po_amount': po_amount,
                            'score': 100
                        }
                        
                        # Check amount match
                        invoice_total = invoice_data.get('total_amount', 0) or 0
                        if po_amount and po_amount > 0:
                            variance = abs(invoice_total - po_amount)
                            variance_pct = (variance / po_amount) * 100
                            match_info['variance'] = variance
                            match_info['variance_pct'] = round(variance_pct, 2)
                            
                            if variance_pct > 10:
                                result['flags'].append({
                                    'severity': 'HIGH',
                                    'message': f"PO #{po_id}: Invoice ({invoice_total:,.2f}) differs from PO ({po_amount:,.2f}) by {variance_pct:.1f}%"
                                })
                            elif variance_pct > 5:
                                result['flags'].append({
                                    'severity': 'MEDIUM',
                                    'message': f"PO #{po_id}: Minor variance of {variance_pct:.1f}%"
                                })
                            else:
                                match_info['status'] = 'MATCHED'
                        else:
                            match_info['status'] = 'NO_AMOUNT'
                            result['flags'].append({
                                'severity': 'LOW',
                                'message': f"PO #{po_id} found but no amount available for comparison"
                            })
                        
                        result['matches'].append(match_info)
                        result['po_number'] = po_id
                        break
        
        if not po_matched and po_number:
            result['flags'].append({
                'severity': 'MEDIUM',
                'message': f"PO #{po_number} referenced on invoice not found in ERP"
            })
        elif not po_matched and not po_number:
            result['flags'].append({
                'severity': 'LOW',
                'message': "No PO number detected on invoice"
            })
        
        # ============================================
        # 3. LINE ITEM MATCHING
        # ============================================
        line_items = invoice_data.get('line_items', [])
        if self.po_database is not None and po_matched and line_items:
            matched_items = 0
            unmatched_items = []
            
            for item in line_items:
                desc = item.get('description', '')
                item_total = item.get('line_total', 0) or 0
                
                # Search PO database for this item
                item_found = False
                for _, po_row in self.po_database.iterrows():
                    for col in self.po_database.columns:
                        cell_val = str(po_row[col]).lower() if pd.notna(po_row[col]) else ''
                        if len(cell_val) > 5 and len(desc) > 5:
                            score = fuzz.partial_ratio(desc.lower(), cell_val)
                            if score > 70:
                                item_found = True
                                matched_items += 1
                                break
                
                if not item_found:
                    unmatched_items.append({
                        'description': desc,
                        'amount': item_total
                    })
            
            if unmatched_items:
                result['flags'].append({
                    'severity': 'HIGH',
                    'message': f"{len(unmatched_items)} line item(s) not found in PO — possible unauthorized items"
                })
                result['unmatched_items'] = unmatched_items
        
        # ============================================
        # 4. DETERMINE FINAL STATUS
        # ============================================
        high_flags = [f for f in result['flags'] if f['severity'] == 'HIGH']
        medium_flags = [f for f in result['flags'] if f['severity'] == 'MEDIUM']
        
        if not result['flags']:
            result['status'] = 'APPROVED_FOR_PAYMENT'
            result['confidence'] = 95
        elif not high_flags and len(medium_flags) <= 1:
            result['status'] = 'APPROVED_WITH_NOTES'
            result['confidence'] = 80
        elif high_flags:
            result['status'] = 'REVIEW_REQUIRED'
            result['confidence'] = 50
        else:
            result['status'] = 'NEEDS_REVIEW'
            result['confidence'] = 65
        
        return result
    
    def _extract_po_from_invoice(self, invoice_data):
        """Try to find PO number in invoice data"""
        # Check common PO fields
        for field in ['po_number', 'purchase_order', 'order_number', 'reference']:
            val = invoice_data.get(field)
            if val:
                return str(val)
        return None
    
    def match_batch(self, invoices):
        """Match multiple invoices at once"""
        self.results = []
        for inv in invoices:
            if 'error' not in inv:
                result = self.match_invoice(inv)
                self.results.append(result)
        return self.results
    
    def get_summary(self):
        """Generate matching summary report"""
        if not self.results:
            return pd.DataFrame()
        
        summary = []
        for r in self.results:
            summary.append({
                'Invoice #': r.get('invoice_number', 'N/A'),
                'Vendor': r.get('vendor_name', 'N/A'),
                'Total': r.get('invoice_total', 0),
                'PO #': r.get('po_number', 'N/A'),
                'Status': r.get('status', 'PENDING'),
                'Confidence': r.get('confidence', 0),
                'Flags': len(r.get('flags', [])),
                'High Severity': len([f for f in r.get('flags', []) if f['severity'] == 'HIGH']),
            })
        
        return pd.DataFrame(summary)
    
    def export_report(self, filepath=None):
        """Export matching results to Excel"""
        if not filepath:
            filepath = f"output/matching_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        summary_df = self.get_summary()
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Summary sheet
            summary_df.to_excel(writer, sheet_name='Matching Summary', index=False)
            
            # Detailed results
            detail_rows = []
            for r in self.results:
                for f in r.get('flags', []):
                    detail_rows.append({
                        'Invoice #': r.get('invoice_number', ''),
                        'Vendor': r.get('vendor_name', ''),
                        'Status': r.get('status', ''),
                        'Severity': f['severity'],
                        'Flag': f['message']
                    })
            
            if detail_rows:
                pd.DataFrame(detail_rows).to_excel(writer, sheet_name='Flags & Issues', index=False)
            
            # Matches
            match_rows = []
            for r in self.results:
                for m in r.get('matches', []):
                    match_rows.append({
                        'Invoice #': r.get('invoice_number', ''),
                        'Match Type': m.get('type', ''),
                        'Matched To': m.get('matched_to', m.get('po_number', '')),
                        'Score': m.get('score', 0),
                        'Status': m.get('status', '')
                    })
            
            if match_rows:
                pd.DataFrame(match_rows).to_excel(writer, sheet_name='Matches Found', index=False)
        
        return filepath


# ============================================
# DEMO / TEST FUNCTION
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("  Churchgate-AI ERP Matching Engine")
    print("="*60)
    
    matcher = ERPMatcher()
    
    # Sample invoice
    sample_invoice = {
        'vendor_name': 'PRIMETECH SECURITY Equip Co. Ltd.',
        'invoice_number': '058',
        'invoice_date': '2016-04-26',
        'total_amount': 256000.00,
        'currency': 'NGN',
        'po_number': 'PO-2024-001',
        'line_items': [
            {'description': '4TB WD HDD DIFFERENTIAL', 'quantity': 8, 'unit_price': 32000, 'line_total': 256000}
        ]
    }
    
    print("\n📋 Test Invoice:")
    print(f"   Vendor: {sample_invoice['vendor_name']}")
    print(f"   Total: NGN {sample_invoice['total_amount']:,.2f}")
    print(f"   PO #: {sample_invoice['po_number']}")
    
    # Without ERP data
    print("\n🔍 Matching without ERP data...")
    result = matcher.match_invoice(sample_invoice)
    
    print(f"\n   Status: {result['status']}")
    print(f"   Confidence: {result['confidence']}%")
    print(f"   Flags: {len(result['flags'])}")
    for flag in result['flags']:
        print(f"     [{flag['severity']}] {flag['message']}")