import os, glob, io, sys, numpy as np
from multiprocessing import Pool
from PIL import Image
from playwright.sync_api import sync_playwright
CHROME = glob.glob('/opt/pw-browsers/chromium-*/chrome-linux*/chrome')[0]
URL = 'file://' + os.path.abspath('joy-loop.html') + '?capture=1'
OUT = sys.argv[1]; FPS = 30; NF = 360; SUB = 8; THR = 100.0
def shot(pg, t):
    pg.evaluate(f'render({t!r})')
    return np.asarray(Image.open(io.BytesIO(pg.screenshot())).convert('RGB'), dtype=np.float32)
def work(idx):
    blurred = 0
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
        pg = b.new_page(viewport={'width': 1080, 'height': 1920}); pg.goto(URL); pg.evaluate('window.ready')
        assert pg.evaluate('window.fontOK'), 'font failed'
        for i in idx:
            t = i / FPS
            if pg.evaluate(f'motionSpeed({t!r})') > THR:      # fast move → 180° shutter, 8 sub-frames
                acc = sum(shot(pg, t + ((k + .5) / SUB - .5) / (2 * FPS)) for k in range(SUB)) / SUB
                blurred += 1
            else:
                acc = shot(pg, t)
            Image.fromarray(np.clip(acc + .5, 0, 255).astype(np.uint8)).save(f'{OUT}/f{i:04d}.png')
        b.close()
    return blurred
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    chunks = [list(range(k, NF, 4)) for k in range(4)]
    with Pool(4) as pool: print('motion-blurred frames:', sum(pool.map(work, chunks)))
