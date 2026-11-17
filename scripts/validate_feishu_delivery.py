#!/usr/bin/env python3
"""Check a Feishu component plan before writing and against fetched DocxXML after writing."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SECTION_IDS = {"opening", "tasks", "comparison", "solution", "interaction", "review"}
SECTION_ITEMS = {
    "opening": {"background", "business_goal", "version_boundary"},
    "tasks": {"job"},
    "comparison": {"competitive_comparison"},
    "solution": {"scope", "object_relationship"},
    "interaction": {"rules"},
    "review": {"decisions", "validation"},
}
CASE_IDS = {"experience_goal", "design_goal", "journey", "page_flow", "page_layout"}
COMPONENTS = {"p", "callout", "blockquote", "table", "whiteboard", "img", "omit"}


def fail(message):
    print(json.dumps({"ok": False, "errors": [message]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read JSON {path}: {exc}")


def validate_plan(plan):
    errors = []
    if not isinstance(plan, dict):
        return ["Plan must be a JSON object."]
    if not plan.get("document_url") or "replace-with-target" in plan["document_url"]:
        errors.append("Set the actual document_url before writing.")
    sections = plan.get("sections", [])
    if not isinstance(sections, list):
        return errors + ["sections must be an array."]
    ids = {section.get("id") for section in sections if isinstance(section, dict)}
    if ids != SECTION_IDS or len(sections) != len(SECTION_IDS):
        errors.append(f"Cover each reading task once: {', '.join(sorted(SECTION_IDS))}.")
    for section in sections:
        if not isinstance(section, dict):
            errors.append("Each section must be an object.")
            continue
        if not section.get("reader_task") or not section.get("placement"):
            errors.append(f"Section {section.get('id')}: reader_task and placement are required.")
        if not section.get("items"):
            errors.append(f"Section {section.get('id')}: list planned components or explicit omissions.")
        required_ids = SECTION_ITEMS.get(section.get("id"), set())
        item_ids = {item.get("id") for item in section.get("items", []) if isinstance(item, dict)}
        if not required_ids.issubset(item_ids):
            errors.append(f"Section {section.get('id')}: decide each slot: {', '.join(sorted(required_ids))}.")
        if section.get("id") == "opening" and not any(item.get("id") == "business_goal" and item.get("component") != "omit" for item in section.get("items", []) if isinstance(item, dict)):
            errors.append("Opening: business_goal must be present.")
        if section.get("id") == "tasks" and not any(item.get("id") == "job" and item.get("component") != "omit" for item in section.get("items", []) if isinstance(item, dict)):
            errors.append("Tasks: job must be present.")
    cases = plan.get("cases", [])
    if not isinstance(cases, list) or not cases:
        errors.append("List every Case and its component decisions.")
        cases = []
    all_items = []
    for section in sections:
        if isinstance(section, dict):
            all_items.extend((section.get("id"), item) for item in section.get("items", []))
    case_names = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append("Each Case must be an object.")
            continue
        case_id = case.get("id")
        if not case_id or case_id in case_names or not case.get("title") or "替换" in case["title"]:
            errors.append(f"Case {case_id}: set a unique id and actual title.")
        case_names.add(case_id)
        items = case.get("items", [])
        item_ids = {item.get("id") for item in items if isinstance(item, dict)}
        if item_ids != CASE_IDS:
            errors.append(f"Case {case_id}: decide {', '.join(sorted(CASE_IDS))} (use omit with reason when inapplicable).")
        for required in ("experience_goal", "design_goal"):
            if any(item.get("id") == required and item.get("component") == "omit" for item in items if isinstance(item, dict)):
                errors.append(f"Case {case_id}: {required} cannot be omitted.")
        all_items.extend((case_id, item) for item in items)
    seen = set()
    for owner, item in all_items:
        if not isinstance(item, dict):
            errors.append(f"{owner}: each component decision must be an object.")
            continue
        key = (owner, item.get("id"))
        if not key[1] or key in seen:
            errors.append(f"{owner}: component ids must be nonempty and unique.")
        seen.add(key)
        component = item.get("component")
        if component not in COMPONENTS:
            errors.append(f"{owner}/{item.get('id')}: choose a supported component.")
        if component == "omit":
            if not item.get("reason") or item["reason"].startswith("【待填写】"):
                errors.append(f"{owner}/{item.get('id')}: explain why this component is omitted.")
        else:
            marker = item.get("marker", "")
            if not marker or "替换" in marker:
                errors.append(f"{owner}/{item.get('id')}: set an actual unique text marker.")
    if not any(item.get("component") in {"callout", "blockquote"} for _, item in all_items if isinstance(item, dict)):
        errors.append("Route at least one key conclusion to a scan-friendly native component, or document an exception in the plan.")
    return errors


def validate_fetch(plan, fetch):
    errors = []
    try:
        content = fetch["data"]["document"]["content"]
        document_id = fetch["data"]["document"]["document_id"]
    except (KeyError, TypeError):
        return ["Fetched JSON must be the full lark-cli docs +fetch response."]
    if document_id not in plan["document_url"]:
        # Wiki URLs have a node token instead of a document id, so only enforce for direct docx URLs.
        if "/docx/" in plan["document_url"]:
            errors.append("Fetched document does not match document_url.")
    try:
        root = ET.fromstring(f"<root>{content}</root>")
    except ET.ParseError as exc:
        return [f"Fetched DocxXML cannot be parsed: {exc}"]
    for owner in [*plan["sections"], *plan["cases"]]:
        for item in owner["items"]:
            component = item["component"]
            if component == "omit":
                continue
            marker = item["marker"]
            if component in {"whiteboard", "img"}:
                token = item.get("token")
                if not token:
                    errors.append(f"{owner['id']}/{item['id']}: add the written {component} token for verification.")
                elif not any(token in node.attrib.values() for node in root.iter(component)):
                    errors.append(f"{owner['id']}/{item['id']}: {component} token not found in document.")
                if marker not in "".join(root.itertext()):
                    errors.append(f"{owner['id']}/{item['id']}: component label/Case heading not found.")
                continue
            tags = ("blockquote", "callout") if component == "blockquote" else (component,)
            matches = [node for tag in tags for node in root.iter(tag) if marker in "".join(node.itertext())]
            if not matches:
                errors.append(f"{owner['id']}/{item['id']}: {component} with marker '{marker}' not found.")
            elif component == "table" and not any(node.findall(".//tbody/tr") for node in matches):
                errors.append(f"{owner['id']}/{item['id']}: table has no body rows.")
    return errors


def main():
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in {"plan", "verify"} or (sys.argv[1] == "verify") != (len(sys.argv) == 4):
        fail("Usage: validate_feishu_delivery.py plan <plan.json> | verify <plan.json> <fetch.json>")
    plan = load_json(sys.argv[2])
    errors = validate_plan(plan)
    if not errors and sys.argv[1] == "verify":
        errors = validate_fetch(plan, load_json(sys.argv[3]))
    print(json.dumps({"ok": not errors, "phase": sys.argv[1], "errors": errors}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
