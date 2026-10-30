"""Attach source-checked roles and instrument links; verify facts offline.

Roles/links are curated evidence, not inferred from amounts or reconciliation.
Original HTML snapshots are immutable inputs. Unknown filings stay unannotated.
"""
import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
import re

import pandas as pd
import json

COLUMNS = ["source_role", "source_scope", "source_instrument_key", "source_fact_id",
           "source_document_sha256", "source_url", "source_decimals"]


class _Attributes(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)


def _element(document, name, element_id):
    pattern = (rf'<(?:[\w-]+:)?{name}\b[^>]*\bid=["\']{re.escape(element_id)}["\']'
               rf'[^>]*>.*?</(?:[\w-]+:)?{name}>')
    found = re.findall(pattern, document, re.I | re.S)
    if len(found) != 1:
        raise ValueError(f"Expected one {name} with ID {element_id}; found {len(found)}")
    parser = _Attributes(); parser.feed(found[0].split(">", 1)[0] + ">")
    return found[0], parser.attrs


def _text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def attach(canon, manifest, documents):
    """Validate selected annotations before attaching them to canonical rows.

    A stale/malformed annotation for a selected filing fails loudly. Evidence
    for an unselected release/filing does not apply. Missing evidence never drops
    a row. All rows of one annotated context receive the same verified metadata.
    """
    out = canon.copy()
    for col in COLUMNS:
        out[col] = pd.Series(None, index=out.index, dtype="object")
    if manifest is None:
        return out
    data = json.loads(Path(manifest).read_text())
    if data.get("version") != 1:
        raise ValueError("Unsupported source evidence version")
    root = Path(documents).resolve()
    cache, seen = {}, set()
    for entry in data["facts"]:
        a, release, period = entry["adsh"], entry["release"], entry["period"]
        selected = out["adsh"].eq(a) & out["release"].eq(release)
        if not selected.any():
            continue
        key = (a, release, period, entry["identifier"], entry["subsidiary"])
        if key in seen:
            raise ValueError(f"Duplicate source annotation: {key}")
        seen.add(key)
        if entry["role"] not in {"cash_equivalent", "schedule", "narrative_repeat", "rollforward_repeat"}:
            raise ValueError("Unknown source role")
        expected_scope = "outside_investment_total" if entry["role"] == "cash_equivalent" else "investment"
        if entry["scope"] != expected_scope or not entry["basis"].strip() or not entry["instrument_key"].strip():
            raise ValueError("Source annotation needs scope, basis and instrument identity")
        m = selected & out["ddate"].eq(period) & out["identifier"].eq(entry["identifier"])
        subsidiary = out["subsidiary"] if "subsidiary" in out else pd.Series(None, index=out.index)
        m &= subsidiary.fillna("").eq(entry["subsidiary"] or "")
        if not m.any() or not out.loc[m, "period"].eq(period).all():
            raise ValueError(f"Source annotation no longer matches current rows: {key}")
        doc = data["documents"][a]
        if a not in cache:
            path = (root / doc["file"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Source snapshot must be inside configured document directory")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != doc["sha256"]:
                raise ValueError(f"Source snapshot fingerprint mismatch: {a}")
            cache[a] = raw.decode("utf-8")
        document = cache[a]
        fact, attr = _element(document, "nonFraction", entry["fact_id"])
        if attr.get("name", "").split(":")[-1] != "InvestmentOwnedAtFairValue" or any(
                k.endswith(":nil") and v == "true" for k, v in attr.items()):
            raise ValueError("Evidence must reference a non-nil investment fair-value fact")
        context, _ = _element(document, "context", attr["contextref"])
        instant = re.findall(r'<(?:\w+:)?instant[^>]*>(.*?)</(?:\w+:)?instant>', context, re.S)
        entity = re.findall(r'<(?:\w+:)?identifier\b[^>]*>(.*?)</(?:\w+:)?identifier>', context, re.S)
        members = re.findall(r'<(?:\w+:)?typedMember\b[^>]*dimension=["\'][^"\']*:InvestmentIdentifierAxis["\'][^>]*>(.*?)</(?:\w+:)?typedMember>', context, re.S)
        if (instant != [period] or len(entity) != 1 or
                not out.loc[m, "cik"].astype(int).eq(int(entity[0])).all() or
                [_text(x) for x in members] != [entry["identifier"]]):
            raise ValueError("Source fact context does not match filing, date or investment identifier")
        unit, _ = _element(document, "unit", attr["unitref"])
        if _text(unit) != "iso4217:USD":
            raise ValueError("Source evidence requires USD")
        if attr.get("format", "").split(":")[-1] not in {"num-dot-decimal", "numdotdecimal"}:
            raise ValueError("Unsupported source numeric format")
        value = float(_text(fact).replace(",", "")) * 10 ** int(attr.get("scale", 0))
        if attr.get("sign") == "-":
            value = -value
        decimals = int(attr["decimals"])
        if not -12 <= decimals <= 12 or not value > 0 or value == float("inf"):
            raise ValueError("Unsupported source precision/value")
        values = out.loc[m, "fair_value"].dropna()
        if values.empty or not values.sub(value).abs().le(.000001).all():
            raise ValueError("Source evidence value differs from extracted fair value")
        metadata = [entry["role"], entry["scope"], entry["instrument_key"], entry["fact_id"],
                    doc["sha256"], doc["url"], decimals]
        out.loc[m, COLUMNS] = metadata
    return out
