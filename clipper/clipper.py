#!/usr/bin/env python3
import os
import random
import sys
import argparse

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


def get_audio(youtube_id):
    filepath = '/tmp/{}.mp4'.format(youtube_id)
    if not os.path.exists(filepath):
        yt = YouTube("http://www.youtube.com/watch?v={}".format(youtube_id))
        yt.set_filename(youtube_id)
        print(yt.videos)
        video = yt.filter('mp4')[-1]
        video.download('/tmp')
    return AudioFileClip(filepath)


def run(options):
    audio = get_audio(options.audio)
    period = find_audio_period(audio)
    print("Found audio period of {:.2f}".format(period))
    result = collage(
        options.videos, period * options.multiplier, options.length,
        options.seed)
    result = result.set_audio(audio.subclip(0, options.length).audio_fadeout(2))
    print("Writing")
    result.write_videofile(
        options.output, fps=30, bitrate=options.bitrate, codec='libx264')


def main():
    parser = argparse.ArgumentParser(description="Make a collage of videos")
    parser.add_argument('--length', type=int,
                        help='Length of the resulting video in seconds')
    parser.add_argument('--multiplier', type=float, default=1.0,
                        help='How often to change the video')
    parser.add_argument('--audio',
                        default="sESVVM7FiLo",
                        #default="ZpHC2KFJn-o",
                        help='The youtube video id to use the sound from')
    parser.add_argument('--output',
                        default="result.mp4",
                        help='The name of the output file')
    parser.add_argument('--bitrate',
                        default="5000k",
                        help='The name of the output file')
    parser.add_argument('--seed', default="amaze me", help='Random seed')
    parser.add_argument('videos', nargs='+', help='Video files to process')
    args = parser.parse_args()

    run(options)


if __name__ == '__main__':
    main()
