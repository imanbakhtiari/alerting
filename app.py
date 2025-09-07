from flask import Flask, request, render_template, redirect, url_for, jsonify
import os
import requests
import time
import json
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUMBERS_FILE = os.path.join(BASE_DIR, "numbers.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.txt")

TEAMS = ["all", "devops", "cloud", "web", "noc", "managers"]

DEFAULT_TEMPLATE = "{status} {summary}"


# ---------------- UTILITIES ---------------- #
def load_numbers():
    """Load numbers + SMS providers from file"""
    if not os.path.exists(NUMBERS_FILE):
        with open(NUMBERS_FILE, "w") as f:
            for t in TEAMS:
                f.write(f"[{t}]\n\n")
            f.write("[sms_provider]\n\n")

    with open(NUMBERS_FILE, "r") as f:
        content = f.read()

    teams = {t: [] for t in TEAMS}
    providers = []
    current_team = None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section in TEAMS:
                current_team = section
            elif section == "sms_provider":
                current_team = "sms_provider"
        elif current_team == "sms_provider":
            try:
                provider = json.loads(line) if line.startswith("{") else line
                providers.append(provider)
            except Exception:
                providers.append(line)
        elif current_team and current_team in TEAMS:
            parts = line.split("|", 1)
            number = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            teams[current_team].append({"number": number, "desc": desc})

    return teams, providers


def save_numbers(teams, providers):
    """Save numbers + providers back to file"""
    with open(NUMBERS_FILE, "w") as f:
        for t in TEAMS:
            f.write(f"[{t}]\n")
            for entry in teams[t]:
                number = entry["number"]
                desc = entry.get("desc", "")
                if desc:
                    f.write(f"{number} | {desc}\n")
                else:
                    f.write(f"{number}\n")
            f.write("\n")

        f.write("[sms_provider]\n")
        for p in providers:
            if isinstance(p, dict):
                f.write(json.dumps(p) + "\n")
            else:
                f.write(str(p) + "\n")


def get_template():
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r") as f:
            return f.read().strip()
    return None


def save_template(template):
    if not template:
        if os.path.exists(TEMPLATE_FILE):
            os.remove(TEMPLATE_FILE)
    else:
        with open(TEMPLATE_FILE, "w") as f:
            f.write(template)


def build_message(data, custom_template=None):
    messages = []
    template = custom_template if custom_template else DEFAULT_TEMPLATE

    if "alerts" in data:  # Grafana/Alertmanager webhook
        for a in data["alerts"]:
            status = a.get("status", "firing")
            annotations = a.get("annotations", {})
            summary = annotations.get("summary", "No summary")
            description = annotations.get("description", "")
            alertname = a.get("labels", {}).get("alertname", "")
            msg = template.format(
                status=status, summary=summary,
                description=description, alertname=alertname
            )
            messages.append(msg)

    elif "title" in data and "state" in data:  # Grafana newer format
        status = data.get("state", "firing")
        summary = data.get("message", "No message")
        alertname = data.get("ruleName", "")
        msg = template.format(status=status, summary=summary, alertname=alertname)
        messages.append(msg)

    return "\n".join(messages)


def send_sms(numbers, message, providers):
    """Send alerts via SMS providers and webhook providers."""

    for provider in providers:
        try:
            if isinstance(provider, dict):
                url = provider.get("url")
                headers = provider.get("headers", {})
            else:
                url = provider
                headers = {}

            if not url:
                continue

            # 🚀 Webhook providers (Rocket.Chat, Slack, etc.)
            if "/hooks/" in url:
                payload = {"text": message}
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                print(f"[Webhook] sent via {url}: {resp.status_code} {resp.text}")

            # 📱 SMS providers (like Kavenegar)
            else:
                seen_numbers = set()
                for number in numbers:
                    if number in seen_numbers:
                        continue
                    seen_numbers.add(number)

                    payload = {"receptor": number, "message": message}
                    # 🔑 IMPORTANT: SMS API expects form data, not JSON
                    resp = requests.post(url, data=payload, headers=headers, timeout=10)
                    print(f"[SMS] to {number} via {url}: {resp.status_code} {resp.text}")

        except Exception as e:
            print(f"❌ Failed to send via provider {provider}: {e}")

        time.sleep(1)


# ---------------- SECURITY ---------------- #
def mask_url(url: str) -> str:
    """Mask sensitive tokens inside query strings and path segments."""
    if not url:
        return url

    # Mask common query params (apikey, token, key, secret)
    url = re.sub(r'(?i)(apikey|token|key|secret)=([^&]+)', r'\1=*****', url)

    # Mask long random path segments (20+ chars alphanumeric)
    url = re.sub(r'/[A-Za-z0-9]{20,}(?=/|$)', r'/*****', url)

    return url

def mask_headers(headers: dict) -> dict:
    """Mask sensitive headers for UI."""
    safe = {}
    for k, v in headers.items():
        if "authorization" in k.lower() or "token" in k.lower():
            safe[k] = "*****"
        else:
            safe[k] = v
    return safe

def mask_providers(providers):
    """Return a copy of providers with masked headers + URLs for UI"""
    safe_providers = []
    for p in providers:
        if isinstance(p, dict):
            safe_providers.append({
                "url": mask_url(p.get("url")),
                "headers": mask_headers(p.get("headers", {}))
            })
        else:
            safe_providers.append(mask_url(p))
    return safe_providers


# ---------------- ROUTES ---------------- #
@app.route("/")
def index():
    teams, providers = load_numbers()
    template = get_template()
    safe_providers = mask_providers(providers)
    return render_template("index.html", teams=teams, providers=safe_providers, template=template)


@app.route("/add_number/<team>", methods=["POST"])
def add_number(team):
    number = request.form.get("number")
    desc = request.form.get("desc", "")
    teams, providers = load_numbers()

    if team in teams and number:
        if not any(entry["number"] == number for entry in teams[team]):
            teams[team].append({"number": number, "desc": desc})
        if not any(entry["number"] == number for entry in teams["all"]):
            teams["all"].append({"number": number, "desc": desc})
        save_numbers(teams, providers)

    return redirect(url_for("index"))


@app.route("/remove_number/<team>/<number>")
def remove_number(team, number):
    teams, providers = load_numbers()
    if team in teams:
        teams[team] = [n for n in teams[team] if n["number"] != number]
        save_numbers(teams, providers)
    return redirect(url_for("index"))


@app.route("/add_provider", methods=["POST"])
def add_provider():
    url = request.form.get("url")
    headers_raw = request.form.get("headers", "")
    teams, providers = load_numbers()

    headers = {}
    if headers_raw:
        try:
            headers = json.loads(headers_raw)
        except Exception:
            pass

    provider = {"url": url, "headers": headers} if headers else url
    if provider not in providers:
        providers.append(provider)

    save_numbers(teams, providers)
    return redirect(url_for("index"))


@app.route("/remove_provider/<int:idx>")
def remove_provider(idx):
    teams, providers = load_numbers()
    if 0 <= idx < len(providers):
        providers.pop(idx)
        save_numbers(teams, providers)
    return redirect(url_for("index"))


@app.route("/set_template", methods=["POST"])
def set_template():
    template = request.form.get("template")
    save_template(template)
    return redirect(url_for("index"))


@app.route("/alert/<team>", methods=["POST"])
def alert(team):
    data = request.get_json(force=True)
    template = get_template()
    teams, providers = load_numbers()

    entries = teams.get(team, [])
    seen = set()
    unique_numbers = []
    for entry in entries:
        number = entry["number"]
        if number not in seen:
            seen.add(number)
            unique_numbers.append(number)

    message = build_message(data, template)
    send_sms(unique_numbers, message, providers)

    return jsonify({"status": "ok", "sent_to": unique_numbers})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

