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

import mltmaker


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


class CollageMaker:

    def __init__(
        self,
        output,
        files,
        bitrate,
        audio,
        period=2.0,
        length=15.0,
        seed="amaze me",
        shuffle=False,
        flip=False,
        preview=False,
    ):
        self.output = output
        self.files = files
        self.bitrate = bitrate
        self.audio = audio
        self.period = period
        self.length = length
        self.seed = seed
        self.shuffle = shuffle
        self.flip = flip
        self.preview = preview

    def load(self):
        footage = []
        offset = 0
        for fn in self.files:
            print("\r", fn, end="")
            with VideoFileClip(fn, audio=False) as vid:
                footage.append(VidData(offset, fn, vid.duration))
            offset += vid.duration

        return footage, offset

    def collage(self):

        print("Loading...")
        footage, footage_length = self.load()
        print("\nDone")

        rand = random.Random(self.seed)

        subclips = []
        starts = []

        def time_random():
            """A random poke into the "timeline" of the footage.

            Favors long videos.  Results in clusters sometimes.
            """
            start = rand.uniform(0, footage_length - self.period)
            vid = max(v for v in footage if v.start <= start)
            return start, vid

        bag = footage[:]

        def round_robin(bag):
            """Pick videos from a bag and show random clips from them."""
            if not bag:
                bag += footage
            vid = rand.choice(bag)
            bag.remove(vid)
            start = rand.uniform(vid.start, vid.start + vid.duration - self.period)
            return start, vid

        for i in range(int(self.length / self.period)):
            while True:
                # Random shots into the timeline result in weird clusters and in many clips
                # not being used at all.  Let's try to combine poking a random poke into
                # each clip with poking into the timeline.
                start, vid = round_robin(bag) if bag else time_random()
                skip = start - vid.start
                # Make sure the clip does not span past the end of the clip
                if skip + self.period <= vid.duration:
                    # Make sure clips don't overlap
                    distances = [abs(s - start) for s in starts]
                    if not distances or min(distances) > self.period * 2:
                        break
            starts.append(start)
            subclips.append(ClipInfo(start, skip, vid.filename, self.period))

        if not self.shuffle:
            subclips.sort()

        return self.write(subclips)

    def write(self, subclips):
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
            if sub.w != 1920:
                sub = sub.resize((1920, 1080))
            clips.append(sub)
            if len(clips) >= LIMIT or clip is subclips[-1]:
                batchfile = f"temp{batch:04d}.mp4"
                print(f"Writing {batchfile}", flush=True)
                batchvid = concatenate_videoclips(clips, method="compose")
                batchvid.write_videofile(
                    batchfile,
                    fps=30,
                    bitrate=self.bitrate,
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
        result = concatenate_videoclips(cut)

        result = result.set_audio(self.audio.subclip(0, self.length).audio_fadeout(2))
        if self.flip:
            print("Rotating")
            result = result.fx(vfx.rotate, 180)
        if self.preview:
            result.preview(fps=10)
            return
        print("Writing")
        result.write_videofile(
            self.output, fps=30, bitrate=self.bitrate, codec="libx264"
        )


class MLTCollageMaker(CollageMaker):

    def load(self):
        footage = []
        offset = 0
        for fn in self.files:
            print("\r", fn, end="")
            vid = mltmaker.get_video_metadata(fn)
            footage.append(VidData(offset, fn, vid["duration"]))
            offset += vid["duration"]

        return footage, offset

    def write(self, subclips):
        mltclips = []
        for clip in subclips:
            mltclips.append((os.path.basename(clip.filename), clip.skip, clip.duration))

        mltmaker.generate_mlt_file(self.files, mltclips, self.output)


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

    if not options.shotcut:
        collage_maker_class = CollageMaker
    else:
        collage_maker_class = MLTCollageMaker

    clm = collage_maker_class(
        options.output,
        options.videos,
        options.bitrate,
        audio,
        period * options.multiplier,
        options.length,
        options.seed,
        shuffle=options.shuffle,
        flip=options.flip,
        preview=options.preview,
    )
    clm.collage()


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
    parser.add_argument(
        "--shotcut",
        action="store_true",
        help="Output Shotcut's MLT file rather than render video",
    )
    parser.add_argument("videos", nargs="+", help="Video files to process")
    options = parser.parse_args()

    run(options)


if __name__ == "__main__":
    main()
