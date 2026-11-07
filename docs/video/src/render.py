import json, subprocess, sys
from pathlib import Path
import imageio_ffmpeg
HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
TL = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
OUT = Path(r"D:\PROJECTS\Switch-the-flip\team-pikachu-switch-ai\docs\video\out"); OUT.mkdir(parents=True, exist_ok=True)
X = 0.3
st = TL["stills"]; total = TL["total"]
voice = sys.argv[1] if len(sys.argv) > 1 else None   # optional recorded voiceover file (whole track)
args = [FF, "-y", "-hide_banner", "-loglevel", "error"]
for k, s in enumerate(st):
    L = s["dur"] + (X if k < len(st) - 1 else 0)
    args += ["-loop", "1", "-framerate", "30", "-t", f"{L:.3f}", "-i", s["png"]]
na = len(st)
if voice:
    args += ["-i", voice]
else:
    for a in TL["audio"]:
        args += ["-i", str(HERE / "audio" / f"seg{a['n']}.mp3")]
fc = [f"[{k}:v]format=yuv420p,setsar=1[v{k}]" for k in range(na)]
prev = "v0"
for k in range(1, na):
    off = st[k]["t0"]
    fc.append(f"[{prev}][v{k}]xfade=transition=fade:duration={X}:offset={off:.3f}[x{k}]"); prev = f"x{k}"
if voice:
    fc.append(f"[{na}:a]apad,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
else:
    for j, a in enumerate(TL["audio"]):
        ms = int(a["at"] * 1000)
        fc.append(f"[{na + j}:a]aresample=48000,adelay={ms}|{ms}[d{j}]")
    fc.append("".join(f"[d{j}]" for j in range(len(TL["audio"]))) + f"amix=inputs={len(TL['audio'])}:normalize=0,apad,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
args += ["-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(OUT / "prove-it-demo.mp4")]
r = subprocess.run(args, capture_output=True, text=True)
print(r.returncode, r.stderr[-2000:])
