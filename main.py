from bs4 import BeautifulSoup
from pydantic import BaseModel
import requests
from playwright.sync_api import sync_playwright


class Video(BaseModel):
    def get_main_urls(self, url: str) -> list[str]:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            # 查找指定元素下的所有a标签
            links_container = soup.select_one("#list_videos_common_videos_list_items")
            if links_container:
                links = links_container.find_all("a", href=True)
                urls = [link["href"] for link in links]
                return urls
            else:
                return "指定的元素没有找到。"
        else:
            return "网页请求失败，状态码：" + str(response.status_code)

    def get_video_url(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)

            # 模拟点击
            page.click("#kt_player > div.fp-player")
            # 等待视频元素加载
            page.wait_for_selector("#kt_player > div.fp-player > video")

            # 获取视频的直接链接
            video_url = page.query_selector("#kt_player > div.fp-player > video").get_attribute(
                "src"
            )

            browser.close()
        return video_url

    def download_video(self, url: str, filename: str) -> str:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            return "视频下载成功"
        else:
            return "视频下载失败，状态码：" + str(response.status_code)


# 你想要获取URL的网页
downloader = Video()
url = "https://tktube.com/zh/categories/fc2/"
main_urls = downloader.get_main_urls(url)
for main_url in main_urls:
    urls = downloader.get_video_url(main_url)
    urls = downloader.download_video(urls, "test")
    break
