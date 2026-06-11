import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(
    page_title="Export Checklist Verifier",
    page_icon="🚢",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F0F4F8; }
.app-header {
    background: linear-gradient(135deg, #0F2D52 0%, #1A5276 100%);
    color: white; padding: 1.5rem 2rem;
    border-radius: 12px; margin-bottom: 1.5rem;
}
.app-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
.app-header p  { margin: 0; font-size: 0.85rem; opacity: 0.75; }
.section-head {
    background: #1A5276; color: white;
    padding: 0.55rem 1rem; border-radius: 6px 6px 0 0;
    font-size: 0.8rem; font-weight: 600;
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


def extract_text(uploaded_file):
    if uploaded_file is None:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        return "\n".join(pages)
    except Exception as e:
        st.warning(f"Could not read PDF: {e}")
        return ""


def extract_fields(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    full = text

    def fr(patterns):
        for pat in patterns:
            m = re.search(pat, full, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and val not in ("&", "-", "–", "/", ""):
                    return val
        return ""

    fields = {}

    # ── Exporter Name ──
    # Invoice/PL: "OMNI LENS PVT. LTD." appears early, skip CHA lines
    # Checklist: appears after "EXPORTER DETAILS" block
    exporter = ""
    # Try after EXPORTER DETAILS label first (checklist)
    for i, line in enumerate(lines):
        if re.search(r'EXPORTER\s+DETAILS', line, re.IGNORECASE):
            # IEC number is on same/next line, company name follows after
            for j in range(i+1, min(i+6, len(lines))):
                candidate = lines[j].strip()
                if re.search(r'\b(PVT|LTD|LLC|INC|CORP|EXPORTS?|TRADERS?|INDUSTRIES|ENTERPRISE)\b',
                             candidate, re.IGNORECASE):
                    if not re.search(r'(CLEARING|AGENCY|FREIGHT|FORWARDER|CHA\b|CUSTOM|GSTIN|PAN\s)',
                                     candidate, re.IGNORECASE):
                        exporter = candidate
                        break
            break
    # Fallback: first company-looking line in top 20
    if not exporter:
        for line in lines[:20]:
            if re.search(r'\b(PVT|LTD|LLC|INC|CORP|EXPORTS?|TRADERS?|INDUSTRIES|ENTERPRISE)\b',
                         line, re.IGNORECASE):
                if not re.search(r'(CLEARING|AGENCY|FREIGHT|FORWARDER|CHA\b|CUSTOM|GSTIN|PAN\s)',
                                 line, re.IGNORECASE):
                    exporter = line.strip()
                    break
    fields["Exporter Name"] = exporter

    # ── IEC ──
    # Invoice/PL: "IEC CODE : 0893006939"  on header line
    # Checklist: "0893006939 GSTIN: ..." — IEC is first token after EXPORTER DETAILS
    fields["IEC"] = fr([
        r"IEC\s*(?:CODE)?[\s:\-#]*([0-9]{10})\b",
        r"\bIEC\b[\s\S]{0,10}([0-9]{10})\b",
        # Checklist: standalone 10-digit number at start of line after EXPORTER DETAILS
        r"(?:^|\n)\s*([0-9]{10})\s+GSTIN",
    ])

    # ── GSTIN ──
    fields["GSTIN"] = fr([
        r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b",
    ])

    # ── PAN ──
    fields["PAN"] = fr([
        r"PAN\s*(?:No\.?|:)?\s*([A-Z]{5}[0-9]{4}[A-Z])\b",
        r"\b([A-Z]{5}[0-9]{4}[A-Z])\b",
    ])

    # ── AD Code ──
    # Invoice/PL: "Bank AD Code :8656901"
    # Checklist:  "Ad. Code 8656901"
    fields["AD Code"] = fr([
        r"(?:Bank\s+)?AD\s*\.?\s*Code[\s:\-]*([0-9]{7})\b",
        r"Ad\.\s*Code[\s:\-]*([0-9]{7})\b",
    ])

    # ── Invoice No ──
    # Seen: "E/GST/043/26-27" in invoice header and checklist
    # Invoice header line: "Invoice No & Date IEC CODE : 0893006939 ... E/GST/043/26-27"
    fields["Invoice No"] = fr([
        r"\b(E/(?:GST|LUT)/[0-9]+/[0-9\-]+)\b",
        r"Inv\.?\s*No\.?[\s:\-]*([A-Z0-9]{1,6}/[A-Z0-9/\-]{3,20})",
        r"Invoice\s*No[\s:\-]*([A-Z0-9]{1,6}/[A-Z0-9/\-]{3,20})",
        r"\b([0-9]{4}/[0-9]{2,3}/[0-9]{2,4})\b",
    ])

    # ── Invoice Date ──
    # Seen: "09.06.2026"
    fields["Invoice Date"] = fr([
        r"(?:Inv\.?\s*Date|Invoice\s+Date)[\s:\-]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})",
        r"\b(\d{2}[./\-]\d{2}[./\-]\d{4})\b",
        r"\b(\d{1,2}[-\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s]\d{4})\b",
    ])

    # ── Buyer / Consignee ──
    # Seen: "MD TECH srl" after Consignee label
    consignee = ""
    for i, line in enumerate(lines):
        if re.search(r'\bConsignee\b', line, re.IGNORECASE):
            for j in range(i+1, min(i+5, len(lines))):
                nxt = lines[j].strip()
                if (nxt and len(nxt) > 3
                        and not re.search(r'\b(if other|consignee|buyer|name|address)\b', nxt, re.IGNORECASE)
                        and not nxt.startswith((':', '-', '.'))):
                    consignee = nxt
                    break
            break
    # Checklist: consignee is after "CONSIGNEE" header
    if not consignee:
        for i, line in enumerate(lines):
            if re.search(r'^CONSIGNEE$', line, re.IGNORECASE):
                if i + 1 < len(lines):
                    consignee = lines[i+1].strip()
                break
    fields["Buyer / Consignee"] = consignee

    # ── Buyer PO No ──
    fields["Buyer PO No"] = fr([
        r"(?:Buyer'?s?\s+)?Order\s*(?:No\.?|Number|#)[\s:\-]*([A-Z0-9/\-]{3,25})",
        r"P\.?O\.?\s*(?:No|#)[\s:\-]*([A-Z0-9/\-]{3,25})",
    ])

    # ── Country of Origin ──
    # Invoice/PL: "Country of origin of goods ... INDIA"
    # The line is: "Country of origin of goods Country of final Destination"
    # Then next line: "INDIA ITALY"
    # So we need to find INDIA after this label
    co_origin = fr([
        r"Country\s+of\s+origin\s+of\s+goods[\s\S]{0,60}?(INDIA|[A-Z]{4,20})\s+(?:[A-Z]{4,20}|$)",
    ])
    if not co_origin:
        # Next line approach: find line with "Country of origin" then grab first word of next line
        for i, line in enumerate(lines):
            if re.search(r'Country\s+of\s+origin', line, re.IGNORECASE):
                # value may be on same line after label or on next line
                # Same line: after second occurrence splits
                m = re.search(r'Country\s+of\s+origin[^\n]*?([A-Z]{4,20})\s*$', line, re.IGNORECASE)
                if m:
                    co_origin = m.group(1)
                    break
                if i + 1 < len(lines):
                    # Next line: first word
                    nxt = lines[i+1].strip()
                    first_word = nxt.split()[0] if nxt.split() else ""
                    if re.match(r'^[A-Z]{3,20}$', first_word):
                        co_origin = first_word
                        break
    # Checklist direct
    if not co_origin:
        co_origin = fr([r"Country\s+of\s+[Oo]rigin[\s:\-]+([A-Z][A-Za-z]{2,20})\b"])
    fields["Country of Origin"] = co_origin

    # ── Country of Destination ──
    # Invoice/PL: same line as origin "Country of final Destination" → ITALY (second word on next line)
    # Checklist: "Country of Dest Italy" or "Discharge Country Italy"
    co_dest = fr([
        r"(?:Country\s+of\s+(?:final\s+)?[Dd]est(?:ination)?|Discharge\s+Country)[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
    ])
    if not co_dest:
        for i, line in enumerate(lines):
            if re.search(r'Country\s+of\s+(?:final\s+)?Dest', line, re.IGNORECASE):
                m = re.search(r'Country\s+of\s+(?:final\s+)?Dest[^\n]*?([A-Z]{4,20})\s*$', line, re.IGNORECASE)
                if m:
                    co_dest = m.group(1)
                    break
                if i + 1 < len(lines):
                    nxt = lines[i+1].strip().split()
                    # second word on next line (first = origin country)
                    if len(nxt) >= 2 and re.match(r'^[A-Z]{3,20}$', nxt[1]):
                        co_dest = nxt[1]
                        break
                    elif len(nxt) >= 1 and re.match(r'^[A-Z]{3,20}$', nxt[0]):
                        co_dest = nxt[0]
                        break
    fields["Country of Destination"] = co_dest

    # ── Port of Loading ──
    # Invoice/PL: "Port of Loading\nAHMEDABAD-INDIA"  or  "Port of Loading AHMEDABAD-INDIA"
    # Checklist:  "Port Of Loading Ahmedabad Air Cargo(INAMD4)"
    fields["Port of Loading"] = fr([
        r"Port\s+[Oo]f\s+Loading[\s:\-]+([A-Za-z][A-Za-z0-9 \-()]{3,40}?)(?=\s*(?:\n|Port|Nature|Country|$))",
        r"Port\s+[Oo]f\s+Loading[\s\n:\-]+([A-Za-z][A-Za-z0-9 \-]{3,30})",
    ])

    # ── Port of Discharge ──
    # Invoice/PL: "Port of Discharge\nMILAN" then "Final Destination\nMILAN ITALY"
    # Checklist:  "Port Of Discharge Milano(ITMIL)"
    fields["Port of Discharge"] = fr([
        r"Port\s+[Oo]f\s+Discharge[\s:\-]+([A-Za-z][A-Za-z0-9 \-()]{2,30}?)(?=\s*(?:\n|Port|Final|Country|$))",
        r"Port\s+[Oo]f\s+Discharge[\s\n:\-]+([A-Za-z][A-Za-z0-9 \-]{2,25})",
    ])

    # ── Incoterm ──
    fields["Delivery Terms (Incoterm)"] = fr([
        r"\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b",
    ])

    # ── Payment Terms ──
    # Seen: "Payment within 180 days from the date of shipment"
    # Checklist: "Nature Of Payment DA  Period Of Payment 180 days"
    fields["Payment Terms"] = fr([
        r"Nature\s+Of\s+Payment[\s:\-]+([A-Za-z]{2,10})",
        r"Payment\s+within[\s:\-]+([0-9]+\s*days?[^,\n]{0,30})",
        r"\b(DA\s+\d+\s*[Dd]ays?|DP\s+\d+\s*[Dd]ays?|Advance|T/?T|L/?C)\b",
        r"\b(DA|DP|TT|LC|Advance)\b",
    ])

    # ── Mode of Transport ──
    fields["Mode of Transport"] = fr([
        r"Mode\s+of\s+(?:Transport|Shipment)[\s:\-]+([A-Za-z]{3,15})",
        r"\b(Sea|Air|Road|Rail|Multimodal)\b",
        r"CIF\s+BY\s+\(([A-Za-z]+)\)",
    ])

    # ── Marks & Nos ──
    # Seen: "Crtn.SR.no 01 to 01 Total Cartons : 01"
    # Checklist: "WE INTEND TO CLAIM REWARDS RODTEP"
    fields["Marks & Nos"] = fr([
        r"Marks?\s*(?:&|and)\s*[Nn]o[s.]?[\s:\-]+([^\n]{3,60})",
        r"(Crtn\.SR\.no[^\n]{3,40})",
        r"(WE\s+INTEND\s+TO[^\n]{5,50})",
    ])

    # ── Currency ──
    # Invoice: "EURO" and "EUR"
    foreign = fr([r"\b(EUR|USD|GBP|AED|JPY|CNY|SGD|CAD|AUD)\b"])
    fields["Currency"] = foreign if foreign else fr([r"\b(INR)\b"])

    # ── Total Invoice Value ──
    # Invoice: "Total Tax Value (Rs.) 34697.80"  ← this is IGST only, NOT total
    # Real total: "6352.00" (EUR) or "EURO SIX THOUSAND..." → 6352.00
    # Checklist: "Inv. Value EUR 6352.00 (INR 693956.00)"
    fields["Total Invoice Value"] = fr([
        r"Inv\.?\s*Value\s+(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.?[0-9]{0,2})",
        r"(?:Invoice|Inv\.?)\s*(?:Value|Amount)[\s:\-]*(?:EUR|USD|GBP|INR|AED)?\s*([0-9,]+\.?[0-9]{0,2})",
        r"Amount\s+Chargeable[^\n]*\n[^\n]*?([0-9,]{3,}\.?[0-9]{0,2})\s*$",
        # Last number on the "Amount Chargeable" line
        r"(?:EUR|USD|GBP)\s+(?:[A-Z ]+\s+)?([0-9,]+\.?[0-9]{0,2})\s*$",
        r"(?:IGST\s+Taxable\s+Value|Inv\.?\s*Value)[\s(INR):\-]*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── FOB Value ──
    # Invoice: "Before Tax Value (Rs.) 693956.00"  ← INR FOB
    # Checklist: "FOB Value EUR 6337.00 (INR 692317.25)" or "Total FOB (INR) 692317.25"
    fields["FOB Value"] = fr([
        r"FOB\s+Value\s+(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.?[0-9]{0,2})",
        r"Total\s+FOB\s*\([A-Z]+\)[\s:\-]*([0-9,]+\.?[0-9]{0,2})",
        r"FOB\s+Val(?:ue)?\s*\([A-Z]+\)[\s:\-]*([0-9,]+\.?[0-9]{0,2})",
        r"Before\s+Tax\s+Value\s*\([A-Z]+\.?\)[\s:\-]*([0-9,]+\.?[0-9]{0,2})",
        r"FOB[\s:\-]+(?:EUR|USD|GBP|INR|AED)?\s*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── Gross Weight ──
    # PL: "6.00"  Checklist: "Gross Weight 6.000 KGS"
    fields["Gross Weight"] = fr([
        r"Gross\s+(?:Weight|Wt\.?|wt)[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"G\.?\s*W(?:eight|t)?\.?[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        # PL table: "465 4.50 6.00" — gross is last number in totals row
        r"Total\s+[0-9]+\s+([0-9]+\.[0-9]{2,3})\s+([0-9]+\.[0-9]{2,3})",
    ])
    # For PL: gross weight is 3rd number in "Total 465 4.50 6.00"
    if not fields["Gross Weight"]:
        m = re.search(r'Total\s+[0-9]+\s+([0-9]+\.[0-9]{2,3})\s+([0-9]+\.[0-9]{2,3})', full)
        if m:
            fields["Gross Weight"] = m.group(2)  # last = gross

    # ── Net Weight ──
    fields["Net Weight"] = fr([
        r"Net\s+(?:Weight|Wt\.?|wt)[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"N\.?\s*W(?:eight|t)?\.?[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
    ])
    # For PL: net weight is 2nd number in "Total 465 4.50 6.00"
    if not fields["Net Weight"]:
        m = re.search(r'Total\s+[0-9]+\s+([0-9]+\.[0-9]{2,3})\s+([0-9]+\.[0-9]{2,3})', full)
        if m:
            fields["Net Weight"] = m.group(1)  # first = net

    # ── No. of Packages ──
    # Invoice/PL: "Total Cartons : 01"
    # Checklist: "Total Packages 1 CTN"
    fields["No. of Packages"] = fr([
        r"Total\s+(?:Cartons?|Packages?|Pkgs?)[\s:\-]*([0-9]+)\b",
        r"(?:No\.?\s+of\s+)?(?:Cartons?|Packages?|Boxes|Cases)[\s:\-]*([0-9]+)\b",
        r"([0-9]+)\s+CTN\b",
    ])

    # ── LUT / Bond ──
    # Invoice has: "E/GST/043/26-27" (same as invoice no for GST export)
    # Checklist: LUT info in marks: "LUTNO.AD2403260563860DT:28.03.2026"
    fields["LUT / Bond"] = fr([
        r"\b(E/LUT/[0-9]+/[0-9\-]+)\b",
        r"LUT\s*(?:No\.?|NUMBER)?[\s:\-]*([A-Z0-9/\-]{4,30})",
        r"LUTNO\.([A-Z0-9]+)",
    ])

    # ── DBK ──
    # Seen: "DBK Sr. no. 9021/B" and "Shipment Under Duty Drawback No. 9021/B"
    fields["DBK / Drawback"] = fr([
        r"Duty\s+Drawback\s+No\.?[\s:\-]*([A-Z0-9/\-]{2,20})",
        r"DBK\s+(?:Sr\.?\s*[Nn]o\.?|Declaration|Sl\s*No)[\s:\-]*([A-Z0-9/\-]{2,20})",
        r"(?:DBK|Drawback)[\s:\-]+([A-Z0-9/\-]{2,15})",
        r"9021/?[A-Z]\b",
    ])
    if not fields["DBK / Drawback"]:
        m = re.search(r'\b(9021/?[A-Z])\b', full)
        if m:
            fields["DBK / Drawback"] = m.group(1)

    # ── RoDTEP ──
    # Checklist: "RODTEP Amount(INR) 2704.74"
    fields["RoDTEP"] = fr([
        r"RODTEP\s+Amount[\s(INR):\-]*([0-9,]+\.?[0-9]{0,2})",
        r"RoDTEP[\s:\-]*(?:Amount)?[\s(INR):\-]*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── IGST ──
    # Checklist: "IGST Amount(INR) 34697.80"
    fields["IGST Refund"] = fr([
        r"IGST\s+Amount[\s(INR):\-]*([0-9,]+\.?[0-9]{0,2})",
        r"IGST[\s(INR):\-]+([0-9,]+\.?[0-9]{0,2})",
        r"Add\s*:\s*IGST\s*\([A-Z]+\.?\)[\s:\-]*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── HSN Code ──
    # Invoice: "H.S.CODE : 9021 3900"  (with space in middle)
    # Checklist: "90213900" (RITC column)
    fields["HSN Code"] = fr([
        r"H\.?S\.?(?:N\.?)?\s*CODE[\s:\-]*([0-9]{4}\s*[0-9]{4})",
        r"H\.?S\.?(?:N\.?)?\s*CODE[\s:\-]*([0-9]{4,8})",
        r"\bRITC\b[\s\S]{0,30}?([0-9]{8})\b",
        r"\b(9021\s*3900)\b",
        r"\b(90213900)\b",
    ])
    # Clean space from HSN like "9021 3900" → "90213900"
    if fields["HSN Code"]:
        fields["HSN Code"] = fields["HSN Code"].replace(" ", "")

    # ── Bank A/C No ──
    # Invoice/PL: "A/C - 01020107664"
    # Checklist: "Forex Bank A/c No" followed by number, or "BankA/cNo 0036683667"
    fields["Bank A/C No"] = fr([
        r"A/C\s*[-–]\s*([0-9]{9,18})\b",
        r"(?:Bank\s*)?A/?[Cc]\s*(?:No\.?|Number)?[\s:\-]+([0-9]{9,18})\b",
        r"BankA/cNo\s*([0-9]{9,18})\b",
        r"Forex\s+Bank\s+A/c\s+No[\s\S]{0,20}?([0-9]{9,18})\b",
        r"Account\s*(?:No\.?|Number)[\s:\-]*([0-9]{9,18})\b",
    ])

    return {k: v.strip() if v else "" for k, v in fields.items()}


CRITICAL_FIELDS = {
    "IEC", "GSTIN", "Invoice No", "Invoice Date",
    "Total Invoice Value", "FOB Value", "HSN Code",
    "Port of Loading", "Port of Discharge",
    "Country of Destination", "Gross Weight",
}

def normalise(val):
    return re.sub(r"[\s,./\-()]", "", val).upper()

def compare(inv_val, pack_val, chk_val):
    vals = [normalise(v) for v in (inv_val, pack_val, chk_val) if v]
    if not vals:
        return "❌ Missing"
    if len(set(vals)) == 1:
        return "✅ Match"
    return "⚠️ Mismatch"

def build_comparison_table(inv, pack, chk):
    rows = []
    for field in inv.keys():
        i = inv.get(field, "")
        p = pack.get(field, "")
        c = chk.get(field, "")
        status = compare(i, p, c)
        rows.append({
            "Field": field,
            "Invoice": i or "—",
            "Packing List": p or "—",
            "Checklist": c or "—",
            "Status": status,
        })
    return pd.DataFrame(rows)


STATUS_COLOR = {
    "✅ Match":    "background-color:#D5F5E3;color:#1E8449",
    "⚠️ Mismatch": "background-color:#FEF9E7;color:#B7770D",
    "❌ Missing":  "background-color:#FADBD8;color:#C0392B",
}

def style_row(row):
    style = STATUS_COLOR.get(row["Status"], "")
    return [""] * (len(row) - 1) + [style]

SECTIONS = {
    "🏭 Exporter & Registration": ["Exporter Name", "IEC", "GSTIN", "PAN", "AD Code", "Bank A/C No"],
    "📄 Invoice Reference":       ["Invoice No", "Invoice Date", "Buyer / Consignee", "Buyer PO No"],
    "🚢 Shipment Details":        ["Country of Origin", "Country of Destination",
                                   "Port of Loading", "Port of Discharge",
                                   "Delivery Terms (Incoterm)", "Payment Terms",
                                   "Mode of Transport", "Marks & Nos"],
    "💰 Financial Details":       ["Currency", "Total Invoice Value", "FOB Value",
                                   "Gross Weight", "Net Weight", "No. of Packages",
                                   "HSN Code"],
    "📋 Export Scheme / Duty":    ["LUT / Bond", "DBK / Drawback", "RoDTEP", "IGST Refund"],
}

def render_section(title, fields, df):
    subset = df[df["Field"].isin(fields)]
    if subset.empty:
        return
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)
    st.dataframe(
        subset.style.apply(style_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)


# ── APP ──

st.markdown("""
<div class="app-header">
  <h1>🚢 Export Checklist Verifier</h1>
  <p>Compare Invoice · Packing List · Export Checklist — field by field</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    inv_file  = st.file_uploader("📄 Commercial Invoice (PDF)", type="pdf", key="inv")
with col2:
    pack_file = st.file_uploader("📦 Packing List (PDF)", type="pdf", key="pack")
with col3:
    chk_file  = st.file_uploader("✅ Export Checklist / SB (PDF)", type="pdf", key="chk")

st.markdown("---")

if not any([inv_file, pack_file, chk_file]):
    st.info("Upload at least one document above to begin verification.")
    st.stop()

with st.spinner("Reading documents…"):
    inv_text  = extract_text(inv_file)  if inv_file  else ""
    pack_text = extract_text(pack_file) if pack_file else ""
    chk_text  = extract_text(chk_file)  if chk_file  else ""

    inv_data  = extract_fields(inv_text)
    pack_data = extract_fields(pack_text)
    chk_data  = extract_fields(chk_text)

    df = build_comparison_table(inv_data, pack_data, chk_data)

matched  = (df["Status"] == "✅ Match").sum()
mismatch = (df["Status"] == "⚠️ Mismatch").sum()
missing  = (df["Status"] == "❌ Missing").sum()
total    = len(df)

t1, t2, t3, t4 = st.columns(4)
with t1:
    st.markdown(f'<div class="tile tile-matched"><h2>{matched}</h2><p>✅ Matched</p></div>', unsafe_allow_html=True)
with t2:
    st.markdown(f'<div class="tile tile-mismatch"><h2>{mismatch}</h2><p>⚠️ Mismatched</p></div>', unsafe_allow_html=True)
with t3:
    st.markdown(f'<div class="tile tile-missing"><h2>{missing}</h2><p>❌ Missing</p></div>', unsafe_allow_html=True)
with t4:
    pct = int(matched / total * 100) if total else 0
    st.metric("Completeness", f"{pct}%", delta=f"{total} fields checked")

st.markdown("---")

critical_issues = df[
    (df["Field"].isin(CRITICAL_FIELDS)) &
    (df["Status"] != "✅ Match")
]
if not critical_issues.empty:
    lines_html = ""
    for _, row in critical_issues.iterrows():
        icon = "⚠️" if row["Status"] == "⚠️ Mismatch" else "❌"
        lines_html += f'<div class="critical-item">{icon} <b>{row["Field"]}</b> — {row["Status"]}'
        if row["Status"] == "⚠️ Mismatch":
            lines_html += (f' &nbsp;|&nbsp; Invoice: <code>{row["Invoice"]}</code>'
                           f' Packing: <code>{row["Packing List"]}</code>'
                           f' Checklist: <code>{row["Checklist"]}</code>')
        lines_html += '</div>'
    st.markdown(f"""
    <div class="critical-box">
        <h4>🚨 Critical Issues — Resolve before export clearance</h4>
        {lines_html}
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
else:
    st.success("🎉 No critical issues found. All mandatory fields match.")

for section_title, field_list in SECTIONS.items():
    render_section(section_title, field_list, df)

with st.expander("🔍 View extracted raw text (debug)"):
    tabs = st.tabs(["Invoice", "Packing List", "Checklist"])
    for tab, txt in zip(tabs, [inv_text, pack_text, chk_text]):
        with tab:
            if txt:
                st.markdown(f'<div class="raw-text">{txt[:5000]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No document uploaded.")

st.markdown("---")
csv_data = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download Full Report (CSV)",
    data=csv_data,
    file_name="export_verification_report.csv",
    mime="text/csv",
)
