import logging
from .server import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Program Entrence')

def run(spider_name):
    app.run(host='0.0.0.0', port=95)