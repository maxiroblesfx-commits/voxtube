"""
VoxTube — Servicio de mezcla y sincronización de audio con FFmpeg.
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path
from config import TEMP_DIR

def mix_audio(
    tts_results: list[dict],
    total_duration: float,
    job_id: str,
) -> str:
    output_dir = TEMP_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "translated_audio.mp3"
    
    valid_clips = []
    for seg in tts_results:
        if seg.get("success") and seg.get("path") and Path(seg["path"]).exists():
            valid_clips.append(seg)
            
    if not valid_clips:
        # Create a simple silent mp3 of total_duration
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", f"-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(total_duration), str(output_path)
        ], check=True, capture_output=True)
        return str(output_path)

    # We will build an ffmpeg filter complex command
    inputs = []
    
    # Input 0: Silent background track of the correct length
    inputs.extend(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo"])
    
    filter_parts = []
    amix_inputs = ["[0:a]"]
    
    for idx, seg in enumerate(valid_clips):
        # inputs are 0-indexed. 0 is silence, so seg idx+1
        in_idx = idx + 1
        inputs.extend(["-i", str(seg["path"])])
        
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        available_ms = end_ms - start_ms
        
        # FFmpeg adelay filter.
        # We can't easily check the duration of the mp3 without ffprobe,
        # so we will just delay it to start_ms. If it overlaps, amix handles it.
        # Format for adelay: delay in ms for each channel.
        # We apply adelay and assign a label.
        filter_parts.append(f"[{in_idx}:a]adelay={start_ms}|{start_ms}[a{in_idx}]")
        amix_inputs.append(f"[a{in_idx}]")

    # Combine all delayed inputs and the silent track using amix
    amix_str = "".join(amix_inputs)
    filter_parts.append(f"{amix_str}amix=inputs={len(valid_clips) + 1}:duration=first:dropout_transition=0[outa]")
    
    filter_complex = ";".join(filter_parts)
    
    cmd = [
        "ffmpeg", "-y",
    ] + inputs + [
        "-t", str(total_duration), # limit to original video duration
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        str(output_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    return str(output_path)
