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
import traceback
from PIL import Image
from utils import mkdir_p
from images_to_gif import images_to_gif
from animated_gif import change_gif_speed
import user

sys.path.insert(0, './externals/fbchat')
import fbchat
from fbchat.models import ThreadType, FBchatFacebookError, ThreadLocation

INIT = './stickerbot.ini'
DEFAULT_SPEED = 2.0
PENDING_THREAD_DURATION_SEC = 30

class StickerBot(fbchat.Client):

    def __init__(self,email, password, logfile, debug=True, user_agent=None):
        fbchat.Client.__init__(self,email, password)
        self.logfile = logfile
        self.user_configs_file = './users_confs.txt'
        self.user_configs = self._load_userconfs()
        self.debug = debug
        self.last_check_pending = 0
        print 'init: user conig', self.user_configs

    def _load_userconfs(self):
        return user.load_users(self.user_configs_file)

    def _add_user_config(self, uid, is_group, speed, enabled):
        self.user_configs[uid] = user.User(uid, is_group, speed, enabled)
        self._write_userconfs()

    def _write_userconfs(self):
        return user.write_users(self.user_configs, self.user_configs_file)

    def onMessage(self, mid=None, author_id=None, message=None, thread_id=None,
                  thread_type=ThreadType.USER, ts=None, metadata=None, msg={}):
        self.markAsDelivered(author_id, mid) #mark delivered
        self.markAsRead(author_id) #mark read

        print("%s said: %s"%(author_id, message))

        print 'meta:'
        pprint(msg['delta'])
        meta = msg['delta']

        #if you are not the author, echo
        if str(author_id) != str(self.uid):
            is_group = (thread_type == ThreadType.GROUP)
            rcpt_id = author_id if not is_group else self._get_threadid(meta)

            msg = Message(mid, author_id, message, meta)
            print 'rcpt_id', rcpt_id, 'is_group', is_group
            replymsg = self._handle(rcpt_id, thread_type, msg)
            if replymsg:
                self.sendMessage(replymsg, rcpt_id, thread_type)

    def doOneListen(self, markAlive=True):
        """
        Does one cycle of the listening loop.
        This method is useful if you want to control fbchat from an external event loop
        :param markAlive: Whether this should ping the Facebook server before running
        :type markAlive: bool
        :return: Whether the loop should keep running
        :rtype: bool
        """
        try:
            if markAlive:
                self._ping(self.sticky, self.pool)
            content = self._pullMessage(self.sticky, self.pool)
            if content:
                self._parseMessage(content)

            # only query for pending threads once every N seconds
            if time.time() - self.last_check_pending > PENDING_THREAD_DURATION_SEC:
                pending_threads = self.fetchThreadList(0, 20, ThreadLocation.PENDING)
                for t in pending_threads:
                    self._handle_pending_thread(t)
                self.last_check_pending = time.time()

        except KeyboardInterrupt:
            return False
        except requests.Timeout:
            pass
        except requests.ConnectionError:
            # If the client has lost their internet connection, keep trying every 30 seconds
            time.sleep(30)
        except FBchatFacebookError as e:
            # Fix 502 and 503 pull errors
            if e.request_status_code in [502, 503]:
                self.req_url.change_pull_channel()
                self.startListening()
            else:
                raise e
        except Exception as e:
            return self.onListenError(exception=e)

        return True

    def _is_group(self, msg_metadata):
        if 'otherUserFbId' in msg_metadata['messageMetadata']['threadKey']:
            return False
        else:
            # 'threadFbId'
            return True

    def _get_threadid(self, msg_metadata):
        return msg_metadata['messageMetadata']['threadKey']['threadFbId']

    def _handle(self, rcpt_id, thread_type, msg):
        # parsed = json.loads(msg)
        # print json.dumps(msg, indent=4, sort_keys=True)
        is_group = (thread_type == ThreadType.GROUP)
        if not rcpt_id in self.user_configs:
            self._add_user_config(rcpt_id, is_group, DEFAULT_SPEED, enabled=True)
            self.sendMessage('你好。想查詢有什麼功能請打 /help', rcpt_id, thread_type)

        user = self.user_configs[rcpt_id]
        text = msg.text.strip()
        reply = None

        if msg.is_sticker():
            print 'is sticker!'
            print msg.sticker.n_columns, msg.sticker.n_rows

            if user.enabled:
                sticker = msg.sticker
                folder = osp.join('./stickers', sticker.pack_id, sticker.sticker_id)
                tb_path, big_path = self._get_or_download_sticker(sticker, folder)
                if sticker.dynamic:
                    framepaths = self._split_dynamic_sticker(sticker, big_path, folder)
                    speed = user.speed
                    method = 'imagemagick'
                    gif_path = osp.join(folder, 'hey_%f_%s.gif' % (speed, method))
                    print 'speed:', speed, ' framerate:', sticker.frame_rate

                    override = False
                    if not osp.isfile(gif_path) or override:
                        images_to_gif(gif_path, framepaths, 1000. / (sticker.frame_rate * speed), method)

                    self.sendLocalImage(thread_id=rcpt_id, message='', image_path=gif_path, thread_type=thread_type)
                    sticker.dump(osp.join(folder, 'sticker.json'))
                    self.log('sent to %s, is_group=%d, packid=%s, stickerid=%s' % (rcpt_id, is_group, sticker.pack_id, sticker.sticker_id))
            else:
                print 'disabled'

        if msg.is_gif():
            print 'is gif!'

            if user.enabled:
                gif = msg.gif
                folder = osp.join('./gifs', gif.id)
                path = self._get_or_download_gif(gif, folder)
                speed = user.speed
                new_gif_path = osp.join(folder, 'hey_%f.gif' % (speed))

                override = False
                if not osp.isfile(new_gif_path) or override:
                    change_gif_speed(path, new_gif_path, speed)


                self.sendLocalImage(thread_id=rcpt_id, message='', image_path=new_gif_path, thread_type=thread_type)
                gif.dump(osp.join(folder, 'gif.json'))
                self.log('sent to %s, is_group=%d, gifid=%s' % (rcpt_id, is_group, gif.id))
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
                traceback.print_exc()
                reply = '格式: speed <up/down/0.8>'

        elif text.lower() == '/stop':
            self._add_user_config(rcpt_id, is_group, user.speed, False)
            options = ['我去冬眠嚕。', 'ㄅㄅ。', 'Stop all function. ', '我也累了，請讓我一個人靜一靜。']
            reply = random.choice(options) + '重新啟動請輸入 /start'

        elif text.lower() == '/start':
            self._add_user_config(rcpt_id, is_group, user.speed, True)
            options = ['啟動！', '讓我們吵吵鬧鬧一輩子吧！', '貼圖加速模式已開啟。', '上工囉。']
            reply = random.choice(options) + '關閉我請輸入 /stop'

        elif text.lower().startswith('/give '):
            try:
                tokens = text[6:].strip().split(' ', 1)
                if len(tokens) == 1:
                    raise ValueError('no "what"')
                whom = tokens[0].strip()
                what = tokens[1].strip()

                if whom.lower() == 'me':
                    whom = 'OK'

                reply = '%s, here you are:\nhttp://lmgtfy.com/?q=%s' % (whom, '+'.join(what.split()))

            except Exception, e:
                print str(e)
                traceback.print_exc()
                reply = '格式: /give <who> <what>'

        elif text.lower() == '/help':
            reply = """動態貼圖/動態GIF : 加速
靜態貼圖 : 沒用
/start : 啟動
/stop : 停用
speed <up/down/2.5> : 加速/減速/設定速度倍數。 (一定倍數以上無效)
            """

        else: print 'nothing'

        return reply

    def _get_or_download_sticker(self, sticker, folder):
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


    def _get_or_download_gif(self, gif, folder):
        mkdir_p(folder)
        path = osp.join(folder, 'animated.gif')
        if not osp.isfile(path):
            urllib.urlretrieve(gif.url, path)

        return path


    def _split_dynamic_sticker(self, sticker, big_path, folder):
        im = Image.open(big_path).convert('RGBA')

        # paste the (may be) transparent image on the white bg
        # if not this, the background sometimes become "black"
        bg = Image.new('RGBA', im.size, (255,255,255,255))
        bg.paste(im, (0,0), mask=im)
        im = bg

        w, h = im.size
        print 'Imagesize:', w, h
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


    def _handle_pending_thread(self, thread):
        """
        Pending threads will go into "inbox" thread list and be removed from
        "pending" thread list when a message is sent back.
        """

        uid = thread.uid
        self.markAsRead(uid)
        self._add_user_config(uid, is_group=False, speed=DEFAULT_SPEED, enabled=True)
        self.sendMessage('你好。想查詢有什麼功能請打 /help', uid)


    def log(self, msg):
        if not osp.isfile(self.logfile):
            open(self.logfile, 'w+').close()
        timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.logfile, 'a') as f:
            print>>f, '[%s] %s' % (timestr, msg)


class Message:
    def __init__(self, mid, author_id, message, metadata_delta):
        self.mid = mid
        self.author_id = author_id
        self.text = message
        self.meta = metadata_delta
        if self.is_sticker():
            self.sticker = Sticker(self.sticker_meta(), self.sticker_url())
        if self.is_gif():
            self.gif = Gif(self.gif_meta(), self.gif_url())

    def is_sticker(self):
        try:
            return 'sticker_attachment' in self.meta['attachments'][0]['mercury']
        except (KeyError, IndexError), e:
            # print 'Message is_sticker() Error:', str(e)
            # print self.meta
            pass
        return False

    def is_gif(self):
        try:
            return self.meta['attachments'][0]['mercury'] \
                    ['blob_attachment']['__typename'] == 'MessageAnimatedImage'

        except (KeyError, IndexError), e:
            # print 'Message is_sticker() Error:', str(e)
            # print self.meta
            pass
        return False

    def sticker_meta(self):
        if not self.is_sticker(): return None
        return self.meta['attachments'][0]['mercury']['sticker_attachment']

    def sticker_url(self):
        if not self.is_sticker(): return None
        return self.sticker_meta()['url']

    def gif_meta(self):
        if not self.is_gif(): return None
        return self.meta['attachments'][0]['mercury']['blob_attachment']

    def gif_url(self):
        if not self.is_gif(): return None
        # url is None, but preview_url is good
        return self.gif_meta()['preview_image']['uri']

class Sticker:
    def __init__(self, sticker_meta, sticker_url):
        m = sticker_meta
        self.meta = sticker_meta
        self.static_url = sticker_url
        if 'sprite_image_2x' in m:
            self.url = m['sprite_image_2x']['uri']
        else:
            self.url = m['url']
        self.sticker_id = str(m['id'])
        self.frame_count = m['frame_count']
        self.frame_rate = float(m['frame_rate'])
        self.n_columns = m['frames_per_row']
        self.n_rows = m['frames_per_column']
        self.w, self.h = m['width'], m['height']
        self.pack_id = str(m['pack']['id'])
        self.dynamic = (m['frame_count'] > 1)

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


class Gif:
    def __init__(self, gif_meta, gif_url):
        m = gif_meta
        self.meta = gif_meta
        self.url = gif_url
        self.w = m['original_dimensions']['x']
        self.h = m['original_dimensions']['y']
        self.id = str(m['legacy_attachment_id'])

    def dump(self, info_path):
        folder = osp.dirname(info_path)
        mkdir_p(folder)
        with open(info_path, 'w+') as f:
            json.dump(self.__dict__, f, indent=4, sort_keys=True)

def load_configs():
    if 'HEROKU' in os.environ:
        # on heroku
        email = os.environ['EMAIL']
        password = os.environ['PASSWORD']
        logfile = os.environ['LOGFILE']
    else:
        # on regular linux
        config = ConfigParser.ConfigParser()
        config.read(INIT)

        email = config.get('Basic', 'email')
        password = config.get('Basic', 'password')
        logfile = config.get('Basic', 'logfile')

    return email, password, logfile


def main():
    email, password, logfile = load_configs()
    bot = StickerBot(email, password, logfile)

    # block here: listen to messages
    bot.listen()


if __name__ == '__main__':
    main()
