#!/usr/bin/env python3
import os
import random
import glob
import argparse
from dataclasses import dataclass


from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.editor import AudioFileClip
from pytube import YouTube

from moviepy.audio.tools.cuts import find_audio_period
from moviepy.video.fx import all as vfx


@dataclass(order=True)
class VidData:
    start: float
    filename: str
    duration: float


@dataclass(order=True)
class ClipInfo:
    start: float  # timecode of the start of the clip in the total footage
    skip: float  # start of the subclip relative to clip
    filename: str
    duration: float


def collage(files, bitrate, period=2.0, length=15.0, seed="amaze me", shuffle=False):

    print("Loading...")
    footage = []
    offset = 0
    for fn in files:
        print("\r", fn, end="")
        with VideoFileClip(fn, audio=False) as vid:
            footage.append(VidData(offset, fn, vid.duration))
        offset += vid.duration
    footage_length = offset
    print("\nDone")

    rand = random.Random(seed)

    subclips = []
    starts = []

    def time_random():
        """A random poke into the "timeline" of the footage.

        Favors long videos.  Results in clusters sometimes.
        """
        start = rand.uniform(0, footage_length - period)
        vid = max(v for v in footage if v.start <= start)
        return start, vid

    bag = footage[:]
    def round_robin(bag):
        """Pick videos from a bag and show random clips from them."""
        if not bag:
            bag += footage
        vid = rand.choice(bag)
        bag.remove(vid)
        start = rand.uniform(vid.start, vid.start + vid.duration - period)
        return start, vid

    for i in range(int(length / period)):
        while True:
            # Random shots into the timeline result in weird clusters and in many clips
            # not being used at all.  Let's try to combine poking a random poke into
            # each clip with poking into the timeline.
            start, vid = round_robin(bag) if bag else time_random()
            vid_index = footage.index(vid)
            skip = start - vid.start
            # Make sure the clip does not span past the end of the clip
            if skip + period <= vid.duration:
                # Make sure clips don't overlap
                distances = [abs(s - start) for s in starts]
                if not distances or min(distances) > period * 2:
                    break
        starts.append(start)
        subclips.append(ClipInfo(start, skip, vid.filename, period))

    if not shuffle:
        subclips.sort()

    print("Cutting")
    clips = []
    vids = []
    batches = []
    batch = 0
    LIMIT = 20

    for clip in subclips:
        print(f"Cutting {clip.filename} at {clip.skip}")
        vid = VideoFileClip(clip.filename, audio=False)
        vids.append(vid)
        sub = vid.subclip(clip.skip, clip.skip + clip.duration)
        clips.append(sub)
        if len(clips) >= LIMIT or clip is subclips[-1]:
            batchfile = f"temp{batch:04d}.mp4"
            print(f"Writing {batchfile}", flush=True)
            batchvid = concatenate_videoclips(clips)
            batchvid.write_videofile(
                batchfile,
                fps=30,
                bitrate=bitrate,
                codec="libx264",
                logger=None,
            )
            batches.append(batchfile)
            batch += 1
            clips = []
            for vid in vids:
                vid.close()
            vids = []

    print("Concatenating")
    def feed(subclips):
        for fn in subclips:
            print(fn, flush=True)
            yield fn
    cut = [VideoFileClip(clip, audio=False) for clip in feed(batches)]
    total = concatenate_videoclips(cut)
    return total


def get_audio(youtube_id):
    matches = glob.glob(f"/tmp/{youtube_id}.*")
    filepath = matches[0] if matches else None
    if filepath is None or not os.path.exists(filepath):
        yt = YouTube("http://www.youtube.com/watch?v={}".format(youtube_id))
        print(yt.streams.filter(only_audio=True).all())
        video = yt.streams.filter(only_audio=True).first()
        video.download("/tmp", youtube_id)
        filepath = glob.glob(f"/tmp/{youtube_id}.*")[0]
    return AudioFileClip(filepath)


def run(options):
    if options.youtube_audio:
        audio = get_audio(options.youtube_audio)
    else:
        audio = AudioFileClip(options.audio_path)
    period = find_audio_period(audio)
    print("Found audio period of {:.4f}".format(period))
    if options.length is None:
        options.length = audio.duration
    result = collage(
        options.videos,
        options.bitrate,
        period * options.multiplier,
        options.length,
        options.seed,
        shuffle=options.shuffle,
    )
    result = result.set_audio(audio.subclip(0, options.length).audio_fadeout(2))
    if options.flip:
        print("Rotating")
        result = result.fx(vfx.rotate, 180)
    if options.preview:
        result.preview(fps=10)
        return
    print("Writing")
    result.write_videofile(
        options.output, fps=30, bitrate=options.bitrate, codec="libx264"
    )


def main():
    parser = argparse.ArgumentParser(description="Make a collage of videos")
    parser.add_argument(
        "--length", type=int, help="Length of the resulting video in seconds"
    )
    parser.add_argument(
        "--multiplier", type=float, default=1.0, help="How often to change the video"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--youtube-audio", help="The youtube video id to use the sound from."
    )
    group.add_argument("--audio-path", help="File path of the audio track.")
    parser.add_argument(
        "--output", default="result.mp4", help="The name of the output file"
    )
    parser.add_argument("--bitrate", default="5000k", help="The output bitrate")
    parser.add_argument("--seed", default="amaze me", help="Random seed")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle clips")
    parser.add_argument("--flip", action="store_true", help="Rotate by 180 degrees")
    parser.add_argument(
        "--preview", action="store_true", help="Show video instead of rendering it."
    )
    parser.add_argument("videos", nargs="+", help="Video files to process")
    options = parser.parse_args()

    run(options)


if __name__ == "__main__":
    main()
