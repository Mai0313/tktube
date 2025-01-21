import re
import json
from typing import TYPE_CHECKING
import asyncio
from pathlib import Path

from bs4 import BeautifulSoup
import anyio
import httpx
import pandas as pd
from pydantic import BaseModel, model_validator
from src.config import Config
from rich.console import Console

# 改用 async 版本的 playwright
from playwright.async_api import async_playwright

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

    async def parse_content(self, content: str) -> list[VideoModel]:
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
        video_informations_list = [vi.model_dump() for vi in video_informations]
        data = pd.DataFrame(video_informations_list)
        log_path = Path(self.output_path)
        log_path.mkdir(exist_ok=True, parents=True)
        data.to_csv(log_path / "log.csv", index=False)
        return video_informations

    async def get_main_urls(self, url: str) -> list[VideoModel]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(url)
            content = await page.content()
            await browser.close()
        video_informations = await self.parse_content(content=content)
        return video_informations

    async def _get_cookies(self) -> None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(self.url)
            await page.click("a[href='/login']")
            await page.fill("input[name='email']", self.username)
            await page.fill("input[name='password']", self.password)
            await page.click("button#submitlogin")
            await page.wait_for_load_state("networkidle")

            cookies = await context.cookies()
            # with open("cookies.json", "w", encoding="utf-8") as f:
            #     json.dump(cookies, f)
            async with await anyio.open_file("cookies.json", "w", encoding="utf-8") as f:
                await f.write(json.dumps(cookies))

            await browser.close()

    async def _download(self, title: str, download_link: str) -> str:
        output_path = Path(self.output_path)
        output_path.mkdir(exist_ok=True, parents=True)

        output_file = output_path / f"{title}.mp4"

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", download_link) as response:
                async with await anyio.open_file(output_file, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)

        console.print(f"[green]下載完成:[/green] {output_file.as_posix()}")
        return output_file.as_posix()

    async def download_video(self, video_info: VideoModel, sem: asyncio.Semaphore) -> None:
        """非同步下載單部影片的流程：
        1. 取得或載入 cookies
        2. 使用 cookies 訪問下載頁面
        3. 抓取下載連結
        4. 實際下載影片
        其中使用 semaphore 限制同時只能處理 5 部影片。
        """
        async with sem:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()

                # 讀取 cookies，如不存在則先取得
                cookie_path = Path("cookies.json")
                if not cookie_path.exists():
                    await self._get_cookies()

                async with await anyio.open_file("cookies.json", encoding="utf-8") as f:
                    cookies = json.loads(await f.read())

                await context.add_cookies(cookies)
                page = await context.new_page()

                # 進入相對應的下載頁面
                await page.goto("https://appscyborg.com/video-cyborg")

                # 填写视频 URL
                await page.fill("input[name='url']", video_info.url)

                # 点击下载按钮
                await page.click("button#singleinput")

                # 等待下载按钮出现
                download_button = await page.wait_for_selector(
                    "a[href*='download']", timeout=60000
                )

                download_link = None
                if download_button:
                    download_link = await download_button.get_attribute("href")
                    await page.click("a[href*='download']")

                await browser.close()

            if download_link:
                await self._download(title=video_info.title, download_link=download_link)
            else:
                console.print(f"[red]無法取得下載連結[/red]：{video_info.url}")


async def main(config: Config, max_processor: int, max_videos: int) -> None:
    url = "https://tktube.com/zh/categories/fc2/"
    downloader = Video(url=url, **config.model_dump())
    main_urls = await downloader.get_main_urls(url)
    main_urls = main_urls[:max_videos]
    sem = asyncio.Semaphore(max_processor)
    tasks = []
    for video_info in main_urls:
        tasks.append(asyncio.create_task(downloader.download_video(video_info, sem)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    config = Config()

    asyncio.run(main(config=config, max_processor=5, max_videos=5))
