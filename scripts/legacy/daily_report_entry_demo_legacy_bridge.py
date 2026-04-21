import daily_report_entry_demo as legacy_demo


def build_legacy_sections(data, target_date):
    report = legacy_demo.generate_markdown_report(data, target_date)
    return {
        "preamble": report.split("\n\n", 1)[0],
        "summary": report,
    }
