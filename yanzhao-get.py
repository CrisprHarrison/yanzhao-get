import time
import requests
import logging
from urllib.parse import urljoin, quote_plus
from lxml import etree
import sqlite3
import datetime
import threading
import yaml

# Load configuration from YAML file
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Unpack configuration variables
PAGE_URL = config['page_url']
XPATH_EXPRESSION = config['xpath_expression']
BARK_URL = config['bark_url']
INTERVAL_SECONDS = config['interval_seconds']

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[logging.StreamHandler(), logging.FileHandler('./log.log')])

# 连接到本地 sqlite 数据库，如果不存在则创建新的数据库和表
conn = sqlite3.connect('./articles.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (title text, link text, time text)''')
conn.commit()

def check_new_element():
    # 建立数据库连接并创建游标
    conn = sqlite3.connect('./articles.db')
    c = conn.cursor()

    try:
        while True:
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
                    time.sleep(INTERVAL_SECONDS) # 在这里添加间隔时间
                    continue

                # 构造 Bark 推送消息
                message = encoded_title  # 使用 URL 编码后的标题作为消息文本
                url = f'{BARK_URL}{message}?url={link}&encode=true'

                # 发送 HTTP 请求触发消息推送
                requests.get(url, headers={'Content-Type': 'text/plain;charset=utf-8'}, params={'encode': True})

                # 将变更内容写入数据库
                now = datetime.datetime.now()
                time_str = now.strftime('%Y-%m-%d %H:%M:%S')
                c.execute("INSERT INTO articles VALUES (?, ?, ?)", (title, link, time_str))
                conn.commit()

                logging.info(f'Successfully pushed and recorded new article: {title}')
            except Exception as e:
                logging.error(f'Error pushing or recording new article: {e}')
            
            # 每隔五分钟检测一次
            time.sleep(INTERVAL_SECONDS)

    finally:
        # 关闭游标和数据库连接
        c.close()
        conn.close()

        
def send_heartbeat():
    while True:
        try:
            # 获取当前时间并计算下一个整点时间
            now = datetime.datetime.now()
            next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

            # 计算下一个整点时间与当前时间的差值
            delta = next_hour - now
            wait_seconds = delta.total_seconds()

            # 等待到达下一个整点时间
            time.sleep(wait_seconds)

            # 构造心跳消息
            message = '服务正常/Sent heartbeat message'

            # 发送 HTTP 请求触发心跳消息
            requests.get(BARK_URL + message, headers={'Content-Type': 'text/plain;charset=utf-8'})

            logging.info('Sent heartbeat message.')
        except Exception as e:
            logging.error(f'Error sending heartbeat message: {e}')

# 创建并启动两个线程
check_thread = threading.Thread(target=check_new_element)
heart_thread = threading.Thread(target=send_heartbeat)
check_thread.start()
heart_thread.start()