import requests
from bs4 import BeautifulSoup
import sys
from datetime import datetime, timezone, timedelta

# 北京时间时区
BJ_TZ = timezone(timedelta(hours=8))

# 钉钉机器人 Webhook
WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=c3cb96f094f75cf54fb9ac901ad756a4d4ec8357f82ef0dc3ae76e6616ad3224"

# AIBase 日报页面
DAILY_URL = "https://news.aibase.com/zh/daily"
BASE_URL = "https://news.aibase.com"


def fetch_top5_news():
    """抓取 AIBase 日报前 5 条资讯，返回 [(标题, 图片URL, 详情链接), ...]"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(DAILY_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    cards = []
    seen_ids = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("/zh/daily/"):
            continue
        daily_id = href.split("/zh/daily/")[1].split("/")[0].split("?")[0]
        if not daily_id.isdigit():
            continue
        if daily_id in seen_ids:
            continue
        seen_ids.add(daily_id)

        img = a_tag.find("img")
        img_url = ""
        if img:
            src = img.get("src", "")
            if src and not src.startswith("data:"):
                img_url = src
                if img_url.startswith("//"):
                    img_url = "https:" + img_url

        h3 = a_tag.find("h3")
        if h3:
            title = h3.get_text(strip=True)
        elif img and img.get("alt"):
            title = img.get("alt", "").strip()
        else:
            title = a_tag.get_text(strip=True)

        detail_url = BASE_URL + href
        cards.append((title, img_url, detail_url))

        if len(cards) >= 5:
            break

    return cards


def send_dingtalk_text(content):
    """发送纯文本消息，返回是否成功"""
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    return resp.json().get("errcode") == 0


def send_dingtalk_feedcard(news_list):
    """发送 feedCard 消息，返回是否成功"""
    links = []
    for i, (title, img_url, detail_url) in enumerate(news_list):
        if i == 0:
            title = f"机器人提醒 | {title}"

        links.append({
            "title": title,
            "messageURL": detail_url,
            "picURL": img_url or "",
        })

    payload = {
        "msgtype": "feedCard",
        "feedCard": {"links": links},
    }

    resp = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    return resp.json().get("errcode") == 0


def main():
    try:
        now_str = datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')
        print(f"=== {now_str} 开始抓取 ===")
        news = fetch_top5_news()
        if not news or len(news) == 0:
            raise Exception("未抓取到任何新闻条目")

        print(f"抓取到 {len(news)} 条资讯，开始推送...")

        # 1. 标题文本
        header = f"机器人提醒：今日 AI 日报 TOP5\n发布时间：{datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M')}（北京时间）"
        send_dingtalk_text(header)

        # 2. FeedCard 卡片
        ok = send_dingtalk_feedcard(news)
        if not ok:
            raise Exception("钉钉 feedCard 推送返回失败")

        # 3. 底部链接
        footer = "每日早8点自动推送 | 点击链接查看完整日报\nhttps://news.aibase.com/zh/daily"
        send_dingtalk_text(footer)

        print(f"推送成功，共 {len(news)} 条资讯")

    except Exception as e:
        print(f"推送失败: {e}", file=sys.stderr)
        send_dingtalk_text(f"机器人提醒：抓取数据未成功，请直接访问 {DAILY_URL} 查看。")
        sys.exit(1)


if __name__ == "__main__":
    main()
