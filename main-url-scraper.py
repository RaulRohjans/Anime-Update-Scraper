import requests
import cloudscraper
from bs4 import BeautifulSoup

# url = 'https://anime-update.com/'
url = 'https://anime-update.com/animelist/genre/?years%5B0%5D=2021&years%5B1%5D=2020&years%5B2%5D=2019&years%5B3%5D=2018&years%5B4%5D=2017&years%5B5%5D=2016&years%5B6%5D=2015&years%5B7%5D=2014&years%5B8%5D=2013&years%5B9%5D=2012&years%5B10%5D=2011&years%5B11%5D=2010&years%5B12%5D=2009&years%5B13%5D=2008&years%5B14%5D=2007&years%5B15%5D=2006&years%5B16%5D=2005&years%5B17%5D=2004&years%5B18%5D=2003&years%5B19%5D=2002&years%5B20%5D=2001&years%5B21%5D=2000&years%5B22%5D=1990&years%5B23%5D=1980&years%5B24%5D=1970&page=1'

# To get these vars, please use google chrome network tools
CLOUDFLARE_COOKIE = 'cf_clearance=kCXn6ZYHhu.U17Mi_XyLfAasgoKqwjXDOlmtg6uuQvg-1637867503-0-150'
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36'
            
headers = {
  'authority': 'anime-update.com',
  'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
  'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
  'sec-ch-ua-mobile': '?0',
  'user-agent': USER_AGENT,
  'cookie': CLOUDFLARE_COOKIE,
  'sec-fetch-site': 'none',
  'sec-fetch-mode': 'navigate',
  'sec-fetch-dest': 'document',
  'sec-fetch-user': '?1',
  'upgrade-insecure-requests': '1',
  'accept-language': 'en-US,en;q=0.9',
  'accept-encoding': 'gzip, deflate'
}

i = 1
while True:
	print("Starting page " + str(i))
	pager_url = url[:-1]
	pager_url = pager_url + str(i)

	session = cloudscraper.create_scraper()
	page = session.get(pager_url, headers=headers)
	# print(page)

	soup = BeautifulSoup(page.content, "lxml")
	div_tags = soup.find_all("div", class_="col-sm-6")

	for div in div_tags:
		if div.a is not None and div.a.text != "Anime List" and div.a.text != "Contact Us":
			with open('anime-update-scraped.txt', 'a+') as file_object:
				file_object.write("https://anime-update.com" + div.a['href'])
				file_object.write("\n")
				file_object.close()

	if i == 92:
		print("Done")
		break
	else:
		i = i + 1

