from __future__ import annotations

from typing import Any

import pandas as pd
from fpdf import FPDF

from frontend.style import safe_ts, split_lines


def reports_csv(reports: list[dict[str, Any]]) -> bytes:
    return pd.DataFrame(reports).to_csv(index=False).encode("utf-8")


def integrity_csv(integrity: dict[str, Any]) -> bytes:
    rows = [{"source_vm": vm, **(data or {})} for vm, data in integrity.items()]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Sentinel-Chain Security Report", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 60, 90)
        self.line(10, 22, 200, 22)
        self.ln(8)

    def write_wrapped(self, text: Any, height: int = 6) -> None:
        self.multi_cell(self.epw, height, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    def section(self, title: str, value: Any) -> None:
        self.set_font("Helvetica", "B", 11)
        self.write_wrapped(title, 7)
        self.set_font("Helvetica", "", 10)
        lines = split_lines(value)
        if not lines:
            self.write_wrapped("No data available.")
        else:
            for line in lines:
                self.write_wrapped(f"- {line}")
        self.ln(3)


def _pdf_safe(value: Any) -> str:
    text = str(value or "")
    wrapped_words = []
    for word in text.split(" "):
        if len(word) > 48:
            wrapped_words.append(" ".join(word[i : i + 48] for i in range(0, len(word), 48)))
        else:
            wrapped_words.append(word)
    return " ".join(wrapped_words)


def reports_pdf(reports: list[dict[str, Any]]) -> bytes:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    for report in reports:
        pdf.set_font("Helvetica", "B", 12)
        pdf.write_wrapped(
            f"Report #{report.get('id', 'n/a')} | Batch {report.get('batch_id', 'n/a')} | {report.get('severity', 'UNKNOWN')}",
            7,
        )
        pdf.set_font("Helvetica", "", 10)
        pdf.write_wrapped(
            f"Source: {report.get('source_vm', 'unknown')} | Type: {report.get('log_type', 'unknown')} | Time: {safe_ts(report.get('ts'))}",
            6,
        )
        pdf.section("1. Executive Summary", report.get("summary"))
        pdf.section("2. Severity", report.get("severity"))
        pdf.section("3. Findings", report.get("findings"))
        pdf.section("4. Recommendations", report.get("recommendations"))
        pdf.section("5. Integrity Context", report.get("integrity_status", "VERIFIED"))
        pdf.ln(4)
    data = pdf.output(dest="S")
    if isinstance(data, str):
        return data.encode("latin-1")
    return bytes(data)


def integrity_pdf(integrity: dict[str, Any]) -> bytes:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.write_wrapped("Integrity Verification", 7)
    for vm, data in integrity.items():
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.write_wrapped(f"{vm}: {data.get('status', 'UNKNOWN')}", 7)
        pdf.set_font("Helvetica", "", 10)
        for key in ("checked_batches", "tampered_batch_id", "last_hash", "expected_hash", "actual_hash"):
            value = data.get(key)
            if value is not None:
                pdf.write_wrapped(f"{key}: {value}")
    output = pdf.output(dest="S")
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)
