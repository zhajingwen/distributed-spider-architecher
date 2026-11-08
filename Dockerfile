FROM your-registry.example.com/spider:latest
ENV TZ=Asia/Shanghai
COPY . /spider
WORKDIR /spider
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install --upgrade httpx && pip install --upgrade ccxt