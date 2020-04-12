from __future__ import unicode_literals

import os
import sys
import redis
import aiml
import json
from argparse import ArgumentParser

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
, ImageComponent, LocationMessage, LocationSendMessage
                            )
from linebot.utils import PY3


def get_module_dir(name):
    path = getattr(sys.modules[name], '__file__', None)
    if not path:
        raise AttributeError('module %s has not attribute __file__' % name)
    return os.path.dirname(os.path.abspath(path))


print(os.path.abspath('../templates'))
app = Flask(__name__, template_folder=os.path.abspath('../templates'))

alice_path = get_module_dir('aiml') + '/botdata/alice'
# 切换到语料库所在工作目录
os.chdir(alice_path)
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
rich_menu_to_create = RichMenu(
    size=RichMenuSize(width=2500, height=843),
    selected=False,
    name="Nice richmenu",
    chat_bar_text="Tap here",
    areas=[RichMenuArea(
        bounds=RichMenuBounds(x=0, y=0, width=2500, height=843),
        action=URIAction(label='Go to line.me', uri='https://line.me'))]
)
rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
print(rich_menu_id)


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
        body, html, #container {
            height: 100%;
            margin: 0px;
            font: 12px Arial;
        }

        .taiwan {
            border: solid 1px red;
            color: red;
            float: left;
            width: 50px;
            background-color: rgba(255, 0, 0, 0.1)
        }
    </style>
    <title>Marker example</title>
</head>
<body>
<div id="container" tabindex="0"></div>
<script src="https://webapi.amap.com/js/marker.js"></script>
<script src="https://webapi.amap.com/maps?v=1.4.15&key=999bd05545f336fce91acad15209da89"></script>
<script type="text/javascript">

    var map = new AMap.Map('container', {resizeEnable: true, zoom: 4});
    var markers = []; //province见Demo引用的JS文件
    for (var i = 0; i < provinces.length; i += 1) {
        var marker;
        if (provinces[i].type === 0) {
            var icon = new AMap.Icon({
                image: 'https://vdata.amap.com/icons/b18/1/2.png',
                size: new AMap.Size(24, 24)
            });
            marker = new AMap.Marker({
                icon: icon,
                position: provinces[i].center.split(','),
                offset: new AMap.Pixel(-12, -12),
                zIndex: 101,
                title: provinces[i].name,
                map: map
            });
        } else {
            marker = new AMap.Marker({
                position: provinces[i].center.split(','),
                title: provinces[i].name,
                map: map
            });
            if (provinces[i].type === 2) {
                var content = "<div class = 'taiwan'>宝岛台湾</div>";
                baodao = new AMap.Marker({
                    content: content,
                    position: provinces[i].center.split(','),
                    title: provinces[i].name,
                    offset: new AMap.Pixel(0, 0),
                    map: map
                });
            }
        }
        markers.push(marker);
    }
    map.setFitView();
</script>
<script type="text/javascript" src="https://webapi.amap.com/demos/js/liteToolbar.js"></script>
</body>
</html>'''


@app.route('/map', methods=['GET'])
def hello_world():
    return map


# Handler function for Text Message
def handle_TextMessage(event):
    req = event.message.text
    if req == 'map':
        bubble_string = """{
  "type": "bubble",
  "hero": {
    "type": "image",
    "url": "https://inews.gtimg.com/newsapp_bt/0/11308840372/1000",
    "size": "full",
    "aspectRatio": "20:13",
    "aspectMode": "cover",
    "action": {
      "type": "uri",
      "uri": "https://z.cbndata.com/2019-nCoV/index.html"
    }
  },
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "separator",
        "margin": "none"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "image",
            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/01_1_cafe.png",
            "size": "xs",
            "aspectRatio": "1:1",
            "aspectMode": "cover",
            "align": "start",
            "position": "relative",
            "gravity": "center",
            "flex": 2
          },
          {
            "type": "text",
            "text": "内地流感情况",
            "align": "start",
            "size": "md",
            "style": "normal",
            "gravity": "center",
            "position": "relative",
            "action": {
              "type": "uri",
              "label": "action",
              "uri": "https://healthcarer-project.herokuapp.com/map"
            },
            "flex": 5
          }
        ]
      },
      {
        "type": "separator"
      },
      {
        "type": "separator",
        "margin": "md"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "image",
            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/01_1_cafe.png",
            "size": "xs",
            "aspectRatio": "1:1",
            "aspectMode": "cover",
            "align": "start",
            "position": "relative",
            "gravity": "center",
            "flex": 2
          },
          {
            "type": "text",
            "text": "国际流感情况",
            "align": "start",
            "size": "md",
            "style": "normal",
            "gravity": "center",
            "position": "relative",
            "action": {
              "type": "uri",
              "label": "action",
              "uri": "http://linecorp.com/"
            },
            "flex": 5
          }
        ]
      },
      {
        "type": "separator"
      },
      {
        "type": "separator",
        "margin": "md"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "image",
            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/01_1_cafe.png",
            "size": "xs",
            "aspectRatio": "1:1",
            "aspectMode": "cover",
            "align": "start",
            "position": "relative",
            "gravity": "center",
            "flex": 2
          },
          {
            "type": "text",
            "text": "内地流感情况",
            "align": "start",
            "size": "md",
            "style": "normal",
            "gravity": "center",
            "position": "relative",
            "action": {
              "type": "uri",
              "label": "action",
              "uri": "http://linecorp.com/"
            },
            "flex": 5
          }
        ]
      },
      {
        "type": "separator"
      }
    ]
  },
  "styles": {
    "header": {
      "separator": true
    }
  }
}"""
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


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(host='0.0.0.0', debug=options.debug, port=heroku_port)
