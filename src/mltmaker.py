#!/usr/bin/env python3
"""
Shotcut MLT Generator

This script generates an MLT file compatible with Shotcut video editor based on
a provided list of video files and clip information. It uses ffprobe to detect
video metadata and creates an MLT structure matching Shotcut's native format.

Usage:
    - Modify the clips list with your video clip information
    - Run the script
    - Import the generated output.mlt file into Shotcut
"""
import subprocess
import json
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import hashlib
import datetime


metadata_cache = {}

def get_video_metadata(video_path):
    """
    Get metadata (duration, resolution, frame rate) from a video file using ffprobe.

    Args:
        video_path (str): Path to the video file

    Returns:
        dict: Dictionary containing duration, width, height, and frame_rate
    """
    global metadata_cache
    if video_path in metadata_cache:
        return metadata_cache[video_path].copy()

    if not os.path.exists(video_path):
        print(f"Error: File not found - {video_path}")
        return None

    # FFprobe command to get video metadata in JSON format
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # Initialize default values
        metadata = {
            "duration": 0,
            "width": 1920,
            "height": 1080,
            "frame_rate_num": 30000,
            "frame_rate_den": 1001,
            "creation_time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "colorspace": "709",
            "color_trc": "1",
            "sample_rate": 48000,
            "audio_channels": 2,
            "audio_codec": "aac",
        }

        # Extract format information
        if "format" in data:
            if "duration" in data["format"]:
                metadata["duration"] = float(data["format"]["duration"])

            if "tags" in data["format"] and "creation_time" in data["format"]["tags"]:
                metadata["creation_time"] = data["format"]["tags"]["creation_time"]

        # Find the video stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                # Get resolution
                metadata["width"] = stream.get("width", 1920)
                metadata["height"] = stream.get("height", 1080)

                # Get frame rate
                if "r_frame_rate" in stream:
                    fr_parts = stream["r_frame_rate"].split("/")
                    if len(fr_parts) == 2:
                        metadata["frame_rate_num"] = int(fr_parts[0])
                        metadata["frame_rate_den"] = (
                            int(fr_parts[1]) if int(fr_parts[1]) > 0 else 1
                        )
                    elif len(fr_parts) == 1:
                        metadata["frame_rate_num"] = int(float(fr_parts[0]))
                        metadata["frame_rate_den"] = 1

                # Get codec info
                if "codec_name" in stream:
                    metadata["codec_name"] = stream["codec_name"]
                if "pix_fmt" in stream:
                    metadata["pix_fmt"] = stream["pix_fmt"]
                if "colorspace" in stream:
                    metadata["colorspace"] = stream["colorspace"]
                if "color_trc" in stream:
                    metadata["color_trc"] = stream["color_trc"]

            elif stream.get("codec_type") == "audio":
                if "sample_rate" in stream:
                    metadata["sample_rate"] = int(stream["sample_rate"])
                if "channels" in stream:
                    metadata["audio_channels"] = stream["channels"]
                if "codec_name" in stream:
                    metadata["audio_codec"] = stream["codec_name"]

        metadata_cache[video_path] = metadata.copy()
        return metadata

    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error parsing ffprobe output for {video_path}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def time_to_timecode(seconds):
    """Convert seconds to Shotcut's timecode format HH:MM:SS.SSS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{msecs:03d}"


def calculate_hash(filename):
    """Generate a hash similar to what Shotcut uses for resource identification"""
    return hashlib.md5(filename.encode("utf-8")).hexdigest()


def generate_mlt_file(video_files, clips, output_file="output.mlt"):
    """
    Generate an MLT file for Shotcut with the specified video clips.

    Args:
        video_files (list): List of video file paths
        clips (list): List of tuples (filename, start_time, duration)
        output_file (str): Output MLT file name
    """
    # Get first video metadata for profile settings
    profile_metadata = None
    for video_path in video_files:
        metadata = get_video_metadata(video_path)
        if metadata:
            profile_metadata = metadata
            break

    if not profile_metadata:
        print("Warning: Could not detect video properties, using default HD profile")
        profile_metadata = {
            "width": 1920,
            "height": 1080,
            "frame_rate_num": 30000,
            "frame_rate_den": 1001,
        }

    # Calculate aspect ratio
    gcd = lambda a, b: a if b == 0 else gcd(b, a % b)
    width, height = profile_metadata["width"], profile_metadata["height"]
    divisor = gcd(width, height)
    display_aspect_num = width // divisor
    display_aspect_den = height // divisor

    # Process video files and clips to determine timeline duration
    video_metadata = {}
    filename_to_path = {}
    chain_elements = []

    # Create root MLT element
    mlt = ET.Element(
        "mlt",
        {
            "LC_NUMERIC": "C",
            "version": "7.22.0",
            "title": "Shotcut version 24.04.01",
            "producer": "main_bin",
        },
    )

    # Add profile
    profile = ET.SubElement(
        mlt,
        "profile",
        {
            "description": f"{width}x{height} {profile_metadata['frame_rate_num']}/{profile_metadata['frame_rate_den']} fps",
            "width": str(width),
            "height": str(height),
            "progressive": "1",
            "sample_aspect_num": "1",
            "sample_aspect_den": "1",
            "display_aspect_num": str(display_aspect_num),
            "display_aspect_den": str(display_aspect_den),
            "frame_rate_num": str(profile_metadata["frame_rate_num"]),
            "frame_rate_den": str(profile_metadata["frame_rate_den"]),
            "colorspace": "709",
        },
    )

    # Process all video files
    for i, video_path in enumerate(video_files):
        filename = os.path.basename(video_path)
        filename_to_path[filename] = video_path

        # Get metadata
        metadata = get_video_metadata(video_path)
        if not metadata:
            print(f"Warning: Could not get metadata for {video_path}, using defaults")
            metadata = profile_metadata.copy()

        video_metadata[filename] = metadata

        # Calculate duration in frames and timecode
        fps = metadata["frame_rate_num"] / metadata["frame_rate_den"]
        duration_frames = int(metadata["duration"] * fps)
        duration_tc = time_to_timecode(metadata["duration"])

        # Create chain element for main_bin
        chain_bin = ET.SubElement(
            mlt, "chain", {"id": f"chain{i*2}", "out": duration_tc}
        )

        # Add essential properties
        ET.SubElement(chain_bin, "property", {"name": "length"}).text = f"{duration_tc}"
        ET.SubElement(chain_bin, "property", {"name": "eof"}).text = "pause"
        ET.SubElement(chain_bin, "property", {"name": "resource"}).text = video_path
        ET.SubElement(chain_bin, "property", {"name": "mlt_service"}).text = (
            "avformat-novalidate"
        )

        # Add video stream metadata
        ET.SubElement(chain_bin, "property", {"name": "meta.media.nb_streams"}).text = (
            "5"  # Typical for GoPro
        )
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.stream.type"}
        ).text = "video"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.stream.frame_rate"}
        ).text = str(fps)
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.stream.sample_aspect_ratio"}
        ).text = "0"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.width"}
        ).text = str(metadata["width"])
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.height"}
        ).text = str(metadata["height"])
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.pix_fmt"}
        ).text = metadata["pix_fmt"]
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.sample_aspect_ratio"}
        ).text = "1"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.colorspace"}
        ).text = metadata["colorspace"]
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.0.codec.name"}
        ).text = metadata["codec_name"]

        # Add audio stream metadata
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.1.stream.type"}
        ).text = "audio"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.1.codec.sample_fmt"}
        ).text = "fltp"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.1.codec.sample_rate"}
        ).text = str(metadata["sample_rate"])
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.1.codec.channels"}
        ).text = str(metadata["audio_channels"])
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.1.codec.name"}
        ).text = metadata["audio_codec"]

        # Add general properties
        ET.SubElement(chain_bin, "property", {"name": "seekable"}).text = "1"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.sample_aspect_num"}
        ).text = "1"
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.sample_aspect_den"}
        ).text = "1"
        ET.SubElement(chain_bin, "property", {"name": "audio_index"}).text = "1"
        ET.SubElement(chain_bin, "property", {"name": "video_index"}).text = "0"
        ET.SubElement(chain_bin, "property", {"name": "creation_time"}).text = metadata[
            "creation_time"
        ]
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.frame_rate_num"}
        ).text = str(metadata["frame_rate_num"])
        ET.SubElement(
            chain_bin, "property", {"name": "meta.media.frame_rate_den"}
        ).text = str(metadata["frame_rate_den"])
        ET.SubElement(chain_bin, "property", {"name": "meta.media.colorspace"}).text = (
            metadata["colorspace"]
        )
        ET.SubElement(chain_bin, "property", {"name": "meta.media.width"}).text = str(
            metadata["width"]
        )
        ET.SubElement(chain_bin, "property", {"name": "meta.media.height"}).text = str(
            metadata["height"]
        )

        # Add Shotcut-specific properties
        file_hash = calculate_hash(filename)
        ET.SubElement(chain_bin, "property", {"name": "shotcut:hash"}).text = file_hash
        ET.SubElement(chain_bin, "property", {"name": "xml"}).text = "was here"

        # Store for later reference
        chain_elements.append(
            {
                "id": f"chain{i*2}",
                "filename": filename,
                "path": video_path,
                "hash": file_hash,
            }
        )

    # Create main_bin playlist
    main_bin = ET.SubElement(
        mlt, "playlist", {"id": "main_bin", "title": "Shotcut version 24.04.01"}
    )

    ET.SubElement(
        main_bin, "property", {"name": "shotcut:projectAudioChannels"}
    ).text = "2"
    ET.SubElement(main_bin, "property", {"name": "shotcut:projectFolder"}).text = "1"
    ET.SubElement(main_bin, "property", {"name": "xml_retain"}).text = "1"

    # Add entries to main_bin
    for i, chain in enumerate(chain_elements):
        duration_tc = time_to_timecode(video_metadata[chain["filename"]]["duration"])
        entry = ET.SubElement(
            main_bin,
            "entry",
            {"producer": chain["id"], "in": "00:00:00.000", "out": duration_tc},
        )

    # Create black background producer
    max_duration = 0
    for filename, start_time, duration in clips:
        end_time = start_time + duration
        if end_time > max_duration:
            max_duration = end_time

    black_out_tc = time_to_timecode(max_duration)

    black = ET.SubElement(
        mlt, "producer", {"id": "black", "in": "00:00:00.000", "out": black_out_tc}
    )

    ET.SubElement(black, "property", {"name": "length"}).text = black_out_tc
    ET.SubElement(black, "property", {"name": "eof"}).text = "pause"
    ET.SubElement(black, "property", {"name": "resource"}).text = "0"
    ET.SubElement(black, "property", {"name": "aspect_ratio"}).text = "1"
    ET.SubElement(black, "property", {"name": "mlt_service"}).text = "color"
    ET.SubElement(black, "property", {"name": "mlt_image_format"}).text = "rgba"
    ET.SubElement(black, "property", {"name": "set.test_audio"}).text = "0"

    # Add background playlist
    bg_playlist = ET.SubElement(mlt, "playlist", {"id": "background"})
    ET.SubElement(
        bg_playlist,
        "entry",
        {"producer": "black", "in": "00:00:00.000", "out": black_out_tc},
    )

    # Create chain elements for playlist clips
    clip_chains = []
    for i, chain in enumerate(chain_elements):
        # Create chain element for playlist
        chain_playlist = ET.SubElement(
            mlt,
            "chain",
            {
                "id": f"chain{i*2+1}",
                "out": time_to_timecode(video_metadata[chain["filename"]]["duration"]),
            },
        )

        # Add same properties as in the main_bin chain
        ET.SubElement(chain_playlist, "property", {"name": "length"}).text = (
            time_to_timecode(video_metadata[chain["filename"]]["duration"])
        )
        ET.SubElement(chain_playlist, "property", {"name": "eof"}).text = "pause"
        ET.SubElement(chain_playlist, "property", {"name": "resource"}).text = chain[
            "path"
        ]
        ET.SubElement(chain_playlist, "property", {"name": "mlt_service"}).text = (
            "avformat-novalidate"
        )

        # Add same metadata as in the main_bin chain
        metadata = video_metadata[chain["filename"]]

        # Add video stream metadata (abbreviated)
        ET.SubElement(
            chain_playlist, "property", {"name": "meta.media.nb_streams"}
        ).text = "5"
        ET.SubElement(
            chain_playlist, "property", {"name": "meta.media.0.stream.type"}
        ).text = "video"
        ET.SubElement(
            chain_playlist, "property", {"name": "meta.media.0.codec.width"}
        ).text = str(metadata["width"])
        ET.SubElement(
            chain_playlist, "property", {"name": "meta.media.0.codec.height"}
        ).text = str(metadata["height"])

        # Add minimal required properties
        ET.SubElement(chain_playlist, "property", {"name": "seekable"}).text = "1"
        ET.SubElement(chain_playlist, "property", {"name": "audio_index"}).text = "1"
        ET.SubElement(chain_playlist, "property", {"name": "video_index"}).text = "0"
        ET.SubElement(chain_playlist, "property", {"name": "shotcut:hash"}).text = (
            chain["hash"]
        )
        ET.SubElement(chain_playlist, "property", {"name": "xml"}).text = "was here"
        ET.SubElement(chain_playlist, "property", {"name": "shotcut:caption"}).text = (
            chain["filename"]
        )

        clip_chains.append({"id": f"chain{i*2+1}", "filename": chain["filename"]})

    # Create main playlist
    playlist = ET.SubElement(mlt, "playlist", {"id": "playlist0"})
    ET.SubElement(playlist, "property", {"name": "shotcut:video"}).text = "1"
    ET.SubElement(playlist, "property", {"name": "shotcut:name"}).text = "V1"

    # Add clips to playlist
    for filename, start_time, duration in clips:
        if filename not in filename_to_path:
            print(f"Warning: {filename} not found in video_files, skipping")
            continue

        # Find the chain for this filename
        chain_id = None
        for chain in clip_chains:
            if chain["filename"] == filename:
                chain_id = chain["id"]
                break

        if not chain_id:
            print(f"Warning: Chain for {filename} not found, skipping")
            continue

        # Convert times to timecode
        metadata = video_metadata[filename]
        fps = metadata["frame_rate_num"] / metadata["frame_rate_den"]
        start_tc = time_to_timecode(start_time)
        end_tc = time_to_timecode(start_time + duration)

        # Create playlist entry
        entry = ET.SubElement(
            playlist, "entry", {"producer": chain_id, "in": start_tc, "out": end_tc}
        )

    # Create tractor (timeline)
    tractor = ET.SubElement(
        mlt,
        "tractor",
        {
            "id": "tractor0",
            "title": "Shotcut version 24.04.01",
            "in": "00:00:00.000",
            "out": black_out_tc,
        },
    )

    ET.SubElement(tractor, "property", {"name": "shotcut"}).text = "1"
    ET.SubElement(
        tractor, "property", {"name": "shotcut:projectAudioChannels"}
    ).text = "2"
    ET.SubElement(tractor, "property", {"name": "shotcut:projectFolder"}).text = "1"

    # Add tracks to tractor
    ET.SubElement(tractor, "track", {"producer": "background"})
    ET.SubElement(tractor, "track", {"producer": "playlist0"})

    # Add standard transitions
    transition0 = ET.SubElement(tractor, "transition", {"id": "transition0"})
    ET.SubElement(transition0, "property", {"name": "a_track"}).text = "0"
    ET.SubElement(transition0, "property", {"name": "b_track"}).text = "1"
    ET.SubElement(transition0, "property", {"name": "mlt_service"}).text = "mix"
    ET.SubElement(transition0, "property", {"name": "always_active"}).text = "1"
    ET.SubElement(transition0, "property", {"name": "sum"}).text = "1"

    transition1 = ET.SubElement(tractor, "transition", {"id": "transition1"})
    ET.SubElement(transition1, "property", {"name": "a_track"}).text = "0"
    ET.SubElement(transition1, "property", {"name": "b_track"}).text = "1"
    ET.SubElement(transition1, "property", {"name": "version"}).text = "0.1"
    ET.SubElement(transition1, "property", {"name": "mlt_service"}).text = (
        "frei0r.cairoblend"
    )
    ET.SubElement(transition1, "property", {"name": "threads"}).text = "0"
    ET.SubElement(transition1, "property", {"name": "disable"}).text = "1"

    # Format the XML with proper indentation
    xml_str = ET.tostring(mlt, "utf-8")
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")

    # Add XML declaration
    xml_declaration = '<?xml version="1.0" standalone="no"?>\n'

    # Write to file
    with open(output_file, "w") as f:
        f.write(xml_declaration + pretty_xml[pretty_xml.find("<mlt") :])

    print(f"MLT file generated successfully: {output_file}")


# Example usage:
if __name__ == "__main__":
    # List of video files (full paths)
    video_files = [
        "/media/alga/KINGSTON/GoPro/2025 Tenerife/GH010815.MP4",
        "/media/alga/KINGSTON/GoPro/2025 Tenerife/GH010816.MP4",
        "/media/alga/KINGSTON/GoPro/2025 Tenerife/GH010817.MP4",
    ]

    # List of clips (filename, start_time in seconds, duration in seconds)
    clips = [
        ("GH010815.MP4", 3.0, 5.0),  # video1.mp4, starting at 10.5s, for 5 seconds
        (
            "GH010816.MP4",
            0.0,
            8.2,
        ),  # video2.mp4, starting at beginning, for 8.2 seconds
        ("GH010817.MP4", 0.1, 5.0),  # video3.mp4, starting at 15s, for 10 seconds
        ("GH010815.MP4", 10.0, 7.5),  # Another clip from video1.mp4
    ]
    generate_mlt_file(video_files, clips, "my_project.mlt")
