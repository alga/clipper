#!/usr/bin/env python3
import os
import random
import sys

from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.editor import AudioFileClip
from pytube import YouTube

#from moviepy.video.tools.cuts import find_video_period
from moviepy.audio.tools.cuts import find_audio_period


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

def get_audio(youtube_id="9pqa1Y0pSMg"):
    filepath = '/tmp/{}.mp4'.format(youtube_id)
    if not os.path.exists(filepath):
        yt = YouTube("http://www.youtube.com/watch?v={}".format(youtube_id))
        yt.set_filename(youtube_id)
        video = yt.get('mp4', '720p')
        video.download('/tmp')
    return AudioFileClip(filepath)

def main():
    audio = get_audio()
    period = find_audio_period(audio) * 4
    length = 15
    print("Found audio period of {:.2f}".format(period))
    result = collage(sys.argv[1:], period, length)
    result = result.set_audio(audio.subclip(0, length).audio_fadeout(2))
    print("Writing")
    result.write_videofile(
        'result.mp4',
        fps=30, bitrate="5000k", codec='libx264')


if __name__ == '__main__':
    main()
