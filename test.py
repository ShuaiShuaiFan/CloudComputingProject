from bs4 import BeautifulSoup
import requests

head = {
    "accept": "text/html, */*; q=0.01",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-HK,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,en-US;q=0.5",
    'referer': 'https://www.news.gov.hk/chi/categories/covid19/index.html',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
}
params = {
    'language': 'chi',
    'category': 'covid19',
    'max': '4',
    'returnCnt': '100',

}

page = 'https://www.news.gov.hk/jsp/customSortNewsArticle.jsp'

s = requests.Session()
s.get(page, headers=head)
s.headers.update(head)
r = s.get(page, params=params)
# print(r)

soup = BeautifulSoup(r.text, 'xml')
items=soup.find_all('item')
# print(r.text)
news=[]
for item in items:
    title=item.find('title').text
    img_url='https://www.news.gov.hk'+item.find('landingPagePreviewImage').text
    summary=item.find('articleSummary').text
    article_url='https://www.news.gov.hk'+item.find('generateHtmlPath').text
    news.append([title,img_url,summary,article_url])
print(news)
