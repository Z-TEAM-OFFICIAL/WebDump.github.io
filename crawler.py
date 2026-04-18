#!/usr/bin/env python3.14
import argparse
import os
import time
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

class WebDumpCrawler:
    def __init__(self, start_url, code_root, media_root, delay=1):
        self.start_url = start_url.rstrip('/')
        self.code_root = code_root
        self.media_root = media_root
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'WebDump/1.0'})
        self.visited = set()
        self.domain = urlparse(start_url).netloc

    def is_same_domain(self, url):
        return urlparse(url).netloc == self.domain

    def get_local_path(self, url, is_media):
        parsed = urlparse(url)
        path = parsed.path
        if not path or path == '/':
            path = '/index.html'
        if path.endswith('/'):
            path += 'index.html'
        path = path.lstrip('/')
        base = self.code_root if not is_media else self.media_root
        return os.path.join(base, self.domain, path)

    def download_resource(self, url, is_media):
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get('Content-Type', '')
            local_path = self.get_local_path(url, is_media)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            if 'html' in content_type and not is_media:
                return resp.text, local_path
            else:
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                return None, local_path
        except Exception as e:
            print(f"Failed {url}: {e}")
            return None, None

    def rewrite_links(self, html, base_url):
        soup = BeautifulSoup(html, 'html.parser')
        current_file = self.get_local_path(base_url, is_media=False)
        current_dir = os.path.dirname(current_file)
        for tag in soup.find_all(['a', 'link', 'script', 'img']):
            attr = None
            if tag.name == 'a':
                attr = 'href'
            elif tag.name == 'link':
                attr = 'href'
            elif tag.name == 'script':
                attr = 'src'
            elif tag.name == 'img':
                attr = 'src'
            if attr and tag.get(attr):
                raw = tag[attr]
                full = urljoin(base_url, raw)
                if self.is_same_domain(full):
                    path = urlparse(full).path
                    if any(path.endswith(ext) for ext in ['.css', '.js', '.html', '.htm']):
                        target_root = self.code_root
                    else:
                        target_root = self.media_root
                    target_path = os.path.join(target_root, self.domain, path.lstrip('/'))
                    rel = os.path.relpath(target_path, current_dir)
                    tag[attr] = rel
        return str(soup)

    def crawl(self, url=None, depth=0, max_depth=5):
        if depth > max_depth or url in self.visited:
            return
        url = url or self.start_url
        self.visited.add(url)
        print(f"Crawling: {url}")
        time.sleep(self.delay)

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get('Content-Type', '')
            is_media = not ('html' in content_type or 'css' in content_type or 'javascript' in content_type)

            if is_media:
                self.download_resource(url, is_media=True)
                return
            else:
                content, local_path = self.download_resource(url, is_media=False)
                if content is None:
                    return
                if 'html' in content_type:
                    content = self.rewrite_links(content, url)
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                if 'html' in content_type:
                    soup = BeautifulSoup(content, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        next_url = urljoin(url, link['href'])
                        if self.is_same_domain(next_url) and next_url not in self.visited:
                            self.crawl(next_url, depth+1, max_depth)
                    for tag in soup.find_all(['link', 'script', 'img']):
                        attr = 'href' if tag.name == 'link' else 'src'
                        if attr and tag.get(attr):
                            asset_url = urljoin(url, tag[attr])
                            if self.is_same_domain(asset_url):
                                self.crawl(asset_url, depth+1, max_depth)
        except Exception as e:
            print(f"Error {url}: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output-code', default='./WebDump1')
    parser.add_argument('--output-media', default='./WebDump2')
    args = parser.parse_args()
    crawler = WebDumpCrawler(args.url, args.output_code, args.output_media)
    crawler.crawl()
    print("Done.")

if __name__ == '__main__':
    main()
