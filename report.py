def generate_pdf(errors, comparison):
    file_path = "report.txt"

    with open(file_path, "w") as f:
        f.write("EXPORT VERIFICATION REPORT\n\n")

        f.write("ERRORS:\n")
        for e in errors:
            f.write(f"{e['field']} - {e['issue']} ({e['source']})\n")

        f.write("\nCOMPARISON:\n")
        for c in comparison:
            f.write(f"{c['field']} | {c['invoice']} | {c['status']}\n")

    return file_path
