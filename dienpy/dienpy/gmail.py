import os
import smtplib
import subprocess
from email.message import EmailMessage
import sys

EMAIL_ADDRESS = os.environ["GMAIL_ADDR"]
EMAIL_PASSWORD = os.environ["GMAIL_APP_PW"]


def get_signature():
    return subprocess.check_output(["hostname"]).decode().strip()


def email(subject, body, to=EMAIL_ADDRESS):
    msg = EmailMessage()
    msg.add_header("Content-Type", "text/html")
    msg.set_payload(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to, msg.as_string())


def main():
    to = EMAIL_ADDRESS if len(sys.argv) <= 3 else sys.argv[3]
    email(sys.argv[1], sys.argv[2], to)
