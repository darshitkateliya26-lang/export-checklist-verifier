def validate(invoice, packing, checklist):

    results = []

    def compare(field, inv, pack, chk):

        if inv == pack == chk and inv is not None:
            status = "✅"
        elif inv or pack or chk:
            status = "⚠️"
        else:
            status = "❌"

        return {
            "Field": field,
            "Invoice": inv if inv else "-",
            "Packing": pack if pack else "-",
            "Checklist": chk if chk else "-",
            "Status": status
        }

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
