import requests

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridClient:
    def __init__(self, api_key: str, from_email: str, from_name: str):
        if not api_key:
            raise ValueError("SENDGRID_API_KEY is not set")
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, to_email: str, subject: str, body: str) -> None:
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.post(SENDGRID_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
