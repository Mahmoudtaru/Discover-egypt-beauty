import glob, os
from playwright.sync_api import sync_playwright
CHROME = glob.glob('/opt/pw-browsers/chromium-*/chrome-linux*/chrome')[0]
JS = """() => {
  const worst = {min: 1e9, t: 0, line: ''};
  // [line, from, to] -> row slot is read from slotOf at each t
  const lines = [['A',2.6,5.25],['B',3.0,7.5],['C',5.25,9.75],['D',7.5,9.75]];
  for (const [name,a,b] of lines) {
    const half = L.lines[name].total/2 + 60;
    for (let t=a; t<=b; t+=0.02) {
      const sl = slotOf(name, t), cy = 986 + sl.y;
      const st = shapeState(t).slice(0,3), br = breathe(t), sq = squash(t);
      let m = 1e9;
      for (let x=CX-half; x<=CX+half; x+=30) for (const y of [cy-111, cy-60, cy, cy+94]) {
        let best = -1e9;
        for (const c of st) { if (c.r<=0) continue;
          const px = CX+(x-CX)/(br*sq.sx), py = CY+(y-CY)/(br*sq.sy);
          const rr = c.rx!==undefined ? Math.min(c.rx,c.ry) : c.r;
          best = Math.max(best, rr - Math.hypot(px-c.x, py-c.y)); }
        m = Math.min(m, best);
      }
      if (m < worst.min) { worst.min = m; worst.t = t; worst.line = name; }
    }
  }
  return worst; }"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
    pg = b.new_page(viewport={'width':1080,'height':1920}); pg.on('pageerror', lambda e: print('ERR', e))
    pg.goto('file://'+os.path.abspath('joy-loop.html')+'?capture=1'); pg.evaluate('window.ready')
    print('worst clearance of expanded text box inside shape (px, >0 = inside):', pg.evaluate(JS))
    b.close()
