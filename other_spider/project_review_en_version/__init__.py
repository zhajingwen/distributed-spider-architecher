from .server import app

def run(spidername):
    app.run(host='0.0.0.0', port=90)