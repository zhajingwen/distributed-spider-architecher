import os
import logging
import time
from config import config
from scrapy.utils.response import response_status_message
from scrapy.downloadermiddlewares.retry import RetryMiddleware,get_retry_request
from utils.redisdb import redis_cli
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Retry Middleware')

class RetryChangeProxy(RetryMiddleware):
    """
    重试中间件
    """
    def __init__(self, settings):
        super().__init__(settings)
        self.redis_c = redis_cli()
        self.proxy = config.PROXY_URL
        # self.max_retry_times = settings.getint("RETRY_TIMES")
        self.web_hook_api=  os.getenv('LARK_WEBHOOK_SCRAPY_SPIDER', '')

    def process_response(self, request, response, spider):
        """
        自定义分级重试等待时间；
        重试超过指定次数发告警
        """
        # 超过重试次数发告警
        self.beyond_max_retries(request, spider)
        if request.meta.get("dont_retry", False):
            return response
        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            # 动态设置延迟时间
            if request.meta.get('retry_times',0) <= 1:
                delay = 1
            elif request.meta.get('retry_times',0) <= 3:
                delay = 2  # 设置重试延迟时间
            elif request.meta.get('retry_times',0) <= 5:
                delay = 2*60
            else:
                delay = 10*60
            time.sleep(delay)
            return self._retry(request, reason, spider) or response
        return response

    def process_exception(self, request, exception, spider):
        """
        判断是否需要重试
        """
        # # 是否启用代理
        # proxy_status = hasattr(spider,'proxy')
        # if proxy_status:
        #     if not spider.proxy:
        #         return
        # 内置方法通过捕获settings里面的异常响应状态码实现
        # 属于重试的错误类型才重试
        if isinstance(exception, self.EXCEPTIONS_TO_RETRY):
            # 如果不指定不重试，则重试
            if not request.meta.get('dont_retry', False):
                # 超过重试次数发告警
                self.beyond_max_retries(request, spider)
                # 动态设置延迟时间
                delay = 5  # 设置默认延迟时间
                if request.meta.get('retry_times',0) > 1:
                    delay = 10  # 设置重试延迟时间
                if request.meta.get('retry_times', 0) > 3:
                    delay = 2 * 60
                time.sleep(delay)
                # 发起重试请求 (self._retry 带有超过重试次数的判断，超过则放弃)
                # 并且会给新的请求自动添加 dont_filter
                return self._retry(request, exception, spider)

    def beyond_max_retries(self, request, spider):
        """
        超过重试次数发告警
        """
        max_retry_times = request.meta.get("max_retry_times")
        if max_retry_times:
            self.max_retry_times = max_retry_times
        retry_times = request.meta.get("retry_times", 0) + 1
        if retry_times > self.max_retry_times:
            content = f'{spider.name} 重试溢出：{retry_times} {request.url}'
            sender(content, self.web_hook_api, '重试溢出')
            # 超过重试次数，丢入失败队列
            self.redis_c.sadd(f'{spider.name}:requests:failedurl', request._url)
            logger.error(f'该url 重试次数超过{retry_times}次，放弃并且加入错误redis队列...')