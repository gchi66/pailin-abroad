def paragraphs(doc_json):
    """Yield dicts with indent and markdown-formatted text for each paragraph."""
    for elem in doc_json["body"]["content"]:
        p = elem.get("paragraph")
        if not p:  # skip tables/images for now
            continue

        # ----- indent -----
        indent = p.get("bullet", {}).get("nestingLevel", 0)
        if indent == 0:
            pts = p.get("paragraphStyle", {}).get("indentStart", {}).get("magnitude", 0)
            indent = round(pts / 18)

        # ----- text with markdown -----
        parts = []
        for run in p["elements"]:
            tr = run.get("textRun")
            if not tr:
                continue
            txt = tr["content"].rstrip("\n")
            st  = tr.get("textStyle", {})
            if st.get("bold"):
                txt = f"**{txt}**"
            if st.get("italic"):
                txt = f"*{txt}*"
            if st.get("underline"):
                txt = f"__{txt}__"
            parts.append(txt)

        yield {
            "indent": indent,
            "text":   "".join(parts).strip()
        }
