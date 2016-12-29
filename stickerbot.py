# -*- coding=utf-8 -*-
import requests
import json
import time
from pprint import pprint
# import multiprocessing as mp
import threading as th
import ConfigParser
import fbchat
import datetime
import os
import os.path as osp
import urllib
from PIL import Image
from utils import mkdir_p

INIT = './stickerbot.ini'

class StickerBot(fbchat.Client):

    def __init__(self,email, password, debug=True, user_agent=None):
        fbchat.Client.__init__(self,email, password, debug, user_agent)

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
        reply = None
        if msg.is_sticker():
            print 'is sticker!'
            print 'returning:'
            reply = 'sticker!\n' + str(msg.sticker)
            
            sticker = msg.sticker
            folder = osp.join('./stickers', sticker.pack_id, sticker.sticker_id)
            tb_path, big_path = self._download(sticker, folder)
            if sticker.dynamic:
                frames = self._split_dynamic_sticker(sticker, big_path, folder)
                self.sendLocalImage(rcpt_id, message='', image=big_path) 
            
        return reply
    
    def _download(self, sticker, folder):
        mkdir_p(folder)
        thumbnail_path = osp.join(folder, 'static.png')
        urllib.urlretrieve(sticker.static_url, thumbnail_path)
        if sticker.dynamic:
            big_path = osp.join(folder, 'big.png')
            urllib.urlretrieve(sticker.url, big_path)
        return thumbnail_path, big_path

    def _split_dynamic_sticker(self, sticker, big_path, folder):
        im = Image.open(big_path) 
        w, h = im.size
        n_col = sticker.n_columns
        n_row = sticker.n_rows
        w_split, h_split = w / n_col, h / n_row
        k = 1
        croppeds = []
        for i in range(0, h, h_split):
            for j in range(0, w, w_split):
                box = (j, i, j + w_split, i + h_split)
                s = im.crop(box)
                mkdir_p(folder)
                s.save(osp.join(folder, '%02d.png' % k))
                croppeds.append(s)
                k += 1
                if k > sticker.frame_count:
                    return croppeds
        

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
            print 'Message is_sticker() Error:', str(e)
            print self.meta
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
        self.url = m['spriteURI'] or ''
        self.sticker_id = str(m['stickerID'])
        self.frame_count = m['frameCount']
        self.frame_rate = m['frameRate']
        self.n_columns = m['framesPerCol']
        self.n_rows = m['framesPerRow']
        self.w, self.h = m['width'], m['height']
        self.pack_id = str(m['packID'])
        self.dynamic = (m['frameCount'] > 1)
        
    def __str__(self):
        s = 'id:' + self.sticker_id + '\n'
        s += 'dynamic:' + str(self.dynamic) + '\n'
        s += 'url:' + self.url
        return s
        
    def dump(self, info_path):
        pass
    

def main():
    config = ConfigParser.ConfigParser()
    config.read(INIT)
    
    email = config.get('Basic', 'email')
    password = config.get('Basic', 'password')
    bot = StickerBot(email, password)

    # block here: listen to messages
    bot.listen()


if __name__ == '__main__':
    main()
