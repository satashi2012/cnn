import asyncio
import sys
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

TARGET_URL = "https://www.cnnindonesia.com/tv/embed?smartautoplay=true"

async def main():
    m3u8_urls = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled", # Tắt cờ báo hiệu đang dùng tool tự động
                "--autoplay-policy=no-user-gesture-required"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}, # Giả lập kích thước màn hình thật
            extra_http_headers={
                "Referer": "https://www.cnnindonesia.com/",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )
        page = await context.new_page()

        # Kích hoạt chế độ tàng hình trước khi truy cập trang web
        await stealth_async(page)

        def handle_request(request):
            if ".m3u8" in request.url:
                if "wowzatoken" in request.url or "livecnn-sec" in request.url:
                    m3u8_urls.insert(0, request.url)
                else:
                    m3u8_urls.append(request.url)

        page.on("request", handle_request)

        try:
            # Dùng networkidle để đảm bảo trang tải xong hoàn toàn các script ẩn
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)
            await page.mouse.click(640, 360) # Click giả lập thao tác người dùng
            await page.wait_for_timeout(8000)
        except Exception as e:
            print(f"[LOG] Bỏ qua lỗi timeout hoặc tải trang: {e}")
        finally:
            await browser.close()

    if m3u8_urls:
        link = m3u8_urls[0]
        with open("cnn_link.txt", "w", encoding="utf-8") as f:
            f.write(link)

        with open("cnn.m3u8", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U\n#EXTINF:-1 tvg-id="CNNIndonesia.id" tvg-name="CNN Indonesia",CNN Indonesia\n{link}\n')
            
        print("[THÀNH CÔNG] Đã bắt được Token và lưu file.")
    else:
        print("[LỖI] Bị chặn hoặc không tìm thấy m3u8!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
