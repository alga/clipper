#!/usr/bin/env python3
import os
import random
import glob
import argparse

from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.editor import AudioFileClip
from pytube import YouTube

from moviepy.audio.tools.cuts import find_audio_period
from moviepy.video.fx import all as vfx


def collage(files, period=2.0, length=15.0, seed="amaze me", shuffle=False):
    print("Loading...")
    vids = [VideoFileClip(fn, audio=False) for fn in files]
    rand = random.Random(seed)
    print("Done")

    offsets = []
    offset = 0
    for vid in vids:
        offsets.append(offset)
        offset += vid.duration
    footage_length = offset

    subclips = []
    starts = []
    for i in range(int(length / period)):
        while True:
            start = rand.uniform(0, footage_length - period)
            vid_index = offsets.index(max(o for o in offsets if o <= start))
            vid = vids[vid_index]
            vid_start = start - offsets[vid_index]
            # Make sure the clip does not span past the end of the clip
            if vid_start + period <= vid.duration:
                # Make sure clips don't overlap
                distances = [abs(s-start) for s in starts]
                if not distances or min(distances) > period:
                    break
        starts.append(start)
        print("Cutting {} at {:.2f}".format(vid.filename, vid_start))
        subclips.append((start, vid.subclip(vid_start, vid_start + period)))

    if not shuffle:
        subclips.sort()

    subclips = [clip for (start, clip) in subclips]

    print("Concatenating")
    total = concatenate_videoclips(subclips)
    return total


def get_audio(youtube_id):
    matches = glob.glob(f'/tmp/{youtube_id}.*')
    filepath = matches[0] if matches else None
    if filepath is None or not os.path.exists(filepath):
        yt = YouTube("http://www.youtube.com/watch?v={}".format(youtube_id))
        print(yt.streams.filter(only_audio=True).all())
        video = yt.streams.filter(only_audio=True).first()
        video.download('/tmp', youtube_id)
        filepath = glob.glob(f'/tmp/{youtube_id}.*')[0]
    return AudioFileClip(filepath)


def run(options):
    if options.youtube_audio:
        audio = get_audio(options.youtube_audio)
    else:
        audio = AudioFileClip(options.audio_path)
    period = find_audio_period(audio)
    print("Found audio period of {:.2f}".format(period))
    if options.length is None:
        options.length = audio.duration
    result = collage(
        options.videos, period * options.multiplier, options.length,
        options.seed, shuffle=options.shuffle)
    result = result.set_audio(audio.subclip(0, options.length).audio_fadeout(2))
    if options.flip:
        print("Rotating")
        result = result.fx(vfx.rotate, 180)
    if options.preview:
        result.preview(fps=10)
        return
    print("Writing")
    result.write_videofile(
        options.output, fps=30, bitrate=options.bitrate, codec='libx264')


def main():
    parser = argparse.ArgumentParser(description="Make a collage of videos")
    parser.add_argument('--length', type=int,
                        help='Length of the resulting video in seconds')
    parser.add_argument('--multiplier', type=float, default=1.0,
                        help='How often to change the video')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--youtube-audio',
                       help='The youtube video id to use the sound from.')
    group.add_argument('--audio-path', help='File path of the audio track.')
    parser.add_argument('--output',
                        default="result.mp4",
                        help='The name of the output file')
    parser.add_argument('--bitrate',
                        default="5000k",
                        help='The name of the output file')
    parser.add_argument('--seed', default="amaze me", help='Random seed')
    parser.add_argument('--shuffle', action='store_true', help='Shuffle clips')
    parser.add_argument('--flip', action='store_true',
                        help='Rotate by 180 degrees')
    parser.add_argument('--preview', action='store_true',
                        help='Show video instead of rendering it.')
    parser.add_argument('videos', nargs='+', help='Video files to process')
    options = parser.parse_args()

    run(options)


if __name__ == '__main__':
    main()
