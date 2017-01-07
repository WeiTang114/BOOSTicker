# -*- coding=utf-8 -*-
import requests
import json
import time
from pprint import pprint
import threading as th
import ConfigParser
import datetime
import sys
import os
import os.path as osp
import urllib
import datetime
import inspect
import random
from PIL import Image
from utils import mkdir_p
from images_to_gif import images_to_gif
import user

sys.path.append('./externals/fbchat')
import fbchat

INIT = './stickerbot.ini'
DEFAULT_SPEED = 2.0

class StickerBot(fbchat.Client):

    def __init__(self,email, password, logfile, debug=True, user_agent=None):
        fbchat.Client.__init__(self,email, password, debug, user_agent)
        self.logfile = logfile
        self.user_configs_file = './users_confs.txt'
        self.user_configs = self._load_userconfs()
        print 'init: user conig', self.user_configs

    def _load_userconfs(self):
        return user.load_users(self.user_configs_file)

    def _add_user_config(self, uid, is_group, speed, enabled):
        self.user_configs[uid] = user.User(uid, is_group, speed, enabled)
        self._write_userconfs()

    def _write_userconfs(self):
        return user.write_users(self.user_configs, self.user_configs_file)

    def on_message(self, mid, author_id, author_name, message, metadata):
        self.markAsDelivered(author_id, mid) #mark delivered
        self.markAsRead(author_id) #mark read

        print("%s said: %s"%(author_id, message))
    
        print 'meta:'
        pprint(metadata['delta'])

        #if you are not the author, echo
        if str(author_id) != str(self.uid):
            is_group = self._is_group(metadata)
            msg_type = 'group' if is_group else 'user'
            rcpt_id = author_id if not is_group else self._get_threadid(metadata)

            msg = Message(mid, author_id, author_name, message, metadata['delta'])
            print 'rcpt_id', rcpt_id, 'is_group', is_group
            replymsg = self._handle(rcpt_id, is_group, msg, msg_type)
            if replymsg:
                self.send(rcpt_id, replymsg, message_type=msg_type)

    def _is_group(self, msg_metadata):
        if 'otherUserFbId' in msg_metadata['delta']['messageMetadata']['threadKey']:
            return False
        else:
            # 'threadFbId'
            return True

    def _get_threadid(self, msg_metadata):
        return msg_metadata['delta']['messageMetadata']['threadKey']['threadFbId'] 

    def _handle(self, rcpt_id, is_group, msg, msg_type='user'):
        # parsed = json.loads(msg) 
        # print json.dumps(msg, indent=4, sort_keys=True)
        if not rcpt_id in self.user_configs:
            self._add_user_config(rcpt_id, is_group, DEFAULT_SPEED, enabled=True)
            self.send(rcpt_id, '你好。想查詢有什麼功能請打 /help', message_type=msg_type)
        
        user = self.user_configs[rcpt_id]
        text = msg.text.strip()
        reply = None

        if msg.is_sticker():
            print 'is sticker!'
            print msg.sticker.n_columns, msg.sticker.n_rows

            if user.enabled:
                sticker = msg.sticker
                folder = osp.join('./stickers', sticker.pack_id, sticker.sticker_id)
                tb_path, big_path = self._get_or_download(sticker, folder)
                if sticker.dynamic:
                    framepaths = self._split_dynamic_sticker(sticker, big_path, folder)
                    speed = user.speed
                    method = 'imagemagick'
                    gif_path = osp.join(folder, 'hey_%f_%s.gif' % (speed, method))
                    print 'speed:', speed, ' framerate:', sticker.frame_rate
                    
                    override = False
                    if not osp.isfile(gif_path) or override:
                        images_to_gif(gif_path, framepaths, 1000. / (sticker.frame_rate * speed), method)

                    self.sendLocalImage(rcpt_id, message='', image=gif_path, message_type=msg_type) 
                    sticker.dump(osp.join(folder, 'sticker.json'))
                    self.log('sent to %s, is_group=%d, packid=%s, stickerid=%s' % (rcpt_id, is_group, sticker.pack_id, sticker.sticker_id))
            else:
                print 'disabled'

        elif text.lower().startswith('speed') or text.lower().startswith('/speed'):
            speed = user.speed
            try:
                if len(msg.text.strip().split()) > 1:
                    arg = msg.text.strip().split()[1]
                    if arg == 'up':
                        speed *= 2. 
                    elif arg == 'down':
                        speed *= 0.5
                    elif float(arg) != 0:
                        speed = float(arg)
                self._add_user_config(rcpt_id, is_group, speed, user.enabled)
                reply = '速度: %fX' % speed
            except Exception, e:
                print str(e)
                reply = '格式: speed <up/down/0.8>'

        elif text.lower() == '/stop':
            self._add_user_config(rcpt_id, is_group, speed, False)
            options = ['我去冬眠嚕。', 'ㄅㄅ。', 'Stop all function. ', '我也累了，請讓我一個人靜一靜。']
            reply = random.choice(options) + '重新啟動請輸入 /start'

        elif text.lower() == '/start':
            self._add_user_config(rcpt_id, is_group, speed, True)
            options = ['啟動！', '讓我們吵吵鬧鬧一輩子吧！', '貼圖加速模式已開啟。', '上工囉。']
            reply = random.choice(options) + '關閉我請輸入 /stop'
            
        elif text.lower() == '/help':
            reply = """動態貼圖 : 加速
靜態貼圖 : 沒用
/start : 啟動
/stop : 停用
speed <up/down/2.5> : 加速/減速/設定速度倍數。 (一定倍數以上無效) 
            """

        return reply
    
    def _get_or_download(self, sticker, folder):
        mkdir_p(folder)
        thumbnail_path = osp.join(folder, 'static.png')
        big_path = None
        if not osp.isfile(thumbnail_path):
            urllib.urlretrieve(sticker.static_url, thumbnail_path)
        if sticker.dynamic:
            big_path = osp.join(folder, 'big2.png')
            if not osp.isfile(big_path):
                urllib.urlretrieve(sticker.url, big_path)
        return thumbnail_path, big_path

    def _split_dynamic_sticker(self, sticker, big_path, folder):
        im = Image.open(big_path) 

        # paste the (may be) transparent image on the white bg
        # if not this, the background sometimes become "black"
        bg = Image.new('RGBA', im.size, (255,255,255,255))
        bg.paste(im, (0,0), mask=im)
        im = bg

        w, h = im.size
        n_col = sticker.n_columns
        n_row = sticker.n_rows
        w_split, h_split = w / n_col, h / n_row
        k = 1
        paths = []
        for i in range(n_row):
            for j in range(n_col):
                path = osp.join(folder, '%02d.png' % k)
                if not osp.isfile(path):
                    left = j * w_split
                    right = left + w_split
                    top = i * h_split
                    bottom = top + h_split
                    box = (left, top, left + w_split, top + h_split)
                    s = im.crop(box)
                    mkdir_p(folder)
                    s.save(path)

                paths.append(path)
                k += 1
                if k > sticker.frame_count:
                    return paths 
            
    
    def log(self, msg):
        if not osp.isfile(self.logfile):
            open(self.logfile, 'w+').close()
        timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.logfile, 'a') as f:
            print>>f, '[%s] %s' % (timestr, msg)


class Message:
    def __init__(self, mid, author_id, author_name, message, metadata_delta):
        self.mid = mid
        self.author_id = author_id
        self.author_name = author_name
        self.text = message
        self.meta = metadata_delta
        if self.is_sticker():
            self.sticker = Sticker(self.sticker_meta(), self.sticker_url())

    def is_sticker(self):
        try:
            return self.meta['attachments'][0]['mercury']['attach_type'] == 'sticker'
        except (KeyError, IndexError), e:
            # print 'Message is_sticker() Error:', str(e)
            # print self.meta
            pass
        return False

    def sticker_meta(self):
        if not self.is_sticker(): return None
        return self.meta['attachments'][0]['mercury']['metadata']

    def sticker_url(self):
        if not self.is_sticker(): return None
        return self.meta['attachments'][0]['mercury']['url']
        

class Sticker: 
    def __init__(self, sticker_meta, sticker_url):
        m = sticker_meta
        self.meta = sticker_meta
        self.static_url = sticker_url
        self.url = m['spriteURI2x'] or ''
        self.sticker_id = str(m['stickerID'])
        self.frame_count = m['frameCount']
        self.frame_rate = float(m['frameRate'])
        self.n_columns = m['framesPerRow']
        self.n_rows = m['framesPerCol']
        self.w, self.h = m['width'], m['height']
        self.pack_id = str(m['packID'])
        self.dynamic = (m['frameCount'] > 1)
        
    def __str__(self):
        s = 'id:' + self.sticker_id + '\n'
        s += 'dynamic:' + str(self.dynamic) + '\n'
        s += 'url:' + self.url
        return s

    def dump(self, info_path):
        folder = osp.dirname(info_path)
        mkdir_p(folder)
        with open(info_path, 'w+') as f:
            json.dump(self.__dict__, f, indent=4, sort_keys=True)
    

def main():
    config = ConfigParser.ConfigParser()
    config.read(INIT)
    
    email = config.get('Basic', 'email')
    password = config.get('Basic', 'password')
    logfile = config.get('Basic', 'logfile')
    bot = StickerBot(email, password, logfile)

    # block here: listen to messages
    bot.listen()


if __name__ == '__main__':
    main()
