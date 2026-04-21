def build_legacy_sections(data, target_date):
    try:
        import daily_report_entry_demo as legacy_demo
    except (ImportError, ModuleNotFoundError):
        import daily_report_render as legacy_render

        report = legacy_render.generate_markdown_report(data, target_date)
    else:
        report = legacy_demo.generate_markdown_report(data, target_date)

    preamble, summary = (report or "").split("\n\n", 1) if "\n\n" in (report or "") else ((report or ""), "")
    return {
        "preamble": preamble,
        "summary": summary,
    }
