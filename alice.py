from __future__ import unicode_literals
import re
import os
import sys
import redis
import aiml
import json
from argparse import ArgumentParser
import requests
from bs4 import BeautifulSoup
from aip.speech import AipSpeech
from flask import Flask, request, abort, render_template
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)

from linebot.models import (RichMenu, RichMenuArea, RichMenuBounds, RichMenuSize, URIAction,
                            MessageEvent, TextMessage, TextSendMessage, ImageMessage, VideoMessage, FileMessage,
                            StickerMessage, StickerSendMessage,
                            BubbleContainer, TextComponent, BoxComponent, IconComponent, FlexSendMessage,
                            SpacerComponent, ButtonComponent, SeparatorComponent
, ImageComponent, LocationMessage, LocationSendMessage, AudioMessage
                            )
from linebot.utils import PY3

# baidu-aip for audio recognize

""" 你的 APPID AK SK """
APP_ID = '11031096'
API_KEY = 'Znj7ZUGi7HK93nDEGAXdzAjI'
SECRET_KEY = '64c3e4a4ba912a4e0dde68fafbea127e'

# 19430124 FAN Shuaishuai 's redis
HOST = "redis-13670.c8.us-east-1-4.ec2.cloud.redislabs.com"
PWD = "uOugljWUzWvmfoDuf6CRsonlrfUmYKSD"
PORT = "13670"

client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)
redis1 = redis.Redis(host=HOST, password=PWD, port=PORT, decode_responses=True)


def get_module_dir(name):
    '''
    get alice module
    :param name:
    :return:
    '''
    path = getattr(sys.modules[name], '__file__', None)
    if not path:
        raise AttributeError('module %s has not attribute __file__' % name)
    return os.path.dirname(os.path.abspath(path))

def crawl_news(number=3):
    '''
    crawl covid-19 news from Hong Kong gov
    :param number:
    :return:
    '''
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
        'max': number,
        'returnCnt': '100',

    }

    page = 'https://www.news.gov.hk/jsp/customSortNewsArticle.jsp'

    s = requests.Session()
    s.get(page, headers=head)
    s.headers.update(head)
    r = s.get(page, params=params)
    # print(r)

    soup = BeautifulSoup(r.text, 'xml')
    items = soup.find_all('item')
    # print(r.text)
    news = []
    for item in items:
        title = item.find('title').text
        img_url = 'https://www.news.gov.hk' + item.find('landingPagePreviewImage').text
        summary = item.find('articleSummary').text
        article_url = 'https://www.news.gov.hk' + item.find('generateHtmlPath').text
        news.append([title, img_url, summary, article_url])
    return news


def crawl_qa(page='https://www.who.int/news-room/q-a-detail/q-a-coronaviruses'):
    '''
    crawl covid-19 questions and answers from WHO website
    :param page:
    :return:
    '''
    r = requests.get(page)
    # print(r.text)
    soup = BeautifulSoup(r.text)
    items = soup.find_all(name='div', class_='sf-accordion__panel')
    qa = []

    for i in items:
        qa_dic = {'q': '', 'a': ''}
        q = i.find(name='a', class_='sf-accordion__link').text.strip().replace('?', '').upper()
        q = '<category><pattern>' + q + '</pattern>\n'
        a = i.find_all(name='p')[-1].get_text(strip=True)
        a = a.replace(u'/xa0', u'')
        q = q.replace(u'/xa0', u'')
        print(a)
        a = '<template>' + a + '</template>\n</category>\n'
        qa_dic['q'] = q
        qa_dic['a'] = a
        qa.append(qa_dic)
    texts_list = [i['q'] + i['a'] for i in qa]
    text = ''.join(texts_list)
    return text


def generate_aiml(name='covid'):
    '''
    generate aiml file by crawled data
    :param name:
    :return:
    '''
    text = crawl_qa()
    aiml_ = '<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<aiml version=\"1.0\">\n' + text + '</aiml>\n'
    with open(name + '.aiml', 'w', encoding='UTF-8-sig') as f:
        f.write(aiml_)


print(os.path.abspath('../templates'))
app = Flask(__name__, template_folder=os.path.abspath('../templates'))

alice_path = get_module_dir('aiml') + '/botdata/alice'
# 切换到语料库所在工作目录
os.chdir(alice_path)
generate_aiml()
alice = aiml.Kernel()
alice.learn("startup.xml")
alice.respond('LOAD ALICE')

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)

# obtain the port that heroku assigned to this app.
heroku_port = os.getenv('PORT', None)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    # if event is MessageEvent and message is TextMessage, then echo text
    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if isinstance(event.message, TextMessage):
            handle_TextMessage(event)
        if isinstance(event.message, ImageMessage):
            handle_ImageMessage(event)
        if isinstance(event.message, VideoMessage):
            handle_VideoMessage(event)
        if isinstance(event.message, AudioMessage):
            handle_AudioMessage(event)
        if isinstance(event.message, FileMessage):
            handle_FileMessage(event)
        if isinstance(event.message, StickerMessage):
            handle_StickerMessage(event)
        if isinstance(event.message, LocationMessage):
            handle_location_message(event)

        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

    return 'OK'


map = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="chrome=1">
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no, width=device-width">
    <style type="text/css">
        body, html, #container {{
            height: 100%;
            margin: 0px;
            font: 12px Arial;
        }}

        .taiwan {{
            border: solid 1px red;
            color: red;
            float: left;
            width: 50px;
            background-color: rgba(255, 0, 0, 0.1)
        }}
    </style>
    <title>Confirmed COVID-19s in past 14 days</title>
</head>
<body>
<div id="container" tabindex="0"></div>
<script src="//webapi.amap.com/ui/1.0/main.js?v=1.0.11"></script>
<script src="https://webapi.amap.com/maps?v=1.4.15&key=999bd05545f336fce91acad15209da89"></script>
<script type="text/javascript">

    var map = new AMap.Map('container', {{resizeEnable: true, zoom: 4}});
    var markers = []; //province见Demo引用的JS文件
    var provinces= {0}
    for (var i = 0; i < provinces.length; i += 1) {{
        var marker;
        if (provinces[i].type === 0) {{
            var icon = new AMap.Icon({{
                image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_rs.png',
                size: new AMap.Size(24, 34)
            }});
            marker = new AMap.Marker({{
                icon: icon,
                position: provinces[i].center.split(','),
                offset: new AMap.Pixel(-12, -12),
                zIndex: 101,
                title: provinces[i].name,
                map: map
            }});
        }} else {{
            marker = new AMap.Marker({{
                position: provinces[i].center.split(','),
                title: provinces[i].name,
                map: map
            }});
            if (provinces[i].type === 2) {{
                var content = "<div class = 'taiwan'>宝岛台湾</div>";
                baodao = new AMap.Marker({{
                    content: content,
                    position: provinces[i].center.split(','),
                    title: provinces[i].name,
                    offset: new AMap.Pixel(0, 0),
                    map: map
                }});
            }}
        }}
        markers.push(marker);
    }}
    map.setFitView();
    AMap.plugin('AMap.Geolocation', function() {{
  var geolocation = new AMap.Geolocation({{
    // 是否使用高精度定位，默认：true
    enableHighAccuracy: true,
    // 设置定位超时时间，默认：无穷大
    timeout: 10000,
    // 定位按钮的停靠位置的偏移量，默认：Pixel(10, 20)
    buttonOffset: new AMap.Pixel(10, 20),
    //  定位成功后调整地图视野范围使定位位置及精度范围视野内可见，默认：false
    zoomToAccuracy: true,     
    //  定位按钮的排放位置,  RB表示右下
    buttonPosition: 'RB'
  }})

  geolocation.getCurrentPosition()
  map.addControl(geolocation)
  AMap.event.addListener(geolocation, 'complete', onComplete)
  AMap.event.addListener(geolocation, 'error', onError)

  function onComplete (data) {{
    // data是具体的定位信息
  }}

  function onError (data) {{
    // 定位出错
  }}
}})
</script>
<script type="text/javascript" src="https://webapi.amap.com/demos/js/liteToolbar.js"></script>
</body>
</html>'''.format(redis1.get('provinces'))


@app.route('/map', methods=['GET'])
def hello_world():
    return map

# Handler function for Text Message
def handle_TextMessage(event):
    req = event.message.text
    if req.find('covid-19 map') > -1:
        bubble_string = '''
{{
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "image",
            "url": "https://www.marxist.com/images/cache/db91d266ec83a509da6989b2ca3623b4_w780_h439.JPG",
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "780:439",
            "gravity": "bottom",
            "flex": 1,
            "position": "relative",
            "action": {
              "type": "uri",
              "label": "action",
              "uri": "https://healthcarer-project.herokuapp.com/map"
            }
          }
        ]
      },
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "image",
                "url": "https://image.shutterstock.com/image-vector/hong-kong-city-line-art-260nw-609758045.jpg",
                "aspectMode": "cover",
                "size": "full"
              }
            ],
            "cornerRadius": "100px",
            "width": "72px",
            "height": "72px"
          },
          {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "text",
                "contents": [
                  {
                    "type": "span",
                    "text": "周邊疫情信息查詢",
                    "weight": "bold",
                    "color": "#000000",
                    "size": "lg"
                  }
                ],
                "size": "sm",
                "wrap": true,
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": "https://healthcarer-project.herokuapp.com/map"
                }
              },
              {
                "type": "box",
                "layout": "baseline",
                "contents": [
                  {
                    "type": "text",
                    "size": "md",
                    "color": "#bcbcbc",
                    "text": "coronavirus map",
                    "contents": [
                      {
                        "type": "span",
                        "text": "coronavirus map"
                      }
                    ],
                    "style": "italic",
                    "decoration": "underline",
                    "position": "relative"
                  }
                ],
                "spacing": "sm",
                "margin": "md"
              },
              {
                "type": "text",
                "text": "防疫地圖"
              }
            ]
          }
        ],
        "spacing": "xl",
        "paddingAll": "20px"
      }
    ],
    "paddingAll": "0px"
  }
}
        '''
        message = FlexSendMessage(alt_text="hello", contents=json.loads(bubble_string))
        line_bot_api.reply_message(
            event.reply_token,
            message
        )
    if req.find('covid-19 news') > -1:
        nums = re.findall(r"\d+\.?\d*", req)
        if len(nums) > 0:
            number = int(nums[0])
        else:
            number = 3
        variables = crawl_news(number)
        new = '''
              {{
        "type": "box",
        "layout": "vertical",
        "contents": [
          {{
            "type": "box",
            "layout": "vertical",
            "contents": [
              {{
                "type": "text",
                "text": "{0[0]}",
                "weight": "bold"
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "horizontal",
            "contents": [
              {{
                "type": "image",
                "url": "{0[1]}",
                "size": "sm",
                "aspectRatio": "1.1:1.1",
                "aspectMode": "cover",
                "align": "start",
                "position": "relative",
                "gravity": "center",
                "flex": 2,
                "margin": "none",
                "action": {{
                        "type": "uri",
                         "uri": "{0[3]}"
                          }}
              }},
              {{
                "type": "text",
                "text": "{0[2]}",
                "align": "start",
                "size": "xxs",
                "style": "normal",
                "gravity": "top",
                "position": "relative",
                "action": {{
                  "type": "uri",
                  "label": "action",
                  "uri": "{0[3]}"
                }},
                "flex": 5,
                "weight": "regular",
                "margin": "xs",
                "wrap": true,
                "color": "#84817b"
              }}
            ]
          }},
          {{
            "type": "separator",
            "margin": "md"
          }},
          {{
            "type": "separator",
            "margin": "md"
          }}
        ]
      }},'''
        news = ""
        for i in variables:
            new2 = new.format(i)
            news += new2

        bubble_string = """
{{
  "type": "bubble",
  "body": {{
    "type": "box",
    "layout": "vertical",
    "contents": [
      {{
        "type": "separator",
        "color": "#84817b"
      }},
      {{
        "type": "text",
        "text": "HK COVID-19 NEWS",
        "align": "center",
        "weight": "bold",
        "size": "xl"
      }},
      {{
        "type": "separator",
        "color": "#84817b",
        "margin": "none"
      }},
     {0}
      {{
        "type": "button",
        "action": {{
          "type": "uri",
          "label": "更多",
          "uri": "https://www.news.gov.hk/chi/categories/covid19/index.html"
        }},
        "style": "link"
      }},
      {{
        "type": "separator"
      }}
    ]
  }},
  "styles": {{
    "header": {{
      "separator": true
    }}
  }}
}}
""".format(news)
        message = FlexSendMessage(alt_text="hello", contents=json.loads(bubble_string))
        line_bot_api.reply_message(
            event.reply_token,
            message
        )

    else:
        msg = alice.respond(req)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(msg)
        )


# Handler function for Sticker Message
def handle_StickerMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )


# Handler function for Image Message
def handle_ImageMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="Nice image!")
    )


# Handler function for Video Message
def handle_VideoMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="Nice video!")
    )


# Handler function for File Message
def handle_FileMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="Nice file!")
    )


def handle_location_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        LocationSendMessage(
            title='Location', address=event.message.address,
            latitude=event.message.latitude, longitude=event.message.longitude
        )
    )


# Handler function for File Message
def handle_AudioMessage(event):
    message_content = line_bot_api.get_message_content(event.message.id).content
    res = client.asr(
        message_content, 'm4a',
        16000, {
            'dev_pid': 1737,
        })
    if 'result' in res.keys():
        text = alice.respond(res['result'][0])
    else:
        text = 'I beg your pardon'
    line_bot_api.reply_message(
        event.reply_token,

        TextSendMessage(text=text)
    )


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(host='0.0.0.0', debug=options.debug, port=heroku_port)
