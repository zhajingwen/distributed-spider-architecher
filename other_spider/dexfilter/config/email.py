import os
send_email_accont = os.getenv('SMTP_SENDER_EMAIL', '')
send_email_accont_token = os.getenv('SMTP_AUTH_CODE', '')
# 多个收件人用换行或逗号分隔
receive_emails = os.getenv('SMTP_RECEIVE_EMAILS', '').replace(',', '\n')
