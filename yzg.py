import time
import requests
import logging
from urllib.parse import urljoin, quote_plus
from lxml import etree
import sqlite3

# 目标网页的 URL 和 XPath
PAGE_URL = 'https://yjs.sdju.edu.cn/main.htm'
XPATH_EXPRESSION = "(//div[@id='container-1']/div[@class='inner']/div[contains(@class,'mod')]/div[@class='mr']/div[contains(@class,'post')]/div[@class='con']/ul[contains(@class,'news_list')]/li[contains(@class,'news')]/div[@class='news_title']/a)[1]"

# Bark 推送服务的 URL
BARK_URL = 'https://api.day.app/EbVXR9a3EYxqzbvkGjybha/'

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[logging.StreamHandler(), logging.FileHandler('./log.log')])

# 连接到本地 sqlite 数据库，如果不存在则创建新的数据库和表
conn = sqlite3.connect('./articles.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (title text, link text, time real)''')
conn.commit()

def check_new_element():
    try:
        # 发送 HTTP 请求获取网页内容
        response = requests.get(PAGE_URL)

        # 指定编码为 'utf-8' 并获取网页内容
        response.encoding = 'utf-8'
        html = response.text

        # 使用 lxml 模块解析 HTML，并根据 XPath 获取最新元素
        root = etree.HTML(html)
        element = root.xpath(XPATH_EXPRESSION)[0]

        # 获取元素文本内容和链接
        title = element.text
        relative_link = element.get('href')
        link = urljoin(PAGE_URL, relative_link)

        # 对标题进行 URL 编码
        encoded_title = quote_plus(title)

        # 查询数据库中最新的记录
        c.execute("SELECT title FROM articles ORDER BY time DESC LIMIT 1")
        latest_record = c.fetchone()

        # 如果数据库中已经存在最新记录并且与当前记录一致，则不发送推送消息
        if latest_record and latest_record[0] == title:
            logging.info(f'No new article found: {title}')
            return

        # 构造 Bark 推送消息
        message = encoded_title  # 使用 URL 编码后的标题作为消息文本
        url = f'{BARK_URL}{message}?url={link}&encode=true'

        # 发送 HTTP 请求触发消息推送
        requests.get(url, headers={'Content-Type': 'text/plain;charset=utf-8'}, params={'encode': True})

        # 将变更内容写入数据库
        c.execute("INSERT INTO articles VALUES (?, ?, ?)", (title, link, time.time()))
        conn.commit()

        logging.info(f'Successfully pushed and recorded new article: {title}')
    except Exception as e:
        logging.error(f'Error pushing or recording new article: {e}')

while True:
    check_new_element()
    time.sleep(60)  # 等待五分钟
