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


# ═══════════════════════════════════════════════════════════════
# PDF WORD EXTRACTION
# ═══════════════════════════════════════════════════════════════

def get_words(uploaded_file):
    """Return list of {text, x0, top} across all pages."""
    if uploaded_file is None:
        return []
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            all_words, offset = [], 0
            for page in pdf.pages:
                for w in page.extract_words():
                    all_words.append({
                        "text": w["text"],
                        "x0":  w["x0"],
                        "top": w["top"] + offset,
                    })
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


def wt(words, y1, y2, x1=0, x2=600):
    """Text of all words inside bounding box [x1,x2) × [y1,y2]."""
    return " ".join(
        w["text"] for w in words
        if y1 <= w["top"] <= y2 and x1 <= w["x0"] < x2
    ).strip()


def detect_doc_type(words):
    head = " ".join(w["text"] for w in words[:80]).upper()
    if "CHECKLIST FOR SHIPPING BILL" in head or "SKYLINE AIR" in head:
        return "checklist"
    if "PACKING LIST" in head:
        return "packing"
    return "invoice"


# ═══════════════════════════════════════════════════════════════
# INVOICE EXTRACTOR
# All coordinates verified from sample_invoice__2_.pdf (595×842 pt)
#
#  y=31   → header row: Exporter | Invoice No & Date | IEC CODE
#  y=43   → OMNI LENS PVT. LTD. (left col x=21)
#  y=66   → E/LUT/062/26-27 (x=248) | PAN (x=469)
#  y=102  → 11.06.2026 (x=248)      | GSTIN (x=453)
#  y=142  → Other Ref               | Bank AD Code : 8656901
#  y=176  → TIA Co. Ltd. (consignee, x=21)
#  y=227  → INDIA (x=329) | KOREA REPUBLIC (x=470)
#  y=268  → TIA FEDEX NO. (marks, x=48)
#  y=293  → A/C - 01020107664 (bank, x=378)
#  y=296  → AHMEDABAD-INDIA (POL, x=173)
#  y=319  → SEOUL/KOREA (POD, x=67)
#  y=311  → EX-WORKS (AHMEDABAD) (incoterm, x=363)
#  y=252  → 100 % Advance (payment, x=385)
#  y=343  → USD USD (currency, x=459/531)
#  y=368  → Total Cartons : 01
#  y=379  → item line: qty/rate/amount
#  y=391  → Model : LBHF32UVASP
#  y=403  → H.S.CODE : 9021 3900
#  y=693  → total amount line
# ═══════════════════════════════════════════════════════════════

def extract_invoice(words):
    full = " ".join(w["text"] for w in words)
    f = {}

    # 1. Exporter Name — y≈43, x 21–230
    f["Exporter Name"] = wt(words, 40, 48, 21, 230)

    # 2. IEC — y≈31, x 460+, strip label "IEC CODE :"
    iec_raw = wt(words, 28, 36, 460, 600)
    m = re.search(r'([0-9]{10})', iec_raw)
    f["IEC"] = m.group(1) if m else ""

    # 3. GSTIN — y≈102, x 440+
    gstin_raw = wt(words, 99, 108, 440, 600)
    m = re.search(r'([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])', gstin_raw)
    f["GSTIN"] = m.group(1) if m else ""

    # 4. PAN — y≈66, x 460+
    pan_raw = wt(words, 63, 70, 460, 600)
    m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', pan_raw)
    f["PAN"] = m.group(1) if m else ""

    # 5. AD Code — y≈142, x 470+, 7-digit number
    ad_raw = wt(words, 139, 147, 470, 600)
    m = re.search(r'([0-9]{7})', ad_raw)
    f["AD Code"] = m.group(1) if m else ""

    # 6. Bank A/C No — y≈293, x 378+
    bank_raw = wt(words, 289, 298, 378, 600)
    m = re.search(r'([0-9]{9,18})', bank_raw)
    f["Bank A/C No"] = m.group(1) if m else ""

    # 7. Invoice No — y≈66, x 240–420
    inv_raw = wt(words, 63, 70, 240, 420)
    m = re.search(r'(E/(?:LUT|GST)/[0-9]+/[0-9\-]+)', inv_raw, re.IGNORECASE)
    f["Invoice No"] = m.group(1) if m else inv_raw

    # 8. Invoice Date — y≈102, x 240–360
    date_raw = wt(words, 99, 108, 240, 360)
    m = re.search(r'(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})', date_raw)
    f["Invoice Date"] = m.group(1) if m else ""

    # 9. Buyer / Consignee — y≈176, x 21–230 (first name line below label)
    f["Buyer / Consignee"] = wt(words, 173, 181, 21, 230)

    # 10. Buyer PO No — y≈117, x 336+ (after "Buyer's Order No. & Date :")
    po_raw = wt(words, 114, 122, 336, 600).strip(": ")
    f["Buyer PO No"] = po_raw if po_raw and po_raw not in (":", "") else ""

    # 11. Country of Origin — y≈227, x 296–465
    f["Country of Origin"] = wt(words, 223, 231, 296, 465)

    # 12. Country of Destination — y≈227, x 465+
    f["Country of Destination"] = wt(words, 223, 231, 465, 600)

    # 13. Port of Loading — y≈296, x 160–295
    f["Port of Loading"] = wt(words, 292, 301, 160, 295)

    # 14. Port of Discharge — y≈319, x 60–175
    f["Port of Discharge"] = wt(words, 315, 324, 60, 175)

    # 15. Delivery Terms (Incoterm) — y≈311, x 355+ e.g. "EX-WORKS (AHMEDABAD)" or "CIF"
    inco_raw = wt(words, 307, 316, 355, 600)
    m = re.search(r'\b(FOB|CIF|CFR|EXW|EX.WORKS|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b',
                  inco_raw, re.IGNORECASE)
    f["Delivery Terms (Incoterm)"] = m.group(1).upper() if m else inco_raw

    # 16. Payment Terms — y≈252, x 370+
    pay_raw = wt(words, 248, 257, 370, 600)
    f["Payment Terms"] = pay_raw

    # 17. Payment Days
    m = re.search(r'within\s+(\d+)\s*days', full, re.IGNORECASE)
    f["Payment Days"] = m.group(1) if m else ""

    # 18. Marks & Nos — pre-carriage ref y≈268 (TIA FEDEX / DHL) else carton line y≈356
    pre_raw = wt(words, 264, 273, 40, 200)
    if pre_raw:
        f["Marks & Nos"] = pre_raw
    else:
        f["Marks & Nos"] = wt(words, 353, 370, 0, 200)

    # 19. Currency — column header y≈343, x 450+
    curr_raw = wt(words, 339, 347, 450, 600)
    m = re.search(r'\b(EUR|USD|GBP|AED|INR|JPY)\b', curr_raw)
    f["Currency"] = m.group(1) if m else ""

    # 20. Total Invoice Value — y≈693, last number on Amount Chargeable line
    total_raw = wt(words, 689, 699)
    nums = re.findall(r'([0-9,]+\.[0-9]{2})', total_raw)
    f["Total Invoice Value"] = nums[-1].replace(",", "") if nums else ""

    # 21. FOB Value — "Before Tax Value (Rs.) NNN"
    m = re.search(r'Before\s+Tax\s+Value[^0-9]*([0-9,]+\.?[0-9]{0,2})', full)
    f["FOB Value"] = m.group(1).replace(",", "") if m else ""

    # 22 & 23. Gross/Net Weight — not on invoice
    f["Gross Weight"] = ""
    f["Net Weight"]   = ""

    # 24. No. of Packages — y≈368
    pkg_raw = wt(words, 364, 373, 0, 200)
    m = re.search(r'(\d+)', pkg_raw)
    f["No. of Packages"] = m.group(1) if m else ""

    # 25. Product — y≈379, x 133–395
    f["Product"] = wt(words, 375, 385, 133, 395)

    # 26. Model No — y≈391, x 155+
    f["Model No"] = wt(words, 387, 398, 155, 600)

    # 27. HSN Code — y≈403, x 175+  "9021 3900" → remove space
    hsn_raw = wt(words, 399, 410, 175, 600)
    m = re.search(r'([0-9]{4}\s*[0-9]{4}|[0-9]{8})', hsn_raw)
    f["HSN Code"] = m.group(1).replace(" ", "") if m else ""

    # 28. LUT / Bond — invoice number itself if it contains "LUT"
    f["LUT / Bond"] = f["Invoice No"] if "LUT" in f.get("Invoice No", "").upper() else ""

    # 29. DBK / Advance — "DBK Sr. No. 9021/B" line
    dbk_raw = wt(words, 435, 448)
    m = re.search(r'DBK\s+Sr\.?\s*No\.?\s*([A-Z0-9/]+)', dbk_raw, re.IGNORECASE)
    if not m:
        m = re.search(r'\b(9021/?[A-Z])\b', full)
    f["DBK / Advance"] = m.group(1) if m else ""

    # 30. RoDTEP
    f["RoDTEP"] = "Claimed" if re.search(r'RoDTEP', full, re.IGNORECASE) else ""

    return f


# ═══════════════════════════════════════════════════════════════
# PACKING LIST EXTRACTOR
# Same header layout as invoice; adds gross/net from totals row
# ═══════════════════════════════════════════════════════════════

def extract_packing(words):
    f = extract_invoice(words)      # reuse — identical header layout
    full = " ".join(w["text"] for w in words)

    # Gross / Net from totals row "Total 465 4.50 6.00"
    m = re.search(r'Total\s+[0-9]+\s+([0-9]+\.[0-9]{2,3})\s+([0-9]+\.[0-9]{2,3})', full)
    if m:
        f["Net Weight"]   = m.group(1)
        f["Gross Weight"] = m.group(2)

    m2 = re.search(r'Total\s+Cartons?\s*:\s*0*([1-9][0-9]*)', full, re.IGNORECASE)
    if m2:
        f["No. of Packages"] = m2.group(1)

    f["FOB Value"]           = ""
    f["Total Invoice Value"] = ""
    return f


# ═══════════════════════════════════════════════════════════════
# CHECKLIST EXTRACTOR
# Verified coordinates from 3234316761-OMNI__2_.PDF (595×842 pt)
#
# Layout:
#   Left labels   x 18–120   Left values   x 128–314
#   Right labels  x 314–428  Right values  x 428–580
#
#  y=108  → 0893006939 (IEC, x=19) | GSTIN: 24AAACO1725F1ZY (x=123) | MD TECH SRL (x=314)
#  y=120  → PAN No: AAACO1725F (x=18) | Exporter Type (x=123) | VIA F.LLI... (x=314)
#  y=132  → OMNI LENS PVT. LTD. (x=19)
#  y=184  → Port Of Loading | Ahmedabad Air Cargo(INAMD4) (x=128)
#  y=195  → Port Of Discharge | Milano(ITMIL) (x=128) | Total Packages | 1 CTN (x=428)
#  y=231  → Country of Dest | Italy (x=128) | Gross Weight | 6.000 KGS (x=428)
#  y=243  → Master AWB No | Net Weight | 4.500 KGS (x=428)
#  y=288  → Ad. Code | 8656901 (x=128)
#  y=300  → Forex Bank A/c No (x=19) [value blank on this form]
#  y=336  → RODTEP Amount(INR) | 2704.74 (x=428)
#  y=370  → Inv. No | E/GST/043/26-27 (x=128) | Inv. Value EUR 6352.00 (x=428)
#  y=381  → Inv. Date | 09-Jun-2026 (x=128) | FOB Value EUR 6337.00 (x=428)
#  y=393  → Nature of contract | CIF (x=128)
#  y=417  → Inv. Currenc | EUR (x=82)
#  y=510  → Nature Of Payment | DA (x=128) | Period Of Payment | 180 days (x=414)
#  y=522  → Marks & Nos | WE INTEND TO CLAIM REWARDS RODTEP (x=128)
#  y=744  → 1 | 90213900 | INTRAOCULAR LENS... (item line)
# ═══════════════════════════════════════════════════════════════

def extract_checklist(words):
    full = " ".join(w["text"] for w in words)
    f = {}

    def lv(y1, y2, x1=128, x2=314):
        return wt(words, y1, y2, x1, x2)

    def rv(y1, y2, x1=428, x2=585):
        return wt(words, y1, y2, x1, x2)

    # 1. Exporter Name — y≈132, x 18–200
    f["Exporter Name"] = wt(words, 129, 138, 18, 200)

    # 2. IEC — y≈108, x 18–122 (first token = 10-digit number)
    iec_raw = wt(words, 105, 114, 18, 122)
    m = re.search(r'([0-9]{10})', iec_raw)
    f["IEC"] = m.group(1) if m else ""

    # 3. GSTIN — y≈108, x 148–314
    gstin_raw = wt(words, 105, 114, 148, 314)
    m = re.search(r'([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])', gstin_raw)
    f["GSTIN"] = m.group(1) if m else ""

    # 4. PAN — y≈120, x 45–122
    pan_raw = wt(words, 117, 126, 45, 122)
    m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', pan_raw)
    f["PAN"] = m.group(1) if m else ""

    # 5. AD Code — y≈288, x 120–200
    ad_raw = wt(words, 284, 295, 120, 200)
    m = re.search(r'([0-9]{7})', ad_raw)
    f["AD Code"] = m.group(1) if m else ""

    # 6. Bank A/C No — label "Forex Bank A/c No" y≈300; value usually blank
    bank_raw = wt(words, 296, 308, 128, 314)
    m = re.search(r'([0-9]{9,18})', bank_raw)
    f["Bank A/C No"] = m.group(1) if m else ""

    # 7. Invoice No — y≈370, x 128–314
    inv_raw = lv(366, 376)
    m = re.search(r'(E/(?:LUT|GST)/[0-9]+/[0-9\-]+)', inv_raw, re.IGNORECASE)
    f["Invoice No"] = m.group(1) if m else inv_raw

    # 8. Invoice Date — y≈381, x 128–314
    date_raw = lv(377, 388)
    m = re.search(r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}|\d{2}-[A-Za-z]+-\d{4})', date_raw)
    f["Invoice Date"] = m.group(1) if m else date_raw

    # 9. Buyer / Consignee — y≈108, x 314+
    f["Buyer / Consignee"] = wt(words, 105, 114, 314, 600)

    # 10. Buyer PO No — not on checklist
    f["Buyer PO No"] = ""

    # 11. Country of Origin — not shown on checklist page 1
    f["Country of Origin"] = ""

    # 12. Country of Destination — y≈231, x 128–314  "Italy"
    f["Country of Destination"] = lv(227, 237)

    # 13. Port of Loading — y≈184, x 128–314  "Ahmedabad Air Cargo(INAMD4)"
    f["Port of Loading"] = lv(180, 191)

    # 14. Port of Discharge — y≈195, x 128–314  "Milano(ITMIL)"
    f["Port of Discharge"] = lv(191, 202)

    # 15. Delivery Terms (Incoterm) — y≈393, x 128–314  "CIF"
    inco_raw = lv(389, 401)
    m = re.search(r'\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b',
                  inco_raw, re.IGNORECASE)
    f["Delivery Terms (Incoterm)"] = m.group(1).upper() if m else inco_raw

    # 16. Payment Terms — y≈510, x 128–200  "DA"
    f["Payment Terms"] = wt(words, 506, 517, 128, 200)

    # 17. Payment Days — y≈510, x 410+  "180 days" → extract number
    days_raw = wt(words, 506, 517, 410, 600)
    m = re.search(r'(\d+)', days_raw)
    f["Payment Days"] = m.group(1) if m else days_raw

    # 18. Marks & Nos — y≈522, x 128–314
    f["Marks & Nos"] = lv(518, 531)

    # 19. Currency — y≈417, x 75–130  "EUR"
    curr_raw = wt(words, 413, 423, 75, 132)
    m = re.search(r'\b(EUR|USD|GBP|AED|INR|JPY)\b', curr_raw)
    f["Currency"] = m.group(1) if m else ""

    # 20. Total Invoice Value — y≈369/370, x 428+  "EUR 6352.00 (INR ...)"
    inv_val_raw = rv(365, 377)
    m = re.search(r'(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.[0-9]{2})', inv_val_raw)
    f["Total Invoice Value"] = m.group(1).replace(",", "") if m else ""

    # 21. FOB Value — y≈380/381, x 428+
    fob_raw = rv(376, 390)
    m = re.search(r'(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.[0-9]{2})', fob_raw)
    f["FOB Value"] = m.group(1).replace(",", "") if m else ""

    # 22. Gross Weight — y≈231, x 428+  "6.000 KGS"
    gross_raw = rv(227, 237)
    m = re.search(r'([0-9]+\.[0-9]{3})', gross_raw)
    f["Gross Weight"] = m.group(1) if m else ""

    # 23. Net Weight — y≈243, x 428+  "4.500 KGS"
    net_raw = rv(239, 250)
    m = re.search(r'([0-9]+\.[0-9]{3})', net_raw)
    f["Net Weight"] = m.group(1) if m else ""

    # 24. No. of Packages — y≈195, x 428+  "1 CTN"
    pkg_raw = rv(191, 202)
    m = re.search(r'([0-9]+)', pkg_raw)
    f["No. of Packages"] = m.group(1) if m else ""

    # 25. Product — y≈744, x 148+
    f["Product"] = wt(words, 740, 753, 148, 600)

    # 26. Model No — extracted from product description
    prod = f["Product"]
    m = re.search(r'MODEL\s+([A-Z0-9()*\- ]{3,30}?)(?:\s+PACKING|\s*$)', prod, re.IGNORECASE)
    f["Model No"] = m.group(1).strip() if m else ""

    # 27. HSN Code — y≈744, x 68–148  "90213900"
    hsn_raw = wt(words, 740, 753, 68, 148)
    m = re.search(r'([0-9]{8})', hsn_raw)
    f["HSN Code"] = m.group(1) if m else ""

    # 28. LUT / Bond
    m = re.search(r'(E/LUT/[0-9]+/[0-9\-]+)', full, re.IGNORECASE)
    f["LUT / Bond"] = m.group(1) if m else ""

    # 29. DBK / Advance
    m = re.search(r'\b(9021/?[A-Z])\b', full)
    f["DBK / Advance"] = m.group(1) if m else ""

    # 30. RoDTEP amount — y≈336, x 428+
    rodtep_raw = rv(332, 343)
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


# ═══════════════════════════════════════════════════════════════
# COMPARISON
# ═══════════════════════════════════════════════════════════════

CRITICAL_FIELDS = {
    "IEC", "GSTIN", "Invoice No", "Invoice Date",
    "Total Invoice Value", "FOB Value", "HSN Code",
    "Port of Loading", "Port of Discharge",
    "Country of Destination", "Gross Weight",
}

def normalise(val):
    v = re.sub(r'[\s,./\-()]', '', str(val)).upper()
    return re.sub(r'(KGS?|MT|LBS?)$', '', v)

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
    "🏭 Exporter & Registration": [
        "Exporter Name","IEC","GSTIN","PAN","AD Code","Bank A/C No"],
    "📄 Invoice Reference": [
        "Invoice No","Invoice Date","Buyer / Consignee","Buyer PO No"],
    "🚢 Shipment Details": [
        "Country of Origin","Country of Destination",
        "Port of Loading","Port of Discharge",
        "Delivery Terms (Incoterm)","Payment Terms","Payment Days","Marks & Nos"],
    "💰 Financial Details": [
        "Currency","Total Invoice Value","FOB Value",
        "Gross Weight","Net Weight","No. of Packages"],
    "📦 Product Details": [
        "Product","Model No","HSN Code"],
    "📋 Export Scheme / Duty": [
        "LUT / Bond","DBK / Advance","RoDTEP"],
}

def render_section(title, fields, df):
    subset = df[df["Field"].isin(fields)]
    if subset.empty:
        return
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)
    st.dataframe(subset.style.apply(style_row, axis=1),
                 use_container_width=True, hide_index=True)
    st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# APP UI
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<div class="app-header">
  <h1>🚢 Export Checklist Verifier</h1>
  <p>Compare Invoice · Packing List · Export Checklist — pixel-precise extraction</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1: inv_file  = st.file_uploader("📄 Commercial Invoice (PDF)",    type="pdf", key="inv")
with c2: pack_file = st.file_uploader("📦 Packing List (PDF)",          type="pdf", key="pack")
with c3: chk_file  = st.file_uploader("✅ Export Checklist / SB (PDF)", type="pdf", key="chk")

st.markdown("---")

if not any([inv_file, pack_file, chk_file]):
    st.info("Upload at least one document above to begin verification.")
    st.stop()

with st.spinner("Extracting fields using pixel-coordinate parsing…"):
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
with t1: st.markdown(f'<div class="tile tile-matched"><h2>{matched}</h2><p>✅ Matched</p></div>',  unsafe_allow_html=True)
with t2: st.markdown(f'<div class="tile tile-mismatch"><h2>{mismatch}</h2><p>⚠️ Mismatched</p></div>', unsafe_allow_html=True)
with t3: st.markdown(f'<div class="tile tile-missing"><h2>{missing}</h2><p>❌ Missing</p></div>',  unsafe_allow_html=True)
with t4: st.metric("Completeness", f"{pct}%", delta=f"{total} fields checked")

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
    st.caption(f"Detected → Invoice: **{inv_type}** | Packing: **{pack_type}** | Checklist: **{chk_type}**")
    tabs = st.tabs(["Invoice", "Packing List", "Checklist"])
    for tab, fobj in zip(tabs, [inv_file, pack_file, chk_file]):
        with tab:
            txt = get_raw_text(fobj) if fobj else ""
            st.markdown(f'<div class="raw-text">{txt[:5000]}</div>' if txt
                        else "<i>No document uploaded.</i>", unsafe_allow_html=True)

st.markdown("---")
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download Full Report (CSV)", csv_bytes,
                   "export_verification_report.csv", "text/csv")
