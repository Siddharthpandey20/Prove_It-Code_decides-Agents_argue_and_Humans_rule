import asyncio, re, subprocess, sys, json, os
from pathlib import Path
import edge_tts, imageio_ffmpeg

SRC = Path(r"D:\PROJECTS\Switch-the-flip\team-pikachu-switch-ai\docs\video\VOICEOVER.md")
OUT = Path(__file__).parent / "audio"
OUT.mkdir(exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "en-US-AndrewMultilingualNeural"
ONLY = {int(a) for a in sys.argv[1:]}

text = SRC.read_text(encoding="utf-8")
parts = re.split(r"^## (\d+)\. .*$", text, flags=re.M)
segs = {int(parts[i]): " ".join(parts[i + 1].split()) for i in range(1, len(parts), 2)}

def duration(p):
    r = subprocess.run([FF, "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])

async def main():
    jf = OUT / "segments.json"
    info = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    for n, t in segs.items():
        if ONLY and n not in ONLY:
            continue
        mp3, tmp = OUT / f"seg{n}.mp3", OUT / f"seg{n}.tmp.mp3"
        for attempt in range(4):
            try:
                sents = []
                with open(tmp, "wb") as f:
                    async for ch in edge_tts.Communicate(t, VOICE, rate="+8%", boundary="SentenceBoundary").stream():
                        if ch["type"] == "audio":
                            f.write(ch["data"])
                        elif ch["type"] == "SentenceBoundary":
                            sents.append({"start": ch["offset"] / 1e7, "dur": ch["duration"] / 1e7, "text": ch["text"]})
                break
            except Exception as e:
                print("retry", n, type(e).__name__); await asyncio.sleep(3)
        else:
            raise SystemExit("TTS failed for segment %d" % n)
        os.replace(tmp, mp3)
        info[str(n)] = {"text": t, "dur": duration(mp3), "words": len(t.split()), "sents": sents}
        jf.write_text(json.dumps(info, indent=1), encoding="utf-8")
        print(n, round(info[str(n)]["dur"], 2), len(sents))
    print("total", round(sum(v["dur"] for v in info.values()), 1))

asyncio.run(main())
