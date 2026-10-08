"""Showcase video of a Life run: the torus on the left, a live dashboard on the right, and a soundtrack generated from the data.

Input: <run-dir>/t<nnnnnnnn>.ppm frames (engine option --ppm-every k) and <run-dir>/stats.csv (every report_every ticks).
Dashboard: tick, live cells, distinct genomes, births per tick, mean energy, and the diversity and population curves drawing
themselves up to the current tick. Sound (44.1 kHz stereo): a tone whose pitch follows genome diversity (110 Hz at 50 k genomes,
one octave per doubling), whose loudness follows the birth rate; a low drone whose pitch follows the live fraction; a click every
10,000 ticks. The parameters are interpolated between frames with continuous phase, so the audio is click-free.
usage: python cluster/showcase_video.py <run-dir> <ppm-every> [--fps 30] [--title "..."] [--out file.mp4]
"""
import argparse, csv, glob, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('every', type=int); ap.add_argument('--fps', type=int, default=30)
ap.add_argument('--title'); ap.add_argument('--out'); ap.add_argument('--grid', type=int, default=704); ap.add_argument('--no-audio', action='store_true')
a = ap.parse_args(); run = a.run.rstrip('/\\'); name = os.path.basename(run); out = a.out or os.path.join(run, f'{name}_showcase.mp4')
frames = sorted(glob.glob(os.path.join(run, 't[0-9]*.ppm'))); assert frames, 'no frames'
rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(os.path.join(run, 'stats.csv')))]
st_t = np.array([r['tick'] for r in rows]); report_every = st_t[1] - st_t[0] if len(st_t) > 1 else 1
def series(k): return np.array([r[k] for r in rows])
alive, genomes, births, energy = series('alive'), series('distinct_genomes'), series('births') / report_every, series('mean_energy')
N2 = Image.open(frames[0]).size[0] ** 2; ticks = [int(os.path.basename(f)[1:9]) for f in frames]
def at(arr, t): return float(np.interp(t, st_t, arr))
opts = ''
status_file = os.path.join(os.path.dirname(run), 'status.json')
if os.path.exists(status_file):
    import json; opts = json.load(open(status_file)).get(name, {}).get('options', '').replace('--report-every 1000 ', '').replace('--ppm-every 100', '').replace('--', '')
W, H = 1280, 720; G = a.grid; PX = G + 32; panel_w = W - PX - 16
try: F = ImageFont.truetype('arial.ttf', 22); FB = ImageFont.truetype('arialbd.ttf', 40); FS = ImageFont.truetype('arial.ttf', 16)
except OSError: F = FB = FS = ImageFont.load_default()
title = a.title or name

def plot(draw, x0, y0, w, h, arr, tnow, log=False, color=(120, 200, 255), label=''):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=(28, 28, 34), outline=(70, 70, 80))
    v = np.log10(np.maximum(arr, 1)) if log else arr; lo, hi = v.min(), v.max(); hi = hi if hi > lo else lo + 1
    pts = [(x0 + w * t / st_t[-1], y0 + h - h * (val - lo) / (hi - lo)) for t, val in zip(st_t, v)]
    seg = [p for p, t in zip(pts, st_t) if t <= tnow]
    if len(seg) > 1: draw.line(seg, fill=color, width=2)
    xn = x0 + w * tnow / st_t[-1]; draw.line([xn, y0, xn, y0 + h], fill=(255, 255, 255), width=1)
    draw.text((x0 + 6, y0 + 4), label, fill=(200, 200, 210), font=FS)
    draw.text((x0 + 6, y0 + h - 20), f'{10 ** lo:,.0f}' if log else f'{lo:,.0f}', fill=(130, 130, 140), font=FS)
    draw.text((x0 + w - 90, y0 + 4), f'{10 ** hi:,.0f}' if log else f'{hi:,.0f}', fill=(130, 130, 140), font=FS)

def compose(i):
    t = ticks[i]; im = Image.open(frames[i]).resize((G, G), Image.BOX)
    canvas = Image.new('RGB', (W, H), (16, 16, 20)); canvas.paste(im, (16, (H - G) // 2)); d = ImageDraw.Draw(canvas)
    x = PX; y = 24
    d.text((x, y), title, fill=(240, 240, 240), font=F); y += 30
    d.text((x, y), opts.strip()[:70], fill=(120, 120, 130), font=FS); y += 34
    d.text((x, y), f'tick {t:,}', fill=(255, 255, 255), font=FB); y += 56
    al, ge, bi, en = at(alive, t), at(genomes, t), at(births, t), at(energy, t)
    for lab, val in (('live cells', f'{al:,.0f}  ({100 * al / N2:.1f} %)'), ('distinct genomes', f'{ge:,.0f}'), ('births per tick', f'{bi:,.0f}'), ('mean energy', f'{en:.1f}')):
        d.text((x, y), lab, fill=(150, 150, 160), font=FS); d.text((x + 170, y - 3), val, fill=(230, 230, 240), font=F); y += 30
    y += 10; plot(d, x, y, panel_w, 150, genomes, t, log=True, color=(255, 170, 60), label='distinct genomes (log)'); y += 162
    plot(d, x, y, panel_w, 110, alive, t, color=(120, 200, 255), label='live cells'); y += 122
    plot(d, x, y, panel_w, 90, births, t, color=(170, 255, 140), label='births per tick')
    d.text((x, H - 30), 'hue = genome family, brightness = state, dark = empty', fill=(110, 110, 120), font=FS)
    return canvas

# ---- audio ----
SR = 44100; spf = SR // a.fps; n = len(frames)
def synth():
    gen = np.array([at(genomes, t) for t in ticks]); bi = np.array([at(births, t) for t in ticks]); al = np.array([at(alive, t) for t in ticks])
    f1 = 110 * 2 ** np.log2(np.maximum(gen, 1) / 50000); f1 = np.clip(f1, 60, 2000)
    f2 = 55 + 55 * al / N2; amp = 0.12 + 0.45 * bi / max(bi.max(), 1)
    total = n * spf; tt = np.arange(total) / SR; idx = np.minimum((np.arange(total) // spf), n - 1)
    fr = np.interp(np.arange(total), np.arange(n) * spf, f1); fr2 = np.interp(np.arange(total), np.arange(n) * spf, f2); am = np.interp(np.arange(total), np.arange(n) * spf, amp)
    ph = 2 * np.pi * np.cumsum(fr) / SR; ph2 = 2 * np.pi * np.cumsum(fr2) / SR
    tone = am * (0.6 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)); drone = 0.18 * np.sin(ph2) + 0.06 * np.sin(2 * ph2)
    click = np.zeros(total); rng = np.random.default_rng(1)
    for i, t in enumerate(ticks):
        if t % 10000 == 0 and t > 0:
            s = i * spf; L = int(0.03 * SR); click[s:s + L] += 0.5 * rng.standard_normal(L) * np.exp(-np.arange(L) / (0.006 * SR))
    left = tone + drone + click; right = 0.9 * tone + drone * 1.1 + click
    fade = np.minimum(1, np.minimum(np.arange(total), total - np.arange(total)) / (0.5 * SR))
    stereo = np.stack([left, right], 1) * fade[:, None]; stereo /= max(1.0, np.abs(stereo).max() / 0.9)
    return (stereo * 32767).astype('<i2')
wav = os.path.join(run, f'{name}_showcase.wav')
if not a.no_audio:
    with wave.open(wav, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(synth().tobytes())
cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(a.fps), '-i', 'pipe:0']
if not a.no_audio: cmd += ['-i', wav]
cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p'] + ([] if a.no_audio else ['-c:a', 'aac', '-b:a', '160k', '-shortest']) + ['-movflags', '+faststart', out]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(n):
    p.stdin.write(compose(i).tobytes())
    if i % 200 == 0: print(f'frame {i}/{n}', flush=True)
p.stdin.close(); p.wait(); print('wrote', out, os.path.getsize(out) // 1_000_000, 'MB', 'exit', p.returncode)
