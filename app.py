import streamlit as st
from extractor import extract_invoice_data, extract_packing_data
from validator import validate
from report import generate_pdf

st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF")
packing_file = st.file_uploader("Upload Packing List PDF")

if st.button("Verify Documents"):
    if invoice_file and packing_file:

        invoice_data = extract_invoice_data(invoice_file)
        packing_data = extract_packing_data(packing_file)

        errors, comparison = validate(invoice_data, packing_data)

        st.subheader("🔴 Errors")
        if errors:
            for e in errors:
                st.error(f"{e['field']} - {e['issue']}")
        else:
            st.success("No errors found ✅")

        pdf = generate_pdf(errors, comparison)

        with open(pdf, "rb") as f:
            st.download_button("📥 Download Report", f)

    else:
        st.warning("Upload both files")
