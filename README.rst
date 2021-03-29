clipper -- automatically cut videos out of footage
==================================================

This script downloads a given youtube video, calculates the audio beat
rate, and uses it as a soundtrack for a video of random beat-matched
clips of your footage.

Here's an example of output: https://youtu.be/BMyqhdsilVo

The invocation to to get this video was::

    bin/clipper --youtube-audio aiumJ_nDkhs \
               --length 227 --bitrate 5000k \
               --output sierranevada.mp4 \
               --multiplier 4 --seed sierranevada \
               ~/Video/Sierra\ Nevada\ bike/YDXJ*.mp4
