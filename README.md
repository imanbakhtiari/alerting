# 📡 Grafana SMS Alert Manager

A lightweight Flask-based web application to forward **Grafana alerts** (or any webhook alerts) to:

* 📱 **SMS providers** (e.g., Kavenegar)
* 💬 **Chat platforms** (e.g., Rocket.Chat, Slack, Mattermost) via incoming webhooks

This tool allows you to manage alert receivers by **teams**, define **SMS providers**, and configure a **custom message template** for outgoing alerts.

---

## 🚀 Features

* Manage phone numbers grouped by **teams** (`all`, `devops`, `cloud`, `web`, `noc`, `managers`)
* Add/remove **SMS providers** (e.g., SMS API endpoint)
* Add/remove **Webhook providers** (e.g., Rocket.Chat incoming webhook)
* Supports **custom message templates** with placeholders:

  * `{status}` → alert status (`firing`, `resolved`)
  * `{summary}` → short description of the alert
  * `{description}` → detailed description
  * `{alertname}` → name of the alert rule
* Alerts are forwarded to **both SMS & webhook providers** simultaneously
* Sensitive tokens in provider URLs and headers are **masked in the UI**

---

## 🛠 Installation

### 1. Clone the repository

```bash
git clone https://github.com/imanbakhtiari/alerting.git
cd grafana-sms-alert-manager
```

### 2. Build Docker image

```bash
docker build -t sms-alert-manager .
```

### 3. Run with Docker Compose / Kubernetes

Example **docker run**:

```bash
docker run -d -p 5000:5000 \
  -v $(pwd)/data:/app \
  --name sms-alert-manager \
  sms-alert-manager
```

---

## 📂 File Structure

```
/app
├── app.py            # Flask backend
├── templates/        # HTML templates (Bootstrap UI)
│   └── index.html    # Main UI page
├── numbers.txt       # Phone numbers & providers configuration
├── template.txt      # Optional custom message template
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container build
```

---

## ⚙️ Configuration

### Numbers & Providers

Stored in `numbers.txt`:

```ini
[all]
0912111111 | John Doe

[devops]
09120000001 | Oncall Dev

[sms_provider]
https://api.smsprovider.com/v1/<API_KEY>/sms/send.json
https://chat.domain.tld/hooks/<TOKEN>
```

* Teams (`all`, `devops`, etc.) contain phone numbers with optional descriptions.
* `[sms_provider]` contains a list of **provider endpoints**:

  * **SMS Provider** → `https://api.smsprovider.com/v1/<API_KEY>/sms/send.json`
  * **Webhook Provider** → `https://chat.domain.tld/hooks/<TOKEN>`

### Message Template

Stored in `template.txt`:

```
{status} - {alertname}: {summary}
```

If missing, the default template is:

```
{status} {summary}
```

---

## 📡 API Endpoints

### UI

* `GET /` → Web UI (manage teams, numbers, providers, template)

### Alert Ingestion

* `POST /alert/<team>`

Example:

```bash
curl -X POST http://localhost:5000/alert/devops \
  -H 'Content-Type: application/json' \
  -d '{
        "alerts": [{
          "status": "firing",
          "annotations": {"summary": "CPU > 90%"},
          "labels": {"alertname": "HighCPU"}
        }]
      }'
```

---

## 🖥 Grafana Integration

1. In Grafana → Alerting → Contact Points → Add **Webhook**

2. Set URL to:

   ```
   http://<APP_URL>:5000/alert/<team>
   ```

   Example:

   ```
   http://sms-alert-manager:5000/alert/devops
   ```

3. Test alert → Should send to **Rocket.Chat** + **SMS** simultaneously.

---

## 📜 Logs

Logs show delivery status:

```
[Webhook] sent via https://chat.domain.tld/hooks/... : 200 OK
[SMS] to 0912111111 via https://api.smsprovider.com/v1/... : 200 تایید شد
```

---

## 🔒 Security

* Tokens in URLs are **masked in UI** (but kept raw in `numbers.txt`)
* Headers with `Authorization`/`Token` are masked in UI
* Always run behind **HTTPS** in production

---

## 📦 Requirements

* Python 3.9+
* Flask
* requests
* Bootstrap 5 (for UI)

Install manually:

```bash
pip install -r requirements.txt
```

---

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE).

---

## 👨‍💻 Author

Maintained by **Iman Bakhtiari**.

