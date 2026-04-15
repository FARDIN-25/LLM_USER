def deep_merge_dict(dest: dict, src: dict) -> dict:
    if not isinstance(dest, dict) or not isinstance(src, dict):
        return src if isinstance(src, dict) else (dest if isinstance(dest, dict) else {})
    for key, val in src.items():
        if isinstance(val, dict) and key in dest and isinstance(dest[key], dict):
            dest[key] = deep_merge_dict(dest[key], val)
        else:
            dest[key] = val
    return dest

dest = {
    "profile": {"name": "Arun Kumar", "pan": "ABCDE1234F"},
    "financials": {"salary_income": 800000}
}
src = {
    "financials": {"tax_regime": "new"}
}

result = deep_merge_dict(dest, src)
print(result)
