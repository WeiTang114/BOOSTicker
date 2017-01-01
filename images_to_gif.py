# -*- coding=utf-8 -*-
import subprocess as sp
from PIL import Image
import imageio
import images2gif
import visvis.vvmovie.images2gif as images2gif_visvis
import moviepy 

def images_to_gif(gif_path, image_paths, duration_ms, method='imagemagick'):
    if method == 'imagemagick':
        return images_to_gif_imagemagick(gif_path, image_paths, duration_ms)
    elif method == 'images2gif':
        return images_to_gif_images2gif(gif_path, image_paths, duration_ms)
    elif method == 'imageio':
        return images_to_gif_imageio(gif_path, image_paths, duration_ms)
    elif method == 'moviepy':
        return images_to_gif_movie(gif_path, image_paths, duration_ms)
    raise ValueError('method should be one of "imagemagick" or "images2gif" or "imageio"i or "moviepy"')

def images_to_gif_imagemagick(gif_path, image_paths, duration_ms):
    cmd = ['convert',
           '-dispose', '2',
           '-delay', str(duration_ms),
           '-loop', '0',] + \
           image_paths + \
           [gif_path]
    
    print 'command:' + ' '.join(cmd)
    sp.call(cmd)

def images_to_gif_images2gif(gif_path, image_paths, duration_ms):
    """
    Some blocks at the edge are weird.
    """
    ims = [Image.open(p) for p in image_paths]
    images2gif.writeGif(gif_path, ims, duration=duration_ms / 1000., dither=1, dispose=2)

def images_to_gif_imageio(gif_path, image_paths, duration_ms):
    """
    http://stackoverflow.com/questions/753190/programmatically-generate-video-or-animated-gif-in-python
    the speed is very weird
    """
    print 'imageio. duration:', duration_ms / 1000.
    images = [imageio.imread(p) for p in image_paths]
    imageio.mimsave(gif_path, images, duration=duration_ms / 1000.)
    

def images_to_gif_moviepy(gif_path, image_paths, duration_ms):
    """
    just fails with some error..........
    """
    my_clip = moviepy.editor.ImageSequenceClip(image_paths, fps=1./duration_ms)
    my_clip.write_gif(gif_path)

