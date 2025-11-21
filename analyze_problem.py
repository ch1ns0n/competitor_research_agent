from scrapers.util import smart_get

asin = "B0BKH8HDWK"     # atau apa saja
url = f"https://www.amazon.com/product-reviews/{asin}/?pageNumber=1"

resp = smart_get(url)
html = resp.text

print(html[:2000])

print("data-hook review:", "data-hook='review'" in html)