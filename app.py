import streamlit as st
import pdfplumber
import re
import pandas as pd

# -----------------------------
# Extract text from PDF
# -----------------------------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


# -----------------------------
# Find field using patterns
# -----------------------------
def find_field(patterns, text):
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


# -----------------------------
# Extract Invoice Data
# -----------------------------
def extract_invoice_data(text):
    data = {}

    data["invoice_no"] = find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text)
    data["gstin"] = find_field([r"GSTIN[:\-]?\s*(\S+)"], text)
    data["iec"] = find_field([r"IEC[:\-]?\s*(\S+)"], text)

    data["total"] = find_field([
        r"Total\s*Amount[:\-]?\s*([\d,\.]+)",
        r"Grand\s*Total[:\-]?\s*([\d,\.]+)"
    ], text)

    return data


# -----------------------------
# Extract Packing Data
# -----------------------------
def extract_packing_data(text):
    data = {}

    data["gross_weight"] = find_field([r"Gross\s*Weight[:\-]?\s*([\d\.]+)"], text)
    data["net_weight"] = find_field([r"Net\s*Weight[:\-]?\s*([\d\.]+)"], text)
    data["invoice_no"] = find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text)

    return data


# -----------------------------
# Extract Checklist Data
# -----------------------------
def extract_checklist_data(text):
    data = {}

    data["invoice_no"] = find_field([r"Invoice\s*No[:\-]?\s*(\S+)"], text)
    data["gstin"] = find_field([r"GSTIN[:\-]?\s*(\S+)"], text)
    data["iec"] = find_field([r"IEC[:\-]?\s*(\S+)"], text)

    data["total"] = find_field([
        r"Total[:\-]?\s*([\d,\.]+)"
    ], text)

    data["gross_weight"] = find_field([
        r"Gross\s*Weight[:\-]?\s*([\d\.]+)"
    ], text)

    return data


# -----------------------------
# Validation Logic (TABLE FORMAT)
# -----------------------------
def validate(invoice, packing, checklist):

    def compare(field, inv, pack, chk):
        if inv and pack and chk:
            if inv == pack == chk:
                status = "✅"
            else:
                status = "⚠️"
        else:
            status = "❌"

        return {
            "Field": field,
            "Invoice": inv if inv else "-",
            "Packing List": pack if pack else "-",
            "Checklist": chk if chk else "-",
            "Status": status
        }

    results = []

    results.append(compare("Invoice Number",
                           invoice.get("invoice_no"),
                           packing.get("invoice_no"),
                           checklist.get("invoice_no")))

    results.append(compare("GSTIN",
                           invoice.get("gstin"),
                           packing.get("gstin"),
                           checklist.get("gstin")))

    results.append(compare("IEC",
                           invoice.get("iec"),
                           packing.get("iec"),
                           checklist.get("iec")))

    results.append(compare("Total Value",
                           invoice.get("total"),
                           packing.get("total"),
                           checklist.get("total")))

    results.append(compare("Gross Weight",
                           None,
                           packing.get("gross_weight"),
                           checklist.get("gross_weight")))

    return results


# -----------------------------
# UI START
# -----------------------------
st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
packing_file = st.file_uploader("Upload Packing List PDF", type=["pdf"])
checklist_file = st.file_uploader("Upload Checklist", type=["pdf", "xlsx"])


# -----------------------------
# VERIFY BUTTON
# -----------------------------
if st.button("Verify Documents"):

    if invoice_file and packing_file and checklist_file:

        # Extract text
        inv_text = extract_text(invoice_file)
        pack_text = extract_text(packing_file)
        chk_text = extract_text(checklist_file)

        # Extract structured data
        invoice = extract_invoice_data(inv_text)
        packing = extract_packing_data(pack_text)
        checklist = extract_checklist_data(chk_text)

        # Validate
        results = validate(invoice, packing, checklist)

        # Convert to table
        df = pd.DataFrame(results)

        st.subheader("📊 Export Verification")
        st.table(df)

        # Summary
        matched = sum(1 for r in results if r["Status"] == "✅")
        warning = sum(1 for r in results if r["Status"] == "⚠️")
        missing = sum(1 for r in results if r["Status"] == "❌")

        st.subheader("📈 Summary")

        st.success(f"✅ Matched: {matched}")
        st.warning(f"⚠️ Mismatch: {warning}")
        st.error(f"❌ Missing: {missing}")

        if warning > 0 or missing > 0:
            st.error("🚨 Critical issues detected — fix before export clearance")

    else:
        st.warning("⚠️ Please upload all 3 documents")
``
