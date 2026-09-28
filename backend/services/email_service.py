"""SMTP Email Notification and Health Report Service for CNC Sentinel AI Platform."""

import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

# In-memory email alert cooldown tracker: {machine_id: last_sent_timestamp}
_last_email_sent: Dict[str, float] = {}
_last_email_severity: Dict[str, str] = {}


def is_email_enabled() -> bool:
    """Check if SMTP email integration is enabled via EMAIL_ENABLED or SMTP_ENABLED environment variable."""
    val = os.getenv("EMAIL_ENABLED", os.getenv("SMTP_ENABLED", "false")).strip().lower()
    return val in ("true", "1", "yes", "on")


def get_smtp_config() -> Tuple[str, int, str, str, str, str, bool, int]:
    """Retrieve SMTP server settings, credentials, and configuration safely from environment."""
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        port = 587

    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", username).strip() or username
    recipient = os.getenv("ALERT_RECIPIENT_EMAIL", "").strip()

    use_tls_val = os.getenv("SMTP_USE_TLS", "true").strip().lower()
    use_tls = use_tls_val in ("true", "1", "yes", "on")

    try:
        cooldown = int(os.getenv("EMAIL_COOLDOWN_SEC", "300"))
    except ValueError:
        cooldown = 300

    return host, port, username, password, from_email, recipient, use_tls, cooldown


def is_smtp_configured() -> bool:
    """Check if required SMTP credentials are present in the environment."""
    host, _, username, password, _, _, _, _ = get_smtp_config()
    return bool(host and username and password)


def get_email_status() -> Dict[str, Any]:
    """Return safe public Email integration status without exposing credentials."""
    host, port, username, password, from_email, recipient, use_tls, cooldown = get_smtp_config()
    enabled = is_email_enabled()
    configured = is_smtp_configured()

    redacted_recipient = None
    if recipient and "@" in recipient:
        parts = recipient.split("@")
        name = parts[0]
        domain = parts[1]
        masked_name = name[0] + "***" + (name[-1] if len(name) > 1 else "")
        redacted_recipient = f"{masked_name}@{domain}"
    elif recipient:
        redacted_recipient = "***@***"

    if enabled and configured:
        status_label = "Operational"
    elif configured and not enabled:
        status_label = "Configured (Disabled)"
    else:
        status_label = "Not Configured"

    return {
        "enabled": enabled,
        "configured": configured,
        "smtp_host": host,
        "smtp_port": port,
        "recipient_redacted": redacted_recipient,
        "use_tls": use_tls,
        "cooldown_sec": cooldown,
        "status_label": status_label,
    }


def send_email_message(
    subject: str,
    html_content: str,
    text_content: str,
    recipient_override: Optional[str] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """Send HTML/Text email via SMTP transport.

    Args:
        subject: Email subject line.
        html_content: Rich HTML body.
        text_content: Plain text fallback body.
        recipient_override: Optional explicit target email address.
        force: If True, bypasses EMAIL_ENABLED check (useful for user-triggered test emails/reports).

    Returns:
        Tuple[success: bool, status_message: str]
    """
    host, port, username, password, from_email, default_recipient, use_tls, _ = get_smtp_config()
    target_recipient = (recipient_override or default_recipient).strip()

    if not is_smtp_configured():
        return False, "Email notifications unavailable — SMTP not configured."

    if not force and not is_email_enabled():
        return False, "Email notifications disabled in configuration."

    if not target_recipient or "@" not in target_recipient:
        return False, "Valid alert recipient email address is required."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email or username
    msg["To"] = target_recipient

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        if port == 465 and not use_tls:
            server = smtplib.SMTP_SSL(host, port, timeout=10.0)
        else:
            server = smtplib.SMTP(host, port, timeout=10.0)
            if use_tls:
                server.starttls()

        server.login(username, password)
        server.send_message(msg)
        server.quit()
        return True, f"Email notification successfully delivered to {target_recipient}."
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP Authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD (or App Password)."
    except smtplib.SMTPConnectError:
        return False, f"SMTP Connection failed to {host}:{port}."
    except Exception as e:
        return False, f"SMTP delivery error: {str(e)}"


def send_machine_email_alert(
    machine_id: str,
    equipment_type: str,
    severity: str,
    scenario: str = "SIMULATION",
    temp: float = 0.0,
    vibration: float = 0.0,
    current: float = 0.0,
    rpm: int = 0,
    failure_probability: Optional[float] = None,
    health_index: Optional[float] = None,
    suspected_issue: str = "Threshold Exceedance",
    recommended_action: str = "Perform physical sensor check and spindle inspection.",
    timestamp_str: Optional[str] = None,
    recipient_override: Optional[str] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """Send structured HTML machine alert email with cooldown logic.

    Returns:
        Tuple[success: bool, status_message: str]
    """
    if not is_smtp_configured():
        return False, "Email notifications unavailable — SMTP not configured."

    if not force and not is_email_enabled():
        return False, "Email notifications disabled in configuration."

    now = time.time()
    _, _, _, _, _, _, _, cooldown_sec = get_smtp_config()

    severity_upper = severity.upper()
    last_sent = _last_email_sent.get(machine_id, 0.0)
    prev_sev = _last_email_severity.get(machine_id, "NORMAL")

    # Cooldown logic: allow if past cooldown window OR escalated from WARNING to CRITICAL
    is_escalation = (prev_sev == "WARNING" and severity_upper == "CRITICAL")
    is_recovery = (severity_upper == "RECOVERY" or (prev_sev in ["WARNING", "CRITICAL"] and severity_upper == "NORMAL"))

    if not force and (now - last_sent < cooldown_sec) and not is_escalation and not is_recovery:
        return False, f"Email suppressed for machine {machine_id} by cooldown ({int(cooldown_sec - (now - last_sent))}s remaining)."

    if not timestamp_str:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    prob_str = f"{failure_probability * 100:.1f}%" if failure_probability is not None else "N/A"
    health_str = f"{health_index:.1f}%" if health_index is not None else "N/A"
    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

    severity_color = "#ef4444" if severity_upper == "CRITICAL" else "#f59e0b" if severity_upper == "WARNING" else "#10b981"

    subject = f"[CNC SENTINEL AI ALERT] {severity_upper}: Equipment Anomaly on {machine_id}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); padding: 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; color: #ffffff; letter-spacing: 0.5px; }}
        .header p {{ margin: 4px 0 0 0; font-size: 13px; color: #e0e7ff; }}
        .banner {{ background-color: {severity_color}22; border-left: 4px solid {severity_color}; padding: 16px 20px; margin: 20px; border-radius: 6px; }}
        .banner-title {{ font-size: 16px; font-weight: 700; color: {severity_color}; margin-bottom: 4px; }}
        .banner-desc {{ font-size: 14px; color: #cbd5e1; }}
        .content {{ padding: 0 20px 20px 20px; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
        .table th {{ background-color: #0f172a; color: #94a3b8; text-align: left; padding: 10px 12px; border-bottom: 1px solid #334155; }}
        .table td {{ padding: 10px 12px; border-bottom: 1px solid #334155; color: #f1f5f9; }}
        .action-box {{ background-color: #0f172a; border: 1px solid #334155; padding: 16px; border-radius: 8px; margin-top: 20px; }}
        .action-title {{ font-size: 13px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 6px; }}
        .btn {{ display: inline-block; background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 20px; text-align: center; }}
        .footer {{ background-color: #0f172a; padding: 16px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #334155; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>CNC SENTINEL AI</h1>
          <p>AI-Powered Predictive Maintenance & Machine Health Monitoring</p>
        </div>

        <div class="banner">
          <div class="banner-title">[{severity_upper}] {machine_id} ({equipment_type})</div>
          <div class="banner-desc">{suspected_issue}</div>
        </div>

        <div class="content">
          <table class="table">
            <tr><th>Metric Parameter</th><th>Observed Value</th><th>Status Bounds</th></tr>
            <tr><td>Equipment Temperature</td><td><b>{temp:.1f} °C</b></td><td>Normal &lt; 75.0 °C</td></tr>
            <tr><td>Vibration Velocity</td><td><b>{vibration:.2f} mm/s</b></td><td>Normal &lt; 4.50 mm/s</td></tr>
            <tr><td>Motor Current Draw</td><td><b>{current:.1f} A</b></td><td>Normal &lt; 25.0 A</td></tr>
            <tr><td>Spindle Speed</td><td><b>{rpm} RPM</b></td><td>Operational</td></tr>
            <tr><td>XGBoost Failure Probability</td><td><b>{prob_str}</b></td><td>Threshold: 33%</td></tr>
            <tr><td>Simulator Health Index</td><td><b>{health_str}</b></td><td>Ground Truth</td></tr>
            <tr><td>Event Timestamp</td><td><b>{timestamp_str}</b></td><td>UTC Standard</td></tr>
          </table>

          <div class="action-box">
            <div class="action-title">Recommended Preventive Protocol</div>
            <div style="font-size: 13px; color: #e2e8f0;">{recommended_action}</div>
          </div>

          <div style="text-align: center;">
            <a href="{frontend_url}" class="btn">Launch CNC Sentinel AI Platform Dashboard</a>
          </div>
        </div>

        <div class="footer">
          Notice: Telemetry data source is digital-twin machine simulation. CNC Sentinel AI Automated System.
        </div>
      </div>
    </body>
    </html>
    """

    text_content = (
        f"CNC SENTINEL AI — MACHINE ALERT\n"
        f"========================================\n"
        f"Severity    : {severity_upper}\n"
        f"Machine ID  : {machine_id} ({equipment_type})\n"
        f"Scenario    : {scenario}\n"
        f"Failure Prob: {prob_str}\n"
        f"Health Index: {health_str}\n"
        f"Temperature : {temp:.1f} °C\n"
        f"Vibration   : {vibration:.2f} mm/s\n"
        f"Current     : {current:.1f} A\n"
        f"RPM         : {rpm}\n"
        f"Issue       : {suspected_issue}\n"
        f"Action      : {recommended_action}\n"
        f"Timestamp   : {timestamp_str}\n"
        f"Dashboard   : {frontend_url}\n"
        f"Data Source : SIMULATION\n"
    )

    success, message = send_email_message(
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        recipient_override=recipient_override,
        force=force,
    )

    if success:
        _last_email_sent[machine_id] = now
        _last_email_severity[machine_id] = severity_upper

    return success, message


def send_machine_health_report_email(
    machine_id: str,
    recipient_email: str,
    db: Any,
) -> Tuple[bool, str]:
    """Compile and deliver a comprehensive machine health report via SMTP email.

    Args:
        machine_id: Equipment identifier to generate health report for.
        recipient_email: Destination recipient email.
        db: Active PyMongo database connection.

    Returns:
        Tuple[success: bool, status_message: str]
    """
    if not is_smtp_configured():
        return False, "Email notifications unavailable — SMTP not configured."

    # 1. Validate registered machine
    machine_doc = db["machines"].find_one({"machine_id": machine_id})
    if not machine_doc:
        return False, f"Machine '{machine_id}' is not registered in the system."

    machine_type = machine_doc.get("machine_type", "CNC")

    # 2. Retrieve latest telemetry
    latest_telemetry = db["telemetry"].find_one(
        {"machine_id": machine_id},
        sort=[("timestamp", -1), ("id", -1)],
    )

    # 3. Retrieve latest prediction
    latest_pred = db["prediction_records"].find_one(
        {"machine_id": machine_id},
        sort=[("created_at", -1), ("id", -1)],
    )

    # 4. Retrieve latest maintenance event
    latest_maint = db["maintenance_events"].find_one(
        {"machine_id": machine_id},
        sort=[("event_timestamp", -1), ("id", -1)],
    )

    now_utc = datetime.now(timezone.utc)
    report_timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Format telemetry fields
    if latest_telemetry:
        temp_val = f"{latest_telemetry.get('temp', 0.0):.1f} °C" if latest_telemetry.get("temp") is not None else "Not available"
        vib_val = f"{latest_telemetry.get('vibration', 0.0):.2f} mm/s" if latest_telemetry.get("vibration") is not None else "Not available"
        curr_val = f"{latest_telemetry.get('current', 0.0):.1f} A" if latest_telemetry.get("current") is not None else "Not available"
        rpm_val = f"{latest_telemetry.get('rpm', 0)} RPM" if latest_telemetry.get("rpm") is not None else "Not available"
        wear_val = f"{latest_telemetry.get('tool_wear', 0.0):.1f} min" if latest_telemetry.get("tool_wear") is not None else "Not available"
        workload_val = f"{latest_telemetry.get('workload', 0.0):.1f}%" if latest_telemetry.get("workload") is not None else "Not available"
        health_val = f"{latest_telemetry.get('health_index', 0.0):.1f}%" if latest_telemetry.get("health_index") is not None else "Not available"
        scenario_val = str(latest_telemetry.get("scenario", "normal")).upper()
        t_time = latest_telemetry.get("timestamp")
        telemetry_time_str = t_time.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(t_time, datetime) else str(t_time or "Not available")
    else:
        temp_val = vib_val = curr_val = rpm_val = wear_val = workload_val = health_val = "Not available"
        scenario_val = "Not available"
        telemetry_time_str = "Not available"

    # Format prediction fields
    if latest_pred:
        prob_num = latest_pred.get("failure_probability")
        prob_str = f"{prob_num * 100:.2f}%" if prob_num is not None else "Not available"
        thresh_val = str(latest_pred.get("classification_threshold", 0.33))
        pred_class_val = str(latest_pred.get("predicted_class", 0))
        pred_label_val = str(latest_pred.get("predicted_label", "Normal Operation"))
        model_name_val = str(latest_pred.get("model_name", "XGBoost"))
    else:
        prob_str = "Not available"
        thresh_val = "0.33"
        pred_class_val = "Not available"
        pred_label_val = "Not available"
        model_name_val = "XGBoost"

    # Format maintenance fields
    if latest_maint:
        maint_status_val = str(latest_maint.get("status", "completed")).upper()
        maint_type_val = str(latest_maint.get("event_type", "maintenance")).title()
        maint_desc_val = str(latest_maint.get("description", "Routine inspection logged"))
        m_time = latest_maint.get("event_timestamp")
        maint_time_str = m_time.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(m_time, datetime) else str(m_time or "Not available")
    else:
        maint_status_val = "NORMAL (No Pending Events)"
        maint_type_val = "Not available"
        maint_desc_val = "No maintenance logs recorded for this machine."
        maint_time_str = "Not available"

    # Determine overall status badge
    is_high_risk = bool(latest_pred and latest_pred.get("predicted_class") == 1)
    status_color = "#ef4444" if is_high_risk else "#10b981"
    overall_status_label = "HIGH RISK — ACTION REQUIRED" if is_high_risk else "OPERATIONAL — HEALTHY"

    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    subject = f"CNC Sentinel AI — Machine Health Report — {machine_id}"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b1120; color: #f1f5f9; margin: 0; padding: 24px; }}
    .container {{ max-width: 650px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }}
    .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 50%, #0369a1 100%); padding: 28px 24px; text-align: center; border-bottom: 1px solid #334155; }}
    .header h1 {{ margin: 0; font-size: 24px; color: #38bdf8; letter-spacing: 0.5px; text-transform: uppercase; }}
    .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; }}
    .status-banner {{ background-color: {status_color}1a; border-left: 4px solid {status_color}; padding: 14px 20px; margin: 20px 24px; border-radius: 6px; }}
    .status-title {{ font-size: 15px; font-weight: 700; color: {status_color}; }}
    .status-sub {{ font-size: 13px; color: #cbd5e1; margin-top: 3px; }}
    .section {{ padding: 0 24px 18px 24px; }}
    .section-title {{ font-size: 13px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin: 16px 0 8px 0; border-bottom: 1px solid #334155; padding-bottom: 4px; }}
    .table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .table th {{ background-color: #0f172a; color: #94a3b8; text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; }}
    .table td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; color: #f1f5f9; }}
    .table tr:nth-child(even) {{ background-color: rgba(15, 23, 42, 0.5); }}
    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; margin-top: 8px; }}
    .info-card {{ background-color: #0f172a; padding: 10px 12px; border-radius: 6px; border: 1px solid #334155; }}
    .info-label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; }}
    .info-value {{ font-weight: 600; color: #f8fafc; margin-top: 2px; }}
    .footer {{ background-color: #0f172a; padding: 16px 24px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #334155; }}
    .btn {{ display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 13px; margin: 16px 0 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>CNC SENTINEL AI</h1>
      <p>AI-Powered Predictive Maintenance & Machine Health Monitoring</p>
    </div>

    <div class="status-banner">
      <div class="status-title">Equipment Health Status: {overall_status_label}</div>
      <div class="status-sub">Target Equipment: <b>{machine_id}</b> ({machine_type})</div>
    </div>

    <div class="section">
      <div class="section-title">1. Equipment Overview</div>
      <table class="table">
        <tr><th>Attribute</th><th>Specification</th></tr>
        <tr><td>Machine Identifier</td><td><b>{machine_id}</b></td></tr>
        <tr><td>Equipment Classification</td><td>{machine_type}</td></tr>
        <tr><td>Current Operating Status</td><td>{overall_status_label}</td></tr>
        <tr><td>Health Index</td><td><b>{health_val}</b></td></tr>
      </table>

      <div class="section-title">2. Latest Operating Telemetry</div>
      <table class="table">
        <tr><th>Telemetry Metric</th><th>Observed Value</th><th>Nominal Bound</th></tr>
        <tr><td>Spindle / Tool Temperature</td><td><b>{temp_val}</b></td><td>&lt; 75.0 °C</td></tr>
        <tr><td>Vibration Velocity (RMS)</td><td><b>{vib_val}</b></td><td>&lt; 4.50 mm/s</td></tr>
        <tr><td>Motor Current Draw</td><td><b>{curr_val}</b></td><td>&lt; 25.0 A</td></tr>
        <tr><td>Rotational Speed</td><td><b>{rpm_val}</b></td><td>Operating Range</td></tr>
        <tr><td>Tool Wear Duration</td><td><b>{wear_val}</b></td><td>Max 240 min</td></tr>
        <tr><td>Motor Workload</td><td>{workload_val}</td><td>Optimal &lt; 90%</td></tr>
        <tr><td>Operational Scenario</td><td>{scenario_val}</td><td>Normal / Warning / Critical</td></tr>
        <tr><td>Telemetry Recorded At</td><td>{telemetry_time_str}</td><td>System Time</td></tr>
      </table>

      <div class="section-title">3. Latest AI Predictive Inference</div>
      <table class="table">
        <tr><th>Inference Parameter</th><th>Value</th><th>Context</th></tr>
        <tr><td>Failure Probability</td><td><b>{prob_str}</b></td><td>Risk Estimate</td></tr>
        <tr><td>Classification Threshold</td><td><b>{thresh_val}</b></td><td>Calibrated Safety Limit</td></tr>
        <tr><td>Predicted Operational State</td><td><b>{pred_label_val}</b></td><td>Class {pred_class_val}</td></tr>
        <tr><td>Active ML Model</td><td>{model_name_val}</td><td>Gradient Boosted Pipeline</td></tr>
      </table>

      <div class="section-title">4. Maintenance History & Protocols</div>
      <table class="table">
        <tr><th>Protocol Parameter</th><th>Details</th></tr>
        <tr><td>Maintenance Status</td><td><b>{maint_status_val}</b></td></tr>
        <tr><td>Recent Event Type</td><td>{maint_type_val}</td></tr>
        <tr><td>Logged Description</td><td>{maint_desc_val}</td></tr>
        <tr><td>Event Timestamp</td><td>{maint_time_str}</td></tr>
      </table>

      <div class="section-title">5. Diagnostic & Explainability Context</div>
      <div style="font-size: 13px; color: #cbd5e1; background-color: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;">
        <b>Feature Attribution Note:</b> Model predictions are driven by torque load, rotational speed, tool wear duration, and process thermal differential. Local SHAP contribution values are computed dynamically during live diagnostic sessions.
      </div>

      <div class="section-title">6. System Infrastructure Status</div>
      <table class="table">
        <tr><th>Subsystem</th><th>Status</th></tr>
        <tr><td>FastAPI Backend Server</td><td>Connected &amp; Operational</td></tr>
        <tr><td>Database Storage Engine</td><td>Connected (MongoDB Atlas)</td></tr>
        <tr><td>Inference Engine</td><td>Loaded (XGBoost Classifier, Threshold {thresh_val})</td></tr>
      </table>

      <div style="text-align: center;">
        <a href="{frontend_url}" class="btn">Open CNC Sentinel AI Dashboard</a>
      </div>
    </div>

    <div class="footer">
      Report Generated: {report_timestamp_str}<br>
      Notice: This report was generated by CNC Sentinel AI. Telemetry data is generated by software digital-twin simulation.
    </div>
  </div>
</body>
</html>"""

    text_content = (
        f"CNC SENTINEL AI — MACHINE HEALTH REPORT\n"
        f"============================================================\n"
        f"Official Title: CNC Sentinel AI — AI-Powered Predictive Maintenance\n"
        f"Report Generated: {report_timestamp_str}\n\n"
        f"1. MACHINE INFORMATION\n"
        f"   Machine ID      : {machine_id}\n"
        f"   Machine Type    : {machine_type}\n"
        f"   Health Index    : {health_val}\n"
        f"   Overall Status  : {overall_status_label}\n\n"
        f"2. LATEST TELEMETRY\n"
        f"   Temperature     : {temp_val}\n"
        f"   Vibration       : {vib_val}\n"
        f"   Current         : {curr_val}\n"
        f"   Rotational Speed: {rpm_val}\n"
        f"   Tool Wear       : {wear_val}\n"
        f"   Workload        : {workload_val}\n"
        f"   Scenario        : {scenario_val}\n"
        f"   Timestamp       : {telemetry_time_str}\n\n"
        f"3. LATEST AI PREDICTION\n"
        f"   Failure Prob    : {prob_str}\n"
        f"   Decision Limit  : {thresh_val}\n"
        f"   Predicted State : {pred_label_val}\n"
        f"   Model Name      : {model_name_val}\n\n"
        f"4. MAINTENANCE STATUS\n"
        f"   Status          : {maint_status_val}\n"
        f"   Event Type      : {maint_type_val}\n"
        f"   Description     : {maint_desc_val}\n"
        f"   Timestamp       : {maint_time_str}\n\n"
        f"5. EXPLAINABILITY CONTEXT\n"
        f"   Key Drivers     : Tool wear, rotational speed, torque, process thermal differential.\n\n"
        f"6. SYSTEM STATUS\n"
        f"   Backend         : Connected & Operational\n"
        f"   Database        : Connected (MongoDB Atlas)\n"
        f"   Inference Model : Loaded ({model_name_val}, Threshold {thresh_val})\n\n"
        f"============================================================\n"
        f"Dashboard: {frontend_url}\n"
        f"Notice: Telemetry data source is digital-twin machine simulation.\n"
    )

    return send_email_message(
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        recipient_override=recipient_email,
        force=True,
    )
