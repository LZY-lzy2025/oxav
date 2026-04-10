import asyncio
import os
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from playwright.async_api import async_playwright

app = FastAPI()

# 全局变量存储最新的 m3u 内容
LATEST_M3U = "#EXTM3U\n"
CHANNELS_FILE = os.getenv("CHANNELS_FILE", "/app/channels.txt")
# 默认每 2 小时 (7200秒) 重新抓取一次
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "7200")) 

async def scrape_channels():
    global LATEST_M3U
    if not os.path.exists(CHANNELS_FILE):
        print(f"未找到频道文件: {CHANNELS_FILE}")
        return

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    channels = []
    for line in lines:
        if ":" in line:
            # 只分割第一个冒号，保留 URL 中的 http://
            parts = line.strip().split(":", 1) 
            if len(parts) == 2:
                channels.append((parts[0].strip(), parts[1].strip()))

    new_m3u = "#EXTM3U\n"

    print("开始执行后台抓取任务...")
    async with async_playwright() as p:
        # 启动 Chromium，必须添加无沙盒参数以在 Docker 中运行
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        for name, url in channels:
            print(f"正在访问: {name} - {url}")
            context = await browser.new_context()
            page = await context.new_page()
            
            m3u8_links = []
            
            # 网络请求拦截器
            async def handle_request(request):
                if ".m3u8" in request.url and len(m3u8_links) < 3:
                    # 排除一些常见的广告或无效 m3u8 (可根据实际情况调整)
                    if "ad" not in request.url.lower(): 
                        m3u8_links.append(request.url)

            page.on("request", handle_request)
            
            try:
                # 访问页面，等待网络空闲
                await page.goto(url, timeout=30000, wait_until="networkidle")
                # 额外等待 5 秒，确保播放器加载并发出 m3u8 请求
                await page.wait_for_timeout(5000) 
            except Exception as e:
                print(f"访问 {name} 失败: {e}")
            
            if m3u8_links:
                for i, link in enumerate(m3u8_links):
                    # 如果抓到了多个，按序号命名
                    channel_name = name if i == 0 else f"{name} (源 {i+1})"
                    new_m3u += f'#EXTINF:-1 tvg-name="{channel_name}",{channel_name}\n'
                    new_m3u += f"{link}\n"
                print(f"成功抓取 {name}: 找到 {len(m3u8_links)} 个流")
            else:
                print(f"未能在 {name} 找到 m3u8 链接")
            
            await context.close()
        
        await browser.close()
    
    LATEST_M3U = new_m3u
    print("一轮抓取任务完成。")

async def periodic_scraper():
    """定时执行抓取任务的后台循环"""
    # 启动时先执行一次
    await scrape_channels()
    while True:
        await asyncio.sleep(SCRAPE_INTERVAL)
        await scrape_channels()

@app.on_event("startup")
async def startup_event():
    # FastAPI 启动时挂载后台任务
    asyncio.create_task(periodic_scraper())

@app.get("/m3u", response_class=PlainTextResponse)
async def get_m3u():
    """输出 M3U 播放列表"""
    return LATEST_M3U
