import streamlit as st
import pdfplumber
import re
import pandas as pd

# --------- TEXT EXTRACTION ---------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text

# --------- GENERIC FIND FUNCTION ---------
def find_field(patterns, text):
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

# --------- INVOICE ---------
def extract_invoice(text):
    return {
        "invoice_no": find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text),
        "gstin": find_field([r"GSTIN[:\-]?\s*(\S+)"], text),
        "iec": find_field([r"IEC[:\-]?\s*(\S+)"], text),
        "total": find_field([
            r"Total\s*Amount[:\-]?\s*([\d,\.]+)",
            r"Grand\s*Total[:\-]?\s*([\d,\.]+)"
        ], text)
    }

# --------- PACKING ---------
def extract_packing(text):
    return {
        "invoice_no": find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text),
        "gross_weight": find_field([r"Gross\s*Weight[:\-]?\s*([\d\.]+)"], text),
        "net_weight": find_field([r"Net\s*Weight[:\-]?\s*([\d\.]+)"], text)
    }

# --------- CHECKLIST ---------
def extract_checklist(text):
    return {
        "invoice_no": find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text),
        "gstin": find_field([r"GSTIN[:\-]?\s*(\S+)"], text),
        "iec": find_field([r"IEC[:\-]?\s*(\S+)"], text),
        "total": find_field([r"Total[:\-]?\s*([\d,\.]+)"], text),
        "gross_weight": find_field([r"Gross\s*Weight[:\-]?\s*([\d\.]+)"], text)
    }

# --------- VALIDATION ---------
def validate(inv, pack, chk):

    def compare(field, i, p, c):
        if i and p and c:
            if i == p == c:
                status = "✅"
            else:
                status = "⚠️"
        else:
            status = "❌"

        return {
            "Field": field,
            "Invoice": i or "-",
            "Packing List": p or "-",
            "Checklist": c or "-",
            "Status": status
        }

    return [
        compare("Invoice Number", inv.get("invoice_no"), pack.get("invoice_no"), chk.get("invoice_no")),
        compare("GSTIN", inv.get("gstin"), pack.get("gstin"), chk.get("gstin")),
        compare("IEC", inv.get("iec"), pack.get("iec"), chk.get("iec")),
        compare("Total Value", inv.get("total"), pack.get("total"), chk.get("total")),
        compare("Gross Weight", "-", pack.get("gross_weight"), chk.get("gross_weight"))
    ]

# --------- UI ---------
st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
packing_file = st.file_uploader("Upload Packing List PDF", type=["pdf"])
checklist_file = st.file_uploader("Upload Checklist", type=["pdf"])

if st.button("Verify Documents"):

    if invoice_file and packing_file and checklist_file:

        inv_text = extract_text(invoice_file)
        pack_text = extract_text(packing_file)
        chk_text = extract_text(checklist_file)

        inv = extract_invoice(inv_text)
        pack = extract_packing(pack_text)
        chk = extract_checklist(chk_text)

        results = validate(inv, pack, chk)

        df = pd.DataFrame(results)

        st.subheader("📊 Export Verification Table")
        st.table(df)

        matched = sum(1 for r in results if r["Status"] == "✅")
        warning = sum(1 for r in results if r["Status"] == "⚠️")
        missing = sum(1 for r in results if r["Status"] == "❌")

        st.subheader("📈 Summary")
        st.success(f"✅ Matched: {matched}")
        st.warning(f"⚠️ Mismatch: {warning}")
        st.error(f"❌ Missing: {missing}")

        if warning > 0 or missing > 0:
            st.error("🚨 Fix issues before export clearance")

    else:
        st.warning("⚠️ Upload all 3 documents")
``
