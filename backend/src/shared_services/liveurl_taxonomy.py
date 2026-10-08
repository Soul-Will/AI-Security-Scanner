"""
liveurl_taxonomy.py

Defines the fixed set of vulnerability categories this channel is designed to detect,
as explicitly enumerated in the source flow for Live URL Option (TRD-02 Feature 7).
These codes act as the absolute subset from the 15 total database 'finding_categories'
values that the AI Triage engine is permitted to use for this specific pipeline.
"""

from typing import Dict, TypedDict

class TaxonomyCategory(TypedDict):
    code: str
    display_name: str
    description: str


# 5 categories defined exactly from TRD-02 Feature 7 mapping to DB categories
LIVE_URL_TAXONOMY: Dict[str, TaxonomyCategory] = {
    "dom_xss": {
        "code": "dom_xss",
        "display_name": "DOM-Based Cross-Site Scripting (XSS)",
        "description": "Sourced from OWASP ZAP's active injection testing and DOM structure review."
    },
    "exposed_secrets_js": {
        "code": "exposed_secrets_js",
        "display_name": "Exposed Secret in JS Bundle",
        "description": "Sourced from scanning the extracted compiled JS bundles for hardcoded credentials."
    },
    "broken_access_control": {
        "code": "broken_access_control",
        "display_name": "Broken Access Control", # Also encompassing Insecure API Endpoints
        "description": "Sourced from API routes discovered in frontend JS during crawling and tested via active scanning."
    },
    "security_misconfig": {
        "code": "security_misconfig",
        "display_name": "Security Misconfiguration",
        "description": "Missing HTTP security headers or overly permissive CORS policies, observable from live application responses."
    },
    "info_leakage": {
        "code": "info_leakage",
        "display_name": "Information Leakage",
        "description": "Stack traces or similar backend implementation details inadvertently exposed to the client."
    }
}

# The explicit fallback label to be used by Triage Engine if no other category matches mapping
UNCATEGORIZED_TAXONOMY: TaxonomyCategory = {
    "code": "uncategorized_other",
    "display_name": "Other Security Finding",
    "description": "Explicit fallback label rather than mis-tagging to preserve platform coverage accuracy."
}
