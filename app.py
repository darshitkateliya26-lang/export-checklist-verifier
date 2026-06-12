import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="Export Checklist Verifier", page_icon="🚢", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F0F4F8; }
.app-header {
    background: linear-gradient(135deg, #0F2D52 0%, #1A5276 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
}
.app-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
.app-header p  { margin: 0; font-size: 0.85rem; opacity: 0.75; }
.section-head {
    background: #1A5276; color: white; padding: 0.55rem 1rem;
    border-radius: 6px 6px 0 0; font-size: 0.8rem; font-weight: 600;
    letter-spacing: 0.8px; text-transform: uppercase;
}
.tile { border-radius: 10px; padding: 1rem 1.2rem; text-align: center; }
.tile-matched  { background: #D5F5E3; border: 1px solid #27AE60; }
.tile-mismatch { background: #FEF9E7; border: 1px solid #F39C12; }
.tile-missing  { background: #FADBD8; border: 1px solid #E74C3C; }
.tile h2 { margin: 0; font-size: 2rem; font-weight: 700; }
.tile p  { margin: 0.2rem 0 0; font-size: 0.8rem; font-weight: 500; color: #444; }
.critical-box {
    background: #FDF2F8; border: 1.5px solid #C0392B;
    border-radius: 10px; padding: 1rem 1.2rem; margin-top: 1rem;
}
.critical-box h4 { margin: 0 0 0.5rem; color: #C0392B; font-size: 0.9rem; }
.critical-item { font-size: 0.82rem; color: #333; margin: 4px 0; }
.raw-text { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; white-space: pre-wrap; color: #555; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# PDF helpers
# ─────────────────────────────────────────────────────────────────────

def get_words(uploaded_file):
    if uploaded_file is None:
        return []
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            all_words, offset = [], 0
            for page in pdf.pages:
                for w in page.extract_words():
                    all_words.append({"text": w["text"],
                                      "x0":   w["x0"],
                                      "top":  w["top"] + offset})
                offset += page.height
            return all_words
    except Exception as e:
        st.warning(f"Could not read PDF: {e}")
        return []


def get_raw_text(uploaded_file):
    if uploaded_file is None:
        return ""
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except:
        return ""


def wb(words, y1, y2, x1=0, x2=600):
    """Words in a bounding box."""
    return [w for w in words if y1 <= w["top"] <= y2 and x1 <= w["x0"] < x2]


def wt(words, y1, y2, x1=0, x2=600):
    """Text of words in a bounding box."""
    return " ".join(w["text"] for w in wb(words, y1, y2, x1, x2)).strip()


def detect_doc_type(words):
    full = " ".join(w["text"] for w in words[:60]).upper()
    if "CHECKLIST FOR SHIPPING BILL" in full or "SKYLINE AIR" in full:
        return "checklist"
    if "PACKING LIST" in full:
        return "packing"
    return "invoice"


# ─────────────────────────────────────────────────────────────────────
# INVOICE EXTRACTOR
# Verified coordinates from sample_invoice__2_.pdf (595×842 pt)
# ─────────────────────────────────────────────────────────────────────

def extract_invoice(words):
    full = " ".join(w["text"] for w in words)
    f = {}

    # 1. Exporter Name  y≈43  x 21-200
    f["Exporter Name"] = wt(words, 40, 50, 21, 230)

    # 2. IEC  y≈31  x 460+  → strip label "IEC CODE :"
    iec_t = wt(words, 28, 38, 460, 600)
    m = re.search(r'([0-9]{10})', iec_t)
    f["IEC"] = m.group(1) if m else ""

    # 3. GSTIN  y≈102  x 440+
    gstin_t = wt(words, 99, 108, 440, 600)
    m = re.search(r'([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])', gstin_t)
    f["GSTIN"] = m.group(1) if m else ""

    # 4. PAN  y≈66  x 460+
    pan_t = wt(words, 63, 72, 460, 600)
    m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', pan_t)
    f["PAN"] = m.group(1) if m else ""

    # 5. AD Code  y≈141  x 470+  → 7-digit number
    ad_t = wt(words, 138, 148, 470, 600)
    m = re.search(r'([0-9]{7})', ad_t)
    f["AD Code"] = m.group(1) if m else ""

    # 6. Bank A/C No  y≈294  x 380+
    bank_t = wt(words, 291, 300, 380, 600)
    m = re.search(r'([0-9]{9,18})', bank_t)
    f["Bank A/C No"] = m.group(1) if m else ""

    # 7. Invoice No  y≈66  x 240-420  pattern E/LUT/ or E/GST/
    inv_t = wt(words, 63, 72, 240, 420)
    m = re.search(r'(E/(?:LUT|GST)/[0-9]+/[0-9\-]+)', inv_t, re.IGNORECASE)
    f["Invoice No"] = m.group(1) if m else inv_t

    # 8. Invoice Date  y≈102  x 240-360
    date_t = wt(words, 99, 108, 240, 360)
    m = re.search(r'(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})', date_t)
    f["Invoice Date"] = m.group(1) if m else ""

    # 9. Buyer/Consignee — first full line below "Consignee" label y≈165
    #    actual company name at y≈176, x 21-230
    f["Buyer / Consignee"] = wt(words, 173, 182, 21, 230)

    # 10. Buyer PO No — y≈117 right side, strip label
    po_t = wt(words, 114, 125, 336, 600)
    f["Buyer PO No"] = po_t.strip(": ") if po_t and po_t != ":" else ""

    # 11. Country of Origin  y≈228  x 300-462
    f["Country of Origin"] = wt(words, 225, 235, 300, 462)

    # 12. Country of Destination  y≈228  x 462+
    f["Country of Destination"] = wt(words, 225, 235, 462, 600)

    # 13. Port of Loading  y≈297  x 160-300
    f["Port of Loading"] = wt(words, 294, 304, 160, 300)

    # 14. Port of Discharge  y≈319  x 60-175
    f["Port of Discharge"] = wt(words, 316, 325, 60, 175)

    # 15. Delivery Terms (Incoterm)  y≈311  x 355+  "EX-WORKS (AHMEDABAD)" / "CIF" etc.
    inco_t = wt(words, 308, 317, 355, 600)
    m = re.search(r'\b(FOB|CIF|CFR|EXW|EX.WORKS|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b', inco_t, re.IGNORECASE)
    if m:
        f["Delivery Terms (Incoterm)"] = m.group(1).upper()
    else:
        f["Delivery Terms (Incoterm)"] = inco_t

    # 16. Payment Terms  y≈252  x 370+
    pay_t = wt(words, 249, 260, 370, 600)
    f["Payment Terms"] = pay_t

    # 17. Payment Days — from "within 180 days" text or pre-carriage line
    m = re.search(r'within\s+(\d+)\s*days', full, re.IGNORECASE)
    if not m:
        m = re.search(r'(\d+)\s*%\s*Advance', full, re.IGNORECASE)
        f["Payment Days"] = "" if m else ""
    else:
        f["Payment Days"] = m.group(1)
    # Pre-carriage/FEDEX reference number
    pre_t = wt(words, 264, 274, 40, 200)
    if "FEDEX" in pre_t.upper() or "DHL" in pre_t.upper():
        f["Marks & Nos"] = pre_t
    else:
        # 18. Marks & Nos  y≈357-369
        f["Marks & Nos"] = wt(words, 354, 373, 0, 200)

    # 19. Currency  y≈342  x 450+  column header
    curr_t = wt(words, 339, 348, 450, 600)
    m = re.search(r'\b(EUR|USD|GBP|AED|INR|JPY)\b', curr_t)
    f["Currency"] = m.group(1) if m else re.search(r'\b(EUR|USD|GBP|AED|INR)\b', full) and re.search(r'\b(EUR|USD|GBP|AED|INR)\b', full).group(1) or ""

    # 20. Total Invoice Value — last number on Amount Chargeable line y≈693
    total_t = wt(words, 690, 700)
    nums = re.findall(r'([0-9,]+\.[0-9]{2})', total_t)
    f["Total Invoice Value"] = nums[-1].replace(",", "") if nums else ""

    # FOB Value — "Before Tax Value (Rs.) NNN" if present
    m = re.search(r'Before\s+Tax\s+Value\s*\([A-Z]+\.?\)\s*([0-9,]+\.?[0-9]{0,2})', full)
    f["FOB Value"] = m.group(1).replace(",", "") if m else ""

    # 22. Gross Weight — not on invoice
    f["Gross Weight"] = ""
    # 23. Net Weight — not on invoice
    f["Net Weight"] = ""

    # 24. No. of Packages  y≈369  x 0-200
    pkg_t = wt(words, 366, 376, 0, 200)
    m = re.search(r'(\d+)', pkg_t)
    f["No. of Packages"] = m.group(1) if m else ""

    # 25. Product  y≈378  x 130-390
    f["Product"] = wt(words, 375, 386, 130, 390)

    # 26. Model No  y≈390  x 155+
    model_t = wt(words, 387, 398, 155, 600)
    f["Model No"] = model_t.strip()

    # 27. HSN Code  y≈402  x 175+  "9021 3900" → strip space
    hsn_t = wt(words, 399, 410, 175, 600)
    m = re.search(r'([0-9]{4}\s*[0-9]{4}|[0-9]{8})', hsn_t)
    f["HSN Code"] = m.group(1).replace(" ", "") if m else ""

    # 28. LUT / Bond — if invoice number contains LUT
    f["LUT / Bond"] = f["Invoice No"] if "LUT" in f.get("Invoice No", "").upper() else ""

    # 29. DBK / Advance  y≈438
    dbk_t = wt(words, 435, 446)
    m = re.search(r'DBK\s+Sr\.?\s*No\.?\s*([A-Z0-9/]+)', dbk_t, re.IGNORECASE)
    if not m:
        m = re.search(r'\b(9021/?[A-Z])\b', full)
    f["DBK / Advance"] = m.group(1) if m else ""

    # 30. RoDTEP
    f["RoDTEP"] = "Claimed" if re.search(r'RoDTEP', full, re.IGNORECASE) else ""

    return f


# ─────────────────────────────────────────────────────────────────────
# PACKING LIST EXTRACTOR
# Same layout as invoice; add gross/net weight from totals row
# ─────────────────────────────────────────────────────────────────────

def extract_packing(words):
    f = extract_invoice(words)  # reuse — same header layout
    full = " ".join(w["text"] for w in words)

    # Gross/Net from "Total 465 4.50 6.00"
    m = re.search(r'Total\s+[0-9]+\s+([0-9]+\.[0-9]{2,3})\s+([0-9]+\.[0-9]{2,3})', full)
    if m:
        f["Net Weight"]   = m.group(1)
        f["Gross Weight"] = m.group(2)

    m2 = re.search(r'Total\s+Cartons?\s*:\s*0*([0-9]+)', full, re.IGNORECASE)
    if m2:
        f["No. of Packages"] = m2.group(1)

    # No monetary values on packing list
    f["FOB Value"]          = ""
    f["Total Invoice Value"] = ""
    return f


# ─────────────────────────────────────────────────────────────────────
# CHECKLIST EXTRACTOR
# Verified coordinates from 3234316761-OMNI__2_.PDF (595×842 pt)
# Left labels  x0  18-120   Left values x0  128-310
# Right labels x0 314-425   Right values x0 428-560
# ─────────────────────────────────────────────────────────────────────

def extract_checklist(words):
    full = " ".join(w["text"] for w in words)
    f = {}

    def lv(y1, y2, x1=128, x2=314):
        return wt(words, y1, y2, x1, x2)

    def rv(y1, y2, x1=428, x2=580):
        return wt(words, y1, y2, x1, x2)

    # 1. Exporter Name  y≈132  x 18-200
    f["Exporter Name"] = wt(words, 129, 139, 18, 200)

    # 2. IEC  y≈108  x 18-120  (first token = 10-digit number)
    iec_t = wt(words, 105, 115, 18, 122)
    m = re.search(r'([0-9]{10})', iec_t)
    f["IEC"] = m.group(1) if m else ""

    # 3. GSTIN  y≈108  x 148-314
    gstin_t = wt(words, 105, 115, 148, 314)
    m = re.search(r'([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])', gstin_t)
    f["GSTIN"] = m.group(1) if m else ""

    # 4. PAN  y≈120  x 45-120
    pan_t = wt(words, 117, 128, 45, 122)
    m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', pan_t)
    f["PAN"] = m.group(1) if m else ""

    # 5. AD Code  y≈288  x 120-200
    ad_t = lv(285, 296, 120, 200)
    m = re.search(r'([0-9]{7})', ad_t)
    f["AD Code"] = m.group(1) if m else ""

    # 6. Bank A/C No — "Forex Bank A/c No" label at y≈300; value usually blank on this form
    bank_t = lv(297, 310, 18, 314)
    m = re.search(r'([0-9]{9,18})', bank_t)
    f["Bank A/C No"] = m.group(1) if m else ""

    # 7. Invoice No  y≈370  x 128-314
    inv_raw = lv(366, 378)
    m = re.search(r'(E/(?:LUT|GST)/[0-9]+/[0-9\-]+)', inv_raw, re.IGNORECASE)
    f["Invoice No"] = m.group(1) if m else inv_raw

    # 8. Invoice Date  y≈381  x 128-314
    date_raw = lv(377, 390)
    m = re.search(r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}|\d{2}-[A-Za-z]+-\d{4})', date_raw)
    f["Invoice Date"] = m.group(1) if m else date_raw

    # 9. Buyer / Consignee  y≈108  x 314+
    f["Buyer / Consignee"] = wt(words, 105, 115, 314, 600)

    # 10. Buyer PO No — not on checklist
    f["Buyer PO No"] = ""

    # 11. Country of Origin — not on page 1 checklist
    f["Country of Origin"] = ""

    # 12. Country of Destination  y≈231  x 128-314  "Italy"
    f["Country of Destination"] = lv(228, 238)

    # 13. Port of Loading  y≈184  x 128-314  "Ahmedabad Air Cargo(INAMD4)"
    f["Port of Loading"] = lv(181, 192)

    # 14. Port of Discharge  y≈195  x 128-314  "Milano(ITMIL)"
    f["Port of Discharge"] = lv(192, 203)

    # 15. Delivery Terms (Incoterm)  y≈393  x 128-314  "CIF"
    inco_raw = lv(390, 403)
    m = re.search(r'\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b', inco_raw, re.IGNORECASE)
    f["Delivery Terms (Incoterm)"] = m.group(1).upper() if m else inco_raw

    # 16. Payment Terms  y≈510  x 128-200  "DA"
    f["Payment Terms"] = wt(words, 507, 519, 128, 200)

    # 17. Payment Days  y≈510  x 410+  "180 days" → extract number
    days_t = wt(words, 507, 519, 410, 600)
    m = re.search(r'(\d+)', days_t)
    f["Payment Days"] = m.group(1) if m else days_t

    # 18. Marks & Nos  y≈522  x 128-314
    f["Marks & Nos"] = lv(519, 533)

    # 19. Currency  y≈417  x 75-130  "EUR"
    curr_t = wt(words, 414, 424, 75, 132)
    m = re.search(r'\b(EUR|USD|GBP|AED|INR|JPY)\b', curr_t)
    f["Currency"] = m.group(1) if m else ""

    # 20. Total Invoice Value  y≈369  x 428+  "EUR 6352.00 (INR ...)"
    inv_val_raw = rv(366, 379)
    m = re.search(r'(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.[0-9]{2})', inv_val_raw)
    f["Total Invoice Value"] = m.group(1).replace(",", "") if m else ""

    # 21. FOB Value  y≈380  x 428+
    fob_raw = rv(377, 392)
    m = re.search(r'(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.[0-9]{2})', fob_raw)
    f["FOB Value"] = m.group(1).replace(",", "") if m else ""

    # 22. Gross Weight  y≈231  x 428+  "6.000 KGS"
    gross_raw = rv(228, 240)
    m = re.search(r'([0-9,]+\.[0-9]{3})', gross_raw)
    f["Gross Weight"] = m.group(1) if m else ""

    # 23. Net Weight  y≈242  x 428+  "4.500 KGS"
    net_raw = rv(239, 250)
    m = re.search(r'([0-9,]+\.[0-9]{3})', net_raw)
    f["Net Weight"] = m.group(1) if m else ""

    # 24. No. of Packages  y≈195  x 428+  "1 CTN"
    pkg_raw = rv(192, 203)
    m = re.search(r'([0-9]+)', pkg_raw)
    f["No. of Packages"] = m.group(1) if m else ""

    # 25. Product  y≈744  x 148+
    f["Product"] = wt(words, 741, 753, 148, 600)

    # 26. Model No — embedded in product desc on checklist
    m = re.search(r'MODEL\s+([A-Z0-9()* ]{4,30}?)\s+(?:PACKING|$)', f["Product"], re.IGNORECASE)
    f["Model No"] = m.group(1).strip() if m else ""

    # 27. HSN Code  y≈744  x 68-148  "90213900"
    hsn_t = wt(words, 741, 753, 68, 148)
    m = re.search(r'([0-9]{8})', hsn_t)
    f["HSN Code"] = m.group(1) if m else ""

    # 28. LUT / Bond
    m = re.search(r'(E/LUT/[0-9]+/[0-9\-]+)', full, re.IGNORECASE)
    f["LUT / Bond"] = m.group(1) if m else ""

    # 29. DBK / Advance
    m = re.search(r'\b(9021/?[A-Z])\b', full)
    f["DBK / Advance"] = m.group(1) if m else ""

    # 30. RoDTEP amount  y≈336  x 428+
    rodtep_raw = rv(333, 345)
    m = re.search(r'([0-9,]+\.[0-9]{2})', rodtep_raw)
    f["RoDTEP"] = m.group(1) if m else ""

    return f


def extract_fields(words):
    doc_type = detect_doc_type(words)
    if doc_type == "checklist":
        return extract_checklist(words), doc_type
    elif doc_type == "packing":
        return extract_packing(words), doc_type
    else:
        return extract_invoice(words), doc_type


# ─────────────────────────────────────────────────────────────────────
# COMPARISON
# ─────────────────────────────────────────────────────────────────────

CRITICAL_FIELDS = {
    "IEC", "GSTIN", "Invoice No", "Invoice Date",
    "Total Invoice Value", "FOB Value", "HSN Code",
    "Port of Loading", "Port of Discharge",
    "Country of Destination", "Gross Weight",
}

def normalise(val):
    v = re.sub(r'[\s,./\-()]', '', str(val)).upper()
    v = re.sub(r'(KGS?|MT|LBS?)$', '', v)
    return v

def compare(i, p, c):
    vals = [normalise(v) for v in (i, p, c) if v and v not in ("—", "")]
    if not vals:
        return "❌ Missing"
    if len(set(vals)) == 1:
        return "✅ Match"
    return "⚠️ Mismatch"

FIELD_ORDER = [
    "Exporter Name", "IEC", "GSTIN", "PAN", "AD Code", "Bank A/C No",
    "Invoice No", "Invoice Date", "Buyer / Consignee", "Buyer PO No",
    "Country of Origin", "Country of Destination",
    "Port of Loading", "Port of Discharge",
    "Delivery Terms (Incoterm)", "Payment Terms", "Payment Days",
    "Marks & Nos", "Currency", "Total Invoice Value", "FOB Value",
    "Gross Weight", "Net Weight", "No. of Packages",
    "Product", "Model No", "HSN Code",
    "LUT / Bond", "DBK / Advance", "RoDTEP",
]

def build_table(inv, pack, chk):
    rows = []
    for field in FIELD_ORDER:
        i = inv.get(field, "")
        p = pack.get(field, "")
        c = chk.get(field, "")
        rows.append({"Field": field,
                     "Invoice":      i or "—",
                     "Packing List": p or "—",
                     "Checklist":    c or "—",
                     "Status":       compare(i, p, c)})
    return pd.DataFrame(rows)

STATUS_COLOR = {
    "✅ Match":    "background-color:#D5F5E3;color:#1E8449",
    "⚠️ Mismatch": "background-color:#FEF9E7;color:#B7770D",
    "❌ Missing":  "background-color:#FADBD8;color:#C0392B",
}

def style_row(row):
    return [""] * (len(row) - 1) + [STATUS_COLOR.get(row["Status"], "")]

SECTIONS = {
    "🏭 Exporter & Registration": ["Exporter Name","IEC","GSTIN","PAN","AD Code","Bank A/C No"],
    "📄 Invoice Reference":       ["Invoice No","Invoice Date","Buyer / Consignee","Buyer PO No"],
    "🚢 Shipment Details":        ["Country of Origin","Country of Destination",
                                   "Port of Loading","Port of Discharge",
                                   "Delivery Terms (Incoterm)","Payment Terms","Payment Days","Marks & Nos"],
    "💰 Financial Details":       ["Currency","Total Invoice Value","FOB Value",
                                   "Gross Weight","Net Weight","No. of Packages"],
    "📦 Product Details":         ["Product","Model No","HSN Code"],
    "📋 Export Scheme / Duty":    ["LUT / Bond","DBK / Advance","RoDTEP"],
}

def render_section(title, fields, df):
    subset = df[df["Field"].isin(fields)]
    if subset.empty:
        return
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)
    st.dataframe(subset.style.apply(style_row, axis=1),
                 use_container_width=True, hide_index=True)
    st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# APP UI
# ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="app-header">
  <h1>🚢 Export Checklist Verifier</h1>
  <p>Compare Invoice · Packing List · Export Checklist — coordinate-based extraction</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    inv_file  = st.file_uploader("📄 Commercial Invoice (PDF)",    type="pdf", key="inv")
with col2:
    pack_file = st.file_uploader("📦 Packing List (PDF)",          type="pdf", key="pack")
with col3:
    chk_file  = st.file_uploader("✅ Export Checklist / SB (PDF)", type="pdf", key="chk")

st.markdown("---")

if not any([inv_file, pack_file, chk_file]):
    st.info("Upload at least one document above to begin verification.")
    st.stop()

with st.spinner("Extracting fields using coordinate-based parsing…"):
    inv_words  = get_words(inv_file)  if inv_file  else []
    pack_words = get_words(pack_file) if pack_file else []
    chk_words  = get_words(chk_file)  if chk_file  else []

    inv_data,  inv_type  = extract_fields(inv_words)  if inv_words  else ({}, "invoice")
    pack_data, pack_type = extract_fields(pack_words) if pack_words else ({}, "packing")
    chk_data,  chk_type  = extract_fields(chk_words)  if chk_words  else ({}, "checklist")

    df = build_table(inv_data, pack_data, chk_data)

matched  = (df["Status"] == "✅ Match").sum()
mismatch = (df["Status"] == "⚠️ Mismatch").sum()
missing  = (df["Status"] == "❌ Missing").sum()
total    = len(df)
pct      = int(matched / total * 100) if total else 0

t1, t2, t3, t4 = st.columns(4)
with t1:
    st.markdown(f'<div class="tile tile-matched"><h2>{matched}</h2><p>✅ Matched</p></div>', unsafe_allow_html=True)
with t2:
    st.markdown(f'<div class="tile tile-mismatch"><h2>{mismatch}</h2><p>⚠️ Mismatched</p></div>', unsafe_allow_html=True)
with t3:
    st.markdown(f'<div class="tile tile-missing"><h2>{missing}</h2><p>❌ Missing</p></div>', unsafe_allow_html=True)
with t4:
    st.metric("Completeness", f"{pct}%", delta=f"{total} fields checked")

st.markdown("---")

crit = df[(df["Field"].isin(CRITICAL_FIELDS)) & (df["Status"] != "✅ Match")]
if not crit.empty:
    html = ""
    for _, row in crit.iterrows():
        icon = "⚠️" if row["Status"] == "⚠️ Mismatch" else "❌"
        html += f'<div class="critical-item">{icon} <b>{row["Field"]}</b> — {row["Status"]}'
        if row["Status"] == "⚠️ Mismatch":
            html += (f' &nbsp;|&nbsp; Invoice: <code>{row["Invoice"]}</code>'
                     f'  Packing: <code>{row["Packing List"]}</code>'
                     f'  Checklist: <code>{row["Checklist"]}</code>')
        html += '</div>'
    st.markdown(
        f'<div class="critical-box"><h4>🚨 Critical Issues — Resolve before export clearance</h4>{html}</div>',
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
else:
    st.success("🎉 No critical issues found. All mandatory fields match.")

for sec_title, sec_fields in SECTIONS.items():
    render_section(sec_title, sec_fields, df)

with st.expander("🔍 Debug — raw text & detected doc types"):
    st.caption(f"Invoice: **{inv_type}** | Packing: **{pack_type}** | Checklist: **{chk_type}**")
    tabs = st.tabs(["Invoice", "Packing List", "Checklist"])
    for tab, fobj in zip(tabs, [inv_file, pack_file, chk_file]):
        with tab:
            txt = get_raw_text(fobj) if fobj else ""
            if txt:
                st.markdown(f'<div class="raw-text">{txt[:5000]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No document uploaded.")

st.markdown("---")
csv_data = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download Full Report (CSV)", csv_data,
                   "export_verification_report.csv", "text/csv")
