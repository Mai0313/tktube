from bs4 import BeautifulSoup
from pydantic import BaseModel
import requests


class Video(BaseModel):
    def get_main_urls(self, url) -> list[str]:
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

    def get_video_url(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            video = soup.select_one("video")
            if video:
                video_url = video["src"]
                return video_url
            else:
                return "没有找到视频元素。"
        else:
            return "网页请求失败，状态码：" + str(response.status_code)

    def download_video(self, url, filename) -> str:
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
    print(main_url)
    urls = downloader.get_video_url(main_url)
    print(urls)
