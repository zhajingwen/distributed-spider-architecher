import time
from .webapi import run as webrun



def run(spider_name):
    """
    nohup python manage.py -e prod -s premint.webapi > premint.log &

    """
    webrun()