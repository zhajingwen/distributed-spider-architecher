import logging
import time
from flask import Flask,request,jsonify,abort,send_from_directory,make_response
from concurrent.futures import ThreadPoolExecutor
from .firstpage import Spider


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Flask Api')


# 线程池
executor = ThreadPoolExecutor(20)
app = Flask(__name__)
def worker(id):
    Spider(id).req()
    result = send_from_directory('', f'{id}.csv')
    print('result',result)


sign = 'a;dkal;fgakeinngl'

@app.route('/', methods = ['GET'])
def login():
    if request.method == 'GET':
        sign_client = request.args.get('sign')
        id = request.args.get('id')
        if sign_client == sign:
            # executor.submit(worker,(id))
            path = Spider(id).req()
            # time.sleep(3)
            file_name=f'{id}.csv'
            response = make_response(send_from_directory(path, file_name, as_attachment=True))
            response.headers["Content-Disposition"] = "attachment; filename={}".format(
                file_name.encode().decode('latin-1'))
            return response
        else:
            abort(403)
    else:
        abort(403)

def run():
    app.run(host='0.0.0.0',port=81)


# if __name__ == '__main__':
#     app.run(host='0.0.0.0',port=80)