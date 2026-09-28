"""Telegram Bot Notification Service for CNC Sentinel AI Platform."""

import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

# In-memory alert cooldown tracker: {machine_id: last_sent_timestamp}
_last_alert_sent: Dict[str, float] = {}
_last_severity: Dict[str, str] = {}


def is_telegram_enabled() -> bool:
    """Check if Telegram integration is enabled via TELEGRAM_ENABLED environment variable."""
    val = os.getenv("TELEGRAM_ENABLED", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def get_telegram_config() -> Tuple[str, str, int]:
    """Retrieve Telegram Bot Token, Chat ID, and Cooldown setting."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    try:
        cooldown = int(os.getenv("TELEGRAM_COOLDOWN_SEC", "60"))
    except ValueError:
        cooldown = 60
    return token, chat_id, cooldown


def get_telegram_status() -> Dict[str, Any]:
    """Return safe public Telegram integration status without exposing secrets."""
    token, chat_id, cooldown = get_telegram_config()
    enabled = is_telegram_enabled()
    configured = bool(token and chat_id)
    
    redacted_chat_id = None
    if chat_id:
        redacted_chat_id = "*" * (len(chat_id) - 3) + chat_id[-3:] if len(chat_id) >= 3 else "***"

    return {
        "enabled": enabled,
        "configured": configured,
        "chat_id_redacted": redacted_chat_id,
        "cooldown_sec": cooldown,
        "status_label": "Operational" if (enabled and configured) else ("Configured (Disabled)" if configured else "Not Configured"),
    }


def send_telegram_message(message_text: str, force: bool = False) -> Tuple[bool, str]:
    """Send text message via Telegram Bot API HTTP request.
    
    Args:
        message_text: Formatted string message to send.
        force: If True, bypasses TELEGRAM_ENABLED check (useful for test alerts).
        
    Returns:
        Tuple[success: bool, status_message: str]
    """
    token, chat_id, _ = get_telegram_config()

    if not force and not is_telegram_enabled():
        return False, "Telegram notifications are currently disabled in configuration."

    if not token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is not configured."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                return True, "Telegram alert delivered successfully."
            else:
                return False, f"Telegram API returned status code {resp.status}."
    except urllib.error.HTTPError as e:
        return False, f"Telegram HTTP error: {e.code}"
    except urllib.error.URLError as e:
        return False, f"Telegram network error: {e.reason}"
    except Exception as e:
        return False, f"Telegram delivery error: {str(e)}"


def send_machine_alert(
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
    suspected_issue: str = "Threshold Warning",
    recommended_action: str = "Inspect machine sensors and operating state.",
    timestamp_str: Optional[str] = None,
) -> Tuple[bool, str]:
    """Send structured machine alert to Telegram with cooldown logic.
    
    Args:
        machine_id: Unique identifier for equipment.
        equipment_type: Machine category label.
        severity: 'WARNING', 'CRITICAL', or 'RECOVERY'.
        scenario: Operational scenario state.
        temp, vibration, current, rpm: Current sensor readings.
        failure_probability: Output probability from ML model if available.
        health_index: Simulator health index if available.
        suspected_issue: Diagnostic explanation.
        recommended_action: Actionable recommendation.
        timestamp_str: Reading timestamp string.
        
    Returns:
        Tuple[success: bool, status_message: str]
    """
    if not is_telegram_enabled():
        return False, "Telegram notifications disabled."

    now = time.time()
    _, _, cooldown_sec = get_telegram_config()
    
    severity_upper = severity.upper()
    last_sent = _last_alert_sent.get(machine_id, 0.0)
    prev_sev = _last_severity.get(machine_id, "NORMAL")

    # Cooldown check: Allow if past cooldown, OR if severity escalated from WARNING to CRITICAL
    is_escalation = (prev_sev == "WARNING" and severity_upper == "CRITICAL")
    is_recovery = (severity_upper == "RECOVERY" or (prev_sev in ["WARNING", "CRITICAL"] and severity_upper == "NORMAL"))
    
    if (now - last_sent < cooldown_sec) and not is_escalation and not is_recovery:
        return False, f"Alert suppressed for machine {machine_id} by cooldown ({int(cooldown_sec - (now - last_sent))}s remaining)."

    # Format Telegram alert message per exact user specification
    if not timestamp_str:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    prob_str = f"{failure_probability * 100:.1f}%" if failure_probability is not None else "N/A"
    health_str = f"{health_index:.1f}%" if health_index is not None else "N/A"

    msg = (
        f"<b>CNC SENTINEL AI — MACHINE ALERT</b>\n\n"
        f"<b>Machine:</b> {machine_id}\n"
        f"<b>Equipment:</b> {equipment_type}\n"
        f"<b>Severity:</b> {severity_upper}\n"
        f"<b>Scenario:</b> {scenario}\n"
        f"<b>Failure probability:</b> {prob_str}\n"
        f"<b>Health index:</b> {health_str}\n"
        f"<b>Temperature:</b> {temp:.1f} °C\n"
        f"<b>Vibration:</b> {vibration:.2f} mm/s\n"
        f"<b>Current:</b> {current:.1f} A\n"
        f"<b>RPM:</b> {rpm}\n"
        f"<b>Suspected issue:</b> {suspected_issue}\n"
        f"<b>Recommended action:</b> {recommended_action}\n"
        f"<b>Timestamp:</b> {timestamp_str}\n"
        f"<b>Data source:</b> SIMULATION"
    )

    success, message = send_telegram_message(msg)
    if success:
        _last_alert_sent[machine_id] = now
        _last_severity[machine_id] = severity_upper

    return success, message
