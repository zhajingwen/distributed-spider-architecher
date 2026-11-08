import os
import logging
from flask import jsonify,abort

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review Api')

def match_verify(request):
    """
    在server中 进行配置配对校验
    """
    token = os.getenv('LARK_VERIFY_TOKEN_WALLET_BALANCE', '')
    if request.method == 'POST':
        data = request.json
        # 添加回调地址验证
        if 'challenge' in data:
            CHALLENGE = data['challenge']
            if data['token'] == token:
                return jsonify({'challenge': CHALLENGE})
            else:
                print('token不匹配')
                abort(403)
