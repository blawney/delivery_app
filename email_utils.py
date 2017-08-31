import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import mimetypes
import os
from HTMLParser import HTMLParser
from oauth2client.file import Storage
from apiclient import discovery
import httplib2

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def send_email(credential_file_path, message_html, addresses, subject='Message from CCCB'):
    print 'in send email function'
    creds = '/webapps/cccb_portal/gmail_credentials.json'
    store = Storage(credential_file_path)
    credentials = store.get()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    for recipient in addresses:
        sender = 'cccb@mail.dfci.harvard.edu'
        message = MIMEMultipart('alternative')
        message_text = strip_tags(message_html)
        part2_html = MIMEText(message_html,'html')
        message.attach(part2_html)
        message['to'] = recipient
        message['From'] = formataddr((str(Header('CCCB', 'utf-8')), sender))
        message['subject'] = subject
        msg = {'raw': base64.urlsafe_b64encode(message.as_string())}
        sent_message = service.users().messages().send(userId='me', body=msg).execute()
