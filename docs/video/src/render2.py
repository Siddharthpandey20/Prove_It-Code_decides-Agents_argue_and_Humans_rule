import json, subprocess, sys
from pathlib import Path
import imageio_ffmpeg
HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
TL = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
OUT = Path(r"D:\PROJECTS\Switch-the-flip\team-pikachu-switch-ai\docs\video\out"); OUT.mkdir(parents=True, exist_ok=True)
X = 0.3
st = TL["stills"]; total = TL["total"]
args = [FF, "-y", "-hide_banner", "-loglevel", "error"]
for k, s in enumerate(st):
    L = s["dur"] + (X if k < len(st) - 1 else 0)
    args += ["-loop", "1", "-framerate", "30", "-t", f"{L:.3f}", "-i", s["png"]]
na = len(st)
for a in TL["audio"]:
    args += ["-i", str(HERE / "audio" / f"seg{a['n']}.mp3")]
mi, si = na + len(TL["audio"]), na + len(TL["audio"]) + 1
args += ["-i", str(HERE / "music.wav"), "-i", str(HERE / "sfx.wav")]
fc = [f"[{k}:v]format=yuv420p,setsar=1[v{k}]" for k in range(na)]
prev = "v0"
for k in range(1, na):
    fc.append(f"[{prev}][v{k}]xfade=transition=fade:duration={X}:offset={st[k]['t0']:.3f}[x{k}]"); prev = f"x{k}"
for j, a in enumerate(TL["audio"]):
    ms = int(a["at"] * 1000)
    fc.append(f"[{na + j}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[d{j}]")
fc.append("".join(f"[d{j}]" for j in range(len(TL["audio"]))) + f"amix=inputs={len(TL['audio'])}:normalize=0,apad,atrim=0:{total:.3f},asplit=2[vo][vk]")
fc.append(f"[{mi}:a]aresample=48000,volume=0.30[mu]")
fc.append("[mu][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md]")
fc.append(f"[{si}:a]aresample=48000,volume=0.45[sx]")
fc.append(f"[vo][md][sx]amix=inputs=3:normalize=0,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
args += ["-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(OUT / "prove-it-demo-v3.mp4")]
r = subprocess.run(args, capture_output=True, text=True)
print(r.returncode, r.stderr[-2500:])
