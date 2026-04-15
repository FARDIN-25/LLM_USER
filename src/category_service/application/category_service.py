from __future__ import annotations

import re
from enum import Enum


class ChatCategory(str, Enum):
    GST = "GST"
    INCOME_TAX = "INCOME_TAX"
    TDS = "TDS"
    ROC = "ROC"
    GENERAL = "GENERAL"


def detect_category(question: str) -> str:
    """
    Detect a coarse chat topic category using keyword rules.
    Runs BEFORE retrieval so the category can be stored and later used for routing.
    """
    q = (question or "").lower()

    # ── GST ───────────────────────────────────────────────────────────────────
    gst_keywords = [
        "gst", "goods and services tax", "gstin", "gstr", "gstr-1", "gstr-2",
        "gstr-3b", "gstr-9", "gstr-10", "input tax credit", "itc", "igst",
        "cgst", "sgst", "utgst", "reverse charge", "rcm", "e-invoice",
        "e-way bill", "eway bill", "composition scheme", "gst registration",
        "gst return", "gst filing", "gst refund", "gst exemption", "gst rate",
        "gst slab", "gst portal", "hsn code", "sac code", "tax invoice",
        "gst audit", "gst notice", "gst penalty", "zero rated supply",
        "nil rated", "exempt supply", "taxable supply", "place of supply",
        "time of supply", "gst annual return", "gst reconciliation",
        "gst cancellation", "gst amendment", "gst compliance",
    ]
    if any(kw in q for kw in gst_keywords):
        return ChatCategory.GST.value

    # ── TDS priority guard ────────────────────────────────────────────────────
    # Salary-related questions often contain terms like "salary income" which can
    # overlap with Income Tax keywords. If the user explicitly mentions TDS or
    # core TDS sections, classify as TDS before Income Tax.
    tds_priority_keywords = [
        "tds",
        "tax deducted at source",
        "tcs",
        "tax collected at source",
        "section 192",
        "section 194",
        "withholding tax",
    ]
    if any(kw in q for kw in tds_priority_keywords):
        return ChatCategory.TDS.value

    # ── INCOME TAX ────────────────────────────────────────────────────────────
    income_tax_keywords = [
        "income tax", "itr", "itr-1", "itr-2", "itr-3", "itr-4",
        "tax rebate", "tax return", "tax filing", "tax refund",
        "tax slab", "tax deduction", "tax exemption", "tax saving",
        "80c", "80d", "80g", "80gg", "80e", "80ee", "80tta", "80ttb",
        "section 80", "section 10", "section 24", "section 44ad", "section 44ae",
        "section 44ada", "hra exemption", "leave travel allowance", "lta",
        "house rent allowance", "standard deduction", "advance tax",
        "self assessment tax", "tax computation", "taxable income",
        "gross total income", "capital gains", "short term capital gain",
        "long term capital gain", "stcg", "ltcg", "salary income",
        "business income", "professional income", "other sources",
        "form 16", "form 26as", "ais", "tis", "annual information statement",
        "pan", "pan card", "aadhar linking", "e-filing", "income tax portal",
        "income tax notice", "income tax scrutiny", "income tax refund",
        "tax planning", "new tax regime", "old tax regime", "surcharge",
        "marginal relief", "alternate minimum tax", "amt", "mat",
        "income tax audit", "tax audit", "presumptive taxation",
        "dividend income", "interest income", "rental income",
    ]
    if any(kw in q for kw in income_tax_keywords):
        return ChatCategory.INCOME_TAX.value

    # Heuristic: if "it" appears as a separate word AND the question also includes
    # tax/return keywords, interpret as Income Tax.
    if re.search(r"\bit\b", q) and (("tax" in q) or ("return" in q) or ("refund" in q) or ("itr" in q)):
        return ChatCategory.INCOME_TAX.value

    # ── TDS ───────────────────────────────────────────────────────────────────
    tds_keywords = [
        "tds", "tax deducted at source", "tcs", "tax collected at source",
        "tds deduction", "tds rate", "tds return", "tds certificate",
        "form 16a", "form 16b", "form 26q", "form 24q", "form 27q",
        "form 27eq", "tds on salary", "tds on rent", "tds on interest",
        "tds on professional", "tds on contractor", "tds on commission",
        "tds on property", "tds on freelancer", "section 192", "section 194",
        "section 194a", "section 194b", "section 194c", "section 194d",
        "section 194h", "section 194i", "section 194j", "section 194n",
        "section 194q", "section 195", "lower deduction certificate",
        "nil deduction", "tds refund", "tds mismatch", "traces",
        "tds challan", "tds deposit", "tds due date", "tds filing",
        "tds compliance", "tds notice", "tds default", "tds penalty",
        "withholding tax",
    ]
    if any(kw in q for kw in tds_keywords):
        return ChatCategory.TDS.value

    # ── ROC ───────────────────────────────────────────────────────────────────
    roc_keywords = [
        "roc", "company filing", "roc annual filing", "registrar of companies",
        "mca", "mca21", "companies act", "company registration",
        "incorporation", "form mgt-7", "form aoc-4", "form dir-3",
        "form dir-8", "form dir-12", "form adt-1", "form ifc-1",
        "annual return", "board resolution", "director", "din",
        "digital signature", "dsc", "company compliance", "pvt ltd",
        "private limited", "limited liability partnership", "llp",
        "llp form 8", "llp form 11", "one person company", "opc",
        "section 8 company", "nidhi company", "producer company",
        "charge registration", "form chg", "statutory audit",
        "company secretory", "cs", "corporate governance",
        "share transfer", "debenture", "memorandum", "moa", "aoa",
        "articles of association", "strike off", "winding up",
        "company dissolution", "dormant company", "company name change",
        "registered office", "company address change",
    ]
    if any(kw in q for kw in roc_keywords):
        return ChatCategory.ROC.value

    # ── PF / ESI (no dedicated category; falls to GENERAL) ─────────────────────
    pf_keywords = [
        "pf", "provident fund", "epf", "employees provident fund",
        "ppf", "public provident fund", "esi", "employees state insurance",
        "esic", "pf registration", "pf withdrawal", "pf transfer",
        "epf passbook", "uan", "universal account number", "pf return",
        "form 15g", "form 15h", "pf exemption", "gratuity", "nps",
        "national pension scheme", "superannuation",
    ]
    if any(kw in q for kw in pf_keywords):
        return ChatCategory.GENERAL.value

    # ── CUSTOMS / IMPORT-EXPORT (no dedicated category; falls to GENERAL) ──────
    customs_keywords = [
        "customs", "import duty", "export", "iec", "import export code",
        "dgft", "customs duty", "basic customs duty", "bcd", "cvd",
        "anti dumping", "safeguard duty", "customs bond", "customs warehouse",
        "fema", "fdi", "foreign remittance", "form 15ca", "form 15cb",
        "transfer pricing",
    ]
    if any(kw in q for kw in customs_keywords):
        return ChatCategory.GENERAL.value



def normalize_category(category: str | None) -> str:
    """
    Normalize/validate incoming category strings from API params.
    Returns GENERAL for unknown values so filtering endpoints stay safe.
    """
    if not category:
        return ChatCategory.GENERAL.value
    c = category.strip().upper()
    try:
        return ChatCategory(c).value
    except Exception:
        return ChatCategory.GENERAL.value

