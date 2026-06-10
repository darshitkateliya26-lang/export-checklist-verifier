import streamlit as st
import pdfplumber
import re

# -----------------------------
# Extract Invoice Data
# -----------------------------
def extract_invoice_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    data = {}

    inv_match = re.search(r"Invoice\s*No[:\-]?\s*(\S+)", text)
    if inv_match:
        data["invoice_no"] = inv_match.group(1)

    total_match = re.search(r"Total[:\-]?\s*([\d,\.]+)", text)
    if total_match:
        data["total"] = float(total_match.group(1).replace(",", ""))

    return data


# -----------------------------
# Extract Packing Data
# -----------------------------
def extract_packing_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    data = {}

    gross = re.search(r"Gross\s*Weight[:\-]?\s*([\d\.]+)", text)
    if gross:
        data["gross_weight"] = float(gross.group(1))

    net = re.search(r"Net\s*Weight[:\-]?\s*([\d\.]+)", text)
    if net:
        data["net_weight"] = float(net.group(1))

    return data


# -----------------------------
# Validate Data
# -----------------------------
def validate(invoice, packing):
    errors = []
    comparison = []

    # Invoice checks
    if not invoice.get("invoice_no"):
        errors.append("Invoice Number Missing")

    if not invoice.get("total"):
        errors.append("Total Value Missing")

    # Packing checks
    if packing.get("net_weight") and packing.get("gross_weight"):
        if packing["net_weight"] > packing["gross_weight"]:
            errors.append("Net weight is greater than Gross weight ❌")

    # Comparison
    comparison.append({
        "Field": "Invoice Number",
        "Invoice": invoice.get("invoice_no", "N/A"),
        "Status": "✅" if invoice.get("invoice_no") else "❌"
    })

    return errors, comparison


# -----------------------------
# Generate Report
# -----------------------------
def generate_report(errors, comparison):
    report = "EXPORT VERIFICATION REPORT\n\n"

    report += "ERRORS:\n"
    if errors:
        for e in errors:
            report += f"- {e}\n"
    else:
        report += "No errors found ✅\n"

    report += "\nCOMPARISON:\n"
    for c in comparison:
        report += f"{c['Field']} | {c['Invoice']} | {c['Status']}\n"

    return report


# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
packing_file = st.file_uploader("Upload Packing List PDF", type=["pdf"])
checklist_file = st.file_uploader("Upload Checklist", type=["pdf", "xlsx"])

if st.button("Verify Documents"):

    if invoice_file and packing_file and checklist_file:

        invoice_data = extract_invoice_data(invoice_file)
        packing_data = extract_packing_data(packing_file)

        errors, comparison = validate(invoice_data, packing_data)

        st.subheader("🔴 Errors")
        if errors:
            for err in errors:
                st.error(err)
        else:
            st.success("✅ No errors found")

        st.subheader("📊 Comparison")
        for row in comparison:
            st.write(row)

        report_text = generate_report(errors, comparison)

        st.download_button(
            label="📥 Download Report",
            data=report_text,
            file_name="report.txt"
        )

    else:
        st.warning("⚠️ Please upload Invoice, Packing List and Checklist")
