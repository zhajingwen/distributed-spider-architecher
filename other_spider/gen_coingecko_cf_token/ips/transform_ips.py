

with open('proxyurl', 'w')as w:
    with open('ips-data_center')as f:
        content = f.read()
        for row in content.strip().split('\n'):
            row = row.strip()
            # print(row)
            proxy_ip = 'brd.superproxy.io:22225'
            username_pd = row.replace(f'{proxy_ip}:','').split(':')
            print(username_pd)
            user = username_pd[0]
            password = username_pd[1]
            proxy_url = f'http://{user}:{password}@{proxy_ip}'
            print(proxy_url)
            w.write(proxy_url+'\n')