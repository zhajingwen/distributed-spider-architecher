import sys
import smtplib
import time
import logging
from other_spider.dexfilter.file import path
from other_spider.dexfilter.config.email import *
from traceback import print_exc
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from other_spider.dexfilter.alert.email_main_content import gen_html_content
from email.mime.application import MIMEApplication

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Alert Service')

class Alert:

    def run(self):
        """

        """
        while True:
            try:
                self.send_email()
                break
            except:
                logger.error('邮件发送失败，重试...')
                print_exc()
                time.sleep(60)

    def send_email(self):
        """
        邮件发送模块
        """
        new_time = time.strftime("%Y-%m-%d-%H:%M:%S")
        sender = send_email_accont  # 你发送邮箱的账号
        receivers = receive_emails.strip().split('\n')  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱
        xlsx_file = MIMEApplication(open(f'{path}result.xlsx', 'rb').read())
        xlsx_file.add_header('Content-Disposition', 'attachment', filename='当前目标代币详情.xlsx')
        email_content = gen_html_content()
        email_content = MIMEText(email_content, "html", "utf-8")
        # 创建复合邮件对象
        message = MIMEMultipart()
        # 添加正文到复合邮件对象中
        message.attach(email_content)
        # 添加附件到复合邮件对象里
        message.attach(xlsx_file)
        message['From'] = "行情监控"
        message['To'] = ",".join(receivers)
        # 标题
        subject = f'目标代币状态 {new_time}'
        message['Subject'] = Header(subject, 'utf-8')
        try:
            s = smtplib.SMTP_SSL("smtp.qq.com", 465)
            s.login(sender, send_email_accont_token)
            s.sendmail(sender, receivers, message.as_string())
            logger.info("邮件发送成功")
        except smtplib.SMTPException as e:
            logger.error("Error: 无法发送邮件", e)

if __name__ == '__main__':
    Alert().run()