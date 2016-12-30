# BOOSTicker
Boost all you FB stickers.

# Requirements

- [fbchat](https://github.com/carpedm20/fbchat). 
  - Note that [this patch](https://github.com/carpedm20/fbchat/pull/74/files) must be appllied for **group** messaging.
  - And [this patch](https://github.com/carpedm20/fbchat/pull/77/commits/62c5ae793269dbcc4bdd5b5cb12865a6546fda15) must be applied for **client.listen()** to work.
- [images2gif](https://bitbucket.org/bench/images2gif.py)
  - [This fix](http://stackoverflow.com/questions/19149643/error-in-images2gif-py-with-globalpalette?answertab=active#tab-top) must be applied.

# Usage

## Start the Bot
1. Create an FB account, get the email and password.
2. Copy "stickerbot.ini.example" to "stickerbot.ini" and fill in your email/password.
3. Start the program and leave it running:
```bash
python stickerbot.py
```

## Play with the Bot
Send a dynamic sticker to your bot and get a FAST GIF! 

