package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/robfig/cron/v3"
)

// 目标网页的 URL 和 CSS 选择器
const (
	pageURL         = "https://yjs.sdju.edu.cn/main.htm"
	cssSelector     = "#container-1 .mod .post .con .news_list .news a"
	checkInterval   = 5 * time.Minute
	heartbeatPeriod = time.Hour
)

// Bark 推送服务的 URL
var barkURL = "https://api.day.app/EbVXR9a3EYxqzbvkGjybha/"

// 数据库连接和游标
var db *sql.DB
var stmtInsert *sql.Stmt
var stmtSelectLatest *sql.Stmt

func main() {
	// 打开数据库连接
	var err error
	db, err = sql.Open("sqlite3", "./articles.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	// 创建文章表
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS articles (
			title TEXT,
			link TEXT,
			time TEXT,
			PRIMARY KEY (title, link)
		)
	`)
	if err != nil {
		log.Fatal(err)
	}

	// 准备 SQL 语句
	stmtInsert, err = db.Prepare("INSERT INTO articles (title, link, time) VALUES (?, ?, ?)")
	if err != nil {
		log.Fatal(err)
	}
	stmtSelectLatest, err = db.Prepare("SELECT title FROM articles ORDER BY time DESC LIMIT 1")
	if err != nil {
		log.Fatal(err)
	}

	// 启动定时任务
	c := cron.New()
	c.AddFunc(fmt.Sprintf("@every %s", checkInterval), checkNewElement)
	c.AddFunc(fmt.Sprintf("0 */%d * * * *", heartbeatPeriod/time.Minute), sendHeartbeat)
	c.Start()

	// 阻塞主进程
	select {}
}

// 发送心跳检测
func sendHeartbeat() {
	_, err := http.Get(fmt.Sprintf("%s%s", barkURL, "服务正常"))
	if err != nil {
		log.Printf("Error sending heartbeat notification: %v\n", err)
	}
}

func checkNewElement() {
	// 发送 HTTP 请求获取网页内容
	resp, err := http.Get(pageURL)
	if err != nil {
		log.Printf("Error getting page: %v\n", err)
		return
	}
	defer resp.Body.Close()

	// 使用 goquery 解析 HTML，并根据 CSS 选择器获取最新元素
	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		log.Printf("Error parsing HTML: %v\n", err)
		return
	}
	element := doc.Find(cssSelector).First()

	// 获取元素文本内容和链接
	title := element.Text()
	relativeLink, exists := element.Attr("href")
	if !exists {
		log.Printf("No link found for element: %v\n", element)
		return
	}

	// 处理相对链接，构造绝对链接
	u, err := url.Parse(pageURL)
	if err != nil {
		log.Printf("Error parsing URL: %v\n", err)
		return
	}
	absLink := u.ResolveReference(&url.URL{Path: relativeLink}).String()

	// 查询数据库中最新的文章标题
	var latestTitle string
	err = stmtSelectLatest.QueryRow().Scan(&latestTitle)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("Error querying latest article: %v\n", err)
		return
	}

	// 如果最新文章标题与当前文章标题不同，则插入新文章并发送 Bark 推送
	if title != latestTitle {
		_, err = stmtInsert.Exec(title, absLink, time.Now().Format("2006-01-02 15:04:05"))
		if err != nil {
			log.Printf("Error inserting article: %v\n", err)
			return
		}

		// 发送 Bark 推送
		_, err = http.Get(fmt.Sprintf("%s%s", barkURL, url.QueryEscape(title)))
		if err != nil {
			log.Printf("Error sending Bark notification: %v\n", err)
			return
		}
	}
}
