import time
import requests
from lxml import etree

# 目标网页的 URL 和 XPath
PAGE_URL = 'https://yjs.sdju.edu.cn/main.htm'
XPATH_EXPRESSION = "(//div[@id='container-1']/div[@class='inner']/div[contains(@class,'mod')]/div[@class='mr']/div[contains(@class,'post')]/div[@class='con']/ul[contains(@class,'news_list')]/li[contains(@class,'news')]/div[@class='news_title']/a)[1]"

# Bark 推送服务的 URL
BARK_URL = 'https://api.day.app/EbVXR9a3EYxqzbvkGjybha/'

def check_new_element():
    # 发送 HTTP 请求获取网页内容
    response = requests.get(PAGE_URL)
    html = response.text

    # 使用 lxml 模块解析 HTML，并根据 XPath 获取最新元素
    root = etree.HTML(html)
    element = root.xpath(XPATH_EXPRESSION)[0]

    # 获取元素文本内容和链接
    title = element.text
    link = element.get('href')

    # 构造 Bark 推送消息
    message = f"{title.encode('utf-8')} {link}"
    url = f'{BARK_URL}{message}?url={link}'

    # 发送 HTTP 请求触发消息推送
    requests.get(url)

while True:
    check_new_element()
    time.sleep(300)  # 等待五分钟
