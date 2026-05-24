import re
from dataclasses import asdict, dataclass
from typing import Dict, Tuple


BILLING_HEADER_NAME = "x-anthropic-billing-header"
BILLING_REQUEST_NAME = "x-anthropic-billing-request"
BILLING_HEADER_RE = re.compile(
    r"(?i)^x-anthropic-billing-header\s*:\s*.*\bcch\s*=\s*[^;\s,]+.*$"
)


@dataclass
class SanitizationReport:
    billingHeaderDetected: bool = False
    billingHeaderAction: str = "none"
    cchRedacted: bool = False
    httpHeaderRemoved: bool = False
    systemFirstLineChanged: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def should_strip(policy: str, upstream_protocol: str) -> bool:
    if policy in {"strip", "always-strip"}:
        return True
    if policy == "strip_for_non_anthropic_upstream":
        return upstream_protocol != "anthropic"
    return False


def action_for(policy: str, upstream_protocol: str) -> str:
    if policy == "pass_through":
        return "passed_through"
    if policy == "canonicalize":
        return "canonicalized"
    if should_strip(policy, upstream_protocol):
        return "stripped"
    return "passed_through"


def sanitize_system_first_line(
    system_text: str,
    policy: str = "strip_for_non_anthropic_upstream",
    upstream_protocol: str = "openai",
) -> Tuple[str, SanitizationReport]:
    lines = system_text.splitlines()
    if not lines:
        return system_text, SanitizationReport()

    first = lines[0].strip()
    if not BILLING_HEADER_RE.match(first):
        return system_text, SanitizationReport()

    action = action_for(policy, upstream_protocol)
    report = SanitizationReport(
        billingHeaderDetected=True,
        billingHeaderAction=action,
        cchRedacted=True,
        systemFirstLineChanged=action in {"stripped", "canonicalized"},
    )
    if action == "canonicalized":
        lines[0] = "x-anthropic-billing-header: cch=<stable-redacted>"
        return "\n".join(lines), report
    if action == "stripped":
        return "\n".join(lines[1:]).lstrip("\n"), report
    return system_text, report


def sanitize_headers(
    headers: Dict[str, str],
    policy: str = "strip_for_non_anthropic_upstream",
    upstream_protocol: str = "openai",
) -> Tuple[Dict[str, str], SanitizationReport]:
    action = action_for(policy, upstream_protocol)
    out = {}
    report = SanitizationReport()
    for key, value in headers.items():
        lower = key.lower()
        if lower in {BILLING_HEADER_NAME, BILLING_REQUEST_NAME}:
            report.billingHeaderDetected = True
            report.billingHeaderAction = action
            report.cchRedacted = True
            if action == "canonicalized" and lower == BILLING_HEADER_NAME:
                out[key] = "cch=<stable-redacted>"
            elif action == "passed_through":
                out[key] = value
            else:
                report.httpHeaderRemoved = True
            continue
        out[key] = value
    if not report.billingHeaderDetected:
        report.billingHeaderAction = "none"
    return out, report


def merge_reports(*reports: SanitizationReport) -> SanitizationReport:
    merged = SanitizationReport()
    actions = []
    for report in reports:
        merged.billingHeaderDetected = merged.billingHeaderDetected or report.billingHeaderDetected
        merged.cchRedacted = merged.cchRedacted or report.cchRedacted
        merged.httpHeaderRemoved = merged.httpHeaderRemoved or report.httpHeaderRemoved
        merged.systemFirstLineChanged = merged.systemFirstLineChanged or report.systemFirstLineChanged
        if report.billingHeaderAction != "none":
            actions.append(report.billingHeaderAction)
    merged.billingHeaderAction = actions[0] if actions else "none"
    return merged
