import requests
import pdfplumber
import re
import os
import redis
from bs4 import BeautifulSoup

# 19430124 FAN Shuaishuai 's redis
HOST = "redis-13670.c8.us-east-1-4.ec2.cloud.redislabs.com"
PWD = "uOugljWUzWvmfoDuf6CRsonlrfUmYKSD"
PORT = "13670"


def geocode(location):
    parameters = {'address': location, 'key': '69b47d1b0be4c946ffbbd65e705b6320'}
    base = 'http://restapi.amap.com/v3/geocode/geo'
    response = requests.get(base, parameters)
    answer = response.json()
    if len(answer['geocodes']) == 0:
        return None
    return answer['geocodes'][0]['location']


def get_locations():
    url = 'https://www.chp.gov.hk/files/pdf/building_list_chi.pdf'
    r = requests.get(url)
    my_file = "building_list_chi.pdf"
    with open("building_list_chi.pdf", "wb") as code:
        code.write(r.content)

    pdf = pdfplumber.open("building_list_chi.pdf")
    locations = []
    for page in pdf.pages:
        # print(page.extract_text())
        for pdf_table in page.extract_tables():
            table = []
            cells = []
            for row in pdf_table:
                if not any(row):
                    # 如果一行全为空，则视为一条记录结束
                    if any(cells):
                        table.append(cells)
                        cells = []
                elif all(row):
                    # 如果一行全不为空，则本条为新行，上一条结束
                    if any(cells):
                        table.append(cells)
                        cells = []
                    table.append(row)
                else:
                    if len(cells) == 0:
                        cells = row
                    else:
                        for i in range(len(row)):
                            if row[i] is not None:
                                cells[i] = row[i] if cells[i] is None else cells[i] + row[i]
            for row in table:
                line = [re.sub('\s+', '', cell) if cell is not None else None for cell in row]
                locations.append("香港" + line[1])
                print(line)
            print('---------- 分割线 ----------')

    pdf.close()
    if os.path.exists(my_file):
        # 删除文件，可使用以下两种方法。
        os.remove(my_file)
    return locations





locations = get_locations()
markers = []
for item in locations:
    location = geocode(item)
    if not location:
        continue
    markers.append({"name": item, "center": location, "type": 0, "subDistricts": []})
print('process done')
redis1 = redis.Redis(host=HOST, password=PWD, port=PORT, decode_responses=True)
redis1.set('provinces', str(markers))
print('save redis done')


