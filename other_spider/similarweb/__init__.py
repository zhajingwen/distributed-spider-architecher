# from .event_t import run as testrun
from .server import app


def run(spidername):
    # testrun()
    app.run(host='0.0.0.0', port=88)