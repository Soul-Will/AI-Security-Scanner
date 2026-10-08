CRAWLER_SCRIPT_TEMPLATE = """
import sys
import os
import json
import socket
import ipaddress
import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright

target_url = sys.argv[1]
output_dir = sys.argv[2]
os.makedirs(output_dir, exist_ok=True)

SSRF_DENYLIST = [
    ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"), ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("fc00::/7"), ipaddress.ip_network("fe80::/10"), ipaddress.ip_network("::1/128")
]

def check_ssrf(url):
    try:
        hostname = urlparse(url).hostname
        if not hostname: return False
        addr_info = socket.getaddrinfo(hostname, None)
        for info in addr_info:
            ip = ipaddress.ip_address(info[4][0])
            for net in SSRF_DENYLIST:
                if ip in net: return False
        return True
    except: return False

MAX_PAGES = 1000
MAX_DEPTH = 5
MAX_ASSET_SIZE = 20 * 1024 * 1024

visited = set()
queue = [(target_url, 0)]
api_endpoints = set()
forms = []
html_s = 0; css_s = 0; js_s = 0
h_tr = False; c_tr = False; j_tr = False

async def crawl():
    global html_s, css_s, js_s, h_tr, c_tr, j_tr
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        ctx = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()
        
        async def on_response(resp):
            global html_s, css_s, js_s, h_tr, c_tr, j_tr
            req = resp.request
            rt = req.resource_type
            if rt in ('fetch', 'xhr'): api_endpoints.add(req.url)
            try:
                if rt == 'stylesheet' and not c_tr:
                    b = await resp.body()
                    if css_s + len(b) <= MAX_ASSET_SIZE:
                        with open(f"{output_dir}/bundle.css", "ab") as f: f.write(b + b"\\n")
                        css_s += len(b)
                    else: c_tr = True
                elif rt == 'script' and not j_tr:
                    b = await resp.body()
                    if js_s + len(b) <= MAX_ASSET_SIZE:
                        with open(f"{output_dir}/bundle.js", "ab") as f: f.write(b + b"\\n")
                        js_s += len(b)
                    else: j_tr = True
            except: pass

        page.on("response", on_response)
        
        async def handle_route(route):
            if not check_ssrf(route.request.url):
                print(f"Aborting SSRF violation: {route.request.url}")
                await route.abort()
            else: await route.continue_()

        await ctx.route("**/*", handle_route)
        
        target_domain = urlparse(target_url).netloc
        while queue and len(visited) < MAX_PAGES:
            url, depth = queue.pop(0)
            if url in visited or depth > MAX_DEPTH: continue
            visited.add(url)
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                html = await page.content()
                if not h_tr:
                    html_b = html.encode('utf-8')
                    if html_s + len(html_b) <= MAX_ASSET_SIZE:
                        with open(f"{output_dir}/bundle.html", "ab") as f: f.write(html_b + b"\\n")
                        html_s += len(html_b)
                    else: h_tr = True

                fs = await page.evaluate('''() => Array.from(document.forms).map(form => ({ action: form.action, method: form.method, fields: Array.from(form.elements).map(e => e.name || e.id).filter(Boolean) }))''')
                for f in fs: forms.append({"url": url, **f})
                
                hrefs = await page.evaluate('''() => Array.from(document.links).map(a => a.href)''')
                for href in hrefs:
                    if urlparse(href).netloc == target_domain and href not in visited:
                        queue.append((href, depth + 1))
            except Exception as e: print(f"Crawl err {url}: {e}")
        await browser.close()
        
    with open(f"{output_dir}/api_endpoints.json", "w") as f: json.dump(list(api_endpoints), f)
    with open(f"{output_dir}/forms.json", "w") as f: json.dump(forms, f)
    with open(f"{output_dir}/summary.json", "w") as f: json.dump({
        "crawl_pages_discovered": len(visited), "crawl_forms_discovered": len(forms),
        "crawl_api_endpoints_discovered": len(api_endpoints), "html_truncated": h_tr,
        "css_truncated": c_tr, "js_truncated": j_tr
    }, f)

asyncio.run(crawl())
"""
