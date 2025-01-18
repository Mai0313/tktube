from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from pydantic import BaseModel
import requests
from rich.console import Console
from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from bs4.element import Tag

console = Console()


class VideoModel(BaseModel):
    url: str
    title: str
    rating: str


class Video(BaseModel):
    def get_main_urls(self, url: str) -> list[VideoModel]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url)
            content = page.content()
        soup = BeautifulSoup(content, "html.parser")

        # 獲取包含所有視頻鏈接的容器
        links_container = soup.select_one("#list_videos_common_videos_list_items")
        links: list[Tag] = links_container.find_all("a", href=True)

        video_informations: list[VideoModel] = []
        for link in links:
            # 查找 rating
            rating_tag = link.find_next("div", class_="rating positive")
            rating = rating_tag.text.strip() if rating_tag else "N/A"

            # 查找 title
            title_tag = link.find_next("strong", class_="title")
            title = title_tag.text.strip() if title_tag else "Unknown Title"

            # 將提取的數據存入 VideoModel
            video_informations.append(VideoModel(url=link["href"], rating=rating, title=title))

        console.print(video_informations)
        return video_informations

    def download_video(self, video_info: VideoModel) -> None:
        response = requests.get(video_info.url, stream=True)
        with open(f"test.mp4", "wb") as f:
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
        console.print(video_urls)
        return video_urls


if __name__ == "__main__":
    downloader = Video()
    url = "https://tktube.com/zh/categories/fc2/"
    main_urls = downloader.get_main_urls(url)
