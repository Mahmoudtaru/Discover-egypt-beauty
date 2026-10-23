import sys, glob, asyncio
from playwright.sync_api import sync_playwright
CHROME = glob.glob('/opt/pw-browsers/chromium-*/chrome-linux*/chrome')[0]
html = 'file://' + __import__('os').path.abspath('joy-loop.html') + '?capture=1'
out = sys.argv[1]
times = [float(x) for x in sys.argv[2:]]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
    pg = b.new_page(viewport={'width':1080,'height':1920})
    pg.on('console', lambda m: print('console:', m.text))
    pg.on('pageerror', lambda e: print('ERR', e))
    pg.goto(html); pg.evaluate('window.ready'); 
    print('fontOK', pg.evaluate('window.fontOK'), 'hookW', pg.evaluate('L.hookW'), 'DX0', pg.evaluate('L.DX0'))
    print(pg.evaluate('Object.fromEntries(Object.entries(L.lines).map(([k,v])=>[k,{total:v.total,size:v.size}]))'))
    for t in times:
        pg.evaluate(f'render({t})')
        pg.screenshot(path=f'{out}/still_{t:05.2f}.png')
    b.close()
