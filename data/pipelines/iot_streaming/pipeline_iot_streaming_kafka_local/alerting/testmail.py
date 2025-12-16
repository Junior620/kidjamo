import sendgrid
import os
from sendgrid.helpers.mail import Mail

sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY", ""))

message = Mail(
    from_email="support@kidjamo.app",
    to_emails="christianouragan@gmail.com",
    subject="Test avec mon domaine Kidjamo",
    html_content="<strong>Bonjour 👋, ceci est un test depuis SendGrid avec mon domaine custom.</strong>"
)

response = sg.send(message)
print(response.status_code)
