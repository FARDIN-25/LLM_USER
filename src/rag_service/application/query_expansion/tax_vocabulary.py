from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Tuple, Optional
from enum import Enum
from datetime import datetime
import re
import logging
import time

# --------------------------------------------------
# Logging
# --------------------------------------------------
# Don't reconfigure logging if already configured (prevents duplicate handlers)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
logger = logging.getLogger(__name__)

# --------------------------------------------------
# FastAPI App (optional - can be used as standalone service)
# --------------------------------------------------
# Note: This FastAPI app is created but won't interfere with imports
# The expand_query function can be used independently
app = FastAPI(
    title="Tax Query Expansion Service",
    description="GST & Tax Query Expansion API",
    version="1.0.0"
)

# --------------------------------------------------
# Domain Data
# --------------------------------------------------
TAX_SYNONYMS = {



    # GST Fundamentals

    "gst": ["goods and services tax", "vat", "value added tax", "gst act", "goods & services tax"],

    "gstin": ["gst identification number", "gst number", "tin", "tax id", "gst registration number"],

    "itc": ["input tax credit", "tax credit", "input credit", "credit of input tax"],

    "reverse charge": ["rcm", "reverse charge mechanism", "reverse charge basis"],

    "rcm": ["reverse charge", "reverse charge mechanism", "reverse charge basis"],

    "composition scheme": ["composition", "composite scheme", "composition levy", "compounding scheme"],

    "supply": ["taxable supply", "provision", "furnishing", "delivery"],

    "aggregate turnover": ["total turnover", "combined turnover"],

    

    # GST Registration & Compliance

    "registration": ["gst registration", "register under gst", "enrollment", "enrolment", "registration under gst"],

    "cancellation": ["gst cancellation", "registration cancellation", "surrender", "revocation"],

    "amendment": ["modification", "change", "update", "revision", "alteration"],

    "migration": ["gst migration", "transfer", "transition"],

    "suspension": ["temporary cancellation", "provisional cancellation"],

    "voluntary registration": ["optional registration", "voluntary enrolment"],

    "compulsory registration": ["mandatory registration", "required registration"],

    

    # GST Returns (Comprehensive)

    "gstr-1": ["outward supply return", "sales return", "form gstr-1", "gstr1", "outward supplies"],

    "gstr-2a": ["auto-populated itc", "purchase return", "auto-drafted return"],

    "gstr-2b": ["static itc statement", "auto-drafted itc", "itc statement"],

    "gstr-3b": ["monthly summary return", "summary return", "gstr3b", "monthly return"],

    "gstr-4": ["composition return", "quarterly return", "composition scheme return"],

    "gstr-5": ["non-resident return", "nri return"],

    "gstr-6": ["isd return", "input service distributor return"],

    "gstr-7": ["tds return", "tax deducted return"],

    "gstr-8": ["tcs return", "ecommerce return", "e-commerce operator return"],

    "gstr-9": ["annual return", "yearly return", "annual statement"],

    "gstr-9a": ["composition annual return"],

    "gstr-9c": ["reconciliation statement", "audit return", "certification"],

    "gstr-10": ["final return", "cancellation return"],

    "gstr-11": ["uid return", "unique identity return"],

    "filing": ["return filing", "submission", "lodging", "filing returns"],

    

    # GST Components & Tax Types

    "cgst": ["central gst", "central goods and services tax", "central tax"],

    "sgst": ["state gst", "state goods and services tax", "state tax"],

    "igst": ["integrated gst", "integrated goods and services tax", "interstate gst", "inter-state gst"],

    "utgst": ["union territory gst", "ut gst", "union territory tax"],

    "cess": ["compensation cess", "additional tax", "gst cess"],

    

    # Tax Rates & Classification

    "hsn": ["harmonized system nomenclature", "hsn code", "product code", "commodity code"],

    "sac": ["services accounting code", "service code", "service classification"],

    "tax rate": ["gst rate", "rate of tax", "applicable rate", "tax percentage"],

    "exemption": ["exempt", "zero rated", "nil rated", "exempted", "tax exemption"],

    "taxable": ["liable to tax", "chargeable", "subject to tax"],

    "taxable value": ["transaction value", "assessable value", "value of supply"],

    "place of supply": ["location of supply", "situs of supply"],

    "time of supply": ["point of taxation", "tax point"],

    

    # Documents & Invoices

    "invoice": ["bill", "tax invoice", "commercial invoice", "sale invoice"],

    "debit note": ["debit memo", "dn", "debit memorandum"],

    "credit note": ["credit memo", "cn", "credit memorandum"],

    "e-invoice": ["electronic invoice", "e-invoicing", "irn invoice"],

    "irn": ["invoice reference number", "e-invoice number", "invoice reference"],

    "e-way bill": ["eway bill", "ewb", "electronic waybill", "e-waybill"],

    "proforma invoice": ["pro forma invoice", "quotation invoice"],

    "bill of supply": ["supply bill", "bill without tax"],

    "delivery challan": ["challan", "delivery note"],

    "receipt voucher": ["payment receipt", "voucher"],

    

    # Parties & Entities

    "supplier": ["vendor", "seller", "consignor", "provider"],

    "recipient": ["buyer", "customer", "consignee", "purchaser"],

    "registered person": ["registered taxpayer", "gst registrant"],

    "taxable person": ["person liable to tax", "tax payer"],

    "input service distributor": ["isd", "service distributor"],

    "agent": ["commission agent", "authorized representative"],

    

    # Notices & Proceedings

    "notice": ["intimation", "communication", "letter", "order"],

    "scn": ["show cause notice", "showcause", "show cause memo"],

    "assessment": ["tax assessment", "determination", "adjudication"],

    "demand": ["tax demand", "recovery", "demand order"],

    "refund": ["tax refund", "reimbursement", "refund claim"],

    "appeal": ["objection", "revision", "appellate proceedings"],

    "adjudication": ["adjudication order", "determination order"],

    "rectification": ["correction", "amendment of order"],

    

    # Sections & Provisions (GST Act - Major)

    "section 2": ["definitions", "interpretation"],

    "section 7": ["scope of supply", "supply definition"],

    "section 9": ["levy and collection", "charge of tax"],

    "section 10": ["composition levy", "composition scheme provisions"],

    "section 12": ["time of supply of goods", "tax point goods"],

    "section 13": ["time of supply of services", "tax point services"],

    "section 15": ["value of taxable supply", "valuation"],

    "section 16": ["itc eligibility", "input tax credit conditions", "eligibility of itc"],

    "section 17": ["itc apportionment", "blocked credit", "itc restrictions"],

    "section 18": ["availment of itc", "itc on transition"],

    "section 19": ["itc transfer", "credit transfer"],

    "section 20": ["manner of distribution", "isd distribution"],

    "section 22": ["registration threshold", "persons liable to register"],

    "section 23": ["persons not liable", "exemption from registration"],

    "section 24": ["compulsory registration", "mandatory registration"],

    "section 29": ["cancellation of registration", "registration cancellation"],

    "section 30": ["revocation of cancellation", "restoration"],

    "section 31": ["tax invoice", "invoice requirements"],

    "section 34": ["credit note", "credit note provisions"],

    "section 35": ["debit note", "debit note provisions"],

    "section 37": ["filing of returns", "return provisions"],
    
    "section 38": ["furnishing details of outward supplies", "gstr-1 provisions"],

    "section 39": ["furnishing of return", "return filing provisions"],

    "section 41": ["gstr-3b", "monthly summary"],

    "section 42": ["matching and reversal", "itc matching"],

    "section 43": ["matching and reclaim", "itc reclaim"],

    "section 44": ["annual return", "gstr-9 provisions"],

    "section 49": ["payment of tax", "tax payment provisions"],

    "section 50": ["interest on delayed payment", "interest provisions"],

    "section 51": ["tax deduction at source", "tds provisions"],

    "section 52": ["tax collection at source", "tcs provisions"],

    "section 54": ["refund of tax", "refund provisions"],

    "section 73": ["demand notice", "normal assessment", "determination of tax"],

    "section 74": ["fraud cases", "willful misstatement", "suppression"],

    "section 75": ["general provisions", "assessment provisions"],

    "section 107": ["appeal to appellate authority", "first appeal"],

    "section 112": ["appeal to appellate tribunal", "second appeal"],

    "section 122": ["penalty for certain offences", "penalty provisions"],

    "section 129": ["detention and seizure", "goods detention"],

    "section 130": ["confiscation", "goods confiscation"],

    

    # GST Rules (Important)

    "rule 36": ["reversal of itc", "itc conditions", "documentary requirements"],

    "rule 37": ["itc availment", "credit availment"],

    "rule 38": ["availment of itc", "itc timing"],

    "rule 42": ["matching of itc", "credit matching"],

    "rule 43": ["reversal of itc", "credit reversal"],

    "rule 46": ["tax invoice", "invoice format"],

    "rule 48": ["e-invoice", "electronic invoicing"],

    "rule 53": ["credit note rules", "cn rules"],

    "rule 59": ["return filing", "filing provisions"],

    "rule 61": ["gstr-1 filing", "outward supply return"],

    "rule 80": ["refund application", "refund procedure"],

    "rule 86": ["payment of tax", "tax payment"],

    "rule 138": ["e-way bill", "eway bill rules"],

    

    # Income Tax Terms

    "income tax": ["it", "direct tax"],

    "itr": ["income tax return", "tax return", "return of income"],

    "itr-1": ["sahaj", "individual return"],

    "itr-2": ["capital gains return"],

    "itr-3": ["business return"],

    "itr-4": ["sugam", "presumptive income"],

    "tds": ["tax deducted at source", "withholding tax", "source deduction"],

    "tcs": ["tax collected at source", "collection at source"],

    "pan": ["permanent account number", "pan card"],

    "tan": ["tax deduction account number"],

    "assessment year": ["ay", "financial assessment"],

    "previous year": ["py", "financial year"],

    "advance tax": ["prepaid tax", "tax in advance"],

    "self assessment tax": ["self-assessed tax", "voluntary payment"],

    

    # Penalties & Interest

    "penalty": ["fine", "punitive charge", "penal action"],

    "interest": ["late fee interest", "delayed payment interest", "interest on tax"],

    "late fee": ["delay fee", "penalty for late filing", "belated filing fee"],

    "prosecution": ["criminal proceedings", "legal action"],

    

    # Compliance & Procedures

    "compliance": ["adherence", "conformity", "following rules", "tax compliance"],

    "due date": ["deadline", "last date", "expiry date", "time limit"],

    "payment": ["tax payment", "deposit", "remittance", "tax deposit"],

    "liability": ["tax liability", "obligation", "dues", "tax obligation"],

    "audit": ["tax audit", "statutory audit", "gst audit"],

    "verification": ["validation", "authentication", "checking"],

    "reconciliation": ["matching", "tallying", "reconciling"],

    "transitional credit": ["transition credit", "opening credit", "migrated credit"],

    

    # Special Schemes & Provisions

    "job work": ["toll manufacturing", "contract manufacturing"],

    "goods transport agency": ["gta", "transport service"],

    "works contract": ["construction contract", "building contract"],

    "branch transfer": ["stock transfer", "consignment"],

    "exports": ["export of goods", "export of services", "zero rated supply"],

    "imports": ["import of goods", "import of services"],

    "deemed exports": ["deemed export supply"],

    "sez": ["special economic zone", "sez supply"],

    

    # Portal & Technology

    "gst portal": ["gst website", "gst.gov.in", "gst common portal"],

    "digital signature": ["dsc", "digital certificate"],

    "aadhaar authentication": ["aadhaar verification", "aadhaar otp"],

    "gstin search": ["gstin verification", "registration verification"],

    

    # Other Important Terms

    "threshold limit": ["exemption limit", "registration threshold"],

    "input": ["purchases", "inward supplies"],

    "output": ["sales", "outward supplies"],

    "inward supply": ["purchase", "procurement", "receipt"],

    "outward supply": ["sale", "provision", "dispatch"],

    "zero rated supply": ["export supply", "zero tax supply"],

    "exempt supply": ["non-taxable supply", "exempted supply"],

    "non-gst supply": ["out of scope supply"],

    "mixed supply": ["bundled supply"],

    "composite supply": ["combined supply", "principal supply"],

}

# --------------------------------------------------
# Lesson Keywords
# --------------------------------------------------
LESSON_KEYWORDS = {
    "lesson_3": {
        "core": [
            "exempt income",
            "section 10",
            "agricultural income",
            "partial agricultural income",
            "composite income",
            "non agricultural income",
            "fully exempt income",
            "partially exempt income"
        ],
        "agriculture": [
            "section 10(1)",
            "agricultural land",
            "basic operations",
            "subsequent operations",
            "rent from agricultural land",
            "revenue from agriculture",
            "tea income",
            "coffee income",
            "rubber income",
            "rule 7",
            "rule 7A",
            "rule 7B",
            "rule 8"
        ],
        "personal_exemptions": [
            "HUF member receipt",
            "partner share of profit",
            "NRI interest income",
            "foreign allowance",
            "leave travel concession",
            "foreign technician income",
            "death cum retirement gratuity",
            "commuted pension",
            "leave encashment",
            "retrenchment compensation",
            "VRS compensation"
        ],
        "investment_exemptions": [
            "life insurance proceeds",
            "statutory provident fund",
            "recognized provident fund",
            "superannuation fund",
            "NPS",
            "sukanya samriddhi",
            "interest on investments",
            "tax free bonds"
        ],
        "institutional_exemptions": [
            "local authority income",
            "research association income",
            "news agency income",
            "educational institution income",
            "hospital income",
            "charitable trust income",
            "mutual fund income",
            "venture capital fund income",
            "business trust income"
        ],
        "capital_market_exemptions": [
            "dividend exempt",
            "mutual fund income",
            "UTI income",
            "long term capital gains exempt",
            "equity exemption",
            "agricultural land transfer",
            "sporting event income"
        ],
        "miscellaneous": [
            "reverse mortgage",
            "political party income",
            "infrastructure fund income",
            "foreign company oil income",
            "strategic reserve income"
        ],
        "faq_triggers": [
            "what is exempt income",
            "what income is not taxable",
            "is agricultural income taxable",
            "is gratuity taxable",
            "is pension taxable",
            "is mutual fund income taxable",
            "is dividend taxable"
        ]
    },
    "lesson_4_part_1_salaries": {
        "core": [
            "income under salaries",
            "basis of charge",
            "employer employee relationship",
            "section 15",
            "section 16",
            "section 17",
            "salary definition",
            "taxable salary",
            "gross salary",
            "net salary",
            "due basis",
            "receipt basis",
            "arrears of salary",
            "advance salary"
        ],
        "salary_components": [
            "basic salary",
            "dearness allowance",
            "bonus",
            "commission",
            "fees",
            "overtime",
            "leave salary",
            "gratuity",
            "pension",
            "commuted pension",
            "uncommuted pension",
            "retrenchment compensation",
            "VRS compensation"
        ],
        "allowances": [
            "house rent allowance",
            "HRA",
            "city compensatory allowance",
            "entertainment allowance",
            "children education allowance",
            "hostel allowance",
            "transport allowance",
            "uniform allowance",
            "helper allowance",
            "hill allowance",
            "border area allowance",
            "tribal area allowance"
        ],
        "perquisites": [
            "rent free accommodation",
            "concessional accommodation",
            "motor car perquisite",
            "sweeper gardener",
            "gas electricity water",
            "educational facility",
            "interest free loan",
            "medical facility",
            "club facility",
            "gift vouchers",
            "stock options",
            "ESOP",
            "employer contribution to PF",
            "superannuation fund"
        ],
        "valuation_rules": [
            "perquisite valuation",
            "RFA valuation",
            "motor car valuation",
            "furniture valuation",
            "concessional loan valuation",
            "medical perquisite valuation"
        ],
        "profits_in_lieu": [
            "section 17(3)",
            "compensation on termination",
            "modification of employment",
            "golden handshake",
            "VRS receipt",
            "commutation amount"
        ],
        "retirement_benefits": [
            "gratuity",
            "pension",
            "leave encashment",
            "PF withdrawal",
            "superannuation"
        ],
        "exemptions": [
            "HRA exemption",
            "gratuity exemption",
            "commuted pension exemption",
            "leave encashment exemption",
            "retrenchment exemption",
            "VRS exemption",
            "PF exemption"
        ],
        "deductions": [
            "standard deduction",
            "entertainment allowance deduction",
            "professional tax deduction",
            "section 16"
        ],
        "TDS": [
            "TDS on salary",
            "section 192",
            "form 16",
            "average rate",
            "perquisite tax",
            "relief under section 89"
        ],
        "faq_triggers": [
            "what is salary income",
            "what is perquisite",
            "how HRA is calculated",
            "is gratuity taxable",
            "is pension taxable",
            "is leave encashment taxable",
            "what is standard deduction",
            "how to compute taxable salary"
        ]
    },
    "lesson_4_part_1_house_property": {
        "core": [
            "income from house property",
            "basis of charge",
            "section 22",
            "section 23",
            "section 24",
            "annual value",
            "gross annual value",
            "net annual value",
            "municipal value",
            "fair rent",
            "standard rent"
        ],
        "ownership_concepts": [
            "owner",
            "deemed owner",
            "co-owner",
            "section 27",
            "transfer to spouse",
            "transfer to minor",
            "part performance",
            "member of co-operative society"
        ],
        "property_types": [
            "self occupied property",
            "let out property",
            "deemed let out property",
            "vacant property",
            "composite property"
        ],
        "annual_value_rules": [
            "expected rent",
            "actual rent",
            "higher of expected or actual",
            "vacancy allowance",
            "unrealized rent",
            "municipal taxes"
        ],
        "deductions": [
            "standard deduction 30 percent",
            "interest on borrowed capital",
            "section 24",
            "pre construction interest",
            "housing loan interest"
        ],
        "interest_categories": [
            "self occupied interest",
            "let out interest",
            "co borrowed interest",
            "joint loan interest",
            "pre acquisition interest"
        ],
        "loss_house_property": [
            "loss from house property",
            "set off rules",
            "carry forward loss",
            "section 71B"
        ],
        "exemptions": [
            "self occupied exemption",
            "one house exemption"
        ],
        "faq_triggers": [
            "how to compute house property income",
            "what is annual value",
            "what is deemed let out",
            "what is self occupied property",
            "is housing loan interest deductible",
            "how much interest can be claimed",
            "what is standard deduction"
        ]
    },
    "lesson_4_part_2_business_profession": {
        "core": [
            "income from business",
            "income from profession",
            "profits and gains of business",
            "PGBP",
            "section 28",
            "business income",
            "professional income",
            "chargeability"
        ],
        "business_definitions": [
            "trade",
            "commerce",
            "manufacture",
            "adventure in nature of trade",
            "profession",
            "vocation",
            "speculation business",
            "non speculation business"
        ],
        "taxable_receipts": [
            "compensation receipts",
            "export incentives",
            "duty drawback",
            "cash assistance",
            "profit on sale of license",
            "value of benefit",
            "perquisite from business",
            "remission of liability",
            "recovery of bad debts",
            "forfeited advance",
            "keyman insurance proceeds"
        ],
        "accounting_methods": [
            "cash system",
            "mercantile system",
            "hybrid system",
            "section 145",
            "ICDS",
            "method of accounting"
        ],
        "deductions": [
            "section 30",
            "section 31",
            "section 32",
            "section 35",
            "section 36",
            "section 37",
            "rent",
            "rates and taxes",
            "repairs",
            "insurance",
            "depreciation",
            "scientific research",
            "employee contribution",
            "employer contribution",
            "bonus",
            "commission",
            "bad debts",
            "interest on capital"
        ],
        "general_deduction_rules": [
            "wholly and exclusively",
            "for business purpose",
            "not personal",
            "not capital",
            "not illegal",
            "not prohibited"
        ],
        "disallowances": [
            "section 40",
            "section 40A",
            "cash payment disallowance",
            "excessive payment",
            "related party payment",
            "personal expenses",
            "capital expenditure",
            "income tax payment",
            "penalty payment"
        ],
        "depreciation": [
            "block of assets",
            "WDV method",
            "normal depreciation",
            "additional depreciation",
            "section 32",
            "used for business",
            "partial use",
            "asset put to use"
        ],
        "deemed_profits": [
            "section 41",
            "balancing charge",
            "remission of liability",
            "recovery of loss",
            "bad debt recovery"
        ],
        "special_deductions": [
            "section 35AD",
            "section 35AC",
            "section 35CCC",
            "section 35CCD"
        ],
        "maintenance_of_books": [
            "section 44AA",
            "books of accounts",
            "cash book",
            "ledger",
            "journal",
            "bills",
            "vouchers"
        ],
        "audit_requirements": [
            "section 44AB",
            "tax audit",
            "audit report",
            "form 3CA",
            "form 3CB",
            "form 3CD",
            "turnover limit",
            "gross receipts limit"
        ],
        "presumptive_taxation": [
            "section 44AD",
            "section 44ADA",
            "section 44AE",
            "presumptive income",
            "eligible assessee",
            "eligible business",
            "8 percent rule",
            "6 percent digital receipts"
        ],
        "speculation_business": [
            "speculation transaction",
            "intra day trading",
            "futures",
            "options",
            "derivatives",
            "speculation loss",
            "non speculation loss"
        ],
        "loss_rules": [
            "business loss",
            "speculation loss",
            "non speculation loss",
            "set off rules",
            "carry forward rules"
        ],
        "faq_triggers": [
            "what is business income",
            "what is profession income",
            "what deductions are allowed",
            "what expenses are disallowed",
            "how depreciation is calculated",
            "what is presumptive taxation",
            "is tax audit compulsory",
            "what is speculation business"
        ]
    },
    "lesson_4_part_3_capital_gains": {
        "core": [
            "capital gains",
            "section 45",
            "capital asset",
            "transfer",
            "short term capital gain",
            "long term capital gain",
            "STCG",
            "LTCG"
        ],
        "capital_asset_types": [
            "movable property",
            "immovable property",
            "equity shares",
            "debentures",
            "mutual fund units",
            "bonds",
            "jewellery",
            "goodwill",
            "patent",
            "copyright",
            "trademark"
        ],
        "transfer_modes": [
            "sale",
            "exchange",
            "relinquishment",
            "extinguishment",
            "compulsory acquisition",
            "conversion",
            "gift",
            "distribution",
            "slump sale"
        ],
        "period_rules": [
            "short term period",
            "long term period",
            "holding period",
            "12 months rule",
            "24 months rule",
            "36 months rule"
        ],
        "cost_concepts": [
            "cost of acquisition",
            "indexed cost",
            "cost of improvement",
            "fair market value",
            "section 55"
        ],
        "special_provisions": [
            "section 50",
            "section 50B",
            "section 50C",
            "section 45(2)",
            "section 45(5)",
            "section 49",
            "section 54 series"
        ],
        "exemptions": [
            "section 54",
            "section 54B",
            "section 54D",
            "section 54EC",
            "section 54F",
            "section 54G",
            "section 54GA"
        ],
        "indexation": [
            "CII",
            "cost inflation index",
            "indexed cost formula"
        ],
        "special_assets": [
            "depreciable assets",
            "slump sale",
            "business transfer",
            "conversion of capital asset",
            "stock in trade"
        ],
        "faq_triggers": [
            "what is capital gain",
            "what is long term capital gain",
            "what is short term capital gain",
            "how to calculate capital gain",
            "what is indexation",
            "what exemptions available",
            "what is section 54"
        ]
    },
    "lesson_4_part_4_other_sources": {
        "core": [
            "income from other sources",
            "section 56",
            "residual head",
            "casual income",
            "windfall income"
        ],
        "taxable_items": [
            "dividend",
            "interest income",
            "family pension",
            "lottery winnings",
            "card game winnings",
            "gambling income",
            "betting income",
            "race winnings",
            "gifts",
            "share premium",
            "forfeited advance"
        ],
        "deductions": [
            "section 57",
            "commission",
            "collection charges",
            "family pension deduction",
            "interest on borrowed capital"
        ],
        "disallowances": [
            "section 58",
            "personal expenses",
            "capital expenditure"
        ],
        "special_rules": [
            "dividend definition",
            "deemed dividend",
            "section 2(22)",
            "casual income taxation"
        ],
        "faq_triggers": [
            "what is income from other sources",
            "is lottery income taxable",
            "how dividend is taxed",
            "is gift taxable",
            "what deductions allowed"
        ]
    },
    "lesson_5": {
        "clubbing_core": [
            "clubbing of income",
            "section 60",
            "section 61",
            "section 64",
            "revocable transfer",
            "irrevocable transfer",
            "spouse income",
            "minor child income",
            "son wife income",
            "daughter in law income",
            "HUF conversion",
            "retransfer",
            "income from transferred asset"
        ],
        "clubbing_cases": [
            "transfer without consideration",
            "income from asset transferred",
            "indirect transfer",
            "benefit of spouse",
            "minor child exception",
            "manual skill income",
            "talent based income",
            "disability exception"
        ],
        "setoff_core": [
            "set off of losses",
            "intra head set off",
            "inter head set off",
            "section 70",
            "section 71"
        ],
        "setoff_restrictions": [
            "speculation loss restriction",
            "capital loss restriction",
            "lottery loss restriction",
            "casual income restriction",
            "house property loss limit"
        ],
        "carry_forward": [
            "carry forward of loss",
            "section 72",
            "section 73",
            "section 74",
            "section 74A",
            "section 80",
            "time limit",
            "8 years rule",
            "4 years rule"
        ],
        "loss_types": [
            "business loss",
            "speculation loss",
            "capital loss",
            "short term capital loss",
            "long term capital loss",
            "house property loss",
            "casual loss"
        ],
        "faq_triggers": [
            "what is clubbing of income",
            "when clubbing applies",
            "how set off works",
            "how carry forward works",
            "can capital loss be set off",
            "can speculation loss be set off"
        ]
    },
    "lesson_6": {
        "core": [
            "deductions",
            "gross total income",
            "total income",
            "chapter VIA",
            "section 80"
        ],
        "80c_family": [
            "section 80C",
            "PF",
            "PPF",
            "ELSS",
            "life insurance premium",
            "tuition fees",
            "NSC",
            "home loan principal",
            "stamp duty",
            "registration charges"
        ],
        "80d_family": [
            "section 80D",
            "medical insurance",
            "health insurance",
            "preventive health checkup",
            "senior citizen medical"
        ],
        "80g_family": [
            "section 80G",
            "charitable donation",
            "political party donation",
            "PM relief fund",
            "100 percent deduction",
            "50 percent deduction"
        ],
        "other_deductions": [
            "section 80E",
            "education loan",
            "section 80EE",
            "housing loan",
            "section 80CCD",
            "NPS",
            "section 80TTA",
            "savings interest",
            "section 80TTB",
            "senior citizen interest",
            "section 80U",
            "disability deduction",
            "section 80DD",
            "dependent disability",
            "section 80DDB",
            "medical treatment",
            "section 80RRB",
            "royalty income",
            "section 80QQB",
            "author royalty"
        ],
        "restrictions": [
            "deduction from GTI only",
            "no loss allowed",
            "no double deduction",
            "cash payment restriction"
        ],
        "faq_triggers": [
            "what is section 80C",
            "what deductions can I claim",
            "what is chapter VIA",
            "can I claim 80C and 80D",
            "what is NPS deduction",
            "what is 80G"
        ]
    },
    "lesson_7": {
        "core": [
            "HUF taxation",
            "firm taxation",
            "AOP taxation",
            "BOI taxation",
            "cooperative society taxation",
            "slab rates",
            "special rates"
        ],
        "HUF": [
            "HUF formation",
            "coparcener",
            "karta",
            "partition",
            "partial partition",
            "full partition",
            "HUF deductions",
            "HUF clubbing"
        ],
        "firm": [
            "partnership firm",
            "remuneration to partners",
            "interest to partners",
            "section 40b",
            "book profit",
            "firm slab",
            "MAT exclusion"
        ],
        "AOP_BOI": [
            "determinate share",
            "indeterminate share",
            "maximum marginal rate",
            "MMR"
        ],
        "cooperative": [
            "section 80P",
            "cooperative deduction",
            "primary agricultural credit society",
            "marketing society",
            "consumer society"
        ],
        "faq_triggers": [
            "how HUF is taxed",
            "how firm is taxed",
            "what is MMR",
            "how AOP is taxed",
            "what is 80P"
        ]
    },
    "lesson_8": {
        "core": [
            "company taxation",
            "domestic company",
            "foreign company",
            "corporate tax",
            "MAT",
            "AMT",
            "book profit",
            "normal tax"
        ],
        "rates": [
            "base tax rate",
            "surcharge",
            "health and education cess",
            "special rates"
        ],
        "MAT": [
            "section 115JB",
            "book profit",
            "MAT credit",
            "MAT carry forward"
        ],
        "dividend": [
            "DDT",
            "dividend distribution tax",
            "classical system",
            "dividend income"
        ],
        "losses": [
            "business loss",
            "capital loss",
            "amalgamation loss",
            "demerger loss",
            "change in shareholding"
        ],
        "incentives": [
            "section 115BAB",
            "section 115BAA",
            "startup tax",
            "SEZ units"
        ],
        "faq_triggers": [
            "how companies are taxed",
            "what is MAT",
            "what is book profit",
            "what is corporate tax",
            "what is 115BAA"
        ]
    },
    "lesson_9": {
        "core": [
            "non resident taxation",
            "NRI taxation",
            "foreign income",
            "indian source income",
            "DTAA",
            "double taxation"
        ],
        "residential": [
            "resident",
            "non resident",
            "RNOR",
            "ROR"
        ],
        "special_rates": [
            "royalty tax",
            "FTS tax",
            "capital gains NRI",
            "dividend NRI",
            "interest NRI"
        ],
        "DTAA": [
            "treaty benefit",
            "tax credit",
            "relief section 90",
            "relief section 91",
            "PE concept"
        ],
        "withholding": [
            "TDS on NRI",
            "section 195",
            "grossing up",
            "lower deduction certificate"
        ],
        "faq_triggers": [
            "how NRI is taxed",
            "what income is taxable for NRI",
            "what is DTAA",
            "how foreign income is taxed",
            "what is section 195"
        ]
    },
    "lesson_10": {
        "core": [
            "collection of tax",
            "recovery of tax",
            "advance tax",
            "self assessment tax",
            "regular assessment tax",
            "demand notice",
            "arrears"
        ],
        "modes": [
            "TDS",
            "TCS",
            "advance tax",
            "self assessment",
            "regular demand",
            "recovery certificate"
        ],
        "interest": [
            "section 234A",
            "section 234B",
            "section 234C",
            "interest for default",
            "interest for deferment",
            "interest for delay"
        ],
        "recovery_modes": [
            "attachment",
            "garnishee proceedings",
            "bank attachment",
            "salary attachment",
            "property attachment",
            "arrest",
            "detention"
        ],
        "refunds": [
            "tax refund",
            "interest on refund",
            "section 244A"
        ],
        "faq_triggers": [
            "how tax is collected",
            "what is advance tax",
            "what is self assessment tax",
            "how recovery is done",
            "what is tax refund"
        ]
    },
    "lesson_11": {
        "core": [
            "assessment",
            "return of income",
            "assessment year",
            "previous year",
            "notice",
            "order"
        ],
        "types": [
            "self assessment",
            "summary assessment",
            "scrutiny assessment",
            "best judgment assessment",
            "reassessment",
            "protective assessment"
        ],
        "sections": [
            "section 139",
            "section 143(1)",
            "section 143(3)",
            "section 144",
            "section 147",
            "section 148",
            "section 153"
        ],
        "notices": [
            "intimation",
            "scrutiny notice",
            "reassessment notice",
            "show cause notice"
        ],
        "time_limits": [
            "time barring",
            "limitation period",
            "extended limitation"
        ],
        "faq_triggers": [
            "what is assessment",
            "what is scrutiny assessment",
            "what is reassessment",
            "what is best judgment assessment",
            "what is section 143(1)"
        ]
    },
    "lesson_12": {
        "appeals": [
            "CIT appeals",
            "ITAT",
            "high court appeal",
            "supreme court appeal",
            "appeal procedure",
            "appeal time limit"
        ],
        "revisions": [
            "section 263",
            "section 264",
            "revision by commissioner",
            "prejudicial to revenue"
        ],
        "penalties": [
            "penalty",
            "late filing penalty",
            "under reporting",
            "misreporting",
            "concealment",
            "section 270A",
            "section 271AAC"
        ],
        "offences": [
            "prosecution",
            "willful default",
            "false statement",
            "false verification",
            "tax evasion"
        ],
        "compounding": [
            "compounding of offences",
            "settlement commission",
            "immunity"
        ],
        "faq_triggers": [
            "how to file appeal",
            "what is penalty",
            "what is revision",
            "what is prosecution",
            "how to avoid penalty"
        ]
    },
    "lesson_13": {
        "core": [
            "tax planning",
            "tax management",
            "tax evasion",
            "tax avoidance",
            "tax mitigation"
        ],
        "planning_tools": [
            "investment planning",
            "deduction planning",
            "income splitting",
            "timing of income",
            "residential planning"
        ],
        "compliance": [
            "return filing",
            "advance tax",
            "TDS compliance",
            "audit compliance"
        ],
        "distinction": [
            "tax planning vs tax evasion",
            "tax avoidance vs tax evasion"
        ],
        "faq_triggers": [
            "what is tax planning",
            "what is tax evasion",
            "what is tax avoidance",
            "how to save tax legally"
        ]
    },
    "lesson_14": {
        "core": [
            "international taxation",
            "cross border taxation",
            "source rule",
            "residence rule",
            "DTAA",
            "double taxation"
        ],
        "concepts": [
            "permanent establishment",
            "business connection",
            "arm length price",
            "ALP",
            "transfer pricing"
        ],
        "methods": [
            "exemption method",
            "credit method",
            "deduction method"
        ],
        "tax_treaty": [
            "OECD model",
            "UN model",
            "bilateral treaty",
            "multilateral treaty"
        ],
        "faq_triggers": [
            "what is DTAA",
            "what is permanent establishment",
            "how double taxation avoided",
            "what is transfer pricing"
        ]
    },
    "lesson_15": {
        "GAAR": [
            "general anti avoidance rule",
            "impermissible avoidance arrangement",
            "main purpose test",
            "commercial substance",
            "tax benefit",
            "round tripping",
            "accommodative transaction"
        ],
        "consequences": [
            "denial of tax benefit",
            "recharacterization",
            "reallocation",
            "disregard of arrangement"
        ],
        "advance_ruling": [
            "authority for advance ruling",
            "AAR",
            "binding ruling",
            "applicant",
            "resident applicant",
            "non resident applicant"
        ],
        "faq_triggers": [
            "what is GAAR",
            "what is impermissible arrangement",
            "what is advance ruling",
            "who can apply for AAR"
        ]
    },
    "lesson_16": {
        "core": [
            "service tax",
            "indirect tax",
            "negative list regime",
            "positive list regime",
            "finance act",
            "taxable service",
            "declared service",
            "bundled service"
        ],
        "definitions": [
            "service",
            "person",
            "consideration",
            "activity",
            "business entity",
            "non business entity"
        ],
        "scope": [
            "taxable territory",
            "non taxable territory",
            "place of provision",
            "import of service",
            "export of service"
        ],
        "classification": [
            "specified service",
            "declared service",
            "exempted service",
            "mega exemption"
        ],
        "administration": [
            "CBIC",
            "central excise",
            "service tax department",
            "jurisdiction",
            "registration"
        ],
        "faq_triggers": [
            "what is service tax",
            "what is taxable service",
            "what is negative list",
            "what is declared service",
            "what is bundled service"
        ]
    },
    "lesson_17": {
        "levy": [
            "charging section",
            "taxable event",
            "provision of service",
            "consideration",
            "reverse charge",
            "partial reverse charge"
        ],
        "valuation": [
            "gross amount",
            "pure agent",
            "reimbursement",
            "abatement",
            "composition scheme"
        ],
        "point_of_taxation": [
            "invoice date",
            "payment date",
            "completion date",
            "advance receipt"
        ],
        "payment": [
            "e-payment",
            "due date",
            "monthly payment",
            "quarterly payment",
            "interest on delay"
        ],
        "registration": [
            "service tax registration",
            "single registration",
            "centralized registration"
        ],
        "returns": [
            "ST-3",
            "revised return",
            "nil return"
        ],
        "input_credit": [
            "CENVAT",
            "input service",
            "input goods",
            "capital goods",
            "credit utilization"
        ],
        "adjustments": [
            "excess payment adjustment",
            "refund",
            "rebate"
        ],
        "faq_triggers": [
            "how service tax is levied",
            "what is reverse charge",
            "how service tax is paid",
            "what is CENVAT",
            "how refund is claimed"
        ]
    },
    "lesson_18": {
        "core": [
            "VAT",
            "value added tax",
            "state VAT",
            "indirect tax",
            "multi point tax",
            "destination based tax"
        ],
        "concepts": [
            "input tax",
            "output tax",
            "input tax credit",
            "ITC",
            "tax invoice",
            "credit note",
            "debit note"
        ],
        "registration": [
            "VAT registration",
            "TIN",
            "threshold limit"
        ],
        "returns": [
            "monthly return",
            "quarterly return",
            "annual return",
            "revised return"
        ],
        "valuation": [
            "sale price",
            "MRP",
            "discount",
            "turnover"
        ],
        "rates": [
            "standard rate",
            "reduced rate",
            "zero rate",
            "exempt goods"
        ],
        "ITC_rules": [
            "eligible credit",
            "ineligible credit",
            "blocked credit",
            "apportionment"
        ],
        "faq_triggers": [
            "what is VAT",
            "what is input tax credit",
            "how VAT is calculated",
            "what is output tax",
            "how VAT return filed"
        ]
    },
    "lesson_19": {
        "international_VAT": [
            "VAT in UK",
            "VAT in EU",
            "GST comparison",
            "sales tax",
            "consumption tax",
            "destination principle",
            "origin principle"
        ],
        "comparative_models": [
            "single stage tax",
            "multi stage tax",
            "invoice method",
            "subtraction method"
        ],
        "compliance_roles": [
            "company secretary",
            "compliance officer",
            "tax advisor",
            "indirect tax consultant"
        ],
        "professional_scope": [
            "VAT registration",
            "VAT audit",
            "VAT advisory",
            "litigation support",
            "representation"
        ],
        "procedural_roles": [
            "return filing",
            "assessment reply",
            "appeal filing",
            "refund processing"
        ],
        "faq_triggers": [
            "VAT system in other countries",
            "difference between VAT and GST",
            "role of company secretary",
            "career in indirect taxation"
        ]
    }
}

# --------------------------------------------------
# IFC Keywords
# --------------------------------------------------
IFC_KEYWORDS = {
    "domain": ["audit", "corporate law", "financial reporting", "ifc"],
    "modules": {
        "module_1_overview": {
            "navigation_keywords": [
                "ifc overview",
                "scope of ifc reporting",
                "section 143(3)(i)",
                "auditor responsibility ifc",
                "management responsibility ifc",
                "adequacy vs effectiveness",
                "balance sheet date reporting"
            ],
            "intent_keywords": [
                "what is internal financial control",
                "difference ifc and caro",
                "ifc applicability",
                "ifc unlisted companies",
                "ifc consolidated financials",
                "reasonable assurance",
                "material weakness meaning"
            ],
            "regulatory_keywords": [
                "companies act 2013",
                "section 134",
                "rule 8(5)(viii)",
                "caro 2015",
                "sa 200"
            ]
        },
        "module_2_detailed_guidance": {
            "section_1_background": {
                "core_keywords": [
                    "definition of internal control",
                    "sa 315 definition",
                    "ifc reporting india",
                    "global ifc reporting",
                    "combined audit",
                    "audit of ifc"
                ],
                "global_reference_keywords": [
                    "sox section 404",
                    "pcaob as 5",
                    "j sox",
                    "international ifc practice"
                ],
                "intent_queries": [
                    "why ifc introduced",
                    "history of ifc reporting",
                    "india vs usa ifc",
                    "combined audit meaning"
                ]
            },
            "section_2_reporting_under_companies_act": {
                "legal_keywords": [
                    "criteria for ifc",
                    "benchmark internal control",
                    "objective of ifc audit",
                    "interpretation of ifc",
                    "auditor reporting section 143",
                    "specified date reporting"
                ],
                "practical_keywords": [
                    "as at date vs period testing",
                    "interim financial statements ifc",
                    "ifc reporting unlisted",
                    "management vs auditor responsibility"
                ],
                "standards_mapping": [
                    "sa 200 applicability",
                    "sa 315 applicability",
                    "materiality in ifc",
                    "audit documentation ifc"
                ]
            },
            "section_3_internal_controls_sa_315": {
                "components_keywords": [
                    "control environment",
                    "risk assessment",
                    "control activities",
                    "information system",
                    "monitoring controls"
                ],
                "limitation_keywords": [
                    "limitations of internal control",
                    "human error",
                    "management override",
                    "collusion risk"
                ]
            },
            "section_4_technical_guidance": {
                "audit_approach_keywords": [
                    "top down approach",
                    "entity level controls",
                    "significant accounts",
                    "relevant assertions",
                    "risk of material misstatement"
                ],
                "testing_keywords": [
                    "design effectiveness testing",
                    "operating effectiveness testing",
                    "test of controls",
                    "walkthrough procedures",
                    "dual purpose tests"
                ],
                "deficiency_keywords": [
                    "control deficiency",
                    "significant deficiency",
                    "material weakness",
                    "modified opinion ifc"
                ]
            },
            "section_5_implementation_guidance": {
                "process_it_keywords": [
                    "process flow diagrams",
                    "it general controls",
                    "access security",
                    "change management",
                    "data centre controls",
                    "application controls",
                    "automated controls"
                ],
                "testing_evidence_keywords": [
                    "sampling in controls",
                    "walkthrough documentation",
                    "roll forward testing",
                    "rotation testing plan",
                    "remediation testing"
                ],
                "advanced_case_keywords": [
                    "entity level control precision",
                    "management override risk",
                    "journal entry controls",
                    "audit committee oversight",
                    "whistle blower mechanism",
                    "less complex companies ifc"
                ]
            }
        },
        "module_3_appendices": {
            "illustrative_keywords": [
                "ifc audit report format",
                "management representation letter",
                "engagement letter ifc",
                "examples of control deficiencies",
                "risks of material misstatement",
                "sia 5 sampling"
            ],
            "user_intent_queries": [
                "format of ifc report",
                "sample management representation",
                "examples of material weakness",
                "illustrative audit documentation"
            ]
        }
    },
    "compressed_clusters": {
        "ifc_reporting": [
            "section 143(3)(i)",
            "auditor reporting",
            "adequacy and effectiveness"
        ],
        "control_testing": [
            "design effectiveness",
            "operating effectiveness",
            "walkthrough",
            "test of controls"
        ],
        "control_failures": [
            "control deficiency",
            "significant deficiency",
            "material weakness"
        ],
        "it_controls": [
            "itgc",
            "application controls",
            "automated controls",
            "access management"
        ]
    }
}

# --------------------------------------------------
# Depreciation Keywords
# --------------------------------------------------
DEPRECIATION_KEYWORDS = {
    "book": "Guidance Note on Accounting for Depreciation in Companies – Schedule II",
    "domain": ["accounting", "corporate law", "taxation", "financial reporting"],
    "chapters": {
        "background": {
            "navigation_keywords": [
                "schedule ii overview",
                "depreciation companies act 2013",
                "shift from schedule xiv",
                "useful life concept"
            ],
            "concept_keywords": [
                "rate based vs useful life",
                "commercial depreciation",
                "indicative useful life",
                "true and fair view depreciation"
            ],
            "regulatory_keywords": [
                "companies act 2013",
                "schedule ii",
                "schedule xiv",
                "mca notifications"
            ]
        },
        "objective": {
            "intent_keywords": [
                "objective of guidance note",
                "purpose of schedule ii",
                "uniform depreciation practice",
                "practical application schedule ii"
            ]
        },
        "scope": {
            "scope_keywords": [
                "scope of guidance note",
                "application of schedule ii",
                "companies covered",
                "accounting for depreciation scope"
            ]
        },
        "useful_life_shift": {
            "core_keywords": [
                "useful life definition",
                "indicative useful life",
                "technical justification",
                "estimate useful life"
            ],
            "audit_intent_keywords": [
                "useful life different from schedule",
                "disclosure of useful life",
                "review of useful life",
                "change in estimate"
            ],
            "standards_mapping": [
                "as 6 depreciation",
                "as 5 change in estimate",
                "as 10 fixed assets"
            ]
        },
        "residual_value": {
            "core_keywords": [
                "residual value limit",
                "five percent residual value",
                "technical justification residual value"
            ],
            "decision_keywords": [
                "residual value higher than 5%",
                "residual value disclosure",
                "estimate residual value"
            ]
        },
        "continuous_process_plant": {
            "definition_keywords": [
                "continuous process plant",
                "cpp meaning",
                "twenty four hours operation"
            ],
            "classification_keywords": [
                "cpp vs non cpp",
                "nesd assets",
                "shutdown not cpp"
            ],
            "useful_life_keywords": [
                "cpp useful life",
                "25 years cpp",
                "schedule ii cpp"
            ]
        },
        "multiple_shift_depreciation": {
            "core_keywords": [
                "single shift depreciation",
                "double shift depreciation",
                "triple shift depreciation"
            ],
            "calculation_keywords": [
                "50 percent extra depreciation",
                "100 percent extra depreciation",
                "sporadic extra shift"
            ],
            "decision_keywords": [
                "reassess useful life shift",
                "nesd assets",
                "extra shift not applicable"
            ]
        },
        "unit_of_production_method": {
            "method_keywords": [
                "unit of production method",
                "uop depreciation",
                "production based depreciation"
            ],
            "application_keywords": [
                "change from slm to uop",
                "retrospective depreciation",
                "change in accounting policy"
            ],
            "standards_mapping": [
                "as 6 depreciation method",
                "retrospective adjustment",
                "profit and loss adjustment"
            ]
        },
        "transition_to_schedule_ii": {
            "core_keywords": [
                "transition to schedule ii",
                "remaining useful life",
                "opening retained earnings"
            ],
            "accounting_keywords": [
                "nil remaining useful life",
                "wdv recalculation",
                "slm transition"
            ],
            "tax_keywords": [
                "tax effect retained earnings",
                "adjustment net of tax"
            ]
        },
        "regulatory_rates": {
            "core_keywords": [
                "regulatory depreciation rates",
                "authority prescribed rates",
                "override schedule ii"
            ],
            "examples_keywords": [
                "electricity tariff depreciation",
                "cerc depreciation",
                "regulated entities"
            ]
        },
        "purchase_of_used_assets": {
            "core_keywords": [
                "used asset depreciation",
                "second hand asset",
                "available for use concept"
            ],
            "application_keywords": [
                "buyer estimated useful life",
                "previous owner life irrelevant"
            ]
        },
        "intangible_assets": {
            "core_keywords": [
                "intangible asset amortisation",
                "toll road amortisation",
                "revenue based amortisation"
            ],
            "decision_keywords": [
                "bot boot ppp projects",
                "as 26 intangible assets",
                "optional revenue method"
            ]
        },
        "revaluation_of_assets": {
            "core_keywords": [
                "revaluation depreciation",
                "depreciable amount revalued",
                "substituted cost"
            ],
            "accounting_keywords": [
                "revaluation reserve",
                "additional depreciation",
                "transfer to reserves"
            ]
        },
        "component_approach": {
            "core_keywords": [
                "component accounting",
                "significant parts",
                "separate depreciation"
            ],
            "implementation_keywords": [
                "mandatory from april 2015",
                "component useful life",
                "replacement cost accounting"
            ],
            "transition_keywords": [
                "component nil useful life",
                "retained earnings adjustment"
            ]
        },
        "low_value_assets": {
            "core_keywords": [
                "low value items depreciation",
                "100 percent depreciation",
                "materiality based policy"
            ]
        },
        "pro_rata_depreciation": {
            "core_keywords": [
                "pro rata depreciation",
                "date of acquisition",
                "date of disposal"
            ],
            "practical_keywords": [
                "grouping additions",
                "materiality approach"
            ]
        },
        "different_methods_geographical": {
            "core_keywords": [
                "different depreciation methods",
                "same asset different location"
            ],
            "decision_keywords": [
                "justification for different methods",
                "asset usage pattern"
            ]
        },
        "disclosures": {
            "core_keywords": [
                "schedule ii disclosures",
                "useful life disclosure",
                "residual value disclosure"
            ],
            "audit_keywords": [
                "technical advice disclosure",
                "method disclosure"
            ]
        },
        "transitional_provisions": {
            "core_keywords": [
                "effective date guidance note",
                "early adoption",
                "cumulative impact"
            ]
        },
        "appendices": {
            "appendix_a": [
                "schedule ii useful lives",
                "part a part b part c"
            ],
            "appendix_b": [
                "illustrations depreciation",
                "worked examples"
            ],
            "appendix_c": [
                "industry specific useful lives",
                "asset category table"
            ]
        }
    },
    "compressed_clusters": {
        "useful_life": [
            "useful life",
            "technical estimate",
            "schedule ii indicative"
        ],
        "depreciation_methods": [
            "slm",
            "wdv",
            "uop"
        ],
        "transition": [
            "remaining useful life",
            "retained earnings",
            "tax effect"
        ],
        "special_cases": [
            "cpp",
            "nesd",
            "component accounting"
        ]
    }
}

# --------------------------------------------------
# Fraud Reporting Keywords
# --------------------------------------------------
FRAUD_REPORTING_KEYWORDS = {
    "book": "Guidance Note on Reporting on Fraud under Section 143(12)",
    "edition": "Revised 2016",
    "domain": ["audit", "corporate law", "fraud reporting", "companies act"],
    "parts": {
        "part_a_overview": {
            "persons_covered": {
                "navigation_keywords": [
                    "persons covered section 143(12)",
                    "who should report fraud",
                    "statutory auditor fraud reporting",
                    "branch auditor reporting"
                ],
                "legal_keywords": [
                    "section 143(12)",
                    "section 148 cost audit",
                    "section 204 secretarial audit",
                    "rule 13 audit rules"
                ],
                "exclusion_keywords": [
                    "internal auditor not covered",
                    "tax auditor excluded",
                    "fraud by third parties"
                ]
            },
            "thresholds_and_manner": {
                "core_keywords": [
                    "fraud reporting threshold",
                    "one crore threshold",
                    "below one crore reporting",
                    "rule 13 amended"
                ],
                "process_keywords": [
                    "two days intimation",
                    "forty five days response",
                    "fifteen days reporting",
                    "sealed cover reporting"
                ],
                "form_keywords": [
                    "form adt 4",
                    "reporting to central government",
                    "board audit committee reporting"
                ]
            },
            "auditor_responsibility": {
                "core_keywords": [
                    "auditor responsibility fraud",
                    "consideration of fraud audit",
                    "in course of audit duties"
                ],
                "standards_keywords": [
                    "sa 240 fraud",
                    "sa 200 audit objectives",
                    "sa compliance section 143"
                ]
            },
            "other_services": {
                "core_keywords": [
                    "fraud during limited review",
                    "fraud in interim results",
                    "fraud during attest services"
                ],
                "decision_keywords": [
                    "non attest services fraud",
                    "section 144 services",
                    "use of information in audit"
                ]
            },
            "fraud_already_reported": {
                "core_keywords": [
                    "fraud detected by management",
                    "fraud already reported",
                    "vigil mechanism fraud"
                ],
                "audit_keywords": [
                    "professional skepticism",
                    "verify management detection",
                    "no duplicate reporting"
                ]
            },
            "consolidated_financials": {
                "core_keywords": [
                    "fraud in consolidated financials",
                    "subsidiary fraud reporting",
                    "component auditor fraud"
                ],
                "decision_keywords": [
                    "fraud by parent employees",
                    "foreign subsidiary fraud",
                    "principal auditor responsibility"
                ]
            },
            "prior_period_fraud": {
                "core_keywords": [
                    "fraud prior to companies act 2013",
                    "pre april 2014 fraud",
                    "1956 act fraud"
                ]
            },
            "trigger_point": {
                "core_keywords": [
                    "suspicion vs reason to believe",
                    "knowledge of fraud",
                    "suspected offence involving fraud"
                ],
                "interpretation_keywords": [
                    "reason to believe meaning",
                    "professional skepticism",
                    "objective test fraud"
                ]
            },
            "materiality": {
                "core_keywords": [
                    "materiality in fraud reporting",
                    "quantifiable fraud",
                    "non quantifiable fraud"
                ],
                "standards_keywords": [
                    "sa 320 materiality",
                    "sa 450 misstatements"
                ]
            },
            "corruption_and_other_laws": {
                "core_keywords": [
                    "corruption fraud reporting",
                    "bribery reporting",
                    "money laundering fraud"
                ],
                "standards_keywords": [
                    "sa 250 laws regulations",
                    "illegal acts audit"
                ]
            },
            "decision_tree": {
                "core_keywords": [
                    "section 143(12) decision tree",
                    "fraud reporting flow chart",
                    "trigger based reporting"
                ]
            }
        },
        "part_b_detailed_guidance": {
            "section_i_introduction": {
                "concept_keywords": [
                    "fraud definition",
                    "fraud vs error",
                    "intentional misstatement"
                ],
                "standards_keywords": [
                    "sa 240 responsibilities",
                    "sa 315 fraud risk",
                    "sa 250 non compliance"
                ]
            },
            "section_ii_auditor_reporting": {
                "core_keywords": [
                    "auditor reporting fraud",
                    "issues for consideration",
                    "reporting responsibility auditor"
                ],
                "scenario_keywords": [
                    "fraud during audit",
                    "fraud during limited review",
                    "fraud during non attest services"
                ]
            },
            "section_iii_applicability_of_sas": {
                "standards_keywords": [
                    "sa 240 applicability",
                    "sa 250 applicability",
                    "sa 315 applicability"
                ],
                "audit_keywords": [
                    "risk of material misstatement",
                    "fraud risk assessment"
                ]
            },
            "section_iv_technical_guidance": {
                "engagement_keywords": [
                    "terms of engagement fraud",
                    "engagement letter modification"
                ],
                "risk_keywords": [
                    "fraud risk factors",
                    "assessed fraud risk"
                ],
                "procedure_keywords": [
                    "audit procedures fraud",
                    "reasons to believe fraud",
                    "additional audit procedures"
                ],
                "governance_keywords": [
                    "board audit committee interaction",
                    "obtaining board response",
                    "evaluating board reply"
                ],
                "reporting_keywords": [
                    "reporting to central government",
                    "form adt 4 filing",
                    "audit documentation fraud"
                ],
                "opinion_keywords": [
                    "impact on audit opinion",
                    "impact on ifc",
                    "joint audit fraud"
                ]
            },
            "section_v_appendices": {
                "appendix_a": [
                    "engagement team fraud discussion",
                    "fraud brainstorming"
                ],
                "appendix_b": [
                    "audit committee inquiry checklist",
                    "management inquiry checklist"
                ],
                "appendix_c": [
                    "illustrative fraud risk factors",
                    "fraud red flags"
                ],
                "appendix_d": [
                    "audit procedures fraud risk",
                    "addressing fraud misstatement"
                ],
                "appendix_e": [
                    "reporting format board audit committee"
                ],
                "appendix_f": [
                    "form adt 4 format"
                ],
                "appendix_g": [
                    "management representation letter fraud"
                ]
            }
        }
    },
    "compressed_clusters": {
        "fraud_trigger": [
            "suspicion",
            "reason to believe",
            "knowledge of fraud"
        ],
        "reporting_path": [
            "audit committee",
            "board",
            "central government"
        ],
        "threshold_logic": [
            "one crore",
            "below threshold",
            "above threshold"
        ],
        "audit_standards": [
            "sa 240",
            "sa 250",
            "sa 315",
            "sa 320",
            "sa 450"
        ]
    }
}

# --------------------------------------------------
# CARO Keywords
# --------------------------------------------------
CARO_KEYWORDS = {
    "book": "Guidance Note on the Companies (Auditor's Report) Order",
    "order": "CARO 2016",
    "domain": ["audit", "corporate law", "financial reporting"],
    "chapters": {
        "introduction": {
            "navigation_keywords": [
                "caro introduction",
                "purpose of caro",
                "objective of auditor report order",
                "section 143(11)"
            ],
            "concept_keywords": [
                "supplementary reporting",
                "additional auditor reporting",
                "caro vs main audit report"
            ],
            "historical_keywords": [
                "caro 2016",
                "caro 2015",
                "caro 2003",
                "supersession of earlier orders"
            ]
        },
        "general_provisions_auditor_report": {
            "core_keywords": [
                "general provisions auditor report",
                "supplemental to section 143",
                "auditor duties caro"
            ],
            "legal_keywords": [
                "section 143(1)",
                "section 143(2)",
                "section 143(3)",
                "section 143(5)"
            ],
            "interpretation_keywords": [
                "status of caro",
                "caro vs cag directions",
                "scope of auditor responsibility"
            ]
        },
        "applicability_of_order": {
            "coverage_keywords": [
                "companies covered by caro",
                "foreign company applicability",
                "branch auditor caro"
            ],
            "exemption_keywords": [
                "companies not covered by caro",
                "banking company exemption",
                "insurance company exemption",
                "section 8 company exemption",
                "opc exemption",
                "small company exemption",
                "private company exemption"
            ],
            "threshold_keywords": [
                "paid up capital limit",
                "reserves and surplus limit",
                "borrowings one crore",
                "revenue ten crore"
            ],
            "interpretation_keywords": [
                "aggregate borrowing test",
                "point of time test",
                "balance sheet date test"
            ]
        },
        "period_of_compliance": {
            "core_keywords": [
                "period of compliance caro",
                "whole year compliance",
                "not only balance sheet date"
            ],
            "audit_judgement_keywords": [
                "partial year non compliance",
                "detrimental effect assessment",
                "auditor judgement compliance"
            ]
        },
        "general_approach": {
            "approach_keywords": [
                "general approach caro",
                "not an investigation",
                "specific reporting requirements"
            ],
            "standards_keywords": [
                "sa 200",
                "sa 230",
                "sa 315",
                "sa 320"
            ],
            "documentation_keywords": [
                "working papers caro",
                "audit documentation",
                "management representations",
                "caro checklist"
            ]
        },
        "matters_included_auditor_report": {
            "navigation_keywords": [
                "paragraph 3 matters",
                "clause wise reporting",
                "sixteen clauses caro"
            ],
            "fixed_assets_keywords": [
                "fixed asset records",
                "physical verification fixed assets",
                "title deeds immovable property"
            ],
            "inventory_keywords": [
                "inventory physical verification",
                "inventory discrepancies",
                "abc analysis inventory"
            ],
            "loans_keywords": [
                "loans granted section 189",
                "repayment schedule loans",
                "overdue loans reporting"
            ],
            "statutory_dues_keywords": [
                "statutory dues arrears",
                "gst dues",
                "income tax dues",
                "disputed statutory dues"
            ],
            "borrowings_keywords": [
                "default in repayment",
                "bank borrowings",
                "financial institution loans"
            ],
            "fraud_keywords": [
                "fraud reporting caro",
                "fraud noticed during audit"
            ]
        },
        "comments_on_form_of_report": {
            "core_keywords": [
                "form of caro report",
                "wording of clauses",
                "negative reporting"
            ],
            "presentation_keywords": [
                "caro annexure",
                "main audit report linkage",
                "modified reporting"
            ]
        },
        "boards_report": {
            "core_keywords": [
                "board report reference",
                "consistency with board report"
            ],
            "interpretation_keywords": [
                "auditor reliance on board report",
                "cross reference disclosures"
            ]
        },
        "appendices": {
            "appendix_i": [
                "text of caro 2016",
                "complete caro order"
            ],
            "appendix_ii": [
                "caro 2016 vs caro 2015",
                "clause by clause comparison"
            ],
            "appendix_iii": [
                "financial institutions list",
                "acceptance of deposits rules"
            ],
            "appendix_iv": [
                "illustrative caro checklist",
                "audit checklist caro"
            ],
            "appendix_v": [
                "section 185",
                "section 186"
            ],
            "appendix_vi": [
                "cost records audit rules"
            ],
            "appendix_vii": [
                "section 197",
                "schedule v"
            ],
            "appendix_viii": [
                "nidhi rules"
            ],
            "appendix_ix": [
                "section 42 private placement"
            ],
            "appendix_x": [
                "prospectus allotment rules"
            ]
        }
    },
    "compressed_clusters": {
        "caro_applicability": [
            "covered companies",
            "exempt companies",
            "threshold limits"
        ],
        "audit_reporting": [
            "paragraph 3",
            "clause wise reporting",
            "auditor statement"
        ],
        "asset_reporting": [
            "fixed assets",
            "inventory",
            "title deeds"
        ],
        "loan_and_dues": [
            "section 189",
            "statutory dues",
            "borrowings default"
        ]
    }
}

# --------------------------------------------------
# Special Purpose Reports Keywords
# --------------------------------------------------
SPECIAL_PURPOSE_REPORTS_KEYWORDS = {
    "book": "Guidance Note on Reports or Certificates for Special Purposes",
    "edition": "Revised 2016",
    "domain": ["assurance", "audit", "taxation", "corporate law"],
    "chapters": {
        "introduction": {
            "navigation_keywords": [
                "reports for special purposes",
                "certificates for special purposes",
                "assurance engagements other than audit",
                "framework for assurance engagements"
            ],
            "concept_keywords": [
                "reasonable assurance",
                "limited assurance",
                "engagement risk",
                "absolute assurance not possible"
            ],
            "classification_keywords": [
                "assertion based engagement",
                "direct reporting engagement",
                "intended users",
                "subject matter information"
            ]
        },
        "scope": {
            "coverage_keywords": [
                "scope of guidance note",
                "non audit assurance engagements",
                "historical non financial information"
            ],
            "exclusion_keywords": [
                "srs engagements",
                "agreed upon procedures",
                "compilation engagements",
                "tax return preparation",
                "consulting engagements"
            ]
        },
        "objectives": {
            "core_keywords": [
                "objectives of assurance engagement",
                "obtain reasonable assurance",
                "obtain limited assurance"
            ],
            "reporting_keywords": [
                "express opinion",
                "express conclusion",
                "basis for conclusion",
                "separate opinions"
            ],
            "withdrawal_keywords": [
                "disclaim opinion",
                "withdraw from engagement",
                "unable to obtain assurance"
            ]
        },
        "conduct_of_engagement": {
            "process_keywords": [
                "conduct of assurance engagement",
                "reasonable vs limited assurance procedures",
                "columnar guidance l r"
            ]
        },
        "inability_to_achieve_objective": {
            "decision_keywords": [
                "unable to achieve objective",
                "modify opinion",
                "withdraw from engagement"
            ],
            "documentation_keywords": [
                "significant matter documentation",
                "paragraph 92 documentation"
            ]
        },
        "ethical_and_quality_control": {
            "core_keywords": [
                "ethical requirements",
                "independence requirements",
                "quality control requirements"
            ],
            "standards_keywords": [
                "code of ethics icai",
                "sqc 1",
                "framework assurance engagements"
            ]
        },
        "engagement_acceptance_and_continuance": {
            "acceptance_keywords": [
                "engagement acceptance",
                "engagement continuance",
                "client acceptance procedures"
            ],
            "competence_keywords": [
                "engagement team competence",
                "capabilities assessment"
            ],
            "agreement_keywords": [
                "basis of engagement",
                "common understanding terms"
            ]
        },
        "preconditions_for_engagement": {
            "core_keywords": [
                "preconditions assurance engagement",
                "suitable criteria",
                "appropriate subject matter"
            ],
            "criteria_keywords": [
                "relevance",
                "completeness",
                "reliability",
                "neutrality",
                "understandability"
            ],
            "feasibility_keywords": [
                "evidence availability",
                "rational purpose engagement"
            ]
        },
        "limitation_on_scope_prior_acceptance": {
            "core_keywords": [
                "scope limitation before acceptance",
                "disclaimer expected",
                "refusal of engagement"
            ]
        },
        "agreeing_terms_of_engagement": {
            "core_keywords": [
                "engagement letter",
                "terms of engagement",
                "written agreement"
            ],
            "mandatory_terms": [
                "objective and scope",
                "practitioner responsibility",
                "engaging party responsibility",
                "applicable criteria",
                "unrestricted access",
                "expected report format"
            ]
        },
        "change_in_terms_of_engagement": {
            "core_keywords": [
                "change in engagement terms",
                "reasonable justification",
                "no downgrade of assurance"
            ]
        },
        "assurance_report_prescribed_by_law": {
            "core_keywords": [
                "report prescribed by law",
                "regulatory format report",
                "wording prescribed"
            ],
            "risk_keywords": [
                "user misunderstanding",
                "additional explanation",
                "refusal to accept engagement"
            ],
            "documentation_keywords": [
                "draft report discussion",
                "authority rejection evidence"
            ]
        },
        "professional_skepticism_and_judgment": {
            "core_keywords": [
                "professional skepticism",
                "professional judgment",
                "assurance skills"
            ],
            "application_keywords": [
                "iterative process",
                "systematic engagement approach"
            ]
        },
        "planning": {
            "core_keywords": [
                "engagement planning",
                "scope timing direction",
                "planned procedures"
            ]
        },
        "materiality": {
            "core_keywords": [
                "materiality assurance engagement",
                "qualitative factors",
                "quantitative factors"
            ],
            "judgement_keywords": [
                "aggregate misstatements",
                "materiality threshold",
                "professional judgment materiality"
            ]
        },
        "understanding_subject_matter": {
            "core_keywords": [
                "understanding subject matter",
                "engagement circumstances",
                "internal control understanding"
            ],
            "risk_keywords": [
                "risk of material misstatement",
                "process understanding"
            ]
        },
        "obtaining_evidence": {
            "core_keywords": [
                "sufficient appropriate evidence",
                "limited assurance procedures",
                "reasonable assurance procedures"
            ],
            "risk_response_keywords": [
                "additional procedures",
                "revise risk assessment"
            ]
        },
        "work_of_experts": {
            "practitioner_expert_keywords": [
                "practitioners expert",
                "competence objectivity",
                "evaluate expert work"
            ],
            "other_expert_keywords": [
                "responsible party expert",
                "internal auditor reliance",
                "another practitioner work"
            ]
        },
        "written_representations": {
            "core_keywords": [
                "written representations",
                "management representations",
                "representation reliability"
            ],
            "failure_keywords": [
                "representation not provided",
                "doubt on integrity"
            ]
        },
        "subsequent_events": {
            "core_keywords": [
                "subsequent events consideration",
                "events after report date"
            ]
        },
        "other_information": {
            "core_keywords": [
                "other information review",
                "material inconsistency",
                "misstatement of fact"
            ]
        },
        "description_of_criteria": {
            "core_keywords": [
                "applicable criteria description",
                "criteria framework",
                "no imprecise qualification"
            ]
        },
        "forming_opinion_or_conclusion": {
            "core_keywords": [
                "forming assurance opinion",
                "forming assurance conclusion",
                "evaluate misstatements"
            ],
            "outcome_keywords": [
                "qualified conclusion",
                "adverse conclusion",
                "disclaimer"
            ]
        },
        "preparing_assurance_report": {
            "core_keywords": [
                "preparing assurance report",
                "written report mandatory",
                "short form report",
                "long form report"
            ]
        },
        "assurance_report_content": {
            "mandatory_elements": [
                "independent assurance title",
                "addressee",
                "subject matter identification",
                "applicable criteria",
                "responsibilities statement",
                "ethical compliance",
                "summary of work performed",
                "opinion or conclusion"
            ]
        },
        "reference_to_expert": {
            "core_keywords": [
                "reference to practitioners expert",
                "expert mention in report"
            ]
        },
        "unmodified_and_modified_opinions": {
            "core_keywords": [
                "unmodified opinion",
                "qualified opinion",
                "adverse opinion",
                "disclaimer of opinion"
            ]
        },
        "other_communication": {
            "core_keywords": [
                "other communication responsibilities",
                "communication with engaging party"
            ]
        },
        "documentation": {
            "core_keywords": [
                "engagement documentation",
                "working papers assurance",
                "documentation requirements"
            ]
        },
        "appendices": {
            "appendix_1": [
                "glossary of terms",
                "definitions guidance note"
            ],
            "appendix_2": [
                "illustrative report formats",
                "certificate formats",
                "sample assurance reports"
            ]
        }
    },
    "compressed_clusters": {
        "assurance_levels": [
            "reasonable assurance",
            "limited assurance"
        ],
        "engagement_lifecycle": [
            "acceptance",
            "planning",
            "evidence",
            "reporting"
        ],
        "report_outcomes": [
            "unmodified",
            "qualified",
            "adverse",
            "disclaimer"
        ],
        "governance": [
            "engaging party",
            "responsible party",
            "intended users"
        ]
    }
}

# --------------------------------------------------
# Share-based Payments Keywords
# --------------------------------------------------
SHARE_BASED_PAYMENTS_KEYWORDS = {
    "book": "Guidance Note on Accounting for Share-based Payments",
    "edition": "September 2020",
    "domain": ["accounting", "corporate law", "employee compensation", "taxation"],
    "chapters": {
        "introduction": {
            "core_keywords": [
                "share based payments",
                "employee stock options",
                "esop",
                "espp",
                "stock appreciation rights",
                "non employee share based payments"
            ],
            "governance_keywords": [
                "remuneration alignment",
                "long term incentives",
                "corporate governance compensation"
            ]
        },
        "scope": {
            "coverage_keywords": [
                "equity settled transactions",
                "cash settled transactions",
                "choice of settlement",
                "group share based payments"
            ],
            "exclusion_keywords": [
                "business combinations",
                "amalgamation as 14",
                "joint venture contribution"
            ]
        },
        "definitions": {
            "key_terms": [
                "share based payment arrangement",
                "equity settled",
                "cash settled",
                "grant date",
                "measurement date",
                "vesting condition",
                "performance condition",
                "market condition",
                "fair value",
                "intrinsic value"
            ]
        },
        "accounting": {
            "method_keywords": [
                "fair value method",
                "intrinsic value method",
                "equity recognition",
                "liability recognition"
            ]
        },
        "recognition": {
            "core_keywords": [
                "recognition of services",
                "expense recognition",
                "equity credit",
                "liability recognition timing"
            ]
        },
        "equity_settled_transactions": {
            "measurement_keywords": [
                "grant date fair value",
                "vesting period expense",
                "equity account transfer"
            ],
            "vesting_keywords": [
                "immediate vesting",
                "service period vesting",
                "performance based vesting"
            ]
        },
        "services_received": {
            "core_keywords": [
                "services rendered",
                "time proportion basis",
                "expected vesting period"
            ]
        },
        "fair_value_measurement": {
            "valuation_keywords": [
                "option pricing model",
                "market price",
                "expected volatility",
                "expected life",
                "risk free rate"
            ]
        },
        "fair_value_not_reliable": {
            "fallback_keywords": [
                "intrinsic value method",
                "remeasurement each period",
                "profit or loss impact"
            ]
        },
        "modifications_cancellations": {
            "core_keywords": [
                "repricing of options",
                "cancellation of grant",
                "settlement during vesting",
                "replacement grant"
            ],
            "accounting_keywords": [
                "incremental fair value",
                "acceleration of vesting",
                "equity deduction"
            ]
        },
        "cash_settled_transactions": {
            "core_keywords": [
                "share appreciation rights",
                "liability remeasurement",
                "fair value at reporting date"
            ]
        },
        "net_settlement_tax": {
            "core_keywords": [
                "net settlement feature",
                "withholding tax on esop",
                "equity classification exception"
            ]
        },
        "cash_alternatives": {
            "core_keywords": [
                "cash alternative plans",
                "liability vs equity split",
                "dual component accounting"
            ]
        },
        "counterparty_choice": {
            "core_keywords": [
                "employee choice of settlement",
                "debt component",
                "equity component"
            ]
        },
        "enterprise_choice": {
            "core_keywords": [
                "enterprise settlement choice",
                "present obligation test",
                "commercial substance"
            ]
        },
        "group_transactions": {
            "core_keywords": [
                "parent subsidiary esop",
                "group share based payment",
                "intragroup settlement"
            ]
        },
        "intrinsic_value_method": {
            "core_keywords": [
                "intrinsic value computation",
                "listed company intrinsic value",
                "unlisted valuation report"
            ]
        },
        "recommendation": {
            "core_keywords": [
                "preferred fair value method",
                "permitted intrinsic value method"
            ]
        },
        "graded_vesting": {
            "core_keywords": [
                "graded vesting",
                "tranche wise accounting",
                "multiple vesting dates"
            ]
        },
        "trust_administered_plans": {
            "core_keywords": [
                "esop trust",
                "shares held in trust",
                "loan to esop trust elimination"
            ]
        },
        "earnings_per_share": {
            "core_keywords": [
                "eps impact",
                "diluted eps",
                "potential equity shares",
                "as 20 computation"
            ]
        },
        "disclosures": {
            "core_keywords": [
                "share based payment disclosures",
                "vesting conditions disclosure",
                "option movement reconciliation",
                "fair value assumptions"
            ]
        },
        "effective_date": {
            "core_keywords": [
                "effective date guidance note",
                "withdrawal of earlier guidance"
            ]
        },
        "appendices": {
            "appendix_i": [
                "fair value estimation",
                "option valuation inputs"
            ],
            "appendix_ii": [
                "equity settled illustrations",
                "employee esop examples"
            ],
            "appendix_iii": [
                "modification examples",
                "repricing illustrations"
            ],
            "appendix_iv": [
                "cash settled illustrations",
                "sar accounting examples"
            ],
            "appendix_v": [
                "cash alternative plans example"
            ],
            "appendix_vi": [
                "graded vesting illustration"
            ],
            "appendix_vii": [
                "eps computation example"
            ],
            "appendix_viii": [
                "illustrative disclosures"
            ],
            "appendix_ix": [
                "non employee share based payment"
            ],
            "appendix_x": [
                "group share based payment example"
            ],
            "appendix_xi": [
                "trust administered plan accounting"
            ]
        }
    },
    "compressed_clusters": {
        "measurement_basis": [
            "fair value",
            "intrinsic value"
        ],
        "settlement_type": [
            "equity settled",
            "cash settled",
            "choice of settlement"
        ],
        "vesting_logic": [
            "service condition",
            "performance condition",
            "market condition",
            "graded vesting"
        ],
        "reporting_impact": [
            "profit or loss",
            "equity",
            "liability",
            "eps"
        ]
    }
}

# --------------------------------------------------
# GST Officers Handbook Keywords
# --------------------------------------------------
GST_OFFICERS_HANDBOOK_KEYWORDS = {
    "book": "Handbook for GST Officers",
    "publisher": "NACIN / CBIC",
    "edition": "January 2024",
    "domain": ["gst", "indirect taxation", "tax administration", "cbic"],
    "chapters": {
        "introduction": {
            "taxation": [
                "definition of tax",
                "taxable event",
                "taxpayer meaning",
                "authority of law article 265",
                "direct tax vs indirect tax"
            ],
            "basics_of_indirect_taxation": [
                "consumption tax",
                "tax incidence",
                "burden passed to consumer",
                "revenue leakage",
                "cascading effect",
                "input tax credit concept"
            ],
            "gst_in_india": [
                "gst rollout 1 july 2017",
                "101st constitutional amendment",
                "dual gst model",
                "cgst sgst igst",
                "destination based tax",
                "supply as taxable event"
            ],
            "cbic_role_functions": [
                "cbic mandate",
                "department of revenue",
                "customs excise gst administration",
                "field formations",
                "directorates dggi dri nacin",
                "grievance redressal",
                "audit appeal commissionerates"
            ]
        },
        "gst_in_tables": {
            "core_keywords": [
                "gst at a glance",
                "gst rates slab",
                "registration threshold",
                "composition limit",
                "eway bill limit",
                "einvoice applicability",
                "qrmp scheme"
            ]
        },
        "cgst_act_arrangement": {
            "chapter_keywords": [
                "preliminary",
                "levy and collection",
                "time and value of supply",
                "input tax credit",
                "registration",
                "returns",
                "payment of tax",
                "refunds",
                "assessment",
                "audit",
                "inspection search seizure",
                "demand recovery",
                "offences penalties",
                "appeals",
                "advance ruling",
                "transitional provisions"
            ]
        },
        "key_sections_cgst": {
            "important_sections": [
                "section 7 supply",
                "section 9 levy",
                "section 10 composition",
                "section 12 time of supply goods",
                "section 13 time of supply services",
                "section 15 value of supply",
                "section 16 eligibility of itc",
                "section 17 blocked credits",
                "section 22 registration",
                "section 29 cancellation",
                "section 31 tax invoice",
                "section 34 credit debit notes",
                "section 39 returns",
                "section 44 annual return",
                "section 49 payment of tax",
                "section 54 refund",
                "section 65 audit",
                "section 67 inspection search seizure",
                "section 73 non fraud demand",
                "section 74 fraud demand"
            ]
        },
        "igst_act_arrangement": {
            "core_keywords": [
                "inter state supply",
                "place of supply igst",
                "export zero rated supply",
                "import of services",
                "section 16 igst zero rating"
            ]
        },
        "key_sections_igst": {
            "important_sections": [
                "section 5 igst levy",
                "section 7 inter state supply",
                "section 10 pos goods",
                "section 12 pos services",
                "section 16 zero rated supply"
            ]
        },
        "cgst_rules_arrangement": {
            "procedural_keywords": [
                "registration rules",
                "invoice rules",
                "return filing rules",
                "payment rules",
                "refund rules",
                "e invoice rules",
                "eway bill rules"
            ]
        },
        "key_provisions_cgst_rules": {
            "rule_keywords": [
                "rule 36 itc restriction",
                "rule 42 reversal of itc",
                "rule 43 capital goods itc",
                "rule 48 e invoice",
                "rule 86b itc utilisation limit"
            ]
        },
        "important_circulars_forms": {
            "core_keywords": [
                "gst circulars",
                "cbic instructions",
                "gst forms",
                "procedural clarifications",
                "departmental guidelines"
            ]
        },
        "legal_maxims_phrases": {
            "core_keywords": [
                "ignorantia juris non excusat",
                "actus non facit reum",
                "burden of proof",
                "mens rea",
                "substance over form"
            ]
        },
        "ccs_conduct_rules": {
            "core_keywords": [
                "government servant conduct",
                "disciplinary rules",
                "integrity impartiality",
                "misconduct provisions"
            ]
        },
        "general_financial_rules": {
            "core_keywords": [
                "public finance management",
                "government expenditure rules",
                "procurement rules",
                "financial propriety"
            ]
        },
        "pay_allowances_inspector": {
            "core_keywords": [
                "pay matrix",
                "allowances gst inspector",
                "hra ta da",
                "service benefits"
            ]
        }
    },
    "compressed_clusters": {
        "gst_core_concepts": [
            "supply",
            "itc",
            "time of supply",
            "value of supply",
            "place of supply"
        ],
        "compliance": [
            "registration",
            "returns",
            "payment",
            "refund"
        ],
        "enforcement": [
            "audit",
            "inspection",
            "search seizure",
            "demand recovery",
            "penalties"
        ],
        "administration": [
            "cbic",
            "field formations",
            "directorates",
            "nacin"
        ]
    }
}

# --------------------------------------------------
# GST CGST Act Oriented Keywords
# --------------------------------------------------
GST_CGST_ACT_KEYWORDS = {
    "book": "GST – Indirect Taxes (CGST Act Oriented)",
    "domain": ["gst", "indirect tax", "corporate taxation", "cgst act"],
    "chapters": {
        "chapter_1_introduction_constitution": {
            "core_keywords": [
                "meaning of tax",
                "direct vs indirect tax",
                "destination based tax",
                "concept of gst",
                "features of gst",
                "benefits of gst"
            ],
            "constitutional_keywords": [
                "article 246a",
                "article 269a",
                "article 366",
                "article 279a",
                "gst council",
                "power to levy gst"
            ],
            "structural_keywords": [
                "cgst sgst igst",
                "intra state supply",
                "inter state supply",
                "dual gst model",
                "gstn role"
            ]
        },
        "chapter_2_definitions": {
            "core_keywords": [
                "section 2 definitions",
                "aggregate turnover",
                "supply definition",
                "consideration",
                "business definition"
            ],
            "important_terms": [
                "goods",
                "services",
                "actionable claims",
                "exempt supply",
                "non taxable supply",
                "taxable supply"
            ],
            "person_keywords": [
                "taxable person",
                "casual taxable person",
                "non resident taxable person",
                "registered person",
                "supplier",
                "recipient"
            ],
            "credit_keywords": [
                "input tax",
                "input tax credit",
                "output tax",
                "inward supply",
                "outward supply"
            ]
        },
        "chapter_3_chargeability_goods_services": {
            "charging_keywords": [
                "section 9 cgst",
                "levy of gst",
                "charging section",
                "taxable event gst"
            ],
            "rcm_keywords": [
                "reverse charge mechanism",
                "section 9(3)",
                "section 9(4)",
                "notified supplies rcm"
            ],
            "igst_keywords": [
                "section 5 igst",
                "inter state levy",
                "import of goods",
                "import of services"
            ]
        },
        "chapter_4_supply": {
            "core_keywords": [
                "section 7 supply",
                "scope of supply",
                "taxable event supply"
            ],
            "schedule_keywords": [
                "schedule i",
                "schedule ii",
                "schedule iii"
            ],
            "classification_keywords": [
                "supply of goods",
                "supply of services",
                "composite supply",
                "mixed supply",
                "principal supply"
            ],
            "special_cases": [
                "related party supply",
                "import of services",
                "supply without consideration"
            ]
        },
        "chapter_5_place_of_supply": {
            "core_keywords": [
                "place of supply",
                "nature of supply",
                "inter state vs intra state"
            ],
            "goods_pos": [
                "section 10 igst",
                "section 11 igst",
                "bill to ship to",
                "movement of goods"
            ],
            "services_pos": [
                "section 12 igst",
                "section 13 igst",
                "immovable property services",
                "event based services",
                "performance based services"
            ],
            "special_keywords": [
                "sez supply",
                "tourist refund",
                "territorial waters"
            ]
        },
        "chapter_6_taxable_person": {
            "core_keywords": [
                "taxable person meaning",
                "who is liable to register"
            ],
            "registration_keywords": [
                "section 22 registration",
                "section 23 exemption from registration",
                "section 24 mandatory registration"
            ],
            "special_persons": [
                "casual taxable person",
                "non resident taxable person",
                "e commerce operator",
                "agent registration"
            ]
        },
        "chapter_7_exemption": {
            "core_keywords": [
                "exempt supply",
                "nil rated supply",
                "non taxable supply"
            ],
            "notification_keywords": [
                "exemption notification",
                "conditional exemption",
                "absolute exemption"
            ]
        },
        "chapter_8_valuation": {
            "core_keywords": [
                "value of supply",
                "section 15 valuation",
                "transaction value"
            ],
            "inclusion_exclusion": [
                "taxes duties fees",
                "incidental expenses",
                "subsidy treatment"
            ],
            "special_valuation": [
                "related party valuation",
                "distinct person valuation",
                "pure agent"
            ]
        },
        "chapter_9_reverse_charge": {
            "core_keywords": [
                "reverse charge",
                "recipient liable to pay gst"
            ],
            "statutory_keywords": [
                "section 9(3)",
                "section 9(4)",
                "notified goods services"
            ]
        },
        "chapter_10_invoice": {
            "core_keywords": [
                "tax invoice",
                "bill of supply",
                "debit note",
                "credit note"
            ],
            "time_keywords": [
                "time limit for invoice",
                "revised invoice"
            ]
        },
        "chapter_11_time_of_supply": {
            "core_keywords": [
                "time of supply",
                "section 12",
                "section 13"
            ],
            "special_cases": [
                "time of supply under rcm",
                "voucher supply"
            ]
        },
        "chapter_12_registration": {
            "core_keywords": [
                "gst registration",
                "threshold limit",
                "voluntary registration"
            ],
            "procedural_keywords": [
                "registration amendment",
                "cancellation of registration",
                "revocation"
            ]
        },
        "chapter_13_input_tax_credit": {
            "core_keywords": [
                "input tax credit",
                "section 16 eligibility",
                "conditions for itc"
            ],
            "blocked_itc": [
                "section 17(5)",
                "blocked credits"
            ],
            "reversal_keywords": [
                "rule 42",
                "rule 43",
                "itc reversal"
            ]
        },
        "chapter_14_manner_of_payment": {
            "core_keywords": [
                "payment of tax",
                "electronic cash ledger",
                "electronic credit ledger"
            ],
            "utilisation_keywords": [
                "order of utilisation",
                "igst credit utilisation"
            ]
        },
        "chapter_15_tds_tcs": {
            "core_keywords": [
                "tds under gst",
                "tcs under gst"
            ],
            "statutory_keywords": [
                "section 51 tds",
                "section 52 tcs"
            ]
        },
        "chapter_16_filing_of_return": {
            "core_keywords": [
                "gst returns",
                "gstr 1",
                "gstr 3b"
            ],
            "annual_keywords": [
                "gstr 9",
                "gstr 9c",
                "final return gstr 10"
            ]
        },
        "chapter_17_accounts_records": {
            "core_keywords": [
                "accounts under gst",
                "records maintenance",
                "audit trail"
            ],
            "statutory_keywords": [
                "section 35 accounts",
                "rule 56 records"
            ]
        },
        "chapter_18_eway_bill": {
            "core_keywords": [
                "e way bill",
                "movement of goods",
                "rule 138"
            ],
            "procedural_keywords": [
                "generation of eway bill",
                "validity of eway bill",
                "penalty for eway bill"
            ]
        },
        "list_of_sections_cgst": {
            "core_keywords": [
                "cgst act sections",
                "chapter wise cgst act",
                "important cgst sections"
            ]
        }
    },
    "compressed_clusters": {
        "gst_core": [
            "supply",
            "time of supply",
            "value of supply",
            "place of supply"
        ],
        "compliance": [
            "registration",
            "returns",
            "payment",
            "itc"
        ],
        "enforcement": [
            "reverse charge",
            "tds",
            "tcs",
            "eway bill"
        ]
    }
}

# --------------------------------------------------
# Share-based Payments Keywords (Chapter Locked)
# --------------------------------------------------
SHARE_BASED_PAYMENTS_CHAPTER_LOCKED_KEYWORDS = {
    "book": "Guidance Note on Accounting for Share-based Payments",
    "retrieval_strategy": "chapter_locked_then_expand",
    "domain": ["accounting", "ind as", "corporate law", "employee compensation"],
    "chapters": {
        "chapter_1_introduction": {
            "keywords": [
                "share based payment",
                "employee stock option",
                "equity compensation",
                "stock based remuneration",
                "alignment of employee interest",
                "long term incentive plans",
                "equity linked compensation",
                "scope of guidance note",
                "objective of guidance note"
            ]
        },
        "chapter_2_scope": {
            "keywords": [
                "employee share based payment",
                "non employee share based payment",
                "equity settled transaction",
                "cash settled transaction",
                "choice of settlement",
                "group share based payment",
                "excluded transactions",
                "business combination exclusion",
                "amalgamation exclusion"
            ]
        },
        "chapter_3_definitions": {
            "keywords": [
                "fair value",
                "intrinsic value",
                "grant date",
                "vesting date",
                "vesting period",
                "vesting conditions",
                "service condition",
                "performance condition",
                "market condition",
                "non vesting condition",
                "equity instrument",
                "cash settled liability",
                "counterparty",
                "measurement date"
            ]
        },
        "chapter_4_accounting": {
            "keywords": [
                "recognition principle",
                "measurement principle",
                "expense recognition",
                "equity recognition",
                "liability recognition",
                "matching principle",
                "substance over form"
            ]
        },
        "chapter_5_recognition": {
            "keywords": [
                "recognition of services",
                "recognition of goods",
                "recognition over vesting period",
                "best estimate of vesting",
                "forfeiture estimation",
                "true up mechanism",
                "revision of estimates"
            ]
        },
        "chapter_6_equity_settled_transactions": {
            "keywords": [
                "equity settled share based payment",
                "employee stock option plan",
                "esop accounting",
                "grant date fair value",
                "equity reserve",
                "vesting expense",
                "equity instruments granted",
                "share premium reserve"
            ]
        },
        "chapter_7_services_received": {
            "keywords": [
                "services received in exchange for equity",
                "non employee compensation",
                "measurement of services",
                "fair value of services",
                "fallback to equity valuation"
            ]
        },
        "chapter_8_fair_value_equity_instruments": {
            "keywords": [
                "fair value measurement",
                "option pricing model",
                "black scholes model",
                "binomial model",
                "expected volatility",
                "expected life",
                "risk free interest rate",
                "dividend yield assumptions"
            ]
        },
        "chapter_9_fair_value_not_reliable": {
            "keywords": [
                "fair value not reliably measurable",
                "intrinsic value method",
                "remeasurement at each reporting date",
                "profit or loss impact",
                "liability based accounting"
            ]
        },
        "chapter_10_modifications_cancellations_settlements": {
            "keywords": [
                "modification of grant",
                "repricing of options",
                "cancellation of esop",
                "settlement of options",
                "incremental fair value",
                "acceleration of vesting",
                "replacement grant accounting"
            ]
        },
        "chapter_11_cash_settled_transactions": {
            "keywords": [
                "cash settled share based payment",
                "stock appreciation rights",
                "liability remeasurement",
                "fair value through profit and loss",
                "settlement obligation"
            ]
        },
        "chapter_12_net_settlement_tax": {
            "keywords": [
                "net settlement feature",
                "withholding tax on esop",
                "tax settlement of options",
                "equity classification exception",
                "payroll tax adjustment"
            ]
        },
        "chapter_13_cash_alternatives": {
            "keywords": [
                "share based payment with cash alternative",
                "dual component accounting",
                "liability component",
                "equity component",
                "substance of arrangement"
            ]
        },
        "chapter_14_counterparty_choice": {
            "keywords": [
                "counterparty choice of settlement",
                "employee settlement option",
                "classification based on expectation",
                "present obligation assessment"
            ]
        },
        "chapter_15_entity_choice": {
            "keywords": [
                "entity choice of settlement",
                "discretion of enterprise",
                "constructive obligation",
                "past practice settlement"
            ]
        },
        "chapter_16_group_transactions": {
            "keywords": [
                "group share based payment",
                "parent company grant",
                "subsidiary employee compensation",
                "recharge arrangement",
                "intragroup settlement"
            ]
        },
        "chapter_17_intrinsic_value_method": {
            "keywords": [
                "intrinsic value computation",
                "market price less exercise price",
                "listed company intrinsic value",
                "unlisted valuation report"
            ]
        },
        "chapter_18_recommendation": {
            "keywords": [
                "recommended accounting treatment",
                "preferred fair value approach",
                "best practice guidance"
            ]
        },
        "chapter_19_graded_vesting": {
            "keywords": [
                "graded vesting",
                "tranche wise accounting",
                "multiple vesting dates",
                "straight line vs graded"
            ]
        },
        "chapter_20_trust_administered_plans": {
            "keywords": [
                "esop trust",
                "employee welfare trust",
                "trust administered plans",
                "loan to trust",
                "elimination of intragroup balances"
            ]
        },
        "chapter_21_eps_implications": {
            "keywords": [
                "earnings per share impact",
                "basic eps",
                "diluted eps",
                "potential equity shares",
                "as 20 eps computation"
            ]
        },
        "chapter_22_disclosures": {
            "keywords": [
                "financial statement disclosures",
                "movement of options",
                "vesting conditions disclosure",
                "fair value assumptions",
                "expense recognised"
            ]
        },
        "chapter_23_effective_date": {
            "keywords": [
                "effective date",
                "transition provisions",
                "initial adoption",
                "comparative adjustment"
            ]
        },
        "appendices": {
            "keywords": [
                "illustrative examples",
                "valuation illustrations",
                "esop accounting examples",
                "sample disclosures",
                "worked computations"
            ]
        }
    },
    "global_fallback_keywords": [
        "esop accounting treatment",
        "share based payment journal entries",
        "employee compensation accounting",
        "equity compensation tax impact",
        "ind as share based payments"
    ]
}

# --------------------------------------------------
# Share-based Payments Keywords (Retrieval Mode)
# --------------------------------------------------
SHARE_BASED_PAYMENTS_RETRIEVAL_MODE_KEYWORDS = {
    "book": "Guidance Note on Accounting for Share-based Payments",
    "retrieval_mode": "chapter_locked",
    "domain": ["accounting", "corporate law", "ind as", "employee compensation", "taxation"],
    "chapters": {
        "chapter_1_introduction": {
            "keywords": [
                "share based payment",
                "stock based compensation",
                "employee equity incentives",
                "equity linked remuneration",
                "objective of guidance note",
                "background of share based payments",
                "need for accounting guidance",
                "alignment of employee shareholder interest"
            ]
        },
        "chapter_2_scope": {
            "keywords": [
                "scope of share based payments",
                "employee share based payment",
                "non employee share based payment",
                "equity settled transaction",
                "cash settled transaction",
                "share based payment with cash alternative",
                "group share based payment",
                "excluded transactions",
                "business combination exclusion"
            ]
        },
        "chapter_3_definitions": {
            "keywords": [
                "fair value definition",
                "intrinsic value definition",
                "grant date",
                "vesting date",
                "vesting period",
                "vesting conditions",
                "service condition",
                "performance condition",
                "market condition",
                "non vesting condition",
                "equity instrument",
                "exercise price",
                "counterparty",
                "measurement date",
                "cash settled liability"
            ]
        },
        "chapter_4_accounting_principles": {
            "keywords": [
                "recognition principle",
                "measurement principle",
                "matching concept",
                "substance over form",
                "equity classification",
                "liability classification",
                "expense recognition approach"
            ]
        },
        "chapter_5_recognition": {
            "keywords": [
                "recognition of employee services",
                "recognition of goods received",
                "recognition over vesting period",
                "forfeiture estimation",
                "best estimate of vesting",
                "true up of estimates",
                "revision of vesting assumptions"
            ]
        },
        "chapter_6_equity_settled_share_based_payments": {
            "keywords": [
                "equity settled share based payment",
                "employee stock option plan",
                "esop accounting",
                "grant date fair value",
                "vesting expense",
                "equity reserve",
                "share based payment reserve",
                "accounting during vesting period"
            ]
        },
        "chapter_7_transactions_in_which_services_are_received": {
            "keywords": [
                "services received in exchange for equity",
                "non employee compensation",
                "fair value of services",
                "reliable measurement of services",
                "fallback to equity valuation"
            ]
        },
        "chapter_8_fair_value_of_equity_instruments": {
            "keywords": [
                "fair value measurement",
                "valuation of stock options",
                "option pricing model",
                "black scholes model",
                "binomial model",
                "expected volatility",
                "expected life of option",
                "risk free interest rate",
                "dividend yield",
                "valuation assumptions"
            ]
        },
        "chapter_9_fair_value_not_reliably_measurable": {
            "keywords": [
                "fair value not reliably measurable",
                "intrinsic value method",
                "remeasurement at each reporting date",
                "profit and loss impact",
                "liability based accounting"
            ]
        },
        "chapter_10_modifications_cancellations_settlements": {
            "keywords": [
                "modification of share based payment",
                "repricing of options",
                "cancellation of esop",
                "settlement of share based payment",
                "incremental fair value",
                "acceleration of vesting",
                "replacement grants"
            ]
        },
        "chapter_11_cash_settled_share_based_payments": {
            "keywords": [
                "cash settled share based payment",
                "stock appreciation rights",
                "liability recognition",
                "remeasurement at fair value",
                "fair value through profit or loss",
                "settlement obligation"
            ]
        },
        "chapter_12_net_settlement_for_tax_withholding": {
            "keywords": [
                "net settlement feature",
                "tax withholding on esop",
                "settlement for statutory tax",
                "equity vs liability classification",
                "payroll tax adjustment"
            ]
        },
        "chapter_13_share_based_payment_with_cash_alternatives": {
            "keywords": [
                "cash alternative share based payment",
                "dual settlement feature",
                "equity component",
                "liability component",
                "substance of arrangement"
            ]
        },
        "chapter_14_counterparty_choice_of_settlement": {
            "keywords": [
                "counterparty choice of settlement",
                "employee option to choose cash or equity",
                "expected settlement assessment",
                "classification based on expectation"
            ]
        },
        "chapter_15_entity_choice_of_settlement": {
            "keywords": [
                "entity choice of settlement",
                "discretion of enterprise",
                "constructive obligation",
                "past practice settlement"
            ]
        },
        "chapter_16_group_share_based_payment_transactions": {
            "keywords": [
                "group share based payment",
                "parent entity grant",
                "subsidiary employee compensation",
                "recharge arrangement",
                "intragroup accounting",
                "cost recharge mechanism"
            ]
        },
        "chapter_17_intrinsic_value_method": {
            "keywords": [
                "intrinsic value computation",
                "market price minus exercise price",
                "listed company intrinsic value",
                "unlisted company valuation"
            ]
        },
        "chapter_18_recommendation": {
            "keywords": [
                "recommendations of guidance note",
                "preferred accounting approach",
                "best practice implementation"
            ]
        },
        "chapter_19_graded_vesting": {
            "keywords": [
                "graded vesting",
                "tranche wise vesting",
                "multiple vesting dates",
                "straight line vs graded method"
            ]
        },
        "chapter_20_trust_administered_plans": {
            "keywords": [
                "esop trust",
                "employee welfare trust",
                "trust administered share based payments",
                "loan to trust",
                "accounting by trust",
                "consolidation impact"
            ]
        },
        "chapter_21_earnings_per_share_implications": {
            "keywords": [
                "earnings per share impact",
                "basic eps",
                "diluted eps",
                "potential equity shares",
                "impact of options on eps"
            ]
        },
        "chapter_22_disclosures": {
            "keywords": [
                "share based payment disclosures",
                "financial statement disclosure requirements",
                "movement of options",
                "vesting conditions disclosure",
                "fair value assumptions",
                "expense recognised disclosure"
            ]
        },
        "chapter_23_effective_date": {
            "keywords": [
                "effective date",
                "transition provisions",
                "initial adoption",
                "comparative restatement"
            ]
        },
        "appendices": {
            "keywords": [
                "illustrative examples",
                "valuation illustrations",
                "sample esop computations",
                "worked examples",
                "illustrative disclosures"
            ]
        }
    },
    "global_query_expansion": [
        "esop accounting journal entries",
        "share based payment accounting treatment",
        "employee compensation accounting",
        "equity compensation tax impact",
        "ind as share based payments"
    ]
}

# --------------------------------------------------
# GST Handbook Part A Keywords
# --------------------------------------------------
GST_HANDBOOK_PART_A_KEYWORDS = {
    "part_a": {
        "introduction_taxation": [
            "taxation overview",
            "direct tax vs indirect tax",
            "tax framework india",
            "tax compliance basics",
            "revenue collection",
            "fiscal policy"
        ],
        "indirect_tax_basics": [
            "indirect tax meaning",
            "gst fundamentals",
            "tax incidence",
            "consumption tax",
            "value added tax concept"
        ],
        "cbic_role_functions": [
            "cbic functions",
            "central board indirect taxes",
            "gst administration",
            "customs authority india",
            "tax enforcement body"
        ],
        "citizens_charter": [
            "citizens charter cbic",
            "taxpayer rights",
            "service standards cbic",
            "grievance handling"
        ],
        "cbic_structure": [
            "cbic organisational structure",
            "zonal formation",
            "commissionerate structure",
            "gst hierarchy"
        ]
    }
}

# --------------------------------------------------
# GST Handbook Part B Keywords
# --------------------------------------------------
GST_HANDBOOK_PART_B_KEYWORDS = {
    "part_b": {
        "gst_overview": [
            "what is gst",
            "gst meaning",
            "gst act overview",
            "dual gst model",
            "cgst sgst igst"
        ],
        "supply_concepts": [
            "meaning of supply",
            "scope of supply",
            "section 7 cgst",
            "schedule i ii iii",
            "taxable supply"
        ],
        "types_of_supply": [
            "composite supply",
            "mixed supply",
            "principal supply",
            "bundled supply gst"
        ],
        "registration": [
            "gst registration",
            "mandatory registration",
            "threshold limit gst",
            "registration cancellation",
            "revocation of registration",
            "section 29",
            "section 30"
        ],
        "reverse_charge_mechanism": [
            "reverse charge gst",
            "rcm applicability",
            "section 9(3)",
            "section 9(4)",
            "notified services rcm"
        ],
        "valuation": [
            "valuation of supply",
            "transaction value",
            "inclusions exclusions",
            "discount treatment gst",
            "rule 27 to 35"
        ],
        "input_tax_credit": [
            "input tax credit",
            "blocked credit",
            "section 17(5)",
            "itc reversal",
            "rule 42",
            "rule 43"
        ],
        "place_of_supply": [
            "place of supply goods",
            "place of supply services",
            "inter state supply",
            "intra state supply",
            "igst applicability"
        ],
        "time_of_supply": [
            "time of supply goods",
            "time of supply services",
            "rate change scenarios",
            "tax point"
        ],
        "returns_and_compliance": [
            "gst returns",
            "gstr 1",
            "gstr 3b",
            "due dates gst",
            "late fee interest"
        ],
        "e_invoicing": [
            "e invoicing gst",
            "irn generation",
            "qr code invoice",
            "non compliance consequences"
        ],
        "audit_and_scrutiny": [
            "gst audit",
            "scrutiny of returns",
            "section 65",
            "section 61",
            "audit checklist"
        ],
        "demand_and_recovery": [
            "gst demand",
            "show cause notice",
            "section 73",
            "section 74",
            "section 74a",
            "interest penalty"
        ],
        "penalties_offences": [
            "gst offences",
            "penalty provisions",
            "section 122",
            "section 132",
            "prosecution gst"
        ],
        "refunds": [
            "gst refund",
            "relevant date",
            "refund time limit",
            "unjust enrichment"
        ],
        "appeals": [
            "gst appeal",
            "section 107",
            "section 112",
            "high court appeal",
            "supreme court appeal"
        ]
    }
}

# --------------------------------------------------
# GST Handbook Part C Keywords
# --------------------------------------------------
GST_HANDBOOK_PART_C_KEYWORDS = {
    "part_c": {
        "rti": [
            "right to information act",
            "rti applicability",
            "information disclosure",
            "public authority"
        ],
        "service_conduct": [
            "ccs conduct rules",
            "government servant conduct",
            "disciplinary proceedings"
        ],
        "leave_rules": [
            "leave rules central government",
            "earned leave",
            "casual leave",
            "leave encashment"
        ],
        "ltc": [
            "leave travel concession",
            "ltc eligibility",
            "block year",
            "ltc claims"
        ]
    }
}

# --------------------------------------------------
# GST Handbook Part D Keywords
# --------------------------------------------------
GST_HANDBOOK_PART_D_KEYWORDS = {
    "part_d": {
        "official_language": [
            "official language policy",
            "rajbhasha",
            "language compliance"
        ],
        "office_notings": [
            "office noting format",
            "file noting",
            "administrative drafting"
        ],
        "official_phrases": [
            "government correspondence phrases",
            "official drafting language",
            "bureaucratic terminology"
        ]
    }
}

# --------------------------------------------------
# CGST Act 2017 Keywords
# --------------------------------------------------
CGST_ACT_2017_KEYWORDS = {
    "CGST_ACT_2017": {
        "CHAPTER_I_PRELIMINARY": [
            "cgst act scope",
            "commencement gst",
            "definitions gst",
            "aggregate turnover",
            "business definition",
            "supply definition",
            "goods services meaning",
            "consideration gst",
            "composite supply",
            "mixed supply",
            "principal supply",
            "recipient supplier",
            "reverse charge",
            "input tax",
            "input tax credit",
            "job work definition"
        ],
        "CHAPTER_II_ADMINISTRATION": [
            "gst officers",
            "appointment officers",
            "powers proper officer",
            "authorised officer",
            "cross empowerment"
        ],
        "CHAPTER_III_LEVY_COLLECTION": [
            "scope of supply",
            "section 7 cgst",
            "composite mixed supply tax",
            "levy of gst",
            "section 9 cgst",
            "composition levy",
            "section 10 cgst",
            "gst exemption power"
        ],
        "CHAPTER_IV_TIME_VALUE_SUPPLY": [
            "time of supply goods",
            "time of supply services",
            "rate change supply",
            "value of taxable supply",
            "transaction value",
            "valuation rules"
        ],
        "CHAPTER_V_INPUT_TAX_CREDIT": [
            "eligibility itc",
            "conditions itc",
            "blocked credit",
            "section 17(5)",
            "apportionment itc",
            "itc reversal",
            "job work itc",
            "input service distributor",
            "isd distribution",
            "excess credit recovery"
        ],
        "CHAPTER_VI_REGISTRATION": [
            "gst registration",
            "persons liable registration",
            "mandatory registration",
            "casual taxable person",
            "non resident taxable person",
            "registration procedure",
            "deemed registration",
            "amendment registration",
            "cancellation registration",
            "revocation cancellation"
        ],
        "CHAPTER_VII_TAX_INVOICE": [
            "tax invoice",
            "invoice rules gst",
            "digital payment facility",
            "unauthorised tax collection",
            "credit note",
            "debit note"
        ],
        "CHAPTER_VIII_ACCOUNTS_RECORDS": [
            "gst accounts",
            "books of accounts",
            "record maintenance",
            "retention period"
        ],
        "CHAPTER_IX_RETURNS": [
            "gst returns",
            "outward supply details",
            "inward supply communication",
            "gstr filing",
            "first return",
            "annual return",
            "final return",
            "return defaulters",
            "late fee gst",
            "gst practitioner"
        ],
        "CHAPTER_X_PAYMENT_TAX": [
            "payment of tax",
            "electronic cash ledger",
            "electronic credit ledger",
            "itc utilisation",
            "order of utilisation",
            "interest delayed payment",
            "tds gst",
            "tcs gst",
            "transfer itc"
        ],
        "CHAPTER_XI_REFUNDS": [
            "gst refund",
            "refund eligibility",
            "interest on refund",
            "consumer welfare fund"
        ],
        "CHAPTER_XII_ASSESSMENT": [
            "self assessment",
            "provisional assessment",
            "scrutiny of returns",
            "non filer assessment",
            "unregistered assessment",
            "summary assessment"
        ],
        "CHAPTER_XIII_AUDIT": [
            "gst audit",
            "departmental audit",
            "special audit"
        ],
        "CHAPTER_XIV_INSPECTION_SEARCH": [
            "inspection power",
            "search seizure",
            "arrest gst",
            "summons",
            "access business premises"
        ],
        "CHAPTER_XV_DEMAND_RECOVERY": [
            "gst demand",
            "section 73",
            "section 74",
            "fraud non fraud",
            "tax not paid",
            "erroneous refund",
            "recovery proceedings",
            "attachment property",
            "instalment payment"
        ],
        "CHAPTER_XVI_LIABILITY": [
            "transfer of business",
            "agent principal liability",
            "amalgamation merger",
            "liquidation liability",
            "director liability",
            "partner liability",
            "trustee guardian liability"
        ],
        "CHAPTER_XVII_ADVANCE_RULING": [
            "advance ruling gst",
            "aar authority",
            "application aar",
            "appellate aar",
            "national aar",
            "binding ruling",
            "void ruling"
        ],
        "CHAPTER_XVIII_APPEALS_REVISION": [
            "gst appeal",
            "section 107",
            "revisional authority",
            "gst appellate tribunal",
            "high court appeal",
            "supreme court appeal",
            "non appealable orders"
        ],
        "CHAPTER_XIX_OFFENCES_PENALTIES": [
            "gst offences",
            "penalty provisions",
            "general penalty",
            "detention seizure goods",
            "confiscation",
            "prosecution",
            "cognizance offences",
            "compounding offences"
        ],
        "CHAPTER_XX_TRANSITIONAL": [
            "migration taxpayers",
            "transitional itc",
            "job work transition"
        ],
        "CHAPTER_XXI_MISCELLANEOUS": [
            "common portal gst",
            "deemed exports",
            "anti profiteering",
            "information return",
            "burden of proof",
            "rectification error",
            "service of notice",
            "time limit extension",
            "rule making power"
        ]
    }
}

# --------------------------------------------------
# CGST Rules 2017 Keywords
# --------------------------------------------------
CGST_RULES_2017_KEYWORDS = {
    "CGST_RULES_2017": {
        "COMPOSITION_RULES": [
            "composition rules",
            "composition conditions",
            "composition turnover limit"
        ],
        "REGISTRATION_RULES": [
            "registration rules",
            "gst reg forms",
            "amendment registration rules",
            "cancellation rules"
        ],
        "VALUATION_RULES": [
            "valuation rules",
            "rule 27 to 35",
            "open market value",
            "related party valuation"
        ],
        "ITC_RULES": [
            "itc rules",
            "rule 36",
            "rule 42",
            "rule 43",
            "blocked credit rules"
        ],
        "INVOICE_RULES": [
            "invoice rules",
            "credit note rules",
            "debit note rules"
        ],
        "RETURNS_RULES": [
            "return rules",
            "gstr rules",
            "late fee rules"
        ],
        "REFUND_RULES": [
            "refund rules",
            "relevant date",
            "refund procedure"
        ],
        "EWAY_RULES": [
            "eway bill rules",
            "rule 138",
            "movement of goods"
        ],
        "DEMAND_RECOVERY_RULES": [
            "recovery rules",
            "attachment rules",
            "drc forms"
        ]
    }
}

# --------------------------------------------------
# IGST UTGST Keywords
# --------------------------------------------------
IGST_UTGST_KEYWORDS = {
    "IGST_UTGST": {
        "IGST_CORE": [
            "inter state supply",
            "intra state supply",
            "place of supply goods",
            "place of supply services",
            "zero rated supply",
            "export import gst",
            "igst refund",
            "cross utilisation itc"
        ],
        "UTGST": [
            "utgst levy",
            "union territory tax",
            "utgst credit utilisation",
            "utgst recovery"
        ]
    }
}

# --------------------------------------------------
# GST Chapter Keywords
# --------------------------------------------------
GST_CHAPTER_KEYWORDS = {
    "chapter_1_overview_gst": [
        "gst overview",
        "indirect tax reform",
        "dual gst model",
        "cgst sgst igst",
        "destination based tax",
        "subsumed taxes",
        "gst council",
        "constitutional amendment 101",
        "goods services tax concept"
    ],
    "chapter_2_levy_exemption": [
        "levy of gst",
        "section 9 cgst",
        "taxable event supply",
        "exemption notification",
        "nil rated supply",
        "absolute exemption",
        "conditional exemption",
        "composition levy",
        "reverse charge levy"
    ],
    "chapter_3_registration": [
        "gst registration",
        "section 22 threshold",
        "section 24 compulsory registration",
        "casual taxable person",
        "non resident taxable person",
        "gstin allotment",
        "registration amendment",
        "cancellation of registration",
        "revocation section 30"
    ],
    "chapter_4_scope_of_supply": [
        "meaning of supply",
        "section 7 cgst",
        "schedule i",
        "schedule ii",
        "schedule iii",
        "composite supply",
        "mixed supply",
        "principal supply",
        "activities treated as supply"
    ],
    "chapter_5_time_of_supply": [
        "time of supply goods",
        "time of supply services",
        "section 12",
        "section 13",
        "continuous supply",
        "advance received",
        "change in rate",
        "tax point determination"
    ],
    "chapter_6_valuation_gst": [
        "valuation of supply",
        "transaction value",
        "section 15 cgst",
        "related party valuation",
        "rule 27 to 35",
        "pure agent",
        "discount treatment",
        "open market value"
    ],
    "chapter_7_payment_of_tax": [
        "payment of gst",
        "electronic cash ledger",
        "electronic credit ledger",
        "section 49",
        "interest on delay",
        "late fee",
        "utilisation of itc",
        "order of utilisation"
    ],
    "chapter_8_electronic_commerce": [
        "electronic commerce operator",
        "eco liability",
        "tcs under gst",
        "section 52",
        "online marketplace gst",
        "platform based supply",
        "eco registration"
    ],
    "chapter_9_job_work": [
        "job work gst",
        "section 143",
        "principal job worker",
        "inputs sent for job work",
        "capital goods job work",
        "time limit job work",
        "challan procedure"
    ],
    "chapter_10_input_tax_credit": [
        "input tax credit",
        "section 16",
        "eligibility itc",
        "blocked credit section 17(5)",
        "itc reversal",
        "rule 42",
        "rule 43",
        "conditions for itc"
    ],
    "chapter_11_input_service_distributor": [
        "input service distributor",
        "isd mechanism",
        "section 20",
        "credit distribution",
        "isd invoice",
        "common pan distribution"
    ],
    "chapter_12_returns_matching": [
        "gst returns",
        "gstr 1",
        "gstr 3b",
        "gstr 2b",
        "matching of itc",
        "auto populated returns",
        "return filing due date",
        "late fee returns"
    ],
    "chapter_13_assessment_audit": [
        "self assessment",
        "provisional assessment",
        "scrutiny of returns",
        "gst audit section 65",
        "special audit section 66",
        "best judgment assessment"
    ],
    "chapter_14_refunds": [
        "gst refund",
        "section 54",
        "refund of excess tax",
        "refund of itc",
        "zero rated refund",
        "relevant date refund",
        "interest on delayed refund"
    ],
    "chapter_15_demands_recovery": [
        "gst demand",
        "section 73",
        "section 74",
        "show cause notice",
        "recovery proceedings",
        "provisional attachment",
        "interest penalty recovery"
    ],
    "chapter_16_appeals_review_revision": [
        "gst appeal",
        "section 107",
        "appellate authority",
        "gst tribunal",
        "revision by commissioner",
        "appeal to high court",
        "appeal to supreme court"
    ],
    "chapter_17_advance_ruling": [
        "advance ruling gst",
        "authority for advance ruling",
        "aaar",
        "national appellate authority",
        "binding nature of ruling",
        "void advance ruling"
    ],
    "chapter_18_settlement_commission": [
        "settlement commission gst",
        "omitted chapter",
        "legacy settlement provisions"
    ],
    "chapter_19_inspection_search_arrest": [
        "inspection gst",
        "search and seizure",
        "section 67",
        "power to arrest section 69",
        "summons section 70",
        "detention of goods"
    ],
    "chapter_20_offences_penalties": [
        "gst offences",
        "penalty provisions",
        "section 122",
        "section 125",
        "prosecution gst",
        "compounding of offences",
        "mens rea presumption"
    ],
    "chapter_21_igst_overview": [
        "igst act overview",
        "inter state supply",
        "import export gst",
        "zero rated supply",
        "cross border taxation"
    ],
    "chapter_22_place_of_supply": [
        "place of supply goods",
        "place of supply services",
        "section 10 igst",
        "section 12 igst",
        "section 13 igst",
        "location of supplier",
        "location of recipient"
    ],
    "chapter_23_gstn_portal_process": [
        "gstn portal",
        "common portal",
        "frontend gst process",
        "registration workflow",
        "return filing system",
        "electronic compliance"
    ],
    "chapter_24_transitional_provisions": [
        "transitional provisions",
        "migration of taxpayers",
        "tran 1",
        "tran 2",
        "carry forward credit",
        "legacy tax transition"
    ]
}

# --------------------------------------------------
# GST Flyers NACIN Keywords
# --------------------------------------------------
GST_FLYERS_NACIN_KEYWORDS = {
    "book": "GST Flyers – NACIN",
    "domain": ["GST", "Indirect Tax", "Indian Taxation"],
    "chapters": {
        "1_Registration_under_GST": [
            "gst registration", "gstin", "pan based registration", "state wise registration",
            "threshold exemption", "20 lakh limit", "10 lakh special states",
            "liability to register", "voluntary registration", "compulsory registration",
            "interstate supply registration", "casual taxable person",
            "non resident taxable person", "input service distributor",
            "reverse charge registration", "ecommerce operator registration",
            "uin registration", "sez registration", "business vertical registration",
            "registration amendment", "core amendment", "non core amendment",
            "registration cancellation", "revocation of cancellation",
            "physical verification", "gst reg forms", "gstn portal"
        ],
        "2_Cancellation_of_Registration": [
            "cancellation of gst registration", "voluntary cancellation",
            "suo moto cancellation", "revocation of cancellation",
            "final return gstr 10", "gst reg 17", "gst reg 18",
            "gst reg 19", "gst reg 21", "gst reg 22",
            "non filing of returns", "fraud registration",
            "composition default", "business discontinuance",
            "transfer of business", "death of proprietor",
            "credit reversal on cancellation", "capital goods reversal"
        ],
        "3_Meaning_and_Scope_of_Supply": [
            "supply under gst", "taxable event supply",
            "goods vs services", "schedule ii", "schedule iii",
            "neither goods nor services", "consideration definition",
            "import of services", "barter transaction",
            "related party supply", "distinct person supply",
            "business vs personal supply",
            "taxable supply", "exempt supply",
            "place of supply", "intra state supply",
            "inter state supply", "deemed supply"
        ],
        "4_Composite_and_Mixed_Supply": [
            "composite supply", "mixed supply",
            "principal supply", "naturally bundled",
            "highest rate rule", "single price supply",
            "works contract", "restaurant service",
            "education guide cbec", "printing industry gst",
            "classification of supply",
            "time of supply composite",
            "time of supply mixed"
        ],
        "5_Time_of_Supply": [
            "time of supply goods", "time of supply services",
            "section 12 cgst", "section 13 cgst",
            "invoice date", "date of payment",
            "advance received", "reverse charge time of supply",
            "voucher time of supply",
            "change in tax rate", "residual time of supply",
            "interest late fee penalty",
            "associated enterprises", "rcm services"
        ],
        "6_GST_on_Advances": [
            "gst on advances", "advance receipt taxability",
            "goods vs services advance",
            "notification 66/2017", "exemption for goods advances",
            "receipt voucher", "refund voucher",
            "advance adjustment", "advance refund",
            "rate not determinable", "place of supply not determinable",
            "credit note for advances"
        ],
        "7_Aggregate_Turnover": [
            "aggregate turnover", "all india turnover",
            "exempt supply exclusion", "job work exclusion",
            "threshold calculation", "registration limit",
            "pan based turnover"
        ],
        "8_Non_Resident_Taxable_Person": [
            "non resident taxable person",
            "foreign supplier gst",
            "advance tax payment",
            "temporary registration",
            "period extension"
        ],
        "9_Casual_Taxable_Person": [
            "casual taxable person",
            "temporary business location",
            "advance tax deposit",
            "handicraft exemption"
        ],
        "10_Input_Service_Distributor": [
            "input service distributor",
            "isd registration",
            "credit distribution",
            "isd invoice",
            "common input services"
        ],
        "11_Composition_Levy": [
            "composition scheme",
            "composition tax rate",
            "ineligible persons",
            "composition restrictions",
            "no itc composition",
            "bill of supply"
        ],
        "12_Reverse_Charge_Mechanism": [
            "reverse charge mechanism",
            "section 9(3)", "section 9(4)",
            "recipient liable to pay tax",
            "rcm services", "rcm goods",
            "self invoice under rcm"
        ],
        "13_Tax_Invoice": [
            "tax invoice", "bill of supply",
            "receipt voucher", "refund voucher",
            "invoice particulars",
            "time limit for invoice",
            "continuous supply"
        ],
        "14_Accounts_and_Records": [
            "gst accounts", "records maintenance",
            "retention period",
            "audit trail",
            "electronic records"
        ],
        "15_Credit_Note": [
            "credit note gst",
            "section 34 credit note",
            "return adjustment",
            "tax reduction"
        ],
        "16_Debit_Note": [
            "debit note gst",
            "supplementary invoice",
            "tax increase"
        ],
        "17_Electronic_Ledgers": [
            "electronic cash ledger",
            "electronic credit ledger",
            "electronic liability ledger",
            "offset of tax liability"
        ],
        "18_E_Way_Bill": [
            "e way bill",
            "movement of goods",
            "distance limit",
            "consignor consignee",
            "e way bill penalty"
        ],
        "19_Input_Tax_Credit": [
            "input tax credit",
            "itc eligibility",
            "blocked credits",
            "itc reversal",
            "matching of itc",
            "section 16 cgst"
        ],
        "20_Transition_Provisions": [
            "transitional credit",
            "carry forward cenvat",
            "tran 1", "tran 2",
            "migration to gst"
        ],
        "21_IGST_Act": [
            "integrated gst",
            "interstate supply",
            "place of supply igst",
            "import export gst"
        ],
        "22_Compensation_Cess": [
            "compensation cess",
            "sin goods cess",
            "luxury goods cess"
        ],
        "23_Imports_under_GST": [
            "import of goods",
            "import of services",
            "customs duty vs igst",
            "bill of entry"
        ],
        "24_Zero_Rated_Supplies": [
            "zero rated supply",
            "export under gst",
            "sez supply",
            "refund of igst"
        ],
        "25_Deemed_Exports": [
            "deemed export",
            "refund mechanism",
            "supply without igst"
        ],
        "26_Pure_Agent": [
            "pure agent",
            "reimbursement exclusion",
            "valuation rules"
        ],
        "27_Job_Work": [
            "job work gst",
            "challan movement",
            "job worker itc",
            "time limit job work"
        ],
        "28_Works_Contract": [
            "works contract gst",
            "immovable property",
            "composite supply works contract"
        ],
        "29_Valuation": [
            "valuation of supply",
            "transaction value",
            "related party valuation",
            "rule 27 to 35"
        ],
        "30_Margin_Scheme": [
            "margin scheme",
            "second hand goods",
            "no itc margin scheme"
        ],
        "31_Provisional_Assessment": [
            "provisional assessment",
            "bond and security",
            "final assessment"
        ],
        "32_Returns": [
            "gst returns",
            "gstr 1", "gstr 3b",
            "annual return",
            "late fee penalty"
        ],
        "33_GSTR_1": [
            "statement of outward supplies",
            "invoice level reporting",
            "amendment gstr 1"
        ],
        "34_Refunds": [
            "gst refund",
            "refund procedure",
            "refund forms",
            "unjust enrichment"
        ],
        "35_IGST_Refund_Zero_Rated": [
            "igst refund",
            "export refund",
            "shipping bill refund"
        ],
        "36_ITC_Refund": [
            "refund of unutilized itc",
            "inverted duty structure"
        ],
        "37_Advance_Ruling": [
            "advance ruling",
            "aar", "appellate aar",
            "binding nature"
        ],
        "38_GTA": [
            "goods transport agency",
            "freight gst",
            "rcm gta"
        ],
        "39_Charitable_Trusts": [
            "charitable trust gst",
            "religious trust exemption"
        ],
        "40_Education_Services": [
            "education services gst",
            "school college exemption"
        ],
        "41_Cooperative_Housing": [
            "housing society gst",
            "maintenance charges gst"
        ],
        "42_OIDAR": [
            "oidar services",
            "digital services gst",
            "foreign service provider"
        ],
        "43_GST_Practitioners": [
            "gst practitioner",
            "enrolment conditions",
            "authorized activities"
        ],
        "44_Anti_Profiteering": [
            "anti profiteering authority",
            "price reduction gst"
        ],
        "45_Benefits_of_GST": [
            "benefits of gst",
            "one nation one tax"
        ],
        "46_Special_Audit": [
            "special audit gst",
            "section 66 cgst"
        ],
        "47_TDS_under_GST": [
            "tds under gst",
            "government deductor"
        ],
        "48_TCS_under_GST": [
            "tcs under gst",
            "ecommerce tcs"
        ],
        "49_Inspection_Search_Seizure": [
            "gst inspection",
            "search seizure",
            "arrest under gst"
        ],
        "50_Appeals_and_Review": [
            "gst appeal",
            "appellate authority",
            "revision proceedings"
        ],
        "51_Recovery_of_Tax": [
            "recovery of tax",
            "attachment of bank",
            "recovery proceedings"
        ]
    }
}

# --------------------------------------------------
# Revenue Neutral Rate Report Keywords
# --------------------------------------------------
RNR_REPORT_KEYWORDS = {
    "book": "Report on Revenue Neutral Rate and Structure of Rates for GST",
    "domain": ["GST", "Indirect Tax", "Public Finance", "Tax Policy", "Macroeconomics"],
    "chapters": {
        "Foreword": [
            "gst rate committee",
            "revenue neutral rate mandate",
            "gst rate recommendation",
            "centre state revenue protection",
            "expert committee gst"
        ],
        "I_Introduction": [
            "gst reform india",
            "dual vat system",
            "federal vat comparison",
            "clean dual gst",
            "common tax base",
            "gst fiscal autonomy",
            "inter state taxation",
            "gst constitutional amendment",
            "tax system modernization"
        ],
        "II_Benefits_of_Proposed_GST": [
            "benefits of gst",
            "gst governance reform",
            "self policing tax",
            "input tax credit chain",
            "tax compliance improvement",
            "dual monitoring centre state",
            "make in india gst",
            "one nation one market",
            "elimination of cascading",
            "investment boost gst",
            "capital goods credit",
            "productivity gains",
            "inter state trade efficiency"
        ],
        "III_Current_Indirect_Tax_Structure": [
            "current indirect tax structure",
            "central excise complexity",
            "state vat structure",
            "multiple tax rates",
            "exemptions leakage",
            "cascading taxes",
            "octroi entry tax",
            "central sales tax",
            "cst distortion",
            "cvd sad exemptions",
            "negative protection",
            "manufacturing disadvantage",
            "tax fragmentation"
        ],
        "IV_Estimating_RNR": [
            "revenue neutral rate",
            "rnr definition",
            "single gst rate concept",
            "gst tax base",
            "centre state revenue replacement",
            "gst base estimation",
            "macro approach rnr",
            "indirect tax turnover approach",
            "direct tax turnover approach",
            "gst compliance assumption",
            "exemption impact on rnr",
            "gst base to gdp ratio"
        ],
        "Macro_Approach": [
            "national income accounts",
            "supply use tables",
            "gst macro estimation",
            "potential gst base",
            "exempt sector impact",
            "petroleum electricity exemption",
            "compliance loss assumption",
            "theoretical gst base"
        ],
        "Indirect_Tax_Turnover_Approach": [
            "vat collections based base",
            "state vat data",
            "effective tax rate method",
            "services base estimation",
            "mca database turnover",
            "cascading effect",
            "unorganized sector impact",
            "input output adjustment",
            "itt rnr estimate"
        ],
        "Direct_Tax_Turnover_Approach": [
            "income tax data usage",
            "profit and loss turnover",
            "sector wise gst base",
            "exempt sector removal",
            "input tax credit deduction",
            "unregistered dealer purchases",
            "dtt rnr estimate"
        ],
        "V_Recommendations": [
            "recommended rnr",
            "gst rate calibration",
            "committee preferred rnr",
            "gst standard rate",
            "lower rate gst",
            "rate band structure",
            "two rate gst model",
            "gst regressivity",
            "international vat comparison",
            "gst competitiveness"
        ],
        "Critical_Assessment": [
            "rnr methodology critique",
            "base underestimation risk",
            "cascading omission",
            "withholding effect",
            "textiles sugar exclusion",
            "compliance bias",
            "statutory vs effective rate"
        ],
        "Risk_Analysis": [
            "rnr risk assessment",
            "revenue shortfall risk",
            "centre state trust deficit",
            "gst compensation risk",
            "compliance elasticity",
            "rate sensitivity",
            "political economy gst"
        ],
        "Structure_of_Rates": [
            "gst rate structure",
            "standard rate",
            "lower rate",
            "demerit rate",
            "sin goods taxation",
            "rate differentiation",
            "product rate assignment",
            "rate band flexibility",
            "fiscal autonomy states"
        ],
        "Exemptions_and_Thresholds": [
            "gst exemptions",
            "exemption leakage",
            "threshold exemption",
            "small taxpayer impact",
            "exempt goods services",
            "base erosion"
        ],
        "Price_Impact_and_Distribution": [
            "gst price impact",
            "cpi sensitivity",
            "inflation scenarios",
            "consumption basket",
            "income group tax burden",
            "regressive tax impact",
            "distributional analysis"
        ],
        "Compensation": [
            "gst compensation",
            "state revenue loss",
            "compensation requirement",
            "centre compensation obligation",
            "cst compensation"
        ],
        "VI_Conclusion": [
            "gst policy conclusion",
            "optimal gst rate",
            "long term gst efficiency",
            "tax system rationalization",
            "growth oriented gst"
        ],
        "Tables": [
            "federal vat comparison",
            "cst impact table",
            "cvd exemption illustration",
            "indirect tax summary",
            "rnr comparison table",
            "rate structure table",
            "exemption threshold table"
        ],
        "Figures": [
            "collection efficiency",
            "vat rate comparison",
            "cpi composition",
            "inflation scenarios",
            "rate sensitivity graphs"
        ],
        "Annexures": [
            "macro rnr annex",
            "itt annex",
            "dtt annex",
            "ssi gst impact",
            "effective tax rates scenarios"
        ]
    }
}

# --------------------------------------------------
# Tax Audit Section 44AB Keywords
# --------------------------------------------------
TAX_AUDIT_44AB_KEYWORDS = {
    "book": "Guidance Note on Tax Audit under Section 44AB (Revised 2023)",
    "domain": ["Direct Tax", "Tax Audit", "Income Tax", "Corporate Compliance"],
    "chapters": {
        "Preliminary_Matter": [
            "tax audit guidance note",
            "section 44ab overview",
            "icai guidance",
            "revised 2023 edition",
            "tax audit objectives",
            "audit under income tax act",
            "forms 3ca 3cb 3cd",
            "specified date audit",
            "chartered accountant responsibility"
        ],
        "1_Introduction": [
            "meaning of audit",
            "tax audit definition",
            "objective of tax audit",
            "form 3ca 3cb",
            "form 3cd particulars",
            "verification of books",
            "assessing officer facilitation",
            "scope of tax audit"
        ],
        "2_Background": [
            "history of section 44ab",
            "finance act 1984",
            "presumptive taxation audit",
            "sections 44ad 44ada 44ae",
            "evolution of tax audit",
            "audit expansion amendments",
            "judicial validity of 44ab"
        ],
        "3_Provisions_of_Section_44AB": [
            "section 44ab applicability",
            "tax audit threshold",
            "1 crore limit",
            "10 crore cash condition",
            "50 lakh professional limit",
            "presumptive income audit",
            "specified date definition",
            "rule 6g",
            "forms applicability",
            "44ad 44ada exceptions"
        ],
        "4_Profession_vs_Business": [
            "business definition",
            "profession definition",
            "section 2(13)",
            "section 2(36)",
            "section 44aa professions",
            "legal medical engineering profession",
            "it professionals tax audit",
            "business vs profession test"
        ],
        "5_Sales_Turnover_Gross_Receipts": [
            "sales definition",
            "turnover meaning",
            "gross receipts",
            "gst inclusion turnover",
            "trade discount turnover",
            "scrap sales inclusion",
            "commission agent turnover",
            "share broker turnover",
            "derivatives turnover",
            "futures options turnover",
            "speculative transaction turnover"
        ],
        "6_Liability_to_Tax_Audit_Special_Cases": [
            "special cases tax audit",
            "multiple businesses",
            "unit wise turnover",
            "combined turnover",
            "audit under other law",
            "company llp audit",
            "cooperative society audit"
        ],
        "7_Specified_Date": [
            "specified date meaning",
            "due date tax audit",
            "section 139(1)",
            "audit report deadline",
            "extended due date"
        ],
        "8_Penalty": [
            "penalty section 271b",
            "failure to audit",
            "reasonable cause",
            "section 273b",
            "penalty waiver"
        ],
        "9_Tax_Auditor": [
            "tax auditor eligibility",
            "section 288 accountant",
            "chartered accountant definition",
            "disqualification auditor",
            "professional responsibility"
        ],
        "10_Form_of_Financial_Statements": [
            "financial statements format",
            "balance sheet",
            "profit loss account",
            "audit documentation"
        ],
        "11_Accounting_Standards": [
            "accounting standards applicability",
            "ind as vs as",
            "companies accounting standards rules",
            "non company assessees"
        ],
        "12_Accounts_and_Income_Tax_Law": [
            "accounts under income tax",
            "section 145",
            "cash mercantile system",
            "icds applicability",
            "books of account compliance"
        ],
        "13_Audit_Procedures": [
            "tax audit procedures",
            "audit planning",
            "verification techniques",
            "substantive procedures",
            "reporting responsibility"
        ],
        "14_Professional_Misconduct": [
            "professional misconduct",
            "code of ethics",
            "icai disciplinary action",
            "false certification"
        ],
        "15_Audit_Report": [
            "tax audit report",
            "form 3ca",
            "form 3cb",
            "form 3cd",
            "audit opinion"
        ],
        "16_Issuing_Audit_Report": [
            "issuance of audit report",
            "signing audit report",
            "udins",
            "e filing audit report"
        ],
        "17_Form_3CA": [
            "form 3ca applicability",
            "audit under other law",
            "company audit linkage"
        ],
        "18_Form_3CB": [
            "form 3cb applicability",
            "non corporate audit",
            "independent tax audit"
        ],
        "19_Form_3CD": [
            "form 3cd clauses",
            "tax audit particulars",
            "reporting requirements",
            "clause wise reporting"
        ],
        "20_Form_3CD_Clauses_1_to_8A": [
            "basic particulars",
            "pan tan reporting",
            "registration numbers",
            "section 44ab clause 8a"
        ],
        "21_Clause_9_Members_Partners": [
            "partners details",
            "members particulars",
            "profit sharing ratio"
        ],
        "22_Clause_10_Nature_of_Business": [
            "nature of business",
            "profession classification",
            "business activity code"
        ],
        "23_Clause_11_Books_of_Account": [
            "books of account",
            "supporting documents",
            "section 44aa compliance"
        ],
        "24_Clause_12_Presumptive_Income": [
            "presumptive taxation",
            "section 44ad",
            "section 44ada",
            "section 44ae",
            "lower income declaration"
        ],
        "25_Clause_13_Method_of_Accounting": [
            "method of accounting",
            "cash system",
            "mercantile system",
            "icds disclosures"
        ],
        "26_Clause_14_Closing_Stock": [
            "valuation of closing stock",
            "section 145a",
            "inventory valuation",
            "inclusive taxes"
        ],
        "27_Clause_15_Asset_to_Stock": [
            "conversion of capital asset",
            "stock in trade conversion",
            "section 45(2)"
        ],
        "28_Clause_16_Income_Not_Credited": [
            "income not credited",
            "undisclosed income",
            "taxable receipts"
        ],
        "29_Clause_17_Property_Valuation": [
            "valuation of property",
            "stamp duty value",
            "section 43ca",
            "section 50c"
        ],
        "30_Clause_18_Depreciation": [
            "depreciation details",
            "block of assets",
            "section 32"
        ],
        "31_Clause_19_Admissible_Amounts": [
            "section 32ac",
            "section 35ad",
            "section 35e",
            "capital expenditure deductions"
        ],
        "32_Clause_20_Employee_Payments": [
            "bonus commission",
            "pf esic",
            "employees contribution",
            "section 36(1)(va)"
        ],
        "33_Clause_21_Inadmissible_Expenses": [
            "section 40a",
            "capital expenditure",
            "personal expenses",
            "advertisement expenses"
        ],
        "34_Clause_21b_TDS_Defaults": [
            "section 40(a)",
            "tds disallowance",
            "non deduction tds"
        ],
        "35_Clause_21c_Partner_Payments": [
            "partner salary",
            "partner interest",
            "section 40b"
        ],
        "36_Clause_21d_Cash_Payments": [
            "section 40a(3)",
            "cash expenditure limit"
        ],
        "37_Clause_21e_Provision": [
            "section 40a(7)",
            "provision for gratuity"
        ],
        "38_Clause_21f_Trust_Payments": [
            "section 40a(9)",
            "trust contributions"
        ],
        "39_Clause_21g_Contingent_Liability": [
            "contingent liabilities",
            "unascertained liabilities"
        ],
        "40_Clause_21h_Section_14A": [
            "section 14a",
            "exempt income disallowance"
        ],
        "41_Clause_21i_Borrowing_Cost": [
            "section 36(1)(iii)",
            "interest capitalization"
        ],
        "42_Clause_22_MSME": [
            "msme act",
            "section 23 msme",
            "delayed payments"
        ],
        "43_Clause_23_Specified_Persons": [
            "section 40a(2)(b)",
            "related party payments"
        ],
        "44_Clause_24_Deemed_Profits": [
            "deemed profits",
            "section 32ac",
            "section 33ab"
        ],
        "45_Clause_25_Section_41": [
            "section 41 income",
            "remission cessation"
        ],
        "46_Clause_26_Section_43B": [
            "section 43b",
            "statutory dues",
            "payment basis deduction"
        ],
        "47_Clause_27_Cenvat": [
            "cenvat credit",
            "vat credit reporting"
        ],
        "48_Clause_27b_Prior_Period": [
            "prior period expenses"
        ],
        "49_Clause_28_Section_56": [
            "section 56(2)(viia)",
            "property received"
        ],
        "50_Clause_29_Share_Premium": [
            "section 56(2)(viib)",
            "share premium taxation",
            "angel tax"
        ],
        "51_Clause_29A_56ix": [
            "section 56(2)(ix)"
        ],
        "52_Clause_29B_56x": [
            "section 56(2)(x)",
            "gift taxation"
        ],
        "53_Clause_30_Hundi": [
            "hundi loans",
            "section 69d"
        ],
        "54_Clause_30A_Transfer_Pricing": [
            "section 92ce",
            "primary adjustment"
        ],
        "55_Clause_30B_Thin_Capitalisation": [
            "section 94b",
            "interest limitation"
        ],
        "56_Clause_30C_GAAR": [
            "gaar",
            "impermissible avoidance arrangement",
            "section 96"
        ],
        "57_Clause_31_Loans_Deposits": [
            "section 269ss",
            "loan acceptance",
            "cash loan violation"
        ],
        "58_Clause_31_269ST": [
            "section 269st",
            "cash receipt limit"
        ],
        "59_Clause_31c_Repayment": [
            "section 269t",
            "loan repayment"
        ],
        "62_Clause_32_Losses": [
            "brought forward loss",
            "unabsorbed depreciation"
        ],
        "63_Clause_32b_Shareholding": [
            "change in shareholding",
            "section 79"
        ],
        "64_Clause_32c_Speculation": [
            "speculation loss",
            "section 73"
        ],
        "67_Clause_33_Deductions": [
            "chapter via deductions",
            "chapter iii exemptions"
        ],
        "68_Clause_34_TDS_TCS": [
            "tds compliance",
            "tcs compliance",
            "chapter xvii"
        ],
        "71_Clause_35_Quantitative_Details": [
            "quantitative details",
            "trading concern",
            "manufacturing concern"
        ],
        "75_Clause_37_Cost_Audit": [
            "cost audit report"
        ],
        "76_Clause_38_Excise": [
            "excise audit"
        ],
        "77_Clause_39_Service_Tax": [
            "service tax audit"
        ],
        "78_Clause_40_Goods_Services": [
            "details of goods traded",
            "services rendered"
        ],
        "79_Clause_41_Demand_Refund": [
            "tax demand",
            "refund details"
        ],
        "80_Clause_42_Form_61": [
            "form 61",
            "form 61a",
            "form 61b"
        ],
        "82_Clause_44_GST": [
            "gst compliance",
            "gst turnover",
            "gst reconciliation"
        ],
        "Appendices": [
            "forms 3ca 3cb 3cd specimen",
            "icai authority clarification",
            "cbdt circulars",
            "code of ethics",
            "audit fee guidelines"
        ]
    }
}

# --------------------------------------------------
# Transfer Pricing Section 92E Keywords
# --------------------------------------------------
TRANSFER_PRICING_92E_KEYWORDS = {
    "book": "Guidance Note on Report under Section 92E of the Income-tax Act, 1961",
    "edition": "Ninth Edition (2022)",
    "domain": ["Transfer Pricing", "International Tax", "Direct Tax", "Corporate Compliance"],
    "chapters": {
        "Chapter_1_Introduction": [
            "transfer pricing india",
            "section 92 to 92f",
            "chapter x income tax",
            "legislative framework tp",
            "arm's length principle",
            "profit shifting",
            "base erosion",
            "globalisation tax",
            "cross border transactions",
            "digital economy taxation",
            "objective of guidance note",
            "applicability of tp provisions",
            "specified date",
            "anti avoidance provisions"
        ],
        "Chapter_2_Responsibility_of_Enterprise_and_Accountant": [
            "enterprise responsibility",
            "taxpayer tp compliance",
            "accountant responsibility",
            "chartered accountant role",
            "section 92e reporting",
            "examination of records",
            "professional judgment",
            "professional misconduct",
            "icai code of ethics",
            "false certification risk"
        ],
        "Chapter_3_Associated_Enterprise": [
            "associated enterprise",
            "section 92a definition",
            "deemed associated enterprise",
            "control and management",
            "shareholding threshold",
            "voting power",
            "loan dependence",
            "guarantee relationship",
            "head office branch relationship",
            "permanent establishment",
            "specified domestic transaction ae"
        ],
        "Chapter_4_International_Transaction": [
            "international transaction",
            "section 92b",
            "cross border transaction",
            "tangible property",
            "intangible property",
            "services transaction",
            "financing transaction",
            "capital financing",
            "cost contribution arrangement",
            "free of cost services",
            "guarantees",
            "interplay section 9 and 92",
            "retrospective amendment tp"
        ],
        "Chapter_4A_Specified_Domestic_Transaction": [
            "specified domestic transaction",
            "section 92ba",
            "sdts definition",
            "threshold limit sdt",
            "20 crore limit",
            "related party domestic transaction"
        ],
        "Chapter_5_Arms_Length_Price": [
            "arm's length price",
            "alp determination",
            "uncontrolled transaction",
            "comparable uncontrolled transaction",
            "comparability analysis",
            "functions assets risks analysis",
            "far analysis",
            "characterisation of entity",
            "tested party",
            "contractual terms",
            "market conditions",
            "business strategy",
            "economic circumstances",
            "power of assessing officer"
        ],
        "Chapter_6_Methods_of_Computation_of_ALP": [
            "transfer pricing methods",
            "cup method",
            "rpm method",
            "cost plus method",
            "profit split method",
            "tnmm",
            "other method",
            "most appropriate method",
            "method selection",
            "internal comparable",
            "external comparable",
            "benchmarking study",
            "range concept",
            "multiple year data"
        ],
        "Chapter_7_Documentation_and_Verification": [
            "transfer pricing documentation",
            "section 92d",
            "rule 10d",
            "ownership profile",
            "group structure",
            "international transaction details",
            "method working",
            "relief from documentation",
            "supporting documents",
            "contemporaneous documentation",
            "master file",
            "country by country reporting",
            "cbcr",
            "local file",
            "maintenance of records"
        ],
        "Chapter_8_Penalties": [
            "transfer pricing penalties",
            "concealment of income",
            "under reporting",
            "misreporting of income",
            "penalty immunity",
            "failure to maintain documents",
            "section 271aa",
            "failure to furnish report",
            "section 271ba",
            "failure to furnish information",
            "section 271g",
            "section 271j accountant penalty",
            "section 286 penalty"
        ],
        "Chapter_9_Scope_of_Examination_under_92E": [
            "scope of tax audit 92e",
            "form 3ceb report",
            "verification responsibility",
            "true and correct particulars",
            "annexure to form 3ceb",
            "other examination aspects",
            "limited vs detailed verification"
        ],
        "Annexure_Statutory_Provisions": [
            "sections 92 to 92f",
            "section 92ca",
            "section 92cc",
            "section 92cd",
            "section 92ce",
            "section 94b",
            "section 286",
            "faceless transfer pricing",
            "advance pricing agreement"
        ],
        "Annexure_Rules_and_Forms": [
            "rule 10a to 10e",
            "form 3ceb",
            "rule 10da",
            "master file form",
            "cbcr form",
            "safe harbour rules"
        ],
        "Annexure_Circulars_and_Guidance": [
            "cbdt circulars",
            "memorandum finance bill",
            "transfer pricing clarifications",
            "icai guidance"
        ],
        "Annexure_Ethics_and_Auditing": [
            "code of ethics",
            "mandatory communication",
            "sa 610 revised",
            "using work of internal auditors",
            "professional fees guidance"
        ]
    }
}

# --------------------------------------------------
# CARO 2020 Keywords
# --------------------------------------------------
CARO_2020_KEYWORDS = {
    "book": "Guidance Note on Companies (Auditor's Report) Order, 2020",
    "edition": "Revised 2022",
    "domain": ["Audit", "Corporate Law", "Companies Act", "Taxation"],
    "chapters": {
        "Introduction": [
            "caro 2020",
            "section 143(11)",
            "auditor reporting order",
            "supersession caro 2016",
            "applicability fy 2021-22",
            "audit reporting obligations",
            "guidance note objective"
        ],
        "General_Provisions_Auditors_Report": [
            "section 143 audit report",
            "supplemental reporting",
            "cag directions",
            "government company audit",
            "auditor duties",
            "mandatory statements",
            "reporting vs inquiry"
        ],
        "Applicability_of_the_Order": [
            "companies covered caro",
            "companies exempted",
            "foreign company audit",
            "branch audit applicability",
            "section 8 companies",
            "opc small company exemption",
            "private company thresholds",
            "paid up capital limit",
            "borrowing threshold",
            "revenue threshold",
            "nbfc applicability",
            "reit invit exclusion"
        ],
        "Auditors_Report_Paragraphs_3_and_4": [
            "paragraph 3 reporting",
            "paragraph 4 reporting",
            "as applicable principle",
            "financial year applicability",
            "consolidated financial statements",
            "clause 3(xxi) consolidation"
        ],
        "Period_of_Compliance": [
            "period of reporting",
            "whole year compliance",
            "maintenance of records",
            "balance sheet date vs year",
            "continuous compliance"
        ],
        "General_Approach": [
            "audit approach caro",
            "standards on auditing",
            "sa 230 documentation",
            "materiality sa 320",
            "audit risk",
            "management representations",
            "audit planning",
            "professional judgment",
            "working papers"
        ],
        "Schedule_III_Disclosures": [
            "schedule iii disclosure",
            "benami property",
            "title deeds",
            "revaluation ppe",
            "borrowings against security",
            "wilful defaulter",
            "undisclosed income",
            "csr disclosure",
            "ratio disclosures"
        ],
        "Paragraph_3_i_PPE": [
            "property plant equipment",
            "ppe register",
            "as 10",
            "ind as 16",
            "ind as 116 rou asset",
            "physical verification ppe",
            "reconciliation ppe",
            "componentisation",
            "impairment ppe",
            "title deeds immovable property",
            "benami proceedings"
        ],
        "Paragraph_3_ii_Inventory": [
            "inventory verification",
            "physical stock verification",
            "working capital limits",
            "quarterly statements",
            "stock discrepancies",
            "bank returns inventory"
        ],
        "Paragraph_3_iii_Loans_Investments_Guarantees": [
            "loans granted",
            "advances in nature of loan",
            "guarantees provided",
            "repayment schedule",
            "overdue loans",
            "related party loans",
            "prejudicial interest",
            "section 185",
            "section 186"
        ],
        "Paragraph_3_iv_Section_185_186": [
            "director loans",
            "inter corporate loans",
            "investment compliance",
            "guarantees to directors",
            "section 185 violation",
            "section 186 limits"
        ],
        "Paragraph_3_v_Public_Deposits": [
            "public deposits",
            "sections 73 to 76",
            "deposit rules",
            "unclaimed deposits",
            "nbfc deposits"
        ],
        "Paragraph_3_vi_Cost_Records": [
            "cost records",
            "section 148",
            "cost audit",
            "maintenance of cost records"
        ],
        "Paragraph_3_vii_Statutory_Dues": [
            "statutory dues",
            "gst dues",
            "income tax dues",
            "pf esi",
            "customs excise",
            "disputed dues",
            "arrears more than six months"
        ],
        "Paragraph_3_viii_Undisclosed_Income": [
            "undisclosed income",
            "income tax assessments",
            "previously unrecorded income",
            "tax surrender"
        ],
        "Paragraph_3_ix_Loans_Borrowings": [
            "loan defaults",
            "wilful defaulter",
            "term loan utilisation",
            "short term funds",
            "diversion of funds",
            "subsidiary financing"
        ],
        "Paragraph_3_x_IPO_FPO": [
            "initial public offer",
            "further public offer",
            "preferential allotment",
            "private placement",
            "utilisation of funds"
        ],
        "Paragraph_3_xi_Fraud": [
            "fraud by company",
            "fraud on company",
            "reporting to government",
            "whistle blower complaints",
            "sa 240"
        ],
        "Paragraph_3_xii_Nidhi_Companies": [
            "nidhi company",
            "net owned funds",
            "deposit ratio",
            "default in repayment"
        ],
        "Paragraph_3_xiii_Related_Party": [
            "related party transactions",
            "section 177",
            "section 188",
            "arm's length",
            "disclosure compliance"
        ],
        "Paragraph_3_xiv_Internal_Audit": [
            "internal audit system",
            "commensurate audit",
            "internal auditor reports",
            "scope internal audit"
        ],
        "Paragraph_3_xv_Non_Cash_Transactions": [
            "non cash transactions",
            "director asset transactions",
            "section 192 compliance"
        ],
        "Paragraph_3_xvi_RBI_Act": [
            "nbfc registration",
            "rbi act 45 ia",
            "cic registration",
            "housing finance company"
        ],
        "Paragraph_3_xvii_Cash_Losses": [
            "cash losses",
            "current year losses",
            "previous year losses"
        ],
        "Paragraph_3_xviii_Auditor_Resignation": [
            "auditor resignation",
            "statutory auditor",
            "issues concerns resignation"
        ],
        "Paragraph_3_xix_Material_Uncertainty": [
            "going concern",
            "liability payment uncertainty",
            "financial stress",
            "liquidity risk"
        ],
        "Paragraph_3_xx_CSR": [
            "corporate social responsibility",
            "section 135",
            "unspent csr",
            "csr transfer funds"
        ],
        "Paragraph_3_xxi_Components_CARO": [
            "component auditors",
            "consolidated caro",
            "qualifications adverse remarks"
        ],
        "Comments_on_Form_of_Report": [
            "format of audit report",
            "qualifications",
            "emphasis of matter",
            "caro reporting language"
        ],
        "Board_of_Directors_Report": [
            "board report consistency",
            "section 134",
            "auditor comments"
        ],
        "Appendices": [
            "text of caro 2020",
            "caro 2016 comparison",
            "definitions",
            "important sections",
            "illustrative checklist"
        ]
    }
}

DOMAIN_KNOWLEDGE = {

    "accounting standards": {

        "synonyms": [

            "accounting standard meaning",

            "definition of accounting standards",

            "objectives of accounting standards",

            "benefits of accounting standards",

            "limitations of accounting standards",

            "need for accounting standards"

        ],

        "subtopics": [

            "financial reporting",

            "comparability",

            "consistency",

            "transparency",

            "reliability"

        ]

    },

    "ifrs": {

        "synonyms": [

            "international financial reporting standards",

            "global accounting standards",

            "iasb standards"

        ],

        "subtopics": [

            "iasb",

            "iasc",

            "convergence",

            "global reporting"

        ]

    },

    "ind as": {

        "synonyms": [

            "indian accounting standards",

            "mca notified standards",

            "icai standards"

        ],

        "subtopics": [

            "ind as 1",

            "ind as 2",

            "ind as 16",

            "ind as 38",

            "ind as 40",

            "ind as 115"

        ]

    },

    "ppe": {

        "synonyms": [

            "property plant and equipment",

            "fixed assets",

            "tangible assets",

            "long term assets",

            "ind as 16"

        ],

        "subtopics": [

            "recognition of ppe",

            "measurement of ppe",

            "initial measurement",

            "subsequent measurement",

            "depreciation",

            "revaluation",

            "carrying amount",

            "fair value",

            "useful life",

            "residual value"

        ]

    },

    "depreciation": {

        "synonyms": [

            "wear and tear of asset",

            "asset value reduction"

        ],

        "subtopics": [

            "useful life",

            "residual value",

            "straight line method",

            "written down value",

            "accumulated depreciation",

            "depreciable amount"

        ]

    },

    "revenue": {

        "synonyms": [

            "income",

            "sales revenue",

            "operating revenue",

            "ind as 115"

        ],

        "subtopics": [

            "revenue recognition",

            "five step model",

            "performance obligation",

            "transaction price",

            "contract asset",

            "contract liability"

        ]

    },

    "financial statements": {

        "synonyms": [

            "final accounts",

            "financial reports",

            "ind as 1"

        ],

        "subtopics": [

            "balance sheet",

            "statement of profit and loss",

            "other comprehensive income",

            "notes to accounts",

            "disclosure",

            "presentation"

        ]

    },

    "audit and auditors": {

        "module": "Corporate Law & Compliance",

        "chapter": "Audit and Auditors",

        "domain": ["corporate law", "company audit", "statutory compliance", "taxation advisory"],

        "synonyms": [

            "appointment of auditor",

            "removal of auditor",

            "resignation of auditor",

            "audit report",

            "powers of auditor",

            "disqualification of auditor",

            "government company audit",

            "branch audit",

            "rotation of auditors",

            "reporting of fraud",

            "statutory auditor",

            "external auditor",

            "company auditor",

            "financial auditor",

            "compliance audit",

            "legal audit",

            "corporate audit",

            "who can be appointed as auditor?",

            "what is the term of an auditor?",

            "how to remove an auditor?",

            "what are the powers of an auditor?",

            "what is casual vacancy?",

            "how to report fraud?",

            "can auditor give consultancy?",

            "what is ADT-3 form?",

            "who appoints auditor in government company?",

            "what is auditor rotation?"

        ],

        "subtopics": [

            "statutory audit",

            "first auditor",

            "subsequent auditor",

            "casual vacancy",

            "audit committee",

            "cooling-off period",

            "joint auditors",

            "true and fair view",

            "professional misconduct",

            "fraud reporting",

            "cost audit",

            "branch audit",

            "supplementary audit",

            "test audit",

            "auditing standards",

            "Section 139",

            "Section 140",

            "Section 141",

            "Section 142",

            "Section 143",

            "Section 144",

            "Section 145",

            "Section 146",

            "Section 147",

            "Section 148",

            "appointment of first auditor",

            "appointment of auditor in AGM",

            "appointment of auditor in government company",

            "filling casual vacancy",

            "rotation of auditors",

            "removal of auditor with CG approval",

            "resignation filing",

            "filing ADT-1",

            "filing ADT-2",

            "filing ADT-3",

            "filing ADT-4",

            "special notice for new auditor",

            "branch auditor appointment",

            "cost auditor appointment",

            "only chartered accountant can be auditor",

            "majority partners must be CAs",

            "LLP allowed",

            "partner signing authority",

            "within auditor limit of 20 companies",

            "body corporate not allowed",

            "officer or employee disqualified",

            "holding securities in company",

            "relative holding excess securities",

            "indebtedness above threshold",

            "guarantee exceeding limit",

            "business relationship",

            "full time employment elsewhere",

            "fraud conviction",

            "consulting services conflict",

            "30 days for first auditor by board",

            "90 days by members",

            "15 days filing ADT-1",

            "60 days for CG fraud reporting",

            "45 days for board reply",

            "3 years transition for rotation",

            "5 years cooling period",

            "180 days for CAG appointment",

            "30 days for resignation filing",

            "ADT-1",

            "ADT-2",

            "ADT-3",

            "ADT-4",

            "Central Government",

            "Comptroller and Auditor General (CAG)",

            "NCLT",

            "ICAI",

            "NFRA",

            "Registrar of Companies",

            "fine on company",

            "fine on auditor",

            "imprisonment",

            "refund of remuneration",

            "civil liability",

            "criminal liability",

            "disqualification for 5 years",

            "access to books",

            "right to seek information",

            "inquiry into loans",

            "verify book entries",

            "verify investments sale",

            "verify deposits",

            "check personal expenses",

            "verify share allotment",

            "report adverse findings",

            "attend general meetings",

            "book keeping",

            "internal audit",

            "financial system design",

            "actuarial services",

            "investment advisory",

            "investment banking",

            "outsourced financial services",

            "management services"

        ],

        "routing_keywords": [

            "appointment of auditor",

            "removal of auditor",

            "resignation of auditor",

            "audit report",

            "powers of auditor",

            "disqualification of auditor",

            "government company audit",

            "branch audit",

            "rotation of auditors",

            "reporting of fraud"

        ],

        "core_concepts": [

            "statutory audit",

            "first auditor",

            "subsequent auditor",

            "casual vacancy",

            "audit committee",

            "cooling-off period",

            "joint auditors",

            "true and fair view",

            "professional misconduct",

            "fraud reporting",

            "cost audit",

            "branch audit",

            "supplementary audit",

            "test audit",

            "auditing standards"

        ],

        "legal_sections": [

            "Section 139",

            "Section 140",

            "Section 141",

            "Section 142",

            "Section 143",

            "Section 144",

            "Section 145",

            "Section 146",

            "Section 147",

            "Section 148"

        ],

        "procedures": [

            "appointment of first auditor",

            "appointment of auditor in AGM",

            "appointment of auditor in government company",

            "filling casual vacancy",

            "rotation of auditors",

            "removal of auditor with CG approval",

            "resignation filing",

            "filing ADT-1",

            "filing ADT-2",

            "filing ADT-3",

            "filing ADT-4",

            "special notice for new auditor",

            "branch auditor appointment",

            "cost auditor appointment"

        ],

        "eligibility_rules": [

            "only chartered accountant can be auditor",

            "majority partners must be CAs",

            "LLP allowed",

            "partner signing authority",

            "within auditor limit of 20 companies"

        ],

        "disqualifications": [

            "body corporate not allowed",

            "officer or employee disqualified",

            "holding securities in company",

            "relative holding excess securities",

            "indebtedness above threshold",

            "guarantee exceeding limit",

            "business relationship",

            "full time employment elsewhere",

            "fraud conviction",

            "consulting services conflict"

        ],

        "time_limits": [

            "30 days for first auditor by board",

            "90 days by members",

            "15 days filing ADT-1",

            "60 days for CG fraud reporting",

            "45 days for board reply",

            "3 years transition for rotation",

            "5 years cooling period",

            "180 days for CAG appointment",

            "30 days for resignation filing"

        ],

        "forms": [

            "ADT-1",

            "ADT-2",

            "ADT-3",

            "ADT-4"

        ],

        "authorities": [

            "Central Government",

            "Comptroller and Auditor General (CAG)",

            "NCLT",

            "ICAI",

            "NFRA",

            "Registrar of Companies"

        ],

        "penalties": [

            "fine on company",

            "fine on auditor",

            "imprisonment",

            "refund of remuneration",

            "civil liability",

            "criminal liability",

            "disqualification for 5 years"

        ],

        "powers_and_duties": [

            "access to books",

            "right to seek information",

            "inquiry into loans",

            "verify book entries",

            "verify investments sale",

            "verify deposits",

            "check personal expenses",

            "verify share allotment",

            "report adverse findings",

            "attend general meetings"

        ],

        "prohibited_services": [

            "book keeping",

            "internal audit",

            "financial system design",

            "actuarial services",

            "investment advisory",

            "investment banking",

            "outsourced financial services",

            "management services"

        ],

        "user_query_variants": [

            "who can be appointed as auditor?",

            "what is the term of an auditor?",

            "how to remove an auditor?",

            "what are the powers of an auditor?",

            "what is casual vacancy?",

            "how to report fraud?",

            "can auditor give consultancy?",

            "what is ADT-3 form?",

            "who appoints auditor in government company?",

            "what is auditor rotation?"

        ],

        "semantic_synonyms": [

            "statutory auditor",

            "external auditor",

            "company auditor",

            "financial auditor",

            "compliance audit",

            "legal audit",

            "corporate audit"

        ],

        "appointment_keywords": [

            "appointing authority for auditors",

            "first auditor appointment",

            "auditor appointment procedure",

            "annual general meeting",

            "AGM",

            "sixth annual general meeting",

            "audit committee constitution",

            "board of directors recommendation",

            "auditor eligibility",

            "auditor qualifications",

            "chartered accountant",

            "CA",

            "audit firm",

            "limited liability partnership",

            "LLP auditor",

            "Section 139(1)",

            "Section 139(5)",

            "Section 139(6)",

            "Section 141",

            "Rule 3",

            "Rule 4"

        ],

        "company_type_keywords": [

            "listed company auditor",

            "unlisted public company",

            "private limited company",

            "government company auditor",

            "government controlled company",

            "holding company",

            "subsidiary company",

            "associate company"

        ],

        "threshold_keywords": [

            "paid up capital ten crore",

            "turnover one hundred crore",

            "outstanding loans fifty crore",

            "borrowings fifty crore",

            "debentures fifty crore",

            "deposits fifty crore",

            "paid up share capital",

            "public borrowings",

            "Rs. 1 lakh",

            "Rs. 5 lakh",

            "Rs. 10 crore",

            "Rs. 20 crore",

            "Rs. 50 crore",

            "Rs. 100 crore"

        ],

        "procedural_keywords": [

            "written consent of auditor",

            "certificate of eligibility",

            "Form ADT-1",

            "Form ADT-2",

            "Form ADT-3",

            "Form ADT-4",

            "notice to registrar",

            "15 days filing",

            "30 days appointment",

            "60 days CAG appointment",

            "90 days member appointment",

            "extraordinary general meeting",

            "EGM",

            "ordinary resolution",

            "special resolution",

            "Board resolution"

        ],

        "authority_keywords": [

            "Comptroller and Auditor General",

            "CAG",

            "CAG appointment",

            "180 days appointment period",

            "Board of Directors",

            "members of company",

            "shareholders",

            "Central Government",

            "Registrar of Companies",

            "ROC",

            "Institute of Chartered Accountants of India",

            "ICAI",

            "National Financial Reporting Authority",

            "NFRA",

            "National Company Law Tribunal",

            "NCLT",

            "Ministry of Corporate Affairs",

            "MCA"

        ],

        "disqualification_keywords": [

            "auditor disqualification",

            "body corporate",

            "officer or employee",

            "partner disqualification",

            "relative holding security",

            "interest in company",

            "security limit one lakh",

            "face value limit",

            "indebtedness five lakh",

            "guarantee one lakh",

            "business relationship",

            "commercial transaction",

            "arm's length price",

            "director relative",

            "key managerial personnel",

            "KMP",

            "full time employment",

            "20 companies limit",

            "fraud conviction",

            "ten years disqualification",

            "consulting services",

            "specialized services",

            "Section 141(3)",

            "Section 141(4)",

            "Rule 10"

        ],

        "relationship_keywords": [

            "relative definition",

            "partner employee",

            "holding company interest",

            "subsidiary interest",

            "associate company interest",

            "third person indebtedness",

            "security provider",

            "guarantee provider"

        ],

        "business_relationship_keywords": [

            "commercial purpose transaction",

            "professional services permitted",

            "Chartered Accountants Act 1949",

            "ordinary course of business",

            "telecommunications business",

            "airlines business",

            "hospitals business",

            "hotels business"

        ],

        "vacancy_keywords": [

            "casual vacancy",

            "vacation of office",

            "deemed vacancy",

            "disqualification after appointment",

            "casual vacancy filling",

            "Board fills vacancy",

            "30 days filling",

            "general meeting approval",

            "three months approval",

            "hold till next AGM",

            "CAG fills vacancy",

            "government company vacancy",

            "Section 139(8)"

        ],

        "tenure_keywords": [

            "auditor term",

            "five consecutive years",

            "one term individual",

            "two terms audit firm",

            "cooling off period",

            "5 years cooling off",

            "three years transition",

            "maximum tenure",

            "consecutive years",

            "Section 139(2)",

            "Rule 5"

        ],

        "rotation_keywords": [

            "rotation of auditors",

            "auditing partner rotation",

            "team rotation",

            "expiry of term",

            "incumbent auditor",

            "incoming auditor",

            "outgoing auditor",

            "network of audit firms",

            "same brand name",

            "trade name",

            "common control",

            "partner retirement",

            "joining another firm",

            "five year ineligibility",

            "Section 139(3)",

            "Section 139(4)",

            "Rule 6"

        ],

        "reappointment_keywords": [

            "retiring auditor",

            "re-appointment",

            "qualified for reappointment",

            "unwillingness to reappoint",

            "special resolution",

            "automatic continuation",

            "no auditor appointed",

            "existing auditor continues",

            "Section 139(9)",

            "Section 139(10)"

        ],

        "joint_auditor_keywords": [

            "joint auditors",

            "two or more auditors",

            "staggered rotation",

            "same year completion"

        ],

        "common_partner_keywords": [

            "common partner restriction",

            "previous audit firm",

            "immediately preceding year",

            "partner restriction"

        ],

        "removal_keywords": [

            "removal of auditor",

            "prior approval central government",

            "Form ADT-2",

            "30 days resolution",

            "special resolution removal",

            "60 days general meeting",

            "reasonable opportunity hearing",

            "before expiry of term",

            "Section 140(1)",

            "Rule 7"

        ],

        "resignation_keywords": [

            "auditor resignation",

            "Form ADT-3",

            "30 days from resignation",

            "reasons for resignation",

            "resignation statement",

            "file with registrar",

            "file with CAG",

            "government company resignation",

            "penalty 50000 to 5 lakh",

            "good faith reporting",

            "Section 140(2)",

            "Section 140(3)",

            "Rule 8"

        ],

        "special_notice_keywords": [

            "special notice requirement",

            "retiring auditor replacement",

            "copy to retiring auditor",

            "auditor representation",

            "written representation",

            "notification to members",

            "reasonable length representation",

            "not received too late",

            "read out representation",

            "Tribunal satisfaction",

            "abuse of rights",

            "Section 140(4)"

        ],

        "tribunal_keywords": [

            "National Company Law Tribunal",

            "NCLT",

            "suo moto action",

            "Central Government application",

            "fraudulent manner",

            "abetted fraud",

            "colluded in fraud",

            "15 days order",

            "5 years ineligibility",

            "Section 447 liability",

            "firm liability",

            "partner liability",

            "Section 140(5)"

        ],

        "powers_keywords": [

            "auditor powers",

            "access to books",

            "access to vouchers",

            "information and explanation",

            "all times access",

            "registered office access",

            "other place access",

            "holding company access",

            "subsidiary books access",

            "consolidation purpose",

            "Section 143(1)"

        ],

        "duties_enquiry_keywords": [

            "auditor duties",

            "loans and advances enquiry",

            "security verification",

            "proper security",

            "not prejudicial to interest",

            "book entry transactions",

            "sale of investments",

            "shares debentures securities",

            "price less than purchase",

            "bona fide sale",

            "deposits verification",

            "loans shown as deposits",

            "personal expenses",

            "revenue account charging",

            "allotment for cash",

            "cash actually received",

            "share allotment verification"

        ],

        "audit_report_keywords": [

            "audit report",

            "report to members",

            "financial statements",

            "accounting standards",

            "auditing standards",

            "true and fair view",

            "state of affairs",

            "profit or loss",

            "cash flow",

            "information obtained",

            "proper books of account",

            "returns from branches",

            "branch audit report",

            "agreement with books",

            "comply with standards",

            "adverse effect observations",

            "director disqualification",

            "Section 164(2)",

            "qualification in report",

            "reservation in report",

            "adverse remark",

            "internal financial controls",

            "operating effectiveness",

            "pending litigations",

            "material foreseeable losses",

            "long term contracts",

            "derivative contracts",

            "Investor Education Protection Fund",

            "IEPF",

            "delay in transfer",

            "Section 143(2)",

            "Section 143(3)",

            "Section 143(4)",

            "Rule 11"

        ],

        "fraud_reporting_keywords": [

            "reporting of frauds",

            "fraud by officers",

            "fraud by employees",

            "60 days reporting",

            "45 days reply",

            "Board reply",

            "Audit Committee reply",

            "15 days forwarding",

            "Central Government reporting",

            "Form ADT-4",

            "registered post",

            "speed post",

            "email confirmation",

            "Ministry of Corporate Affairs",

            "MCA",

            "Cost Accountant fraud",

            "Company Secretary fraud",

            "Section 148 fraud",

            "Section 204 fraud",

            "penalty 1 lakh to 25 lakh",

            "good faith protection",

            "Section 143(12)",

            "Section 143(13)",

            "Section 143(14)",

            "Section 143(15)",

            "Rule 13"

        ],

        "CAG_keywords": [

            "CAG directions",

            "supplementary audit",

            "60 days comment",

            "CAG comments",

            "supplement audit report",

            "Section 136(1)",

            "test audit",

            "Section 19A",

            "Comptroller Auditor General Act 1971",

            "Section 143(5)",

            "Section 143(6)",

            "Section 143(7)"

        ],

        "branch_audit_keywords": [

            "branch audit",

            "branch office accounts",

            "company's auditor",

            "branch auditor",

            "foreign branch",

            "competent person",

            "foreign country laws",

            "branch audit report",

            "deal with report",

            "submit to company auditor",

            "Section 143(8)",

            "Rule 12"

        ],

        "auditing_standards_keywords": [

            "auditing standards",

            "comply with auditing standards",

            "ICAI auditing standards",

            "Central Government notification",

            "NFRA consultation",

            "deemed auditing standards",

            "Section 143(9)",

            "Section 143(10)"

        ],

        "remuneration_keywords": [

            "auditor remuneration",

            "fixed in general meeting",

            "Board fixes remuneration",

            "first auditor remuneration",

            "out of pocket expenses",

            "other service payment",

            "request of company",

            "Section 142"

        ],

        "prohibited_services_keywords": [

            "prohibited services",

            "accounting services",

            "book keeping services",

            "internal audit",

            "financial information system",

            "design and implementation",

            "actuarial services",

            "investment advisory",

            "investment banking",

            "outsourced financial services",

            "management services",

            "Board approval required",

            "Audit Committee approval",

            "holding company services",

            "subsidiary company services",

            "Section 144"

        ],

        "signing_keywords": [

            "signing audit report",

            "auditor signature",

            "qualifications in report",

            "observations on transactions",

            "comments on functioning",

            "adverse effect",

            "read before company",

            "general meeting reading",

            "open to inspection",

            "member inspection",

            "Section 145"

        ],

        "attendance_keywords": [

            "auditor attendance",

            "general meeting notice",

            "attend general meeting",

            "authorised representative",

            "qualified representative",

            "right to be heard",

            "business concerning auditor",

            "Section 146"

        ],

        "cost_audit_keywords": [

            "cost records",

            "cost audit",

            "Cost Accountant",

            "production of goods",

            "providing services",

            "prescribed class of companies",

            "special Act regulation",

            "regulatory body consultation",

            "net worth threshold",

            "turnover threshold",

            "cost audit conduct",

            "manner specified",

            "Section 148",

            "Section 148(1)",

            "Section 148(2)",

            "Rule 3"

        ],

        "cost_auditor_keywords": [

            "Cost Accountant in practice",

            "Board appointment cost auditor",

            "Audit Committee recommendation",

            "remuneration by members",

            "remuneration ratification",

            "shareholders ratification",

            "180 days appointment",

            "financial year commencement",

            "cost audit report",

            "180 days submission",

            "reservations in report",

            "qualifications cost audit",

            "observations cost audit",

            "Section 148(3)",

            "Rule 14",

            "Rule 5"

        ],

        "cost_standards_keywords": [

            "cost auditing standards",

            "Institute of Cost and Works Accountants",

            "ICWA",

            "Cost and Works Accountants Act 1959",

            "Central Government approval"

        ],

        "cost_filing_keywords": [

            "furnish to Central Government",

            "30 days furnishing",

            "full information explanation",

            "further information",

            "specified time compliance"

        ],

        "restriction_keywords": [

            "financial auditor restriction",

            "Section 139 auditor",

            "not cost auditor",

            "same company restriction",

            "additional to Section 143",

            "assistance to cost auditor",

            "facilities to auditor"

        ],

        "company_penalties_keywords": [

            "company punishment",

            "fine 25000 to 500000",

            "officer in default",

            "imprisonment one year",

            "fine 10000 to 100000",

            "contravention Section 139 to 146",

            "Section 147"

        ],

        "auditor_penalties_keywords": [

            "auditor punishment",

            "fine 25000 to 500000",

            "knowingly contravention",

            "willfully contravention",

            "intention to deceive",

            "imprisonment one year",

            "fine 100000 to 2500000",

            "refund remuneration",

            "pay damages",

            "incorrect statements",

            "misleading statements",

            "audit report particulars"

        ],

        "damages_keywords": [

            "damages to company",

            "statutory bodies damages",

            "authorities damages",

            "other persons damages",

            "loss arising",

            "Central Government specify",

            "statutory body payment",

            "prompt payment",

            "notification issuance",

            "report filing"

        ],

        "firm_liability_keywords": [

            "audit firm liability",

            "partner liability",

            "fraudulent act",

            "abetted fraud",

            "colluded fraud",

            "civil liability",

            "criminal liability",

            "joint and several",

            "partner concerned"

        ],

        "legal_framework_keywords": [

            "Companies Act 2013",

            "Companies Audit and Auditors Rules 2014",

            "Companies Meetings of Board Rules 2014",

            "Companies Cost Records Rules 2013",

            "Chartered Accountants Act 1949",

            "Limited Liability Partnership Act 2008",

            "Cost and Works Accountants Act 1959",

            "Comptroller Auditor General Act 1971"

        ],

        "time_period_keywords": [

            "15 days",

            "30 days",

            "45 days",

            "60 days",

            "90 days",

            "180 days",

            "3 months",

            "1 year",

            "5 years",

            "10 years",

            "conclusion of meeting",

            "commencement of financial year",

            "date of incorporation",

            "date of registration"

        ],

        "stakeholder_keywords": [

            "shareholders",

            "members",

            "directors",

            "Board of Directors",

            "Audit Committee",

            "officers",

            "employees",

            "key managerial personnel",

            "creditors"

        ],

        "appointment_synonyms": [

            "appointing",

            "appointment",

            "appoint",

            "nomination",

            "designation",

            "selection"

        ],

        "removal_synonyms": [

            "removal",

            "dismissal",

            "termination",

            "discharge",

            "ouster"

        ],

        "qualification_synonyms": [

            "eligibility",

            "qualification",

            "competence",

            "capability",

            "suitability"

        ],

        "disqualification_synonyms": [

            "ineligibility",

            "disqualification",

            "incompetence",

            "unsuitability",

            "bar"

        ],

        "audit_synonyms": [

            "examination",

            "review",

            "inspection",

            "verification",

            "scrutiny",

            "checking"

        ],

        "report_synonyms": [

            "report",

            "statement",

            "account",

            "disclosure",

            "communication"

        ],

        "company_type_synonyms": [

            "listed company",

            "public limited company",

            "private limited company",

            "government company",

            "government undertaking",

            "PSU",

            "holding company",

            "parent company",

            "subsidiary company",

            "subsidiary undertaking",

            "associate company",

            "associated undertaking"

        ],

        "appointment_context_phrases": [

            "who can appoint auditor",

            "auditor appointment procedure",

            "how to appoint first auditor",

            "AGM auditor appointment",

            "Board appoint auditor",

            "members appoint auditor",

            "CAG appoint auditor",

            "government company auditor appointment"

        ],

        "eligibility_context_phrases": [

            "who can be auditor",

            "auditor qualification requirements",

            "chartered accountant as auditor",

            "CA firm as auditor",

            "LLP as auditor"

        ],

        "disqualification_context_phrases": [

            "who cannot be auditor",

            "auditor disqualification grounds",

            "relative holding shares disqualification",

            "business relationship disqualification",

            "employee cannot be auditor",

            "director relative disqualification"

        ],

        "tenure_context_phrases": [

            "auditor term period",

            "how long auditor serve",

            "maximum tenure of auditor",

            "individual auditor term",

            "firm auditor term",

            "cooling off period"

        ],

        "rotation_context_phrases": [

            "when to rotate auditor",

            "auditor rotation requirement",

            "partner rotation",

            "mandatory rotation",

            "rotation on expiry"

        ],

        "removal_context_phrases": [

            "how to remove auditor",

            "removal before term",

            "central government approval removal",

            "special resolution for removal"

        ],

        "resignation_context_phrases": [

            "auditor resignation procedure",

            "how auditor resign",

            "resignation form",

            "ADT-3 filing"

        ],

        "duties_context_phrases": [

            "auditor duties",

            "auditor responsibilities",

            "what auditor must check",

            "auditor enquiries",

            "verification by auditor"

        ],

        "powers_context_phrases": [

            "auditor powers",

            "auditor rights",

            "access to books",

            "access to information"

        ],

        "report_context_phrases": [

            "audit report contents",

            "what audit report contains",

            "auditor report requirements",

            "qualification in audit report",

            "adverse remarks"

        ],

        "fraud_context_phrases": [

            "fraud reporting by auditor",

            "report fraud to government",

            "fraud reporting procedure",

            "ADT-4 form"

        ],

        "remuneration_context_phrases": [

            "auditor fees",

            "auditor remuneration",

            "how auditor paid",

            "who fixes auditor fees"

        ],

        "prohibited_context_phrases": [

            "services auditor cannot provide",

            "prohibited services",

            "what auditor cannot do",

            "restriction on auditor"

        ],

        "cost_audit_context_phrases": [

            "cost audit requirement",

            "cost auditor appointment",

            "cost records maintenance",

            "when cost audit required"

        ],

        "penalty_context_phrases": [

            "auditor penalty",

            "punishment for non-compliance",

            "fine for violation",

            "imprisonment for auditor"

        ],

        "monetary_limits": [

            "Rs. 10,000",

            "Rs. 25,000",

            "Rs. 50,000",

            "Rs. 1,00,000",

            "Rs. 5,00,000",

            "Rs. 25,00,000",

            "one lakh rupees",

            "five lakh rupees",

            "ten crore rupees",

            "twenty crore rupees",

            "fifty crore rupees",

            "hundred crore rupees"

        ],

        "quantity_limits": [

            "20 companies",

            "sixth AGM",

            "first AGM",

            "one term",

            "two terms"

        ]

    }

}

ACCOUNTING_KEYWORDS = {

    "primary_keywords": [

        "Indian Accounting Standards",

        "Ind AS",

        "Accounting Standards Board",

        "ASB",

        "Institute of Chartered Accountants of India",

        "ICAI",

        "International Financial Reporting Standards",

        "IFRS",

        "International Accounting Standards",

        "IAS",

        "International Accounting Standards Board",

        "IASB",

        "International Accounting Standards Committee",

        "IASC",

        "Convergence with IFRS",

        "IFRS convergence",

        "Ministry of Corporate Affairs",

        "MCA",

        "National Advisory Committee on Accounting Standards",

        "NACAS"

    ],

    "conceptual_keywords": [

        "accounting principles",

        "accounting policies",

        "financial reporting standards",

        "accounting framework",

        "standard setting process",

        "accounting harmonization",

        "global accounting standards",

        "accounting regulation"

    ],

    "benefits_objectives": [

        "uniformity in accounting",

        "comparability of financial statements",

        "reliability of financial information",

        "transparency in reporting",

        "fraud prevention",

        "inter-firm comparison",

        "intra-firm comparison",

        "consistency in accounting methods"

    ],

    "challenges": [

        "IFRS implementation challenges",

        "fair value measurement",

        "historical cost accounting",

        "training requirements",

        "legal framework amendments",

        "IT infrastructure requirements",

        "SME applicability",

        "cost-benefit analysis"

    ],

    "standards": [

        "Ind AS 101",

        "Ind AS 102",

        "Ind AS 103",

        "Ind AS 104",

        "Ind AS 105",

        "Ind AS 106",

        "Ind AS 107",

        "Ind AS 108",

        "Ind AS 109",

        "Ind AS 110",

        "Ind AS 111",

        "Ind AS 112",

        "Ind AS 113",

        "Ind AS 114",

        "Ind AS 115",

        "Ind AS 116",

        "Ind AS 1",

        "Ind AS 2",

        "Ind AS 7",

        "Ind AS 8",

        "Ind AS 10",

        "Ind AS 12",

        "Ind AS 16",

        "Ind AS 19",

        "Ind AS 20",

        "Ind AS 21",

        "Ind AS 23",

        "Ind AS 24",

        "Ind AS 27",

        "Ind AS 28",

        "Ind AS 29",

        "Ind AS 32",

        "Ind AS 33",

        "Ind AS 34",

        "Ind AS 36",

        "Ind AS 37",

        "Ind AS 38",

        "Ind AS 40",

        "Ind AS 41",

        "IAS 1",

        "IAS 2",

        "IAS 7",

        "IAS 8",

        "IAS 10",

        "IAS 12",

        "IAS 16",

        "IAS 19",

        "IAS 20",

        "IAS 21",

        "IAS 23",

        "IAS 24",

        "IAS 27",

        "IAS 28",

        "IAS 29",

        "IAS 32",

        "IAS 33",

        "IAS 34",

        "IAS 36",

        "IAS 37",

        "IAS 38",

        "IAS 40",

        "IAS 41",

        "IFRS 1",

        "IFRS 2",

        "IFRS 3",

        "IFRS 4",

        "IFRS 5",

        "IFRS 6",

        "IFRS 7",

        "IFRS 8",

        "IFRS 9",

        "IFRS 10",

        "IFRS 11",

        "IFRS 12",

        "IFRS 13",

        "IFRS 14",

        "IFRS 15",

        "IFRS 16"

    ],

    "ppe_keywords": [

        "Property Plant Equipment",

        "PPE",

        "tangible assets",

        "fixed assets",

        "capital assets",

        "depreciable assets",

        "non-depreciable assets",

        "land",

        "bearer plants",

        "buildings",

        "plant and machinery",

        "furniture and fixtures",

        "vehicles",

        "office equipment",

        "initial measurement",

        "subsequent measurement",

        "cost model",

        "revaluation model",

        "carrying amount",

        "fair value",

        "historical cost",

        "depreciation",

        "accumulated depreciation",

        "residual value",

        "useful life",

        "depreciable amount",

        "asset recognition criteria",

        "future economic benefits",

        "reliable measurement",

        "component approach",

        "spare parts capitalization",

        "major inspections",

        "purchase of assets",

        "self-constructed assets",

        "exchange of assets",

        "business combination acquisition",

        "directly attributable costs",

        "borrowing costs capitalization",

        "site preparation costs",

        "installation costs",

        "dismantling costs",

        "professional fees",

        "revaluation surplus",

        "revaluation reserve",

        "impairment loss",

        "upward revaluation",

        "downward revaluation",

        "revaluation frequency",

        "derecognition",

        "disposal gains",

        "disposal losses",

        "carrying value at disposal"

    ],

    "intangible_assets": [

        "intangible assets",

        "identifiable assets",

        "non-monetary assets",

        "non-physical assets",

        "goodwill",

        "patents",

        "copyrights",

        "trademarks",

        "computer software",

        "licenses",

        "franchises",

        "customer lists",

        "mining rights",

        "fishing rights",

        "brand names",

        "mastheads",

        "publishing titles",

        "identifiability criterion",

        "control over asset",

        "future economic benefits",

        "reliable cost measurement",

        "research phase",

        "development phase",

        "amortization",

        "amortisation",

        "indefinite useful life",

        "finite useful life",

        "amortization period",

        "amortization method",

        "straight-line amortization",

        "separate acquisition",

        "business combination acquisition",

        "internally generated intangibles",

        "government grant acquisition",

        "exchange acquisition",

        "internally generated goodwill",

        "research costs expensing",

        "start-up costs",

        "training costs",

        "advertising costs",

        "relocation costs"

    ],

    "impairment": [

        "impairment of assets",

        "impairment loss",

        "recoverable amount",

        "carrying amount excess",

        "fair value less costs of disposal",

        "value in use",

        "higher of fair value or value in use",

        "present value of cash flows",

        "discount rate",

        "cash flow projections",

        "impairment indicators",

        "external indicators",

        "internal indicators",

        "market value decline",

        "technological obsolescence",

        "economic performance decline",

        "physical damage",

        "cash generating units",

        "CGU",

        "corporate assets",

        "goodwill impairment",

        "annual impairment testing",

        "reversal of impairment",

        "impairment allocation",

        "cost less depreciation",

        "cost less amortization",

        "impairment loss adjustment"

    ],

    "inventories": [

        "inventories",

        "stock valuation",

        "inventory measurement",

        "raw materials",

        "work-in-progress",

        "WIP",

        "finished goods",

        "stock-in-trade",

        "stores and spares",

        "loose tools",

        "goods-in-transit",

        "consumables",

        "lower of cost and NRV",

        "net realizable value",

        "net realisable value",

        "NRV",

        "cost of inventories",

        "cost formulas",

        "FIFO",

        "first in first out",

        "weighted average method",

        "specific identification",

        "purchase costs",

        "conversion costs",

        "other costs",

        "cost of purchase",

        "cost of conversion",

        "import duties",

        "non-refundable taxes",

        "freight inward",

        "handling costs",

        "fixed production overheads",

        "variable production overheads",

        "normal capacity",

        "actual production capacity",

        "overhead allocation",

        "abnormal wastage",

        "abnormal waste",

        "storage costs",

        "administrative overheads",

        "selling costs",

        "start-up costs",

        "joint products",

        "by-products",

        "service provider inventories",

        "agricultural produce",

        "commodity broker-traders",

        "net realizable value determination"

    ],

    "borrowing_costs": [

        "borrowing costs",

        "capitalization of borrowing costs",

        "finance costs",

        "interest costs",

        "interest on bank overdraft",

        "interest on loans",

        "interest on debentures",

        "amortization of discounts",

        "amortization of premiums",

        "ancillary costs",

        "finance charges on leases",

        "exchange differences",

        "assets requiring substantial time",

        "manufacturing plants",

        "power generation facilities",

        "investment properties",

        "intangible assets under development",

        "bearer plants",

        "qualifying assets",

        "commencement of capitalization",

        "cessation of capitalization",

        "suspension of capitalization",

        "capitalization period",

        "eligible borrowing costs",

        "specific borrowings",

        "general borrowings",

        "weighted average rate",

        "capitalization rate",

        "actual borrowing costs",

        "investment income deduction",

        "temporary investment income",

        "non-qualifying assets",

        "routine production inventories",

        "assets ready for use",

        "financial assets"

    ],

    "investment_property": [

        "investment property",

        "rental income property",

        "capital appreciation property",

        "owner-occupied property",

        "land held for appreciation",

        "buildings leased out",

        "property under construction",

        "vacant property held for leasing",

        "cost model",

        "fair value model",

        "initial measurement at cost",

        "subsequent measurement",

        "recognition criteria",

        "derecognition",

        "disposal",

        "transfer criteria",

        "transfer to owner-occupied",

        "transfer from owner-occupied",

        "transfer to inventory",

        "transfer from inventory",

        "transfer to PPE",

        "transfer from PPE",

        "change in use",

        "commencement of owner-occupation",

        "commencement of development for sale",

        "end of owner-occupation",

        "start of operating lease"

    ],

    "provisions": [

        "provisions",

        "contingent liabilities",

        "contingent assets",

        "present obligations",

        "legal obligations",

        "constructive obligations",

        "obligating event",

        "probable outflow",

        "reliable estimate",

        "past event",

        "present obligation",

        "best estimate",

        "expected value method",

        "most likely amount method",

        "present value",

        "discount rate",

        "future events consideration",

        "onerous contracts",

        "restructuring provisions",

        "future operating losses",

        "warranties",

        "decommissioning obligations",

        "environmental provisions",

        "legal claims",

        "tax disputes",

        "reimbursement rights",

        "virtual certainty",

        "separate asset recognition",

        "provision review",

        "provision reversal",

        "use of provisions",

        "provision adjustments"

    ],

    "employee_benefits": [

        "employee benefits",

        "post-employment benefits",

        "termination benefits",

        "short-term benefits",

        "long-term benefits",

        "wages and salaries",

        "social security contributions",

        "paid annual leave",

        "paid sick leave",

        "profit sharing",

        "bonuses",

        "non-monetary benefits",

        "compensated absences",

        "accumulating benefits",

        "non-accumulating benefits",

        "vested benefits",

        "non-vested benefits",

        "defined contribution plans",

        "defined benefit plans",

        "pension plans",

        "gratuity",

        "post-employment medical care",

        "provident fund",

        "PF",

        "employee state insurance",

        "ESI",

        "fixed contributions",

        "no further obligation",

        "actuarial risk transfer",

        "investment risk transfer",

        "actuarial assumptions",

        "discount rate",

        "salary growth rate",

        "mortality rates",

        "current service cost",

        "past service cost",

        "interest cost",

        "plan assets",

        "funded status",

        "actuarial gains",

        "actuarial losses",

        "defined benefit obligation",

        "DBO",

        "expected return on plan assets",

        "re-measurements",

        "net interest approach",

        "long-service leave",

        "sabbatical leave",

        "deferred compensation",

        "long-term disability benefits",

        "redundancy payments",

        "early retirement benefits",

        "voluntary redundancy",

        "expense recognition",

        "liability recognition",

        "asset ceiling",

        "contribution to employees",

        "employer contribution"

    ],

    "revenue_recognition": [

        "revenue recognition",

        "revenue from contracts",

        "contract with customers",

        "five-step model",

        "performance obligations",

        "contract",

        "customer",

        "revenue",

        "income",

        "transaction price",

        "contract asset",

        "contract liability",

        "performance obligation",

        "stand-alone selling price",

        "identify the contract",

        "identify performance obligations",

        "determine transaction price",

        "allocate transaction price",

        "recognize revenue",

        "contract approval",

        "rights identification",

        "payment terms",

        "commercial substance",

        "collectability assessment",

        "enforceable rights",

        "contract term",

        "contract combination",

        "contract modification",

        "distinct goods",

        "distinct services",

        "separately identifiable",

        "capable of being distinct",

        "bundle of goods and services",

        "series of goods and services",

        "fixed consideration",

        "variable consideration",

        "expected value method",

        "most likely amount method",

        "constraint on variable consideration",

        "significant financing component",

        "non-cash consideration",

        "consideration payable to customer",

        "time value of money",

        "relative stand-alone selling price",

        "adjusted market assessment",

        "expected cost plus margin",

        "residual approach",

        "allocation of discounts",

        "allocation of variable consideration",

        "over time recognition",

        "point in time recognition",

        "transfer of control",

        "customer acceptance",

        "performance satisfaction",

        "output methods",

        "input methods",

        "progress measurement",

        "incremental costs",

        "costs to fulfill",

        "capitalization",

        "amortization",

        "impairment",

        "contract assets",

        "receivables",

        "contract liabilities",

        "deferred revenue",

        "advances from customers",

        "principal vs agent",

        "warranties",

        "customer options",

        "material rights",

        "non-refundable upfront fees",

        "licensing arrangements",

        "repurchase agreements",

        "consignment arrangements",

        "bill-and-hold arrangements"

    ],

    "financial_statements": [

        "financial statements",

        "general purpose financial statements",

        "fair presentation",

        "going concern",

        "accrual basis",

        "materiality and aggregation",

        "offsetting",

        "comparative information",

        "Statement of Financial Position",

        "SOFP",

        "Balance Sheet",

        "Statement of Profit and Loss",

        "SOPL",

        "Income Statement",

        "Statement of Changes in Equity",

        "SOCE",

        "Statement of Cash Flows",

        "SOCF",

        "notes to financial statements",

        "accounting policies note",

        "assets",

        "liabilities",

        "equity",

        "current assets",

        "non-current assets",

        "current liabilities",

        "non-current liabilities",

        "property plant and equipment",

        "investment property",

        "intangible assets",

        "goodwill",

        "financial assets",

        "investments",

        "trade receivables",

        "inventories",

        "cash and cash equivalents",

        "bank balances",

        "loans and advances",

        "other current assets",

        "other non-current assets",

        "deferred tax assets",

        "capital work-in-progress",

        "biological assets",

        "assets held for sale",

        "borrowings",

        "trade payables",

        "other financial liabilities",

        "provisions",

        "deferred tax liabilities",

        "current tax liabilities",

        "other current liabilities",

        "other non-current liabilities",

        "share capital",

        "equity share capital",

        "preference share capital",

        "share application money",

        "other equity",

        "reserves and surplus",

        "retained earnings",

        "securities premium",

        "capital reserve",

        "capital redemption reserve",

        "debenture redemption reserve",

        "revaluation surplus",

        "share options outstanding",

        "other comprehensive income",

        "OCI",

        "non-controlling interest",

        "revenue from operations",

        "other income",

        "total income",

        "expenses",

        "cost of materials consumed",

        "purchase of stock-in-trade",

        "changes in inventories",

        "employee benefit expenses",

        "finance costs",

        "depreciation and amortization",

        "other expenses",

        "profit before tax",

        "tax expense",

        "current tax",

        "deferred tax",

        "profit for the period",

        "earnings per share",

        "EPS",

        "basic EPS",

        "diluted EPS",

        "items not reclassified to P&L",

        "items reclassified to P&L",

        "revaluation surplus",

        "re-measurements of defined benefit plans",

        "equity instruments through OCI",

        "debt instruments through OCI",

        "foreign currency translation reserve",

        "cash flow hedges",

        "effective portion of hedges",

        "fair value changes",

        "opening balance",

        "changes in accounting policy",

        "prior period errors",

        "restated balance",

        "total comprehensive income",

        "dividends",

        "issue of shares",

        "share-based payments",

        "transfer to reserves",

        "closing balance",

        "consistency of presentation",

        "current non-current distinction",

        "operating cycle",

        "liquidity presentation",

        "minimum line items",

        "additional line items",

        "subtotals",

        "structure and content",

        "basis of preparation",

        "significant accounting policies",

        "judgments and estimates",

        "sources of estimation uncertainty",

        "capital management",

        "financial risk management",

        "fair value disclosures",

        "related party disclosures",

        "segment information",

        "contingent liabilities",

        "commitments",

        "events after reporting period"

    ],

    "cross_cutting": [

        "conceptual framework",

        "recognition criteria",

        "measurement bases",

        "derecognition",

        "initial recognition",

        "subsequent recognition",

        "initial measurement",

        "subsequent measurement",

        "historical cost",

        "current cost",

        "realizable value",

        "present value",

        "fair value",

        "fair value hierarchy",

        "level 1 inputs",

        "level 2 inputs",

        "level 3 inputs",

        "entity-specific value",

        "market value",

        "replacement cost",

        "net realizable value",

        "economic substance",

        "legal form",

        "arms length transaction",

        "market participants",

        "active market",

        "observable inputs",

        "unobservable inputs",

        "relevance",

        "faithful representation",

        "comparability",

        "verifiability",

        "timeliness",

        "understandability",

        "completeness",

        "neutrality",

        "free from error",

        "predictive value",

        "confirmatory value",

        "materiality",

        "assets",

        "liabilities",

        "equity",

        "income",

        "expenses",

        "gains",

        "losses",

        "contributions from owners",

        "distributions to owners",

        "probable future economic benefits",

        "reliable measurement",

        "control over resources",

        "past transaction or event",

        "enforceable rights",

        "present obligation",

        "changes in accounting policies",

        "changes in estimates",

        "error corrections",

        "retrospective application",

        "retrospective restatement",

        "prospective application",

        "consistency in policies",

        "selection of policies",

        "accounting policy disclosure",

        "judgment disclosure",

        "estimate disclosure",

        "risk disclosure",

        "sensitivity analysis",

        "maturity analysis",

        "reconciliation requirements",

        "comparative information",

        "additional voluntary disclosures",

        "reporting period",

        "reporting entity",

        "reporting currency",

        "functional currency",

        "presentation currency",

        "rounding conventions",

        "going concern assessment",

        "true and fair view",

        "business combinations",

        "related party transactions",

        "discontinued operations",

        "assets held for sale",

        "foreign currency transactions",

        "foreign operations",

        "hyperinflationary economies",

        "interim reporting",

        "segment reporting",

        "current tax",

        "deferred tax",

        "deferred tax assets",

        "deferred tax liabilities",

        "tax base",

        "temporary differences",

        "taxable temporary differences",

        "deductible temporary differences",

        "tax loss carryforwards",

        "tax credit carryforwards",

        "effective tax rate",

        "tax reconciliation",

        "consolidated financial statements",

        "separate financial statements",

        "parent company",

        "subsidiary",

        "associate",

        "joint venture",

        "joint operation",

        "structured entities",

        "control",

        "significant influence",

        "joint control",

        "non-controlling interest",

        "acquisition method",

        "goodwill on consolidation"

    ],

    "calculation_keywords": [

        "computation",

        "calculation",

        "formula",

        "method",

        "approach",

        "rate",

        "percentage",

        "factor",

        "ratio",

        "calculate depreciation",

        "compute borrowing costs",

        "determine impairment",

        "recognize revenue",

        "prepare financial statements",

        "account for employee benefits",

        "measure inventory",

        "assess contingent liability",

        "treatment of",

        "accounting for",

        "recognition criteria for",

        "measurement of",

        "disclosure requirements for",

        "journal entries for",

        "presentation in financial statements",

        "classification of",

        "problem",

        "example",

        "illustration",

        "case study",

        "solved example",

        "journal entry",

        "ledger posting",

        "financial statement preparation",

        "note preparation",

        "working notes"

    ]

}

# TDS Data Analysis Toolkit Keywords
TDS_DATA_ANALYSIS_TOOLKIT_KEYWORDS = {
    "document_metadata": {
        "primary_keywords": [
            "TDS compliance toolkit", "data analytics", "tax administration",
            "voluntary compliance", "revenue realization", "risk-based analytics",
            "fraud detection", "non-compliance detection", "tax evasion",
            "data-driven approach", "structured framework", "risk detection"
        ],
        "platform_keywords": [
            "TRACES platform", "Insight portal", "Insight BI", "Insight Profile",
            "OLTAS", "e-filing portal", "AIS", "Form 26AS", "GSTN portal"
        ],
        "capability_keywords": [
            "Excel skills", "Python skills", "data cleaning", "pivot tables",
            "analytical techniques", "case identification", "case analysis",
            "case verification", "case documentation"
        ]
    },
    "key_competencies_excel": {
        "data_preparation_keywords": [
            "data cleaning", "TRIM function", "CLEAN function", "text parsing",
            "LEFT function", "MID function", "LEN function", "VALUE function",
            "text to columns", "cell formatting", "paste special", "merged cells"
        ],
        "data_manipulation_keywords": [
            "find and replace", "sort and filter", "table format", "headers",
            "SUM function", "AVERAGE function", "COUNT function", "COUNTA function",
            "COUNTIF function", "SUMIF function", "COUNTIFS function", "SUMIFS function"
        ],
        "advanced_excel_keywords": [
            "UNIQUE function", "FILTER function", "SORT function", "SORTBY function",
            "pivot table", "conditional formatting", "IF function", "AND function",
            "IFERROR function", "VLOOKUP", "INDEX-MATCH", "XLOOKUP",
            "CONCAT function", "SEARCH function", "FIND function"
        ]
    },
    "key_competencies_python": {
        "basic_python_keywords": [
            "print output", "variable declaration", "user input", "type conversion",
            "int conversion", "float conversion", "str conversion", "input validation"
        ],
        "control_flow_keywords": [
            "conditional statements", "if-elif-else", "for loop", "while loop",
            "range function", "indefinite repetition", "branching logic"
        ],
        "data_structures_keywords": [
            "lists", "arrays", "indexing", "ordered collection", "mutable data",
            "list operations"
        ],
        "advanced_python_keywords": [
            "functions", "return statement", "modularity", "reusability",
            "error handling", "try-except blocks", "ValueError exception",
            "file reading", "readlines function", "file handling", "with statement"
        ]
    },
    "traces_data_sources": {
        "primary_keywords": [
            "Data Source 1", "top deductors year wise", "year-wise comparison",
            "Data Source 2", "nature of payment wise", "payment categorization",
            "Data Source 4", "TAN non-filer MIS", "non-filing detection",
            "Data Source 8", "TDS defaults list", "defaulter monitoring",
            "Data Source 9", "correction statement MIS", "correction tracking",
            "Data Source 10", "prosecution list", "prosecution cases"
        ],
        "access_keywords": [
            "TRACES portal login", "MIS reports", "business intelligence reports",
            "top deductors report", "financial year filter", "CCA filter",
            "CCIT filter", "CIT filter", "Range filter", "AO filter",
            "nature of payment filter", "category of deductor filter",
            "download utility", "excel export"
        ],
        "field_keywords": [
            "TAN details", "deductor name", "deductor address", "TDS deposited",
            "TCS deposited", "growth rate", "bifurcation", "filing date",
            "delay in filing", "tax deposited amount", "quarter selection",
            "form type", "address details", "latest statement filed"
        ]
    },
    "insight_bi_data_sources": {
        "primary_keywords": [
            "Data Source 3", "TDS collection monitoring", "YTD monitoring",
            "Data Source 5", "non-filer monitoring", "P&L expense analysis",
            "Data Source 6", "transaction value monitoring", "value gap detection",
            "Data Source 7", "audit non-compliance", "Form 3CD analysis"
        ],
        "report_types": [
            "Form 24Q non-filer", "PAN level monitoring", "TAN level monitoring",
            "Form 26Q non-filer", "Form 27EQ non-filer", "audit report based",
            "expense based detection", "transaction value gap", "compliance gap"
        ],
        "filter_keywords": [
            "jurisdiction filter", "major head", "minor head", "payment type",
            "section code filter", "deductor type", "business sector",
            "collection details", "FY selection", "charge selection"
        ],
        "data_fields": [
            "deductor type", "PAN details", "business sector", "ITR sector",
            "collection YTD", "P&L expenses", "audit report data", "Form 3CD fields",
            "substantial expenses", "value mismatch", "non-compliance flag"
        ]
    },
    "insight_profile_data_sources": {
        "primary_keywords": [
            "Data Source 11", "related TANs", "TAN linkage", "master profile",
            "Data Source 12", "aggregated TDS payments", "annual summary",
            "Data Source 13", "aggregated GST transactions", "GSTR-1 data"
        ],
        "profile_access_keywords": [
            "deductor profile view", "tax profile view", "PAN entry",
            "TAN entry", "master profile DMP", "key info section",
            "key person details", "attributes section", "return profile",
            "annual summary TAS", "information tab"
        ],
        "aggregated_data_fields": [
            "information code", "information description", "party PAN",
            "party name", "taxpayer type", "last ITR filed", "nature of business",
            "turnover range", "income range", "primary relationship",
            "transaction count", "amount paid/credited", "TDS amount", "TCS amount",
            "transaction value", "GSTR-1 value", "deductee details"
        ],
        "related_tan_fields": [
            "TAN name", "TAN jurisdiction", "TAN status", "TAN allotment date",
            "deductor category", "deductor sub-category", "address details",
            "email ID", "contact number", "person associated", "years in operation",
            "pincode"
        ]
    },
    "case_identification_methods": {
        "method_1_collection_gap": {
            "primary_keywords": [
                "top deductor analysis", "collection gap analysis", "year-wise comparison",
                "growth rate estimation", "expected rate of change", "actual vs estimated",
                "collection shortfall", "revenue leakage"
            ],
            "process_keywords": [
                "download top deductor list", "determine expected rate", "estimate collection",
                "calculate gap", "categorize deductor", "risk categorization",
                "priority assignment", "P1 priority", "P2 priority", "P3 priority"
            ],
            "category_keywords": [
                "Category A", "very low risk", "Category C", "medium risk",
                "Category E", "very high risk", "analysis pending", "workload consideration"
            ],
            "formula_keywords": [
                "estimated TDS collection", "previous year collection", "rate of change",
                "collection gap formula", "actual minus estimated"
            ]
        },
        "method_2_thematic_analysis": {
            "salary_perquisites_keywords": [
                "Method 2A", "Section 192 analysis", "salary TDS", "perquisite detection",
                "employee benefits", "compensation structure", "payroll analysis",
                "salary growth trend", "no TDS on salary", "lower salary TDS"
            ],
            "benefits_perquisites_keywords": [
                "Method 2B", "Section 194R analysis", "business benefits", "dealer incentives",
                "promotional schemes", "sectoral analysis", "high-risk sectors",
                "benchmark TDS ratio", "194R ratio calculation"
            ],
            "sector_specific_keywords": [
                "alcoholic beverages sector", "financial services sector", "FMCG sector",
                "IT hardware sector", "manufacturing sector", "pharma sector",
                "real estate sector", "wholesale retail sector", "free samples",
                "conference sponsorship", "travel packages", "gold coins", "electronics gifts",
                "channel partner rewards", "loyalty schemes", "dealer conference"
            ],
            "other_sections_keywords": [
                "Method 2C", "section-specific analysis", "third-party information",
                "open source verification", "benchmark computation", "sectoral ratio",
                "statistical analysis", "average median maximum"
            ]
        },
        "method_3_non_filer": {
            "primary_keywords": [
                "non-filer analysis", "stop-filer detection", "filing behavior",
                "financial distress signal", "default intent", "liquidation proceedings",
                "NCLT cases", "repeat defaulters"
            ],
            "identification_keywords": [
                "TRACES non-filer list", "Insight BI non-filer", "high-risk selection",
                "large TDS amounts", "P&L expense substantial", "audit report amounts",
                "CPGRAMS complaints", "sector-based risk", "consolidated list"
            ]
        },
        "method_4_transaction_value": {
            "primary_keywords": [
                "transaction value gap", "TDS statement value", "P&L account value",
                "audit report value", "Form 3CD comparison", "substantial gap",
                "value mismatch", "under-reporting detection"
            ],
            "download_keywords": [
                "transaction value monitoring MIS", "Insight BI download",
                "gap identification", "high-risk selection", "value reconciliation"
            ]
        },
        "method_5_correction_statement": {
            "primary_keywords": [
                "correction statement analysis", "misuse detection", "data manipulation",
                "red flag indicators", "substantial delay", "TDS default reduction",
                "transaction amount reduction", "government deductor correction",
                "unconsumed challan usage", "fraudulent refund", "chain corrections"
            ]
        },
        "method_6_government_deductor": {
            "primary_keywords": [
                "government deductor analysis", "AIN monitoring", "special TAN",
                "24G reconciliation", "BIN analysis", "unclaimed BIN", "AG reconciliation",
                "PAO monitoring", "DDO compliance", "government expenditure risk"
            ],
            "process_keywords": [
                "Form 24G comparison", "OLTAS payment", "BIN linkage", "delayed filing",
                "incorrect mapping", "thematic government analysis", "budgeted expenditure",
                "department-wise analysis", "sector-wise data", "nodal officer engagement"
            ],
            "output_keywords": [
                "reconciliation summary", "BIN utilization report", "expenditure compliance matrix",
                "match mismatch report", "claimed unclaimed BINs", "quarterly reconciliation"
            ]
        },
        "method_7_default_analysis": {
            "primary_keywords": [
                "TDS default analysis", "demand reduction", "demand collection",
                "unconsumed challan tagging", "manual demand", "compounding fees",
                "short payment demand", "net total demand", "active deductors",
                "recent FY defaults"
            ],
            "scenario_keywords": [
                "high unconsumed challan", "total demand equal", "wrong TDS credit",
                "priority assignment", "recovery potential", "tagging potential"
            ]
        },
        "method_8_prosecution": {
            "primary_keywords": [
                "prosecution data analysis", "flagged deductors", "multiple year defaults",
                "prosecution prioritization", "repeated defaulters", "prosecution history",
                "AO interface", "prosecution module", "combine default data"
            ]
        },
        "method_9_other_sources": {
            "grievance_keywords": [
                "E-Nivaran", "CPGRAMS", "TEP analysis", "tax evasion petition",
                "complaint filtering", "TDS issues", "non-filing complaints",
                "wrong PAN TAN", "Form 26AS mismatch", "short deduction complaint"
            ],
            "tep_keywords": [
                "investigation charge", "assessment charge", "non-deduction allegation",
                "under-reporting allegation", "incorrect PAN", "TDS rate verification"
            ],
            "insight_hrr_keywords": [
                "HRR case packet", "suspicious refund", "false TDS entries",
                "fabricated Form 16", "fabricated Form 16A", "refund claim verification"
            ],
            "nclt_keywords": [
                "NCLT database", "sick unit", "MCA database", "ROC database",
                "insolvency proceedings", "TDS during insolvency", "default during liquidation"
            ],
            "disallowance_keywords": [
                "Section 40(a)(ia)", "assessment order reference", "disallowance pattern",
                "across years pattern", "compliance profile"
            ],
            "ldc_keywords": [
                "lower deduction certificate", "LDC deductor risk", "LDC deductee risk",
                "TDS forgone analysis", "197 certificate", "self-assessment tax",
                "deductor-deductee relationship", "sector-wise LDC comparison",
                "certificate validity", "certificate usage", "historical LDC pattern"
            ]
        }
    },
    "case_analysis_methods": {
        "method_1_expense_gap": {
            "primary_keywords": [
                "expense gap analysis", "ITR comparison", "aggregated TDS statements",
                "P&L account extraction", "expense categorization", "section mapping",
                "mismatch calculation", "insufficient TDS", "missing TDS"
            ],
            "itr_field_mapping": [
                "manufacturing account", "trading account", "P&L account",
                "indirect wages", "compensation to employees", "salaries and wages",
                "bonus payment", "medical reimbursement", "leave encashment",
                "LTA benefit", "provident fund contribution", "other employee benefit",
                "medical insurance", "life insurance", "welfare expenses",
                "guest house expenses", "club expenses"
            ],
            "expense_categories": [
                "purchases net", "rent expense", "profit on conversion", "freight outward",
                "stores and spares", "repairs to building", "repairs to machinery",
                "entertainment", "hospitality", "conference expense", "sales promotion",
                "advertisement", "commission payment", "royalty payment",
                "professional fees", "consultancy fees", "technical fees",
                "hotel boarding lodging", "traveling expenses", "foreign travel",
                "conveyance", "festival celebration", "scholarship", "gift expense",
                "donation", "audit fee", "other expenses", "interest paid",
                "proposed dividend", "interim dividend", "direct wages",
                "carriage inward", "other direct expenses", "factory rent",
                "factory general expenses"
            ],
            "tds_mapping": [
                "Section 192 mapping", "Section 194Q mapping", "Section 194IB mapping",
                "Section 194IC mapping", "Section 194C mapping", "Section 194I mapping",
                "Section 194R mapping", "Section 194H mapping", "Section 194G mapping",
                "Section 194J mapping", "Section 194A mapping", "Section 194 mapping",
                "Section 195 mapping"
            ],
            "output_format": [
                "expense category", "expense value", "corresponding section",
                "amount in TDS statement", "gap calculation", "VaR estimation"
            ]
        },
        "method_2_classification": {
            "primary_keywords": [
                "TDS classification analysis", "misclassification detection",
                "lower rate application", "nature of payment", "nature of business",
                "business activity correlation", "transaction nature mismatch"
            ],
            "mismatch_scenarios": [
                "194C for professional", "194Q for manufacturing", "contract vs professional",
                "purchase vs contract", "profession mismatch", "manufacturing mismatch",
                "automated flagging", "Python automation", "high-risk transaction"
            ]
        },
        "method_3_gst_tds_gap": {
            "primary_keywords": [
                "GST-TDS gap analysis", "GSTR-1 comparison", "aggregated GST data",
                "aggregated TDS data", "party-wise summary", "vendor matching",
                "PAN matching", "name matching", "large-value transactions",
                "service provider verification"
            ],
            "gap_scenarios": [
                "GST exists TDS missing", "TDS on lower amount", "significantly lower TDS",
                "gap calculation", "estimated TDS rate", "rate from other transactions",
                "nature-based rate", "VaR computation"
            ]
        },
        "method_4_sectoral_ratio": {
            "primary_keywords": [
                "sectoral transactional analysis", "transactional ratio", "section-wise ratio",
                "expense share calculation", "sector comparison", "benchmark ratio",
                "industry profile", "comparable entities", "similar size comparison",
                "employee strength comparison"
            ],
            "ratio_formula": [
                "transaction amount specific section", "total transaction amount",
                "ratio calculation", "share of expense", "salary expense share",
                "professional fee share", "lower ratio detection", "under-reporting indicator",
                "normalized pattern", "size-independent comparison"
            ]
        },
        "method_5_residential_house": {
            "primary_keywords": [
                "residential house analysis", "accommodation perquisite", "housing benefit",
                "owned property", "leased property", "asset profile", "third-party information",
                "public database", "Form 24Q review", "salary breakup", "rent-free accommodation",
                "concessional housing", "Rule 3 valuation", "perquisite value", "undervaluation detection"
            ]
        },
        "method_6_compliance_behavior": {
            "primary_keywords": [
                "compliance behavior analysis", "collection analysis", "default patterns",
                "correction pattern", "prosecution history", "unconsumed challan behavior",
                "LDC usage pattern", "TEP analysis", "audit findings behavior",
                "risk categorization", "compliant deductor", "occasionally non-compliant",
                "persistently non-compliant", "high-risk watchlist", "behavioral trends",
                "isolated defaults vs patterns"
            ]
        },
        "method_7_open_source": {
            "primary_keywords": [
                "open-source analysis", "public domain information", "news articles",
                "company websites", "press releases", "MCA portal", "GST portal",
                "GeM portal", "LinkedIn", "Crunchbase", "social platform",
                "business platform", "financial context", "tax context",
                "internal data correlation", "red flag identification",
                "verified public data", "transparency accountability"
            ]
        }
    },
    "verification_issues": {
        "issue_1_tds_payments": {
            "keywords": [
                "Issue 1A", "no TDS payments", "no TCS payments", "unusual non-reporting",
                "business operation scale", "no liability explanation",
                "Issue 1B", "lower growth TDS", "lower growth TCS", "stagnant growth",
                "commensurate growth", "business volume", "turnover increase",
                "transaction value", "outsourcing arrangements", "reporting practice changes"
            ]
        },
        "issue_2_filing": {
            "keywords": [
                "Issue 2A", "non-filing statements", "quarterly non-filing", "Rule 31A",
                "mandatory filing", "nil deduction filing", "regular transactions",
                "late fees", "Section 234E",
                "Issue 2B", "delayed filing", "filing after due date", "penalty Section 271H",
                "interest payment", "future filing measures"
            ]
        },
        "issue_3_salary": {
            "keywords": [
                "Issue 3A", "no TDS salary", "Section 192 missing", "senior personnel salary",
                "payroll outsourcing", "exemption arrangement", "reporting lapse",
                "Issue 3B", "significantly lower salary TDS", "comparable entities",
                "employee strength", "industry profile", "compensation structure",
                "under-reporting salary", "sectoral norms",
                "Issue 3C", "lower salary growth", "expected annual growth", "inflationary adjustment",
                "increments", "workforce expansion", "compensation change",
                "Issue 3D", "perquisites to employees", "non-cash benefits", "senior management",
                "key personnel", "top 10 employees", "gross package", "performance incentive",
                "stock options", "perquisite value", "Form 16 reconciliation", "CTC vs taxable",
                "Issue 3E", "ESOP analysis", "share-based benefits", "vesting provisions",
                "exercise provisions", "Board resolution", "scheme agreement",
                "options granted vested exercised", "perquisite value taxable", "IND AS 102",
                "accounting treatment", "expense recognized",
                "Issue 3F", "owned residential property", "leased residential property",
                "accommodation to employee", "accommodation to director", "employer-owned",
                "employer-leased", "person staying", "Rule 3 perquisite", "reason for exclusion"
            ]
        },
        "issue_4_business_benefits": {
            "keywords": [
                "Issue 4A", "benefits to partners", "perquisites to associates",
                "sales marketing expenses", "event sponsorship", "dealer conference",
                "travel accommodation", "hospitality expense", "free samples to distributors",
                "gifts to dealers", "incentives to dealers", "commission brokerage",
                "personal expense reimbursement", "foreign travel sponsored",
                "luxury trips", "Section 194R deduction", "10% rate", "cash or kind benefit"
            ]
        },
        "issue_5_professional_fees": {
            "keywords": [
                "Issue 5", "professional fees 194J", "significantly lower", "similar entities",
                "same sector", "10% rate professional", "resident professional",
                "prescribed threshold", "industry practice", "disproportionately low",
                "service provider details", "PAN of provider", "exemption reason",
                "nil certificate", "lower certificate", "comparative treatment",
                "other expense head", "classification elsewhere"
            ]
        },
        "issue_6_misclassification": {
            "keywords": [
                "Issue 6", "potential misclassification", "inconsistent section",
                "nature of business mismatch", "deductee business activity",
                "lower TDS rate", "transaction nature", "rationale for section",
                "rationale for rate", "annexure listing", "red flag indication"
            ]
        },
        "issue_7_gst_gap": {
            "keywords": [
                "Issue 7", "potential GST TDS gap", "GSTR-1 analysis", "supplier filing",
                "aggregated information", "amount discrepancy", "missing in TDS",
                "substantially lower TDS", "estimated rate justification",
                "supplier-wise explanation", "deductee-wise explanation"
            ]
        },
        "issue_8_corrections": {
            "keywords": [
                "Issue 8", "correction statements filed", "TRACES portal verification",
                "statement status", "view statement status", "reason for correction",
                "PAN modification", "challan re-mapping", "short deduction rectification",
                "books of account alignment", "supporting records", "internal reconciliation"
            ]
        },
        "issue_9_audit": {
            "keywords": [
                "Issue 9", "audit findings", "Form 3CD", "tax audit report", "Section 44AB",
                "Clause 34(a)", "Clause 34(b)", "Clause 34(c)", "non-deduction observation",
                "short deduction observation", "delayed deposit", "auditor remarks",
                "corrective action", "remedial steps"
            ]
        },
        "issue_10_defaults": {
            "keywords": [
                "Issue 10", "TDS defaults", "short deduction instance", "delayed deposit",
                "interest penalty", "justification report", "request download",
                "short payment", "interest levied", "late filing fees", "Section 201 interest",
                "Section 220 interest", "correction submission"
            ]
        },
        "issue_11_challans": {
            "keywords": [
                "Issue 11", "unconsumed challans", "partially consumed", "challan mapping error",
                "pending correction", "excess payment", "challan status", "future use",
                "refund claim", "oversight error", "corrective action confirmation"
            ]
        }
    },
    "process_workflow_keywords": {
        "step_1_identification": {
            "keywords": [
                "case identification", "analytical methods", "potential non-compliance",
                "risk-prone deductors", "quantitative analysis", "risk-based prioritization",
                "evidence-driven enforcement", "macro-level trends", "micro-level red flags",
                "year-on-year deviation", "thematic analysis", "behavioral indicators",
                "holistic risk profile", "data-backed selection"
            ]
        },
        "step_2_selection_analysis": {
            "keywords": [
                "selection for analysis", "alert aggregation", "consolidated risk profile",
                "unified case profile", "risk classification", "very high risk",
                "high risk", "medium risk", "low risk", "very low risk",
                "priority level P1", "priority level P2", "priority level P3",
                "comprehensive analysis", "workload consideration", "resource availability"
            ]
        },
        "step_3_case_analysis": {
            "keywords": [
                "detailed analysis", "nature of discrepancy", "extent of default",
                "root cause analysis", "validate risk", "reconstruct transactions",
                "compliance behavior assessment", "confirm indicators", "quantify default",
                "willful evasion pattern", "financial data integration", "return filing integration",
                "compliance history", "third-party information", "structured scrutiny"
            ]
        },
        "step_4_selection_verification": {
            "keywords": [
                "selection for verification", "online verification", "risk level priority",
                "data sufficiency", "verifiable data", "transaction evidence",
                "past compliance response", "responsive behavior", "field action alternative",
                "resource capacity", "charge capacity", "recorded justification"
            ]
        },
        "step_5_verification": {
            "keywords": [
                "case verification", "appropriate action", "materiality assessment",
                "deductor behavior", "online verification preferred", "non-willful discrepancy",
                "data-driven verification", "share issues", "request information",
                "request documents", "clearly framed queries", "issue-specific queries",
                "time-bound queries", "verification checklist", "systematic verification",
                "comprehensive verification", "departmental guidelines",
                "survey action", "high-risk survey", "serious non-compliance",
                "deliberate evasion", "large-scale non-compliance", "no satisfactory response",
                "competent authority approval", "Income Tax Act procedure",
                "books of accounts examination", "relevant records", "material evidence",
                "actual TDS compliance", "communication template", "clarification request",
                "supporting documentation", "reconcile gaps"
            ]
        },
        "step_6_documentation": {
            "keywords": [
                "case documentation", "alert sources", "analytical methods applied",
                "findings recorded", "verification mode", "verification steps",
                "deductor response", "supporting documents", "final outcome",
                "action taken", "tax recovered", "case closed", "referred for survey",
                "audit trail", "case records", "documentation protocol"
            ]
        }
    },
    "technical_terminology": {
        "forms_documents": [
            "Form 24Q", "Form 26Q", "Form 27Q", "Form 27EQ", "Form 24G",
            "Form 27A", "Form 16", "Form 16A", "Form 3CD", "Form 15G", "Form 15H",
            "Form 197", "GSTR-1", "ITR", "P&L account", "manufacturing account",
            "trading account", "audit report", "tax audit report"
        ],
        "compliance_terms": [
            "deductor", "deductee", "TAN", "PAN", "challan", "CIN",
            "BIN", "AIN", "DDO", "PAO", "AG", "ROC", "MCA",
            "assessment year", "financial year", "quarter", "YTD",
            "deposit", "deduction", "collection", "remittance", "filing",
            "correction", "justification", "reconciliation"
        ],
        "enforcement_terms": [
            "short deduction", "short payment", "late payment", "delayed deposit",
            "non-filing", "stop-filing", "default", "demand", "manual demand",
            "CPC demand", "interest", "penalty", "compounding fee", "prosecution",
            "survey", "e-verification", "verification", "assessment", "disallowance",
            "Section 40(a)(ia)", "Section 234E", "Section 271H", "Section 201",
            "Section 220"
        ],
        "analytical_terms": [
            "gap analysis", "expense gap", "collection gap", "value gap",
            "transaction gap", "GST-TDS gap", "benchmark", "ratio", "threshold",
            "trend", "growth rate", "variance", "mismatch", "discrepancy",
            "deviation", "anomaly", "red flag", "indicator", "pattern",
            "correlation", "comparison", "reconciliation", "aggregation",
            "consolidation", "categorization", "classification", "prioritization",
            "risk profiling", "sectoral analysis", "thematic analysis",
            "behavioral analysis", "compliance pattern"
        ],
        "data_terms": [
            "data source", "data extraction", "data cleaning", "data validation",
            "data integration", "data correlation", "data aggregation",
            "party-wise data", "section-wise data", "year-wise data",
            "quarter-wise data", "transaction-wise data", "deductee-wise data",
            "automated extraction", "manual extraction", "Python automation",
            "Excel analysis", "pivot analysis", "filter application",
            "VLOOKUP matching", "INDEX-MATCH", "consolidation sheet"
        ],
        "portal_navigation": [
            "TRACES login", "hover cursor", "MIS reports", "business intelligence",
            "top deductors menu", "defaulter homepage", "prosecution module",
            "AO interface", "Range report", "TAN with multiple correction",
            "Insight login", "BI dashboard", "tax collection", "TDS compliance",
            "deductor profile", "tax profile", "annual summary", "master profile",
            "related TANs", "aggregated payments", "aggregated transactions",
            "profile access request", "download utility", "export to excel",
            "filter selection", "charge selection", "jurisdiction selection"
        ]
    },
    "sector_industry_keywords": {
        "high_risk_sectors": [
            "real estate", "construction", "pharma", "pharmaceutical",
            "FMCG", "fast-moving consumer goods", "alcoholic beverages",
            "financial services", "IT services", "software", "manufacturing",
            "wholesale", "retail", "hospitality", "hotel industry",
            "IT hardware", "electronics", "e-commerce", "distribution"
        ],
        "business_activities": [
            "contract work", "professional services", "consultancy",
            "technical services", "manufacturing activity", "trading",
            "distribution", "dealership", "agency", "brokerage",
            "commission agents", "service providers", "vendors",
            "suppliers", "contractors", "sub-contractors"
        ]
    },
    "quantitative_keywords": {
        "thresholds": [
            "Rs.10,000 threshold", "Rs.20,000 threshold", "Rs.30,000 threshold",
            "Rs.50,000 threshold", "Rs.1,00,000 threshold", "Rs.5,00,000 threshold",
            "Rs.10,00,000 threshold", "Rs.50,00,000 threshold", "no threshold",
            "single payment", "aggregate amount", "annual aggregate",
            "substantial amount", "large-value", "high-value"
        ],
        "percentages_rates": [
            "1% rate", "2% rate", "5% rate", "10% rate", "20% rate", "30% rate",
            "0.1% rate", "growth rate", "expected rate", "estimated rate",
            "benchmark rate", "sectoral rate", "standard rate", "lower rate",
            "higher rate", "applicable rate"
        ],
        "metrics": [
            "top 500 deductors", "top 10 employees", "YTD collection",
            "transaction count", "turnover range", "income range",
            "employee strength", "business volume", "payment value",
            "expense value", "TDS amount", "TCS amount", "gap value",
            "default value", "demand value", "unconsumed challan value"
        ]
    },
    "action_recommendation_keywords": {
        "verification_actions": [
            "e-verification recommended", "online verification", "seek clarification",
            "request information", "request documents", "verify records",
            "examine books", "reconcile data", "confirm compliance",
            "validate claims", "cross-check", "match records"
        ],
        "enforcement_actions": [
            "survey recommended", "field verification", "physical inspection",
            "demand creation", "demand collection", "penalty imposition",
            "prosecution initiation", "interest calculation", "late fee levy",
            "correction filing", "retrospective deduction", "challan tagging",
            "refund adjustment", "set-off application"
        ],
        "compliance_improvement": [
            "awareness program", "outreach initiative", "training session",
            "capacity building", "guidance provision", "FAQ circulation",
            "best practices sharing", "systemic fix", "internal controls",
            "maker-checker process", "automated alerts", "periodic review",
            "quarterly reconciliation", "timely filing", "proper documentation"
        ]
    },
    "contextual_query_phrases": {
        "identification_queries": [
            "how to identify non-compliant deductors",
            "top deductor collection gap method",
            "thematic analysis for Section 194R",
            "non-filer stop-filer detection",
            "transaction value gap identification",
            "correction statement red flags",
            "government deductor analysis steps",
            "prosecution case prioritization",
            "LDC misuse detection"
        ],
        "analysis_queries": [
            "how to conduct expense gap analysis",
            "TDS classification analysis procedure",
            "GST-TDS reconciliation method",
            "sectoral transactional ratio calculation",
            "residential house perquisite verification",
            "compliance behavior assessment",
            "open-source information analysis",
            "Python automation for TDS analysis",
            "Excel pivot for TDS data"
        ],
        "data_access_queries": [
            "how to download TRACES reports",
            "Insight BI data source access",
            "Insight Profile navigation",
            "aggregated TDS payment extraction",
            "GSTR-1 data download",
            "Form 3CD analysis in Insight",
            "related TAN identification",
            "business sector information"
        ],
        "verification_queries": [
            "how to conduct e-verification",
            "sample communication to deductor",
            "issues to be verified",
            "documents to be requested",
            "survey vs online verification",
            "case documentation requirements",
            "verification checklist usage",
            "final outcome recording"
        ]
    },
    "compliance_checklist_items": {
        "salary_perquisites_192": [
            "all salary components included", "perquisites valued correctly",
            "Rule 3 valuation applied", "Form 24Q matching", "Form 16 reconciliation",
            "HRMS data verification", "accommodation benefit", "car perquisite",
            "ESOP taxation", "loan perquisite", "club membership", "gift valuation",
            "insurance premium", "foreign travel", "education benefit"
        ],
        "benefits_perquisites_194r": [
            "marketing incentive verification", "dealer conference benefit",
            "travel hospitality check", "free samples valuation", "gift voucher tracking",
            "asset personal use", "expense reimbursement", "sponsored trips",
            "loyalty program benefits", "commission in kind", "demo product retention",
            "settlement payment", "insurance coverage benefit", "event tickets",
            "family member expenses", "Rs.20,000 threshold check", "10% TDS deduction",
            "FMV calculation", "business vs personal", "invoice backing"
        ],
        "general_compliance": [
            "timely filing", "challan linkage", "PAN validation", "section correctness",
            "rate appropriateness", "threshold verification", "exemption validity",
            "certificate genuineness", "declaration verification", "reconciliation completeness",
            "documentation adequacy", "audit trail maintenance", "correction justification",
            "default resolution", "interest payment", "penalty discharge"
        ]
    },
    "risk_indicators": {
        "high_risk_flags": [
            "no filing despite turnover", "sudden drop in TDS", "frequent corrections",
            "delayed filing pattern", "prosecution history", "TEP received",
            "NCLT proceedings", "sick unit status", "stop-filing behavior",
            "large unconsumed challans", "excessive LDC usage", "related party transactions",
            "related TAN non-compliance", "audit adverse remarks", "disallowance u/s 40(a)(ia)",
            "grievance complaints", "sector deviation", "peer comparison mismatch"
        ],
        "behavioral_patterns": [
            "compliant deductor", "occasionally non-compliant", "persistently non-compliant",
            "high-risk watchlist", "improvement trend", "deteriorating compliance",
            "seasonal pattern", "year-end rush", "last-minute filing",
            "correction dependency", "persistent defaults", "repeat offender"
        ]
    }
}

# TDS Compliance Verification Toolkit Keywords
TDS_COMPLIANCE_VERIFICATION_TOOLKIT_KEYWORDS = {
    "document_metadata": {
        "primary_keywords": [
            "TDS compliance framework", "tax deducted at source", "Income-tax Act 1961",
            "compliance verification", "systematic checks", "transaction-level checks",
            "TRACES portal", "GSTN", "e-filing portals", "tax authorities scrutiny"
        ],
        "section_keywords": [
            "Form 24Q", "Form 26Q", "Form 27EQ", "TDS returns filing",
            "challan utilization", "defaults resolution", "penalty avoidance",
            "disallowances prevention", "internal auditors", "assessing officers"
        ],
        "semantic_variants": [
            "TDS verification", "tax compliance audit", "source tax deduction",
            "compliance gaps", "tax governance", "proactive compliance"
        ]
    },
    "module_2_traces_portal_compliance": {
        "primary_keywords": [
            "TRACES portal", "return filing verification", "Form 24Q filing",
            "Form 26Q filing", "Form 27EQ filing", "Form 27A acknowledgment",
            "challan reconciliation", "bank reconciliation", "TAN verification"
        ],
        "operational_keywords": [
            "unconsumed challans", "consumed challans monitoring", "automated consumption",
            "CPC tagging", "manual demand", "correction statements", "justification reports",
            "default analysis", "short deduction", "late deduction", "late payment",
            "PAN errors", "section mismatches", "challan mapping"
        ],
        "process_keywords": [
            "timely filing", "quarterly returns", "pending returns", "rejected returns",
            "compliance tracker", "exception monitoring", "escalation process",
            "systemic fixes", "audit trail", "resolution tracking"
        ],
        "technical_keywords": [
            "CIN", "Challan Identification Number", "TDS AO", "deductor portal",
            "6-year restriction", "backdated corrections", "misreporting coverage"
        ]
    },
    "module_3_erp_tds_gap_analysis": {
        "primary_keywords": [
            "ERP-based analysis", "TDS gap analysis", "accounting module gaps",
            "payables module", "transaction reconciliation", "missed deductions",
            "incorrect section mapping", "lower rate deduction"
        ],
        "data_keywords": [
            "ERP data extraction", "party-level TDS", "expense mapping", "TCS mapping",
            "TRACES data download", "bidirectional reconciliation", "bottom-up check",
            "top-down check", "pivot tables", "automated scripts"
        ],
        "annexure_keywords": [
            "Annexure A", "ERP extract file", "data structure", "Annexure B",
            "gap analysis file", "Annexure C", "expense to TDS mapping",
            "TDS/TCS sections", "threshold limits", "amount paid/payable"
        ],
        "control_keywords": [
            "maker-checker process", "ERP workflow", "exception documentation",
            "control summary sheet", "retroactive deduction", "voluntary compliance",
            "interest payment", "corrective action tracking"
        ],
        "technical_fields": [
            "Expense Type", "Section Code", "Party Name", "Party PAN",
            "Amount Credited", "Amount Paid", "ERP Amount", "ERP TDS",
            "Reported Amount", "Reported TDS", "Gap Amount", "Gap TDS"
        ]
    },
    "module_4_gst_tds_gap_analysis": {
        "primary_keywords": [
            "GST-TDS reconciliation", "GSTR-1 matching", "outward supply data",
            "supplier-wise analysis", "GSTIN-PAN mapping", "invoice matching",
            "vendor compliance", "service classification"
        ],
        "process_keywords": [
            "threshold comparison", "unreported vendors", "misclassified services",
            "high-value payments", "insufficient TDS", "vendor-level exceptions",
            "retrospective TDS", "correction filing", "vendor clarifications"
        ],
        "technical_keywords": [
            "GSTR-1 data", "Form 26Q", "Form 27Q", "Form 27EQ matching",
            "PAN validation", "GSTIN validation", "invoice amount matching",
            "nature of service", "nature of payment"
        ],
        "threshold_keywords": [
            "Rs.30,000 threshold", "Rs.1,00,000 annual threshold", "Section 194C threshold",
            "aggregate value", "payment threshold", "annual limit"
        ],
        "exception_keywords": [
            "mismatch identification", "suspected non-compliance", "exception report",
            "vendor flagging", "absence detection", "misclassification detection"
        ]
    },
    "module_5_employee_perquisites": {
        "primary_keywords": [
            "Section 192", "salary TDS", "employee perquisites", "non-cash benefits",
            "payroll verification", "Form 16", "HRMS records", "perquisite valuation"
        ],
        "perquisite_types": [
            "housing benefit", "free accommodation", "concessional accommodation",
            "car perquisite", "vehicle usage", "ESOPs", "stock options",
            "employer contribution", "NPS contribution", "PF excess",
            "loan perquisite", "interest-free loan", "concessional loan",
            "travel perquisite", "leisure travel", "holiday reimbursement",
            "education benefit", "club membership", "gift perquisite"
        ],
        "annexure_d_keywords": [
            "Annexure D verification", "salary components reporting", "gross salary",
            "bonus reporting", "fees commission", "retirement benefits",
            "HRA", "LTA", "children education allowance", "employer NPS"
        ],
        "valuation_keywords": [
            "Rule 3 valuation", "FMV", "fair market value", "perquisite calculation",
            "taxable perquisites", "exempt perquisites", "undervaluation detection"
        ],
        "regime_keywords": [
            "old tax regime", "new tax regime", "regime-specific exemptions",
            "Section 10 exemptions", "Section 80C deductions", "Section 80D deductions"
        ],
        "compliance_keywords": [
            "Form 24Q matching", "payroll integration", "sample-based testing",
            "omission detection", "TDS same month", "correction suggestion"
        ]
    },
    "module_6_business_benefits_194r": {
        "primary_keywords": [
            "Section 194R", "business benefits", "business perquisites",
            "distributor incentives", "agent benefits", "dealer perquisites",
            "non-employee benefits", "Rs.20,000 threshold"
        ],
        "benefit_categories": [
            "marketing incentives", "promotional schemes", "gifts in kind",
            "foreign trips", "event sponsorships", "dealer conferences",
            "luxury accommodation", "travel hospitality", "free samples",
            "vouchers", "festival hampers", "medicine samples"
        ],
        "annexure_e_keywords": [
            "Annexure E checklist", "FMV calculation", "benefit valuation",
            "resident business associates", "10% TDS rate", "annual aggregation"
        ],
        "specific_scenarios": [
            "loyalty programs", "reward schemes", "commission in kind",
            "demo product retention", "settlement payments", "insurance coverage",
            "event tickets", "family member expenses", "reimbursement tracking"
        ],
        "verification_points": [
            "invoice verification", "business vs leisure", "personal component",
            "cost recovery check", "contractual obligation", "documentation review",
            "CBDT Circular 12/2022", "professional samples"
        ],
        "asset_benefits": [
            "company vehicle personal use", "accommodation facility",
            "property usage", "asset retention", "subscription benefits",
            "club fees", "personal reimbursements"
        ]
    },
    "cross_cutting_keywords": {
        "tds_sections": [
            "Section 192", "Section 193", "Section 194", "Section 194A",
            "Section 194B", "Section 194BA", "Section 194BB", "Section 194C",
            "Section 194D", "Section 194DA", "Section 194EE", "Section 194G",
            "Section 194H", "Section 194I", "Section 194IA", "Section 194IB",
            "Section 194IC", "Section 194J", "Section 194K", "Section 194LA",
            "Section 194LB", "Section 194LBA", "Section 194LBB", "Section 194LBC",
            "Section 194LC", "Section 194LD", "Section 194M", "Section 194N",
            "Section 194O", "Section 194P", "Section 194Q", "Section 194R",
            "Section 194S", "Section 194T"
        ],
        "tcs_sections": [
            "Section 206C(1)", "Section 206C(1C)", "Section 206C(1F)",
            "Section 206C(1G)", "TCS on alcohol", "TCS on motor vehicle",
            "TCS on luxury goods", "TCS on LRS", "TCS on overseas tour",
            "TCS on minerals", "TCS on timber", "TCS on forest produce"
        ],
        "payment_nature": [
            "salary and wages", "interest on securities", "dividend payment",
            "interest other than securities", "lottery winnings", "online gaming",
            "horse race winnings", "contract payments", "insurance commission",
            "life insurance maturity", "NSS deposits", "lottery ticket commission",
            "brokerage and commission", "rent payment", "property purchase",
            "professional fees", "technical services", "royalty payment",
            "mutual fund income", "land acquisition", "IDF interest",
            "REIT distribution", "InvIT distribution", "AIF income",
            "securitization trust", "foreign currency borrowing", "rupee bonds",
            "cash withdrawal", "e-commerce payment", "senior citizen interest",
            "goods purchase", "VDA transfer", "partner payment"
        ],
        "rate_keywords": [
            "10% rate", "2% rate", "1% rate", "30% rate", "5% rate",
            "0.1% rate", "slab rate", "individual HUF rate", "company rate",
            "non-resident rate", "foreign company rate", "lower deduction certificate"
        ],
        "threshold_amounts": [
            "Rs.10,000", "Rs.20,000", "Rs.30,000", "Rs.50,000", "Rs.1,00,000",
            "Rs.5,00,000", "Rs.10,00,000", "Rs.20,00,000", "Rs.50,00,000",
            "Rs.1 crore", "Rs.3 crore", "Rs.7,50,000", "no threshold"
        ],
        "compliance_actions": [
            "TDS deduction", "TDS deposit", "TDS payment", "return filing",
            "correction statement", "justification submission", "exception reporting",
            "retroactive deduction", "interest calculation", "penalty avoidance",
            "disallowance prevention", "voluntary disclosure"
        ],
        "entities": [
            "individual", "HUF", "company", "non-company", "resident",
            "non-resident", "foreign company", "partnership firm", "LLP",
            "trust", "AOP", "BOI", "government", "local authority"
        ]
    },
    "technical_compliance_keywords": {
        "forms_and_returns": [
            "Form 24Q", "Form 26Q", "Form 27Q", "Form 27EQ", "Form 27A",
            "Form 16", "Form 15G", "Form 15H", "Form 12B", "quarterly returns",
            "annual returns", "correction return", "revised return", "original return"
        ],
        "dates_and_deadlines": [
            "due date", "quarterly due date", "payment due date", "filing due date",
            "financial year", "assessment year", "FY 2023-24", "AY 2024-25",
            "previous year", "relevant previous year"
        ],
        "penalties_and_interest": [
            "late filing penalty", "late payment interest", "short deduction penalty",
            "disallowance u/s 40(a)(ia)", "disallowance u/s 40(a)(i)",
            "interest u/s 201(1A)", "fee u/s 234E", "prosecution provisions"
        ],
        "certificates_and_documents": [
            "TDS certificate", "Form 16A", "TAN certificate", "PAN validation",
            "lower deduction certificate", "nil deduction certificate", "Section 197",
            "bank statement", "payment voucher", "invoice", "bill", "receipt"
        ]
    },
    "query_expansion_synonyms": {
        "verification_terms": [
            "check", "verify", "validate", "reconcile", "match", "compare",
            "analyze", "review", "examine", "assess", "audit", "inspect"
        ],
        "gap_terms": [
            "gap", "mismatch", "discrepancy", "difference", "variance",
            "shortfall", "omission", "missing", "unreported", "unrecorded"
        ],
        "compliance_terms": [
            "compliance", "adherence", "conformity", "observance", "fulfillment",
            "discharge", "obligation", "requirement", "responsibility", "duty"
        ],
        "action_terms": [
            "deduct", "collect", "deposit", "remit", "pay", "file", "report",
            "disclose", "compute", "calculate", "determine", "ascertain"
        ]
    },
    "contextual_phrases": {
        "common_queries": [
            "how to verify TDS compliance",
            "TDS gap analysis procedure",
            "employee perquisite valuation method",
            "business benefit TDS rate",
            "TRACES portal reconciliation steps",
            "GST TDS mismatch resolution",
            "section 194R applicability",
            "unconsumed challan treatment",
            "correction statement filing process",
            "ERP TDS mapping guidelines"
        ],
        "problem_scenarios": [
            "missed TDS deduction",
            "wrong section applied",
            "lower rate wrongly claimed",
            "threshold not checked",
            "perquisite not valued",
            "benefit not reported",
            "challan not linked",
            "PAN error in return",
            "late payment of TDS",
            "undervaluation of benefit"
        ]
    }
}

# Unconsumed TDS Challan Tagging Framework Keywords
UNCONSUMED_TDS_CHALLAN_TAGGING_KEYWORDS = {
    "document_metadata": {
        "document_name": "Unconsumed TDS Challan Tagging Framework",
        "domain": ["TDS", "Tax Administration", "Demand Management"],
        "primary_entities": [
            "Unconsumed Challan",
            "TDS Demand",
            "TAN-FY Record",
            "CPC-TDS",
            "TDS AO",
            "Deductor",
            "Deductee",
            "TRACES",
            "Manual Demand",
            "System Generated Demand",
            "Compounding Fees",
            "Late Payment Interest (LPI)",
            "Late Deduction Interest",
            "Late Filing Fee (LFF)"
        ],
        "global_themes": [
            "Demand Reduction Strategy",
            "Challan Tagging Logic",
            "Priority-Based Case Selection",
            "Risk-Based Processing",
            "Automation vs Manual Intervention",
            "Challan-Demand Matching",
            "TDS Compliance Optimization",
            "Data-Driven Tax Administration"
        ]
    },
    "module_1_background_policy": {
        "themes": [
            "Central Action Plan",
            "TDS Conference Directive",
            "Mandatory Tagging Targets",
            "Field Monitoring",
            "Administrative Compliance"
        ],
        "keywords": [
            "Central Action Plan 2024-25",
            "21st All India TDS Conference",
            "15% tagging mandate",
            "Last four financial years",
            "Field formation review",
            "Monitoring of unconsumed challans",
            "Administrative direction",
            "Policy-driven tagging"
        ]
    },
    "module_2_data_analysis_reduction": {
        "themes": [
            "Data Aggregation",
            "Demand vs Challan Comparison",
            "Reduction Potential Computation",
            "Volume Analysis"
        ],
        "keywords": [
            "Reduction potential formula",
            "Minimum of demand and challan",
            "FY-wise demand analysis",
            "High volume TAN records",
            "Demand-challan mismatch",
            "Unconsumed challan volume",
            "Demand reduction modeling",
            "Data-driven prioritisation",
            "Aggregated deductor data"
        ]
    },
    "module_3_categorisation_framework": {
        "themes": [
            "Demand Type Classification",
            "Tagging Eligibility Logic",
            "Case Segmentation"
        ],
        "keywords": [
            "Category CC",
            "Category MD",
            "SD=UC",
            "SD>UC",
            "SD<UC",
            "Compounding charge cases",
            "Manual demand cases",
            "System demand equal challan",
            "Demand higher than challan",
            "Demand lower than challan",
            "Challan categorisation logic"
        ]
    },
    "module_4_priority_engine": {
        "themes": [
            "Value-Based Prioritisation",
            "High Impact Case Selection",
            "Efficiency Optimization"
        ],
        "keywords": [
            "P1 priority cases",
            "Demand reduction threshold",
            "High priority TAN-FY",
            "Top reduction cases",
            "Value-based filtering",
            "High impact tagging",
            "Demand reduction bands",
            "Priority scoring model"
        ]
    },
    "module_5_high_priority_identification": {
        "themes": [
            "Selective Verification",
            "Focused Tagging Strategy",
            "Error Prevention"
        ],
        "keywords": [
            "3125 high priority records",
            "38.8% reduction coverage",
            "Targeted tagging",
            "Focused verification",
            "Wrong tagging prevention",
            "High-value challan basket",
            "Priority-based flagging",
            "Selective action approach"
        ]
    },
    "module_6_tagging_rules_compounding": {
        "themes": [
            "Scenario-Based Tagging",
            "Date-Based Eligibility",
            "AO Action Workflow"
        ],
        "keywords": [
            "Challan after provisional acceptance",
            "Compounding fee tagging",
            "AO portal tagging",
            "Manual Demand Management",
            "Tag/Replace challan",
            "Compounding application date",
            "Taxpayer objection opportunity"
        ]
    },
    "module_7_tagging_rules_manual_demand": {
        "themes": [
            "Enforcement-Based Logic",
            "Nature of Demand Check"
        ],
        "keywords": [
            "Manual demand tagging",
            "Post enforcement challan",
            "Non-deduction exclusion",
            "Short deduction exclusion",
            "Non-payment exclusion",
            "Manual demand adjustment"
        ]
    },
    "module_8_tagging_rules_interest_fees": {
        "themes": [
            "Processing-Date Logic",
            "Interest and Fee Adjustment"
        ],
        "keywords": [
            "Late Payment Interest tagging",
            "Late Deduction Interest tagging",
            "Late Filing Fee tagging",
            "Challan after processing date",
            "Interest-fee matching",
            "Correction -> Tagging of Interest and Fee"
        ]
    },
    "module_9_operational_outcomes": {
        "themes": [
            "Impact Measurement",
            "Demand Reduction Results"
        ],
        "keywords": [
            "1824 challans tagged",
            "Demand reduced 25 crore",
            "Category-wise tagging impact",
            "Compounding fee impact",
            "Manual demand impact",
            "Interest and fee impact"
        ]
    },
    "module_10_system_improvements": {
        "themes": [
            "Automation",
            "Risk-Based Controls",
            "System Integration",
            "Fraud Prevention"
        ],
        "keywords": [
            "Automated challan consumption",
            "Relaxed matching criteria",
            "Actionable tagging cases",
            "Risk-based restriction",
            "Correction statement risk model",
            "TDS credit control",
            "Refund fraud prevention",
            "Tax-payment integration",
            "CPC automation",
            "System logic modification"
        ]
    },
    "technical_terminology": {
        "demand_types": [
            "Manual Demand",
            "System Generated Demand",
            "Compounding Fees",
            "Late Payment Interest",
            "Late Deduction Interest",
            "Short Deduction Demand",
            "Non-Deduction Demand",
            "Non-Payment Demand"
        ],
        "challan_status": [
            "Unconsumed Challan",
            "Consumed Challan",
            "Partially Consumed",
            "Tagged Challan",
            "Replaced Challan"
        ],
        "categorisation_codes": [
            "Category CC",
            "Category MD",
            "SD=UC",
            "SD>UC",
            "SD<UC"
        ],
        "priority_levels": [
            "P1 priority",
            "P2 priority",
            "P3 priority",
            "High priority",
            "Medium priority",
            "Low priority"
        ],
        "process_stages": [
            "Provisional acceptance",
            "Final acceptance",
            "Challan tagging",
            "Challan replacement",
            "Demand adjustment",
            "Verification",
            "AO action"
        ]
    },
    "formulas_and_calculations": {
        "reduction_potential": [
            "Reduction potential = Min(Demand, Unconsumed Challan)",
            "FY-wise reduction calculation",
            "TAN-FY record aggregation",
            "Demand reduction modeling"
        ],
        "matching_logic": [
            "Challan-demand matching",
            "Date-based matching",
            "Amount-based matching",
            "TAN-FY matching",
            "Relaxed matching criteria"
        ]
    },
    "operational_keywords": {
        "ao_actions": [
            "AO portal tagging",
            "Manual Demand Management",
            "Tag challan",
            "Replace challan",
            "Verify challan",
            "Approve tagging",
            "Reject tagging"
        ],
        "system_actions": [
            "Automated consumption",
            "CPC tagging",
            "System generated demand",
            "Automated matching",
            "Risk-based restriction"
        ],
        "verification_keywords": [
            "Selective verification",
            "Focused verification",
            "Wrong tagging prevention",
            "Error prevention",
            "Data validation"
        ]
    },
    "impact_metrics": {
        "volume_metrics": [
            "Challans tagged",
            "Demand reduced",
            "Reduction coverage percentage",
            "High priority records",
            "Category-wise impact"
        ],
        "value_metrics": [
            "Demand reduction amount",
            "High-value challan basket",
            "Reduction potential value",
            "Tagging impact value"
        ]
    }
}

# TDS Charge Handbook Keywords
TDS_CHARGE_HANDBOOK_KEYWORDS = {
    "document_metadata": {
        "document": "TDS Charge Handbook",
        "domain": ["Tax Administration", "TDS Enforcement", "Compliance Monitoring"],
        "core_entities": [
            "TDS",
            "TAN",
            "AIN",
            "BIN",
            "TRACES",
            "CPC-TDS",
            "OLTAS",
            "Insight Portal",
            "Deductor",
            "Deductee",
            "TDS AO",
            "CIT(TDS)",
            "CCIT",
            "TRO"
        ],
        "global_themes": [
            "TDS Compliance Enforcement",
            "Revenue Protection",
            "Demand Recovery",
            "Risk-Based Monitoring",
            "Data-Driven Verification",
            "Government Deductor Oversight",
            "System-Based Tax Administration"
        ]
    },
    "module_1_collection_monitoring": {
        "themes": ["Collection Gap", "Top Deductor Risk", "Section Compliance"],
        "keywords": [
            "Top Deductor monitoring",
            "Collection gap analysis",
            "Section-wise TDS trend",
            "Nature of payment MIS",
            "Revenue Augmentation",
            "Deductor growth variance",
            "Section-wise gap",
            "Trend deviation",
            "Low TDS growth",
            "High value deductor risk"
        ]
    },
    "module_2_government_deductor_monitoring": {
        "themes": ["AIN Control", "24G Compliance", "BIN Reconciliation"],
        "keywords": [
            "AIN verification",
            "Form 24G monitoring",
            "AIN non-filer",
            "BIN mismatch",
            "Special TAN reconciliation",
            "Government TAN deactivation",
            "24G compliance report",
            "High risk AIN",
            "BIN abnormal increase",
            "AIN master update"
        ]
    },
    "module_3_demand_management": {
        "themes": ["Demand Lifecycle", "Challan Utilization", "Recovery"],
        "keywords": [
            "Manual demand upload",
            "Unconsumed challan tagging",
            "Demand reduction",
            "Stay application disposal",
            "Short payment demand",
            "Interest & fee tagging",
            "Force match challan",
            "Consolidated demand",
            "Default summary",
            "Demand recovery workflow"
        ]
    },
    "module_4_tds_e_verification": {
        "themes": ["Non-Intrusive Audit", "Risk Detection"],
        "keywords": [
            "e-Verification case selection",
            "TDS compliance BI",
            "Transaction value gap",
            "Expense gap analysis",
            "GST-TDS mismatch",
            "High risk deductor profiling",
            "Related TAN analysis",
            "AIS cross-verification",
            "Third party mismatch",
            "Notice u/s 133(6)"
        ]
    },
    "module_5_tds_survey_133a": {
        "themes": ["Field Enforcement", "On-site Verification"],
        "keywords": [
            "TDS survey case selection",
            "Survey risk parameters",
            "Non-deduction detection",
            "Short deduction verification",
            "On-site TDS inspection",
            "Survey closure report",
            "Survey-based 201 order"
        ]
    },
    "module_6_proceedings_201": {
        "themes": ["Default Determination", "Interest Liability"],
        "keywords": [
            "201(1) order",
            "201(1A) interest",
            "Show cause u/s 201",
            "Failure to deduct TDS",
            "Failure to deposit TDS",
            "201 demand upload",
            "TDS default adjudication"
        ]
    },
    "module_7_tds_penalties": {
        "themes": ["Statutory Penalty"],
        "keywords": [
            "TDS penalty proceedings",
            "Penalty imposition",
            "Penalty monitoring"
        ]
    },
    "module_8_prosecution_276b": {
        "themes": ["Criminal Enforcement"],
        "keywords": [
            "276B prosecution",
            "Failure to deposit TDS prosecution",
            "Prosecution proposal",
            "CIT prosecution approval",
            "Criminal TDS default"
        ]
    },
    "module_9_compounding": {
        "themes": ["Settlement Mechanism"],
        "keywords": [
            "Compounding application",
            "Compounding fee verification",
            "Compounding report",
            "Compounding order follow-up"
        ]
    },
    "module_10_judicial_matters": {
        "themes": ["Litigation Handling"],
        "keywords": [
            "Judicial matter handling",
            "AO level litigation",
            "CIT level litigation",
            "CCIT judicial review"
        ]
    },
    "module_11_taxpayer_services": {
        "themes": ["Service Resolution"],
        "keywords": [
            "TRACES ticket handling",
            "Challan correction request",
            "TDS refund approval",
            "Rectification request",
            "Waiver petition",
            "Unblocking challan"
        ]
    },
    "module_12_grievances_audit": {
        "themes": ["Governance Control"],
        "keywords": [
            "CPGRAM handling",
            "e-Nivaran grievance",
            "Audit objection reply",
            "Major audit objection",
            "Minor audit objection"
        ]
    },
    "module_13_revision_263_264": {
        "themes": ["Order Review"],
        "keywords": [
            "Revision u/s 263",
            "Revision u/s 264",
            "Order revision handling"
        ]
    },
    "technical_terminology": {
        "enforcement_actions": [
            "e-Verification",
            "Survey u/s 133A(2A)",
            "201(1) order",
            "201(1A) interest",
            "Penalty proceedings",
            "Prosecution u/s 276B",
            "Prosecution u/s 276BB",
            "Compounding",
            "Revision u/s 263",
            "Revision u/s 264"
        ],
        "demand_types": [
            "Manual demand",
            "System generated demand",
            "Short payment demand",
            "Interest demand",
            "Fee demand",
            "Consolidated demand"
        ],
        "challan_operations": [
            "Unconsumed challan tagging",
            "Force match challan",
            "Challan correction",
            "Challan unblocking",
            "Challan utilization"
        ],
        "monitoring_keywords": [
            "Collection monitoring",
            "Top deductor monitoring",
            "AIN monitoring",
            "BIN reconciliation",
            "24G compliance",
            "Demand management",
            "Risk-based monitoring"
        ],
        "verification_keywords": [
            "Case selection",
            "Risk detection",
            "Gap analysis",
            "Mismatch detection",
            "Cross-verification",
            "Third party verification"
        ]
    },
    "process_workflows": {
        "demand_recovery": [
            "Demand upload",
            "Challan tagging",
            "Demand reduction",
            "Recovery workflow",
            "Stay application",
            "Default summary"
        ],
        "enforcement_workflow": [
            "Case selection",
            "Show cause notice",
            "Order passing",
            "Interest calculation",
            "Penalty imposition",
            "Prosecution proposal",
            "Compounding application"
        ],
        "service_workflow": [
            "Ticket handling",
            "Refund approval",
            "Rectification",
            "Waiver petition",
            "Grievance resolution"
        ]
    },
    "statutory_provisions": {
        "sections": [
            "Section 133(6)",
            "Section 133A(2A)",
            "Section 201(1)",
            "Section 201(1A)",
            "Section 234E",
            "Section 271H",
            "Section 276B",
            "Section 276BB",
            "Section 263",
            "Section 264"
        ],
        "forms": [
            "Form 24G",
            "Form 24Q",
            "Form 26Q",
            "Form 27Q",
            "Form 27EQ"
        ]
    }
}

# Query Expansion Patterns

QUERY_EXPANSION_PATTERNS = {

    "what is": ["define", "explain", "meaning of", "definition of"],

    "what are": ["list", "enumerate", "types of"],

    "how to": ["procedure for", "process of", "steps to", "method for", "way to"],

    "when to": ["timeline for", "due date for", "time to"],

    "where to": ["place to", "location for"],

    "why": ["reason for", "purpose of", "rationale behind"],

    "can i": ["is it possible to", "am i allowed to", "eligibility for"],

    "should i": ["do i need to", "is it required to", "obligation to"],

    "conditions": ["requirements", "eligibility", "criteria", "prerequisites"],

    "calculate": ["computation", "calculation", "determine", "compute"],

    "due date": ["deadline", "last date", "time limit", "expiry date"],

    "eligible": ["qualification", "entitlement", "eligibility for"],

    "apply": ["avail", "claim", "take benefit", "utilize"],

    "file": ["submit", "upload", "lodge", "furnish"],

    "pay": ["deposit", "remit", "make payment"],

    "claim": ["avail", "take credit", "utilize"],

    "rules": ["provisions", "regulations", "guidelines"],

    "format": ["template", "structure", "form"],

    "documents": ["papers", "records", "documentation"],

    "penalty": ["consequences", "fine for", "punishment for"],

}

# --------------------------------------------------
# Vocabulary Integration & Normalization
# --------------------------------------------------
def _normalize_concept_data(data):
    """Normalize various data formats into standard DOMAIN_KNOWLEDGE schema."""
    if isinstance(data, list):
        return {
            "synonyms": data,
            "subtopics": [],
            "routing_keywords": data # Add to routing_keywords so they are searchable
        }
    if isinstance(data, dict):
        # Already a dict, ensure basic keys exist
        standard = {
            "synonyms": data.get("synonyms", []),
            "subtopics": data.get("subtopics", []),
            "routing_keywords": data.get("routing_keywords", [])
        }
        # If synonyms exist but routing_keywords don't, copy them
        if not standard["routing_keywords"] and standard["synonyms"]:
            standard["routing_keywords"] = standard["synonyms"][:]
            
        # Copy other specific keyword fields if they exist
        for k, v in data.items():
            if k not in ["synonyms", "subtopics", "routing_keywords"]:
                standard[k] = v
                # Also add to routing if it's a list of keywords
                if k.endswith("_keywords") and isinstance(v, list):
                    standard["routing_keywords"].extend(v)
        
        # Deduplicate routing
        standard["routing_keywords"] = list(dict.fromkeys(standard["routing_keywords"]))
        return standard
    
    val_str = str(data)
    return {"synonyms": [val_str], "subtopics": [], "routing_keywords": [val_str]}

def _merge_vocabulary(base_dict, source_dict, prefix=""):
    """Recursively flatten and merge source dictionaries into base_dict."""
    for key, value in source_dict.items():
        if isinstance(value, dict) and "chapters" in value:
            # Special case for NACIN flyers etc.
            _merge_vocabulary(base_dict, value["chapters"], f"{prefix}{key} ")
        elif isinstance(value, dict) and "IGST_CORE" in value: # Specific for IGST_UTGST structure
             _merge_vocabulary(base_dict, value, f"{prefix}{key} ")
        elif isinstance(value, dict) and not any(k in value for k in ["synonyms", "routing_keywords"]):
            # Nested dictionary that isn't a concept data dict -> recurse
            _merge_vocabulary(base_dict, value, f"{prefix}{key} ")
        else:
            # It's a concept
            concept_name = (f"{prefix}{key}").strip().lower()
            norm_data = _normalize_concept_data(value)
            
            if concept_name in base_dict:
                # Merge into existing
                existing = base_dict[concept_name]
                existing["synonyms"].extend(norm_data["synonyms"])
                existing["subtopics"].extend(norm_data["subtopics"])
                existing["routing_keywords"].extend(norm_data["routing_keywords"])
                # Deduplicate
                existing["synonyms"] = list(dict.fromkeys(existing["synonyms"]))
                existing["subtopics"] = list(dict.fromkeys(existing["subtopics"]))
                existing["routing_keywords"] = list(dict.fromkeys(existing["routing_keywords"]))
                base_dict[concept_name] = existing
            else:
                base_dict[concept_name] = norm_data

# 1. Normalize existing DOMAIN_KNOWLEDGE entries first
for concept in list(DOMAIN_KNOWLEDGE.keys()):
    DOMAIN_KNOWLEDGE[concept] = _normalize_concept_data(DOMAIN_KNOWLEDGE[concept])

# 2. Merge all unreferenced dictionaries
_merge_vocabulary(DOMAIN_KNOWLEDGE, TAX_SYNONYMS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, LESSON_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, CGST_RULES_2017_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, IGST_UTGST_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, GST_CHAPTER_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, GST_FLYERS_NACIN_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, RNR_REPORT_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, TAX_AUDIT_44AB_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, TRANSFER_PRICING_92E_KEYWORDS)
_merge_vocabulary(DOMAIN_KNOWLEDGE, CARO_2020_KEYWORDS)


# Common GST Sections

GST_SECTIONS = [

    "section 2", "section 7", "section 9", "section 10", "section 12", "section 13",

    "section 15", "section 16", "section 17", "section 18", "section 19", "section 20",

    "section 22", "section 23", "section 24", "section 29", "section 30", "section 31",

    "section 34", "section 35", "section 37", "section 38", "section 39", "section 41",

    "section 42", "section 43", "section 44", "section 49", "section 50", "section 51",

    "section 52", "section 54", "section 73", "section 74", "section 75", "section 107",

    "section 112", "section 122", "section 129", "section 130"

]

# Common GST Rules

GST_RULES = [

    "rule 36", "rule 37", "rule 38", "rule 42", "rule 43", "rule 46", "rule 48",

    "rule 53", "rule 59", "rule 61", "rule 80", "rule 86", "rule 138"

]

# Common GST Forms

GST_FORMS = [

    "gst reg-01", "gst reg-06", "gst reg-07", "gst reg-16", "gst reg-17",

    "gst drc-01", "gst drc-03", "gst drc-07", "gst drc-20",

    "gst asmt-10", "gst asmt-11", "gst asmt-14",

    "gst pmt-06", "gst pmt-09",

    "gst rfd-01", "gst rfd-10", "gst rfd-11",

    "gst apl-01", "gst apl-05"

]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had"
}

# --------------------------------------------------
# Enums
# --------------------------------------------------
class ExpansionStrategy(str, Enum):
    SYNONYM = "synonym"
    PATTERN = "pattern"
    CONTEXTUAL = "contextual"
    HYBRID = "hybrid"

# --------------------------------------------------
# Models
# --------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    strategy: ExpansionStrategy = ExpansionStrategy.HYBRID
    max_expansions: int = Field(default=15, ge=1, le=50)

    @validator("query")
    def clean_query(cls, v):
        v = re.sub(r"\s+", " ", v.strip())
        if not v:
            raise ValueError("Query cannot be empty")
        return v

class ExpansionResult(BaseModel):
    original: str
    expanded: str
    strategy: str
    priority_score: float

class EntityInfo(BaseModel):
    entity_type: str
    value: str
    context: Optional[str] = None

class QueryResponse(BaseModel):
    original_query: str
    expanded_queries: List[ExpansionResult]
    primary_keywords: List[str]
    secondary_keywords: List[str]
    detected_entities: Dict[str, List[str]]
    entity_details: List[EntityInfo]
    suggestions: List[str]
    expansion_strategies_used: List[str]
    total_expansions: int
    processing_time_ms: float
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    version: str
    total_synonyms: int
    total_patterns: int
    total_sections: int
    total_rules: int
    total_forms: int
    timestamp: str

# --------------------------------------------------
# Utilities
# --------------------------------------------------
def normalize_query(query: str) -> str:
    query = query.lower()
    query = re.sub(r"[^a-z0-9\s\-]", " ", query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()

def safe_replace(text: str, target: str, replacement: str) -> str:
    pattern = r"\b" + re.escape(target) + r"\b"
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)

def normalize_text(text: str) -> str:
    """Normalize text for query expansion (alias for normalize_query)."""
    return normalize_query(text)

def expand_query(user_query: str):
    """Expand query using DOMAIN_KNOWLEDGE."""
    normalized = normalize_text(user_query)
    expanded = set()
    expanded.add(normalized)
    
    # Track important words for answer generation
    important_words = set()
    matched_concepts = []
    
    for concept, data in DOMAIN_KNOWLEDGE.items():
        # Use word-boundary matching for more accurate concept detection
        # This ensures "accounting" matches "accounting standards" but avoids false positives
        concept_pattern = r'\b' + re.escape(concept.lower()) + r'\b'
        matched = False
        
        # Check if concept key matches
        if re.search(concept_pattern, normalized):
            matched = True
        
        # Also check routing keywords for better matching (e.g., "appointment of auditor" should match "audit and auditors")
        if not matched and data.get("routing_keywords"):
            for keyword in data.get("routing_keywords", []):
                keyword_pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(keyword_pattern, normalized):
                    matched = True
                    break
        
        # Also check semantic synonyms for better matching
        if not matched and data.get("semantic_synonyms"):
            for sem_syn in data.get("semantic_synonyms", []):
                sem_syn_pattern = r'\b' + re.escape(sem_syn.lower()) + r'\b'
                if re.search(sem_syn_pattern, normalized):
                    matched = True
                    break
        
        # Check all additional keyword categories for matching
        keyword_categories = [
            "appointment_keywords", "company_type_keywords", "threshold_keywords",
            "procedural_keywords", "authority_keywords", "disqualification_keywords",
            "relationship_keywords", "business_relationship_keywords", "vacancy_keywords",
            "tenure_keywords", "rotation_keywords", "reappointment_keywords",
            "joint_auditor_keywords", "common_partner_keywords", "removal_keywords",
            "resignation_keywords", "special_notice_keywords", "tribunal_keywords",
            "powers_keywords", "duties_enquiry_keywords", "audit_report_keywords",
            "fraud_reporting_keywords", "CAG_keywords", "branch_audit_keywords",
            "auditing_standards_keywords", "remuneration_keywords", "prohibited_services_keywords",
            "signing_keywords", "attendance_keywords", "cost_audit_keywords",
            "cost_auditor_keywords", "cost_standards_keywords", "cost_filing_keywords",
            "restriction_keywords", "company_penalties_keywords", "auditor_penalties_keywords",
            "damages_keywords", "firm_liability_keywords", "legal_framework_keywords",
            "time_period_keywords", "stakeholder_keywords", "appointment_context_phrases",
            "eligibility_context_phrases", "disqualification_context_phrases",
            "tenure_context_phrases", "rotation_context_phrases", "removal_context_phrases",
            "resignation_context_phrases", "duties_context_phrases", "powers_context_phrases",
            "report_context_phrases", "fraud_context_phrases", "remuneration_context_phrases",
            "prohibited_context_phrases", "cost_audit_context_phrases", "penalty_context_phrases"
        ]
        
        if not matched:
            for category in keyword_categories:
                keywords = data.get(category, [])
                if keywords:
                    for keyword in keywords:
                        keyword_pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                        if re.search(keyword_pattern, normalized):
                            matched = True
                            break
                    if matched:
                        break
        
        if matched:
            matched_concepts.append(concept)
            # Add concept as important word
            important_words.add(concept)
            
            # Extract important words from synonyms
            for syn in data.get("synonyms", []):
                expanded.add(syn)
                # Extract key terms from synonyms (split and filter stopwords)
                syn_words = syn.lower().split()
                for word in syn_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Extract important words from subtopics
            for sub in data.get("subtopics", []):
                expanded.add(sub)
                # Add subtopic as important word
                sub_words = sub.lower().split()
                for word in sub_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Handle additional fields for comprehensive expansion
            # Routing keywords
            for keyword in data.get("routing_keywords", []):
                expanded.add(keyword)
                keyword_words = keyword.lower().split()
                for word in keyword_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # User query variants
            for variant in data.get("user_query_variants", []):
                expanded.add(variant)
                variant_words = variant.lower().split()
                for word in variant_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Semantic synonyms
            for sem_syn in data.get("semantic_synonyms", []):
                expanded.add(sem_syn)
                sem_syn_words = sem_syn.lower().split()
                for word in sem_syn_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Core concepts
            for core_concept in data.get("core_concepts", []):
                expanded.add(core_concept)
                core_words = core_concept.lower().split()
                for word in core_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Legal sections
            for section in data.get("legal_sections", []):
                expanded.add(section)
                important_words.add(section.lower())
            
            # Procedures
            for procedure in data.get("procedures", []):
                expanded.add(procedure)
                proc_words = procedure.lower().split()
                for word in proc_words:
                    if len(word) > 2 and word not in STOPWORDS:
                        important_words.add(word)
            
            # Forms
            for form in data.get("forms", []):
                expanded.add(form)
                important_words.add(form.lower())
            
            # Process all additional keyword categories for expansion
            all_keyword_categories = {
                "appointment_keywords": data.get("appointment_keywords", []),
                "company_type_keywords": data.get("company_type_keywords", []),
                "threshold_keywords": data.get("threshold_keywords", []),
                "procedural_keywords": data.get("procedural_keywords", []),
                "authority_keywords": data.get("authority_keywords", []),
                "disqualification_keywords": data.get("disqualification_keywords", []),
                "relationship_keywords": data.get("relationship_keywords", []),
                "business_relationship_keywords": data.get("business_relationship_keywords", []),
                "vacancy_keywords": data.get("vacancy_keywords", []),
                "tenure_keywords": data.get("tenure_keywords", []),
                "rotation_keywords": data.get("rotation_keywords", []),
                "reappointment_keywords": data.get("reappointment_keywords", []),
                "joint_auditor_keywords": data.get("joint_auditor_keywords", []),
                "common_partner_keywords": data.get("common_partner_keywords", []),
                "removal_keywords": data.get("removal_keywords", []),
                "resignation_keywords": data.get("resignation_keywords", []),
                "special_notice_keywords": data.get("special_notice_keywords", []),
                "tribunal_keywords": data.get("tribunal_keywords", []),
                "powers_keywords": data.get("powers_keywords", []),
                "duties_enquiry_keywords": data.get("duties_enquiry_keywords", []),
                "audit_report_keywords": data.get("audit_report_keywords", []),
                "fraud_reporting_keywords": data.get("fraud_reporting_keywords", []),
                "CAG_keywords": data.get("CAG_keywords", []),
                "branch_audit_keywords": data.get("branch_audit_keywords", []),
                "auditing_standards_keywords": data.get("auditing_standards_keywords", []),
                "remuneration_keywords": data.get("remuneration_keywords", []),
                "prohibited_services_keywords": data.get("prohibited_services_keywords", []),
                "signing_keywords": data.get("signing_keywords", []),
                "attendance_keywords": data.get("attendance_keywords", []),
                "cost_audit_keywords": data.get("cost_audit_keywords", []),
                "cost_auditor_keywords": data.get("cost_auditor_keywords", []),
                "cost_standards_keywords": data.get("cost_standards_keywords", []),
                "cost_filing_keywords": data.get("cost_filing_keywords", []),
                "restriction_keywords": data.get("restriction_keywords", []),
                "company_penalties_keywords": data.get("company_penalties_keywords", []),
                "auditor_penalties_keywords": data.get("auditor_penalties_keywords", []),
                "damages_keywords": data.get("damages_keywords", []),
                "firm_liability_keywords": data.get("firm_liability_keywords", []),
                "legal_framework_keywords": data.get("legal_framework_keywords", []),
                "time_period_keywords": data.get("time_period_keywords", []),
                "stakeholder_keywords": data.get("stakeholder_keywords", []),
                "appointment_synonyms": data.get("appointment_synonyms", []),
                "removal_synonyms": data.get("removal_synonyms", []),
                "qualification_synonyms": data.get("qualification_synonyms", []),
                "disqualification_synonyms": data.get("disqualification_synonyms", []),
                "audit_synonyms": data.get("audit_synonyms", []),
                "report_synonyms": data.get("report_synonyms", []),
                "company_type_synonyms": data.get("company_type_synonyms", []),
                "appointment_context_phrases": data.get("appointment_context_phrases", []),
                "eligibility_context_phrases": data.get("eligibility_context_phrases", []),
                "disqualification_context_phrases": data.get("disqualification_context_phrases", []),
                "tenure_context_phrases": data.get("tenure_context_phrases", []),
                "rotation_context_phrases": data.get("rotation_context_phrases", []),
                "removal_context_phrases": data.get("removal_context_phrases", []),
                "resignation_context_phrases": data.get("resignation_context_phrases", []),
                "duties_context_phrases": data.get("duties_context_phrases", []),
                "powers_context_phrases": data.get("powers_context_phrases", []),
                "report_context_phrases": data.get("report_context_phrases", []),
                "fraud_context_phrases": data.get("fraud_context_phrases", []),
                "remuneration_context_phrases": data.get("remuneration_context_phrases", []),
                "prohibited_context_phrases": data.get("prohibited_context_phrases", []),
                "cost_audit_context_phrases": data.get("cost_audit_context_phrases", []),
                "penalty_context_phrases": data.get("penalty_context_phrases", []),
                "monetary_limits": data.get("monetary_limits", []),
                "quantity_limits": data.get("quantity_limits", [])
            }
            
            # Process all keyword categories
            for category, keywords in all_keyword_categories.items():
                for keyword in keywords:
                    expanded.add(keyword)
                    # Extract important words from each keyword
                    keyword_words = keyword.lower().split()
                    for word in keyword_words:
                        if len(word) > 2 and word not in STOPWORDS:
                            important_words.add(word)
                    # Also add the full keyword if it's short enough
                    if len(keyword) <= 50:
                        important_words.add(keyword.lower())
    
    # Also extract important words from the original query
    query_words = normalized.split()
    for word in query_words:
        if len(word) > 3 and word not in STOPWORDS:
            important_words.add(word)
    
    # Sort important words for consistency
    important_words_list = sorted(list(important_words))
    
    return {
        "original_query": user_query,
        "normalized_query": normalized,
        "expanded_queries": list(expanded),
        "important_words": important_words_list,
        "matched_concepts": matched_concepts
    }

# --------------------------------------------------
# Entity Extraction
# --------------------------------------------------
def extract_entities(query: str) -> Tuple[Dict[str, List[str]], List[EntityInfo]]:
    entities = {
        "sections": [],
        "rules": [],
        "forms": [],
        "returns": []
    }
    details = []
    q = normalize_query(query)

    for s in GST_SECTIONS:
        if s in q:
            entities["sections"].append(s)
            details.append(EntityInfo(entity_type="section", value=s, context="GST Act"))

    for r in GST_RULES:
        if r in q:
            entities["rules"].append(r)
            details.append(EntityInfo(entity_type="rule", value=r, context="GST Rule"))

    for f in GST_FORMS:
        if f in q:
            entities["forms"].append(f)
            details.append(EntityInfo(entity_type="form", value=f, context="GST Form"))

    returns = re.findall(r"gstr[-\s]?\d+[a-z]?", q)
    for r in set(returns):
        entities["returns"].append(r)
        details.append(EntityInfo(entity_type="return", value=r, context="GST Return"))

    return entities, details

# --------------------------------------------------
# Expansion Engines
# --------------------------------------------------
def synonym_expansion(query: str, limit: int) -> List[ExpansionResult]:
    q = normalize_query(query)
    results = []
    seen = set([q])

    for term, syns in TAX_SYNONYMS.items():
        if re.search(r"\b" + re.escape(term) + r"\b", q):
            for i, syn in enumerate(syns):
                expanded = safe_replace(q, term, syn)
                if expanded not in seen:
                    seen.add(expanded)
                    results.append(ExpansionResult(
                        original=query,
                        expanded=expanded,
                        strategy="synonym",
                        priority_score=round(1 - (i * 0.1), 2)
                    ))
                if len(results) >= limit:
                    return results
    return results

def pattern_expansion(query: str, limit: int) -> List[ExpansionResult]:
    q = normalize_query(query)
    results = []
    seen = set([q])

    for pattern, alts in QUERY_EXPANSION_PATTERNS.items():
        if pattern in q:
            for i, alt in enumerate(alts):
                expanded = safe_replace(q, pattern, alt)
                if expanded not in seen:
                    seen.add(expanded)
                    results.append(ExpansionResult(
                        original=query,
                        expanded=expanded,
                        strategy="pattern",
                        priority_score=round(0.9 - (i * 0.1), 2)
                    ))
                if len(results) >= limit:
                    return results
    return results

def contextual_expansion(query: str, entities: Dict[str, List[str]], limit: int) -> List[ExpansionResult]:
    results = []
    for sec in entities.get("sections", []):
        variations = [
            f"{sec} provisions",
            f"{sec} eligibility",
            f"{sec} conditions"
        ]
        for v in variations:
            results.append(ExpansionResult(
                original=query,
                expanded=v,
                strategy="contextual",
                priority_score=0.85
            ))
            if len(results) >= limit:
                return results
    return results

def hybrid_expansion(query: str, entities: Dict[str, List[str]], limit: int) -> List[ExpansionResult]:
    combined = []
    combined.extend(synonym_expansion(query, limit))
    combined.extend(pattern_expansion(query, limit))
    combined.extend(contextual_expansion(query, entities, limit))

    unique = {}
    for c in combined:
        key = normalize_query(c.expanded)
        if key not in unique:
            unique[key] = c

    final = list(unique.values())
    final.sort(key=lambda x: x.priority_score, reverse=True)
    return final[:limit]

# --------------------------------------------------
# Keywords & Suggestions
# --------------------------------------------------
def get_keywords(query: str, entities: Dict[str, List[str]]) -> Tuple[List[str], List[str]]:
    q = normalize_query(query)
    primary = set()
    secondary = set()

    for term, syns in TAX_SYNONYMS.items():
        if re.search(r"\b" + re.escape(term) + r"\b", q):
            primary.add(term)
            for s in syns[:2]:
                secondary.add(s)

    for k in ["sections", "rules", "forms", "returns"]:
        for v in entities.get(k, []):
            primary.add(v)

    if not primary:
        words = re.findall(r"\b[a-z]{4,}\b", q)
        for w in words:
            if w not in STOPWORDS:
                primary.add(w)
            if len(primary) >= 5:
                break

    return list(primary), list(secondary)

def generate_suggestions(query: str, entities: Dict[str, List[str]]) -> List[str]:
    q = normalize_query(query)
    s = []

    if "itc" in q:
        s.append("Check Section 16 for ITC eligibility")
    if "refund" in q:
        s.append("File refund using GST RFD-01")
    if "notice" in q:
        s.append("Reply within prescribed timeline")
    if entities.get("returns"):
        s.append("Verify return due dates")

    return s[:5]

# --------------------------------------------------
# API Endpoints (only registered if app exists)
# --------------------------------------------------
if app is not None:
    @app.get("/", response_model=HealthResponse)
    async def root():
        return HealthResponse(
            status="running",
            version="3.1.0",
            total_synonyms=len(TAX_SYNONYMS),
            total_patterns=len(QUERY_EXPANSION_PATTERNS),
            total_sections=len(GST_SECTIONS),
            total_rules=len(GST_RULES),
            total_forms=len(GST_FORMS),
            timestamp=datetime.now().isoformat()
        )

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return await root()

    @app.post("/expand", response_model=QueryResponse)
    async def expand(req: QueryRequest):
        start = time.time()
        try:
            normalized = normalize_query(req.query)
            entities, details = extract_entities(normalized)
            expansions = []
            strategies = []

            if req.strategy == ExpansionStrategy.SYNONYM:
                expansions = synonym_expansion(normalized, req.max_expansions)
                strategies.append("synonym")
            elif req.strategy == ExpansionStrategy.PATTERN:
                expansions = pattern_expansion(normalized, req.max_expansions)
                strategies.append("pattern")
            elif req.strategy == ExpansionStrategy.CONTEXTUAL:
                expansions = contextual_expansion(normalized, entities, req.max_expansions)
                strategies.append("contextual")
            else:
                expansions = hybrid_expansion(normalized, entities, req.max_expansions)
                strategies = ["synonym", "pattern", "contextual"]

            primary, secondary = get_keywords(normalized, entities)
            suggestions = generate_suggestions(normalized, entities)

            return QueryResponse(
                original_query=req.query,
                expanded_queries=expansions,
                primary_keywords=primary,
                secondary_keywords=secondary,
                detected_entities=entities,
                entity_details=details,
                suggestions=suggestions,
                expansion_strategies_used=strategies,
                total_expansions=len(expansions),
                processing_time_ms=round((time.time() - start) * 1000, 2),
                timestamp=datetime.now().isoformat()
            )
        except Exception:
            logger.exception("Expansion failed")
            raise HTTPException(status_code=500, detail="Expansion failed")
