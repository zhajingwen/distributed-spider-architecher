import logging
from flask import Flask,request,abort
from concurrent.futures import ThreadPoolExecutor
from .forward_send import Forward


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TGBOT WEBHOOK')


# 线程池
executor = ThreadPoolExecutor(20)
app = Flask(__name__)

def worker(data):
    Forward().all_channels(data)

# sign = 'a;dkal;fgakeinngl'

@app.route('/', methods = ['GET','POST'])
def hook_message():
    if request.method == 'GET':
        logger.warning('请求方式错误...')
        abort(403)
    elif request.method == 'POST':
        data = request.json
        if 'message' not in data:
            # 比如 edited_message
            # logger.info(f'非正常消息：{data}')
            return ''
        if 'username' not in data['message']['from']:
            logger.warning(f"have no username: {data['message']['from']}")
            return ''
        # 只转发该用户的消息
        username = data['message']['from']['username']
        if username == 'G2hit':
            executor.submit(worker,data)
        else:
            logger.warning(f'请求的用户并非目标用户{username}')
        return 'ok'
    else:
        abort(403)

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=83)