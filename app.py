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
        """Find first regex match across full text."""
        for pat in patterns:
            m = re.search(pat, full, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and val not in ("&", "-", "–", "/", ""):
                    return val
        return ""

    def next_line_after(keyword_pat):
        """Return stripped next line after line matching keyword."""
        for i, line in enumerate(lines):
            if re.search(keyword_pat, line, re.IGNORECASE):
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
        return ""

    def same_or_next(keyword_pat, value_pat=None):
        """Extract value same line (after colon) or next line."""
        for i, line in enumerate(lines):
            if re.search(keyword_pat, line, re.IGNORECASE):
                if value_pat:
                    m = re.search(value_pat, line, re.IGNORECASE)
                    if m:
                        return m.group(1).strip()
                parts = re.split(r'[:\-]', line, maxsplit=1)
                if len(parts) > 1:
                    val = parts[-1].strip()
                    if val and len(val) > 1 and val not in ("&", "-", "–"):
                        return val
                if i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt and len(nxt) > 1:
                        return nxt
        return ""

    fields = {}

    # ── Exporter Name ──
    # First line with company keyword, skip CHA/clearing agents
    exporter = ""
    for line in lines[:20]:
        if re.search(r'\b(PVT|LTD|LLC|INC|CORP|EXPORTS?|TRADERS?|INDUSTRIES|ENTERPRISE)\b', line, re.IGNORECASE):
            if not re.search(r'(CLEARING|AGENCY|FREIGHT|FORWARDER|CHA\b|CUSTOM)', line, re.IGNORECASE):
                exporter = line.strip()
                break
    fields["Exporter Name"] = exporter

    # ── IEC ── strict 10-digit
    fields["IEC"] = fr([
        r"\bIEC\b[\s:\-#]*([0-9]{10})\b",
        r"\bIEC\s*(?:CODE|No\.?)[\s:\-]*([0-9]{10})\b",
        r"(?:IEC|I\.E\.C)[\s\S]{0,10}([0-9]{10})",
    ])

    # ── GSTIN ──
    fields["GSTIN"] = fr([
        r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b",
    ])

    # ── PAN ──
    fields["PAN"] = fr([
        r"\bPAN\s*[:\-#]?\s*([A-Z]{5}[0-9]{4}[A-Z])\b",
        r"\b([A-Z]{5}[0-9]{4}[A-Z])\b",
    ])

    # ── AD Code ── 7-digit number near AD Code label
    fields["AD Code"] = fr([
        r"AD\s*\.?\s*Code[\s:\-]*([0-9]{7})\b",
        r"\bA\.?D\.?\s*Code[\s\S]{0,20}?([0-9]{7})\b",
    ])

    # ── Invoice No ──
    # Format seen: 0057/84/26-27  or  E/GST/043/26-27
    # Must contain slash and numbers, NOT "& Date" or long sentences
    fields["Invoice No"] = fr([
        r"Invoice\s*(?:No|Number|#)[\s:.\-]*([A-Z0-9]{1,6}[/\-][A-Z0-9/\-]{3,20})",
        r"Inv\.?\s*No\.?[\s:.\-]*([A-Z0-9]{1,6}[/\-][A-Z0-9/\-]{3,20})",
        r"\b([0-9]{4}[/\-][0-9]{2,3}[/\-][0-9]{2,4})\b",
        r"\b(E/(?:GST|LUT)/[0-9]+/[0-9\-]+)\b",
    ])

    # ── Invoice Date ──
    fields["Invoice Date"] = fr([
        r"Invoice\s+(?:No\s*[&]\s*)?Date[\s:\-]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})",
        r"Date[\s:\-]*(\d{2}[./\-]\d{2}[./\-]\d{4})",
        r"\b(\d{2}[./\-]\d{2}[./\-]\d{4})\b",
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b",
    ])

    # ── Buyer / Consignee ──
    # Look for actual company after Consignee label, skip template text
    consignee = ""
    for i, line in enumerate(lines):
        if re.search(r'\b(Consignee|Ship\s*To)\b', line, re.IGNORECASE):
            for j in range(i+1, min(i+6, len(lines))):
                nxt = lines[j].strip()
                if (nxt and len(nxt) > 3
                        and not re.search(r'\b(if other|consignee|buyer|name|address)\b', nxt, re.IGNORECASE)
                        and not re.search(r'^[:\-\.]', nxt)):
                    consignee = nxt
                    break
            break
    fields["Buyer / Consignee"] = consignee

    # ── Buyer PO No ──
    fields["Buyer PO No"] = fr([
        r"P\.?O\.?\s*(?:No|Number|#)[\s:\-]*([A-Z0-9/\-]{3,25})",
        r"Purchase\s+Order[\s:\-]*([A-Z0-9/\-]{3,25})",
        r"Order\s*(?:No|Ref)[\s:\-]*([A-Z0-9/\-]{3,25})",
    ])

    # ── Country of Origin ──
    # From invoice: "Country of origin of goods" then value on same line or next
    # Seen value: INDIA
    fields["Country of Origin"] = fr([
        r"Country\s+of\s+(?:origin\s+of\s+goods|Origin)[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
        r"Origin\s+of\s+[Gg]oods[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
        r"Country\s+of\s+[Oo]rigin[\s\S]{0,5}([A-Z]{4,20})\b",
    ])

    # ── Country of Destination ──
    # Seen value: ITALY  — appears after "Country of final Dest"
    fields["Country of Destination"] = fr([
        r"Country\s+of\s+(?:final\s+)?[Dd]est(?:ination)?[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
        r"Final\s+Destination[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
        r"Destination\s+Country[\s:\-]+([A-Z][A-Za-z]{2,20})\b",
    ])

    # ── Port of Loading ──
    # Seen value: AHMEDABAD INDIA  — appears after "Place of Loading" or "Port of Loading"
    fields["Port of Loading"] = fr([
        r"(?:Port|Place)\s+of\s+Loading[\s:\-]+([A-Z][A-Za-z ]{2,30}?)(?=\s*(?:\n|Port|Discharge|Final|Country|$))",
        r"Loading\s+Port[\s:\-]+([A-Z][A-Za-z ]{2,30}?)(?=\s*(?:\n|$))",
        r"\bPOL[\s:\-]+([A-Z][A-Za-z ]{2,30}?)(?=\s*(?:\n|POD|$))",
        r"Port\s+of\s+Loading[\s\S]{0,5}([A-Z][A-Za-z ]{3,25})",
    ])

    # ── Port of Discharge ──
    # Seen value: MILAN  or  ITALY
    fields["Port of Discharge"] = fr([
        r"(?:Port|Place)\s+of\s+Discharge[\s:\-]+([A-Z][A-Za-z ]{2,30}?)(?=\s*(?:\n|Port|Country|$))",
        r"Final\s+(?:Port|Destination)[\s:\-]+([A-Z][A-Za-z ]{2,25}?)(?=\s*(?:\n|$))",
        r"Discharge\s+Port[\s:\-]+([A-Z][A-Za-z ]{2,25}?)(?=\s*(?:\n|$))",
        r"\bPOD[\s:\-]+([A-Z][A-Za-z ]{2,25}?)(?=\s*(?:\n|$))",
    ])

    # ── Incoterm ── strict codes only
    fields["Delivery Terms (Incoterm)"] = fr([
        r"\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT|FAS|DPU)\b",
    ])

    # ── Payment Terms ──
    fields["Payment Terms"] = fr([
        r"Payment\s+(?:within|Terms?)[\s:\-]+([A-Za-z0-9 ,/\-]{3,40}?)(?=\s*(?:\n|days|$))",
        r"\b(DA\s*\d*\s*[Dd]ays?|DP\s*\d*\s*[Dd]ays?|Advance|T/?T|L/?C|Sight)\b",
        r"\b(DA|DP|TT|LC|Advance)\b",
    ])

    # ── Mode of Transport ──
    fields["Mode of Transport"] = fr([
        r"Mode\s+of\s+(?:Transport|Shipment)[\s:\-]+([A-Za-z]{3,20})",
        r"\b(Sea|Air|Road|Rail|Multimodal)\b",
    ])

    # ── Marks & Nos ──
    fields["Marks & Nos"] = fr([
        r"Marks?\s*(?:&|and)\s*Nos?[\s:\-]+([^\n]{3,50})",
        r"Container\s*No[\s:\-]+([^\n]{3,40})",
    ])

    # ── Currency ──
    # Prioritise EUR/USD over INR
    foreign = fr([r"\b(EUR|USD|GBP|AED|JPY|CNY|SGD|CAD|AUD)\b"])
    fields["Currency"] = foreign if foreign else fr([r"\b(INR)\b"])

    # ── Total Invoice Value ──
    # Seen in invoice: "Total Tax Value (Rs.) 8292.08"  and EUR total
    # Seen in checklist: "Inv.Value USD3550.00" or "693956.00"
    fields["Total Invoice Value"] = fr([
        r"Total\s+(?:Invoice\s+)?(?:Tax\s+)?Value[\s:\(RsINR\):\-]*([0-9,]+\.?[0-9]{0,2})",
        r"(?:Grand\s+)?Total\s+(?:Amount|Value)[\s:\-]*(?:EUR|USD|GBP|INR|AED)?\s*([0-9,]+\.?[0-9]{0,2})",
        r"Inv\.?\s*Value\s+(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.?[0-9]{0,2})",
        r"(?:EUR|USD|GBP|INR)\s*([0-9]{3,}\.?[0-9]{0,2})\s*(?:\(|$|\n)",
        r"Amount\s+(?:EUR|USD|GBP|INR|AED)\s*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── FOB Value ──
    fields["FOB Value"] = fr([
        r"(?:Before\s+Tax\s+Value|FOB\s+(?:Value|Amount|Price))[\s:\(Rs\.\)]*([0-9,]+\.?[0-9]{0,2})",
        r"FOB[\s:\-]+(?:EUR|USD|GBP|INR|AED)?\s*([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── Gross Weight ──
    fields["Gross Weight"] = fr([
        r"Gross\s+(?:Weight|Wt\.?)[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"G\.?\s*W(?:eight|t)?\.?[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"Gross\s+wt[\s:\-]*([0-9,]+\.?[0-9]{0,3})",
    ])

    # ── Net Weight ──
    fields["Net Weight"] = fr([
        r"Net\s+(?:Weight|Wt\.?)[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"N\.?\s*W(?:eight|t)?\.?[\s:\-]*([0-9,]+\.?[0-9]{0,3})\s*(?:KGS?|MT|LBS?|KG)?",
        r"Net\s+wt[\s:\-]*([0-9,]+\.?[0-9]{0,3})",
    ])

    # ── No. of Packages ──
    fields["No. of Packages"] = fr([
        r"(?:Total\s+)?(?:No\.?\s+of\s+)?(?:Packages?|Cartons?|Boxes|Cases|Pkgs?)[\s:\-]*([0-9]+)\b",
        r"(?:Packing|Total)\s+Cartons?[\s:\-]*([0-9]+)\b",
    ])

    # ── LUT / Bond ──
    fields["LUT / Bond"] = fr([
        r"\b(E/LUT/[0-9]+/[0-9\-]+)\b",
        r"LUT\s*(?:No\.?|Number|#)?[\s:\-]*([A-Z0-9/\-]{4,30})",
        r"Letter\s+of\s+Undertaking[\s:\-]*([A-Z0-9/\-]{4,30})",
    ])

    # ── DBK ──
    fields["DBK / Drawback"] = fr([
        r"(?:DBK|Drawback)\s*(?:Scheme|No\.?)?[\s:\-]*([A-Za-z0-9 /\-]{2,25})",
    ])

    # ── RoDTEP ──
    fields["RoDTEP"] = fr([
        r"RoDTEP[\s:\-]*([A-Za-z0-9 .%/\-]{2,20})",
    ])

    # ── IGST ──
    fields["IGST Refund"] = fr([
        r"IGST[\s:\-]*(?:Rs\.?\s*)?([0-9,]+\.?[0-9]{0,2})",
    ])

    # ── HSN Code ── 8-digit preferred, then 4-digit
    fields["HSN Code"] = fr([
        r"H\.?S\.?N\.?\s*(?:Code|No\.?)?[\s:\-]*([0-9]{8})\b",
        r"H\.?S\.?\s*Code[\s:\-]*([0-9]{6,8})\b",
        r"HSN[\s:\-]*([0-9]{4,8})\b",
        r"\b(9021[0-9]{4})\b",   # Optics/lens HSN family
    ])

    # ── Bank A/C No ──
    fields["Bank A/C No"] = fr([
        r"(?:Bank\s*A/?C\s*(?:No\.?)|Account\s*(?:No|Number)\.?)[\s:\-]*([0-9]{9,18})\b",
        r"A/?C\s*No\.?[\s:\-]*([0-9]{9,18})\b",
        r"BankA/cNo\s*([0-9]{9,18})\b",
        r"(?:SB|CA|CC|OD)\s*(?:A/?C)?[\s:\-]*([0-9]{9,18})\b",
    ])

    return {k: v.strip() if v else "" for k, v in fields.items()}


CRITICAL_FIELDS = {
    "IEC", "GSTIN", "Invoice No", "Invoice Date",
    "Total Invoice Value", "FOB Value", "HSN Code",
    "Port of Loading", "Port of Discharge",
    "Country of Destination", "Gross Weight",
}

def normalise(val):
    return re.sub(r"[\s,./\-]", "", val).upper()

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
                st.markdown(f'<div class="raw-text">{txt[:4000]}</div>', unsafe_allow_html=True)
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
