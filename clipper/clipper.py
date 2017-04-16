#!/usr/bin/env python3
import sys
from moviepy.editor import VideoFileClip, concatenate_videoclips
import random
#from moviepy.video.tools.cuts import find_video_period
#from moviepy.audio.tools.cuts import find_audio_period


def collage(files, period=2.0, length=15.0, seed="amaze me"):
    print("Loading...")
    vids = [VideoFileClip(fn, audio=False) for fn in files]
    rand = random.Random(seed)
    print("Done")

    subclips = []
    for i in range(int(length / period)):
        vid = rand.choice(vids)
        start = rand.uniform(0, vid.duration - period)
        print("Cutting {} at {:.2f}".format(vid.filename, start))
        subclips.append(vid.subclip(start, start + period))

    print("Concatenating")
    total = concatenate_videoclips(subclips)
    return total


def main():
    result = collage(sys.argv[1:])
    print("Writing")
    result.write_videofile(
        'result.mp4',
        fps=30, bitrate="5000k", codec='libx264')


if __name__ == '__main__':
    main()
