import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "https://www.cnnindonesia.com/tv/embed?smartautoplay=true"

async def main():
    m3u8_urls = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            extra_http_headers={
                "Referer": "https://www.cnnindonesia.com/",
                "Origin": "https://www.cnnindonesia.com"
            }
        )
        page = await context.new_page()

        # Bắt request chứa đuôi .m3u8
        def handle_request(request):
            if ".m3u8" in request.url:
                print(f"[LOG] Tìm thấy link: {request.url}")
                m3u8_urls.append(request.url)

        page.on("request", handle_request)

        try:
            print("[LOG] Mở trang CNN Indonesia...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"[LOG] Lỗi: {e}")
        finally:
            await browser.close()

    if m3u8_urls:
        m3u8_link = m3u8_urls[0]
        print(f"\n[THÀNH CÔNG] Link M3U8: {m3u8_link}")

        # 1. Lưu dạng text thuần (chỉ chứa duy nhất URL)
        with open("cnn_link.txt", "w", encoding="utf-8") as f:
            f.write(m3u8_link)

        # 2. Lưu dạng Playlist IPTV (.m3u8) để dán trực tiếp vào phần mềm IPTV/VLC
        m3u_content = f"""#EXTM3U
#EXTINF:-1 tvg-id="CNNIndonesia.id" tvg-name="CNN Indonesia" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/e/e0/CNN_Indonesia_Logo.svg" group-title="News",CNN Indonesia
{m3u8_link}
"""
        with open("cnn.m3u8", "w", encoding="utf-8") as f:
            f.write(m3u_content)

        print("[LOG] Đã lưu vào file cnn_link.txt và cnn.m3u8")
    else:
        print("[LOG] Không tìm thấy link m3u8!")

if __name__ == "__main__":
    asyncio.run(main())
