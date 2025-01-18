from bs4 import BeautifulSoup
from pydantic import BaseModel
import requests
from playwright.sync_api import sync_playwright


class Video(BaseModel):
    def get_main_urls(self, url: str) -> list[str]:
        response = requests.get(url)
        print(response)
        soup = BeautifulSoup(response.content, "html.parser")
        links_container = soup.select_one("#list_videos_common_videos_list_items")
        print(links_container)
        links = links_container.find_all("a", href=True)
        urls = [link["href"] for link in links]
        return urls

    def download_video(self, url: str, filename: str) -> None:
        response = requests.get(url, stream=True)
        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    def get_video_urls(self, urls: list[str]) -> list[str]:
        video_urls = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # 设置headless=False可以看到浏览器操作过程
            for url in urls:
                page = browser.new_page()
                page.goto(url)
                # 使用 JavaScript 直接触发点击事件
                selector = "#kt_player > div.fp-player > div.fp-ui"
                page.wait_for_selector(selector)
                page.evaluate(f"""document.querySelector('{selector}').click()""")
                # 等待视频元素加载
                video_selector = "#kt_player > div.fp-player > video"
                page.wait_for_selector(video_selector)
                video_url = page.get_attribute(video_selector, "src")
                if video_url:
                    video_urls.append(video_url)
                page.close()
            browser.close()
        return video_urls


if __name__ == "__main__":
    downloader = Video()
    url = "https://tktube.com/zh/categories/fc2/"
    main_urls = downloader.get_main_urls(url)
    video_urls = downloader.get_video_urls(main_urls)
