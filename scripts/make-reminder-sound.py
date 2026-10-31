"""Synthesize FreshTray's original airy glass-and-wood reminder; no external samples."""
from array import array
import math
from pathlib import Path
import random
import sys
import wave

RATE = 44100
DURATION = 2.4
rng = random.Random(4701)
dry = []
breath = 0.0
for frame in range(round(RATE * DURATION)):
    t = frame / RATE
    value = 0.0
    # Soft overlapping fifth: a rounded fundamental with delicate, detuned glass partials.
    for start, frequency, gain in ((0.0, 523.251, 1.0), (0.26, 783.991, 0.72)):
        age = t - start
        if age < 0:
            continue
        attack = 1 - math.exp(-age / 0.025)
        for ratio, level, decay in ((1, 1, 2.8), (2.002, .17, 4.1), (2.997, .055, 5.4)):
            phase = 2 * math.pi * frequency * ratio * age
            shimmer = .014 * math.sin(2 * math.pi * 1.7 * age)
            value += gain * level * attack * math.exp(-decay * age) * math.sin(phase + shimmer)
    # A barely audible filtered breath gives the attack a less electronic texture.
    breath = .93 * breath + .07 * rng.uniform(-1, 1)
    value += .025 * breath * (1 - math.exp(-t / .04)) * math.exp(-t * 4)
    dry.append(value)

samples = []
for frame, value in enumerate(dry):
    # Diffuse, fading reflections rather than an obvious repeated echo.
    for delay, gain in ((.071, .12), (.113, .09), (.179, .065), (.263, .04)):
        offset = round(delay * RATE)
        if frame >= offset:
            value += dry[frame - offset] * gain
    t = frame / RATE
    tail = min(1.0, max(0.0, (DURATION - t) / .45))
    samples.append(value * (.5 - .5 * math.cos(math.pi * tail)))
peak = max(abs(value) for value in samples)
pcm = array('h', (round(value / peak * .28 * 32767) for value in samples))
if sys.byteorder != 'little':
    pcm.byteswap()
path = Path(__file__).resolve().parents[1] / 'src/assets/sounds/reminder.wav'
path.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(path), 'wb') as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(RATE)
    output.writeframes(pcm.tobytes())
print(f'Created {path.name}: {DURATION:.2f}s, 44.1 kHz PCM, peak -11.1 dBFS')


# Additional original presets. All are short, sample-free and deterministic.
def make_preset(name, duration, voices, attack, reflections):
    dry = []
    for frame in range(round(RATE * duration)):
        t = frame / RATE
        value = 0.0
        for start, frequency, gain, decay, partials, glide in voices:
            age = t - start
            if age < 0:
                continue
            envelope = (1 - math.exp(-age / attack)) ** 2 * math.exp(-decay * age)
            phase = 2 * math.pi * frequency * (age + glide * .018 * (1 - math.exp(-age / .018)))
            value += gain * envelope * sum(level * math.sin(ratio * phase) * math.exp(-extra_decay * age)
                                           for ratio, level, extra_decay in partials)
        dry.append(value)
    samples = []
    for frame, value in enumerate(dry):
        for delay, gain in reflections:
            offset = round(delay * RATE)
            if frame >= offset:
                value += gain * dry[frame-offset]
        tail = min(1, (duration-frame/RATE)/.4)
        samples.append(value * (.5-.5*math.cos(math.pi*tail)))
    peak = max(map(abs, samples))
    rms = math.sqrt(sum(v*v for v in samples)/len(samples))
    scale = min(.28/peak, .065/rms)
    pcm = array('h', (round(v*scale*32767) for v in samples))
    if sys.byteorder != 'little': pcm.byteswap()
    target = path.parent/(name+'.wav')
    with wave.open(str(target), 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(RATE); output.writeframes(pcm.tobytes())
    print(f'Created {target.name}: {duration:.2f}s, original PCM preset')

make_preset('warm_bell', 1.9, (
    (0, 440, 1, 3.2, ((1,1,0),(2,.12,2),(3,.035,4)), 0),
    (.19, 659.255, .65, 3.6, ((1,1,0),(2,.1,2)), 0)),
    .012, ((.065,.09),(.137,.055)))
make_preset('glass_drops', 2.1, (
    (0, 783.991, .8, 5, ((1,1,0),(2.01,.1,4)), .065),
    (.18, 1046.502, .65, 5, ((1,1,0),(2.005,.08,4)), .045),
    (.39, 1174.659, .45, 4.8, ((1,1,0),(2,.07,4)), .025)),
    .009, ((.081,.15),(.151,.09),(.237,.05)))
make_preset('soft_horizon', 2.7, (
    (0, 392, .7, 2.1, ((1,1,0),(2.001,.07,1)), 0),
    (.09, 587.33, .65, 2.3, ((1,1,0),(1.999,.06,1)), 0),
    (.21, 783.991, .3, 2.5, ((1,1,0),), 0)),
    .09, ((.097,.17),(.173,.12),(.281,.07)))


# Non-chime alternatives: one low rounded tone, a smooth tonal swell, and
# three miniature mechanical sound designs. No recordings or samples used.
def make_texture(name, duration):
    samples = []
    phase = 0.0
    def hit(age, strength, frequency):
        if age < 0 or age > .22:
            return 0.0
        attack = (1-math.exp(-age/.003))**2
        body = math.sin(2*math.pi*frequency*age)*math.exp(-age*45)
        tick = math.sin(2*math.pi*frequency*2.31*age)*math.exp(-age*190)
        return strength*attack*(.7*body+.12*tick)
    for frame in range(round(RATE*duration)):
        t = frame/RATE
        value = 0.0
        if name == 'low_pulse':
            envelope = (1-math.exp(-t/.025))**2*math.exp(-t*3.8)
            value = envelope*(math.sin(2*math.pi*110*t)+.24*math.sin(2*math.pi*220*t)+.08*math.sin(2*math.pi*330*t))
        elif name == 'soft_breath':
            envelope = math.sin(math.pi*min(1,t/1.35))**2 if t < 1.35 else 0
            value = envelope*(math.sin(2*math.pi*330*t)+.16*math.sin(2*math.pi*660*t))*(.9+.1*math.sin(2*math.pi*1.2*t))
        elif name == 'punchcard':
            # Short feed rollers, a three-step punch, then the card release.
            if .04 < t < .43:
                feed = math.sin(math.pi*(t-.04)/.39)**2
                value += feed*(.08*math.sin(2*math.pi*145*t)+.025*math.sin(2*math.pi*290*t))
            for start,strength,freq in ((.46,1,135),(.55,.8,165),(.64,.62,150),(.96,.35,230),(1.08,.2,190)):
                value += hit(t-start,strength,freq)
            if .78 < t < 1.12:
                value += .06*math.sin(2*math.pi*(210*(t-.78)-70*(t-.78)**2))*math.sin(math.pi*(t-.78)/.34)**2
        elif name == 'relay_click':
            for start,strength,freq in ((.05,.8,280),(.075,.22,370),(.28,.57,220),(.31,.15,350)):
                value += hit(t-start,strength,freq)
        elif name == 'servo_sweep':
            if .05 < t < .95:
                age = (t-.05)/.9
                speed = math.sin(math.pi*age)
                phase += 2*math.pi*(160+180*speed)/RATE
                value += speed**2*(.15*math.sin(phase)+.04*math.sin(phase*3))
            value += hit(t-1.01,.55,170)+hit(t-1.08,.15,240)
        attack = min(1,t/.006)
        tail = min(1,max(0,(duration-t)/.2))
        samples.append(value*(.5-.5*math.cos(math.pi*attack))*(.5-.5*math.cos(math.pi*tail)))
    peak = max(map(abs,samples))
    rms = math.sqrt(sum(v*v for v in samples)/len(samples))
    scale = min(.28/peak,.065/rms)
    pcm = array('h',(round(v*scale*32767) for v in samples))
    if sys.byteorder != 'little': pcm.byteswap()
    target = path.parent/(name+'.wav')
    with wave.open(str(target),'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(RATE); output.writeframes(pcm.tobytes())
    print(f'Created {target.name}: {duration:.2f}s, original synthesized texture')

for name,duration in (('low_pulse',1.65),('soft_breath',1.7),('punchcard',1.65),('relay_click',1.2),('servo_sweep',1.65)):
    make_texture(name,duration)
