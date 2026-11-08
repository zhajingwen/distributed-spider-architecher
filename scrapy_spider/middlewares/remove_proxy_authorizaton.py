
class RemoveProxyAuthMiddleware:
    def process_request(self, request, spider):
        # 移除请求头中的Proxy-Authorization字段
        if 'Proxy-Authorization' in request.headers:
            del request.headers['Proxy-Authorization']