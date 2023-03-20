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
with open('websites.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[logging.StreamHandler(), logging.FileHandler('./log.log')])

# 连接到本地 sqlite 数据库，如果不存在则创建新的数据库和表
conn = sqlite3.connect('./articles.db')
c = conn.cursor()

try:
    for site_config in config['websites']:
        SITE_NAME = site_config['name']
        c.execute(f'''CREATE TABLE IF NOT EXISTS {SITE_NAME}
                     (title text, link text, time text)''')
        conn.commit()

except sqlite3.Error as e:
    logging.error(f'Error creating database: {e}')
    exit()

def check_new_elements():
    # 建立数据库连接并创建游标
    conn = sqlite3.connect('./articles.db')
    c = conn.cursor()

    try:
        while True:
            try:
                for site_config in config['websites']:
                    # Unpack configuration variables
                    SITE_NAME = site_config['SITE_NAME']
                    PAGE_URL = site_config['page_url']
                    XPATH_EXPRESSION = site_config['xpath_expression']
                    BARK_URL = site_config['bark_url']
                    INTERVAL_SECONDS = site_config['interval_seconds']

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
                    c.execute(f"SELECT title FROM {SITE_NAME} WHERE link=? ORDER BY time DESC LIMIT 1", (link,))
                    latest_record = c.fetchone()

                    # 如果数据库中已经存在最新记录并且与当前记录一致，则不发送推送消息
                    if latest_record and latest_record[0] == title:
                        logging.info(f'[{PAGE_URL}] No new article found: {title}')
                        time.sleep(INTERVAL_SECONDS) # 在这里添加间隔时间
                        continue

                    # 构造 Bark 推送消息
                    message = encoded_title  # 使用 URL 编码后的标题作为消息文本
                    url = f'{BARK_URL}{message}?url={link}'

                    # 发送 HTTP 请求触发消息推送
                    requests.get(url, headers={'Content-Type': 'text/plain;charset=utf-8'})

                    # 将变更内容写入数据库
                    now = datetime.datetime.now()
                    time_str = now.strftime('%Y-%m-%d %H:%M:%S')
                    c.execute(f"INSERT INTO {SITE_NAME} VALUES (?, ?, ?)", (title, link, time_str))
                    conn.commit()

                    logging.info(f'Successfully pushed and recorded new article: {title}')

            except Exception as e:
                logging.error(f'Error pushing or recording new article: {e}')

            # 每隔指定的时间间隔检测一次
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

            for site_config in config['websites']:
                # 获取 bark_url 配置
                BARK_URL = site_config['bark_url']

                # 构造心跳消息
                message = '服务正常/Sent heartbeat message'

                # 发送 HTTP 请求触发心跳消息
                requests.get(BARK_URL + message, headers={'Content-Type': 'text/plain;charset=utf-8'})

                logging.info(f'Sent heartbeat message for website: {site_config["name"]}')
        except Exception as e:
            logging.error(f'Error sending heartbeat message: {e}')

# 创建并启动两个线程
check_thread = threading.Thread(target=check_new_elements)
heart_thread = threading.Thread(target=send_heartbeat)
check_thread.start()
heart_thread.start()
