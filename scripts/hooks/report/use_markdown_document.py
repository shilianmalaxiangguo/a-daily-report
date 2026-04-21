HOOK_NAME = "report.markdown_document"


def run(ctx):
    sections = ctx.get("sections") or {}
    ordered_keys = ["preamble", "environment", "observation", "execution", "review", "summary"]
    blocks = []
    for key in ordered_keys:
        block = str(sections.get(key, "") or "").strip()
        if block:
            blocks.append(block)

    markdown = "\n\n".join(blocks)
    return {
        "value": {"markdown_document": markdown},
        "patches": {"rendered": {"markdown_document": markdown}},
        "diagnostics": {"hook_name": HOOK_NAME, "status": "success", "warnings": []},
        "artifacts": {},
    }
