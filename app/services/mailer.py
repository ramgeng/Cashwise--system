"""Sending reports by email over SMTP (Gmail, Outlook, Zoho Mail, SendGrid, Brevo... any SMTP server).

Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM. Without them, the app offers to open
the report in your own email app instead.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from app.core.config import settings
from app.core.errors import AppError
from app.core.money import as_date, inr

EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def clean_recipients(values) -> list[str]:
    if isinstance(values, str):
        values = re.split(r"[,;\s]+", values)
    out, bad = [], []
    for v in values or []:
        v = (v or "").strip()
        if not v:
            continue
        (out if EMAIL_RE.match(v) else bad).append(v.lower())
    if bad:
        raise AppError(422, f"These don't look like email addresses: {', '.join(bad)}", "bad_email")
    return list(dict.fromkeys(out))[:20]


def _left_short(n: int | None) -> str:
    if n is None:
        return "–"
    return f"{inr(-n)} short" if n < 0 else f"{inr(n)} left"


def _signed(n: int | float | None) -> str:
    if n is None:
        return "–"
    return ("+" if n > 0 else "") + inr(n)


def report_lines(rep: dict) -> list[tuple[str, str]]:
    """The key figures, as (label, value) pairs, for the email body."""
    d = rep["data"]
    if rep["kind"] == "summary":
        f = d["flow"]["likely"]
        lines = [("Cash in bank", inr(d["cash"])),
                 (f"Net cash flow, next {d['horizon_days']} days (likely)", _signed(f["net"])),
                 ("Money coming in / going out", f"{inr(f['in'])} / {inr(f['out'])}")]
        if d.get("key_bill"):
            kb = d["key_bill"]
            lines.append((f"After paying {kb['supplier']} on {as_date(d['target_date']):%d %b}",
                          _left_short(d["on_target"]["likely"])))
        p = d["position"]
        lines += [("Net position (cash + owed to you − you owe)", inr(p["net_position"])),
                  ("Alerts needing attention", f"{d['alert_counts']['critical']} urgent, {d['alert_counts']['warning']} to watch")]
        return lines
    rows = {r["key"]: r for r in d["rows"]}
    a, b = d["a"]["label"], d["b"]["label"]
    return [(f"Money in ({a} vs {b})", f"{inr(rows['cash_in']['a'])} vs {inr(rows['cash_in']['b'])}"),
            ("Expenses", f"{inr(rows['expenses']['a'])} vs {inr(rows['expenses']['b'])}"),
            ("Net cash flow", f"{_signed(rows['net']['a'])} vs {_signed(rows['net']['b'])}"),
            ("Average days late", f"{rows['avg_days_late']['a']} vs {rows['avg_days_late']['b']}")]


def compose(rep: dict, link: str | None, note: str = "", sender: str = "") -> tuple[str, str, str]:
    biz = rep["data"]["business"]["name"]
    subject = f"{biz}: {rep['title']}"
    lines = report_lines(rep)
    text = [f"{rep['title']} for {biz}", ""]
    if note:
        text += [note, ""]
    text += [f"{k}: {v}" for k, v in lines]
    if link:
        text += ["", f"Open the full report (read-only): {link}"]
    text += ["", f"Sent from Cashwise{f' by {sender}' if sender else ''}. Cash-flow insights to help you decide, not financial advice."]
    rows = "".join(f"<tr><td style='padding:8px 12px;color:#4d5f55;border-bottom:1px solid #e2eae5'>{escape(k)}</td>"
                   f"<td style='padding:8px 12px;font-weight:700;text-align:right;border-bottom:1px solid #e2eae5'>{escape(v)}</td></tr>"
                   for k, v in lines)
    button = (f"<p style='margin:22px 0'><a href='{escape(link)}' style='background:#0e3b1e;color:#fff;padding:12px 20px;"
              f"border-radius:999px;text-decoration:none;font-weight:700'>Open the full report</a></p>") if link else ""
    html = f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:auto;color:#0f1f17">
  <p style="margin:0;color:#2fbf5b;font-weight:800">Cashwise</p>
  <h2 style="margin:6px 0 4px">{escape(rep['title'])}</h2>
  <p style="margin:0 0 16px;color:#4d5f55">{escape(biz)}</p>
  {f"<p style='background:#f2f6f3;padding:12px 14px;border-radius:12px'>{escape(note)}</p>" if note else ""}
  <table style="width:100%;border-collapse:collapse;font-size:14px">{rows}</table>
  {button}
  <p style="color:#8d9b93;font-size:12px">Sent from Cashwise{escape(f' by {sender}') if sender else ''}.
  Cash-flow insights to help you decide, not financial advice.</p>
</div>"""
    return subject, "\n".join(text), html


def _send(msg: EmailMessage) -> None:      # replaced in tests
    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ssl.create_default_context(), timeout=20) as s:
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)


def send(to: list[str], subject: str, text: str, html: str) -> None:
    if not settings.email_configured:
        raise AppError(503, "Email isn't set up on this server yet. Add SMTP settings (see DEPLOY.md), "
                            "or use 'Open in my email app'.", "email_not_configured")
    if not to:
        raise AppError(422, "Add at least one email address.", "no_recipients")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_from or settings.smtp_user, ", ".join(to)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        _send(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise AppError(502, f"The email server refused the message: {e}", "email_failed")
