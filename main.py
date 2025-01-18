import re
import json
from typing import TYPE_CHECKING
from pathlib import Path

from bs4 import BeautifulSoup
import httpx
from pydantic import BaseModel, model_validator
from rich.console import Console
from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from bs4.element import Tag

console = Console()


class VideoModel(BaseModel):
    url: str
    title: str
    rating: str

    @model_validator(mode="after")
    def _rename_title(self) -> "VideoModel":
        pattern = r"[^\w\s\u4e00-\u9fff-]"
        cleaned_title = re.sub(pattern, "", self.title)
        self.title = cleaned_title.replace(" ", "_")
        return self


class Video(BaseModel):
    url: str
    username: str
    password: str
    output_path: str

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

    def _get_cookies(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url)
            page.click("a[href='/login']")
            page.fill("input[name='email']", f"{self.username}")
            page.fill("input[name='password']", f"{self.password}")
            page.click("button#submitlogin")
            page.wait_for_load_state("networkidle")
            cookies = context.cookies()
            with open("cookies.json", "w") as f:
                json.dump(cookies, f)
            browser.close()

    def _download(self, title: str, download_link: str) -> str:
        with httpx.stream("GET", download_link) as response:
            output_path = Path(self.output_path)
            output_path.mkdir(exist_ok=True, parents=True)
            output_file = output_path / f"{title}.mp4"
            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            return output_file.as_posix()

    def download_video(self, video_info: VideoModel) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            cookie_path = Path("cookies.json")
            if not cookie_path.exists():
                self._get_cookies()
            with open("cookies.json") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)

            page = context.new_page()
            page.goto("https://appscyborg.com/video-cyborg")

            # 填写视频 URL
            page.fill("input[name='url']", video_info.url)

            # 点击下载按钮
            page.click("button#singleinput")

            # 等待下载按钮出现
            download_button = page.wait_for_selector("a[href*='download']", timeout=60000)

            if download_button:
                download_link = download_button.get_attribute("href")
                page.click("a[href*='download']")
            browser.close()
        self._download(title=video_info.title, download_link=download_link)


if __name__ == "__main__":
    from src.config import Config

    config = Config()
    url = "https://tktube.com/zh/categories/fc2/"
    downloader = Video(url=url, **config.model_dump())
    main_urls = downloader.get_main_urls(url)[:1]
    for main_url in main_urls:
        downloader.download_video(main_url)
