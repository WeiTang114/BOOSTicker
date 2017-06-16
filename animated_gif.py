# -*- coding=utf-8 -*-
import subprocess as sp
import math
from PIL import Image

def change_gif_speed(in_gif, out_gif, speed_ratio):
    orig_duration_ms = get_gif_frame_duration(in_gif)
    duration_ms = int(math.ceil(float(orig_duration_ms) / float(speed_ratio)))
    cmd = ['convert',
           '-delay', str(duration_ms),
           '-loop', '0',
           in_gif,
           out_gif]

    print 'command:' + ' '.join(cmd)
    sp.call(cmd)


def get_gif_frame_duration(gif):
    output = sp.check_output('identify -verbose %s | grep Delay' % gif,
                             shell=True)

    ms = output.split('\n')[0].split(' ')[-1].split('x')[0].strip()
    return ms


