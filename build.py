#!/usr/bin/env python3
"""Tiny static build for the IZOLYATSIA Xmas archive (Python 3 stdlib only).

The year pages in public/YYYY/index.html are hand-made legacy pages. Only the
parts between marker comments are managed here, everything else is never touched:

    <!-- @title -->...<!-- /@title -->            head <title>
    <!-- @head -->...<!-- /@head -->              social meta tags + nav.js / nav.css
    <!-- @nav -->...<!-- /@nav -->                year nav, prev/next arrows, key handler
    <!-- @credit -->...<!-- /@credit -->          inner HTML of the page's .credit element
    <!-- @credit_bottom -->...                    optional second credit (2012)

public/index.html has <!-- @head --> (meta tags) and <!-- @cards --> (card grid).
Source of truth: years.json.  See README.md.

    python3 build.py            regenerate all slots
    python3 build.py --check    verify, change nothing, exit 1 on problems
    python3 build.py --images   also regenerate card thumbnails (Pillow) and
                                share images (node + Playwright, scripts/og.mjs)
    python3 build.py --new 2027 create public/2027/index.html from templates/year.html
"""
import argparse
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'
TEMPLATES = ROOT / 'templates'
YEARS_JSON = ROOT / 'years.json'

THUMB_MAX = 900
THUMB_QUALITY = 82
EAGER_CARDS = 4          # first N cards on the home page load eagerly


# ---------------------------------------------------------------- data ----

def load():
    data = json.loads(YEARS_JSON.read_text(encoding='utf-8'))
    years = sorted(data['years'], key=lambda e: e['year'])
    nums = [e['year'] for e in years]
    if len(set(nums)) != len(nums):
        sys.exit('years.json: duplicate year')
    site = dict(data['site'])
    site['first'], site['last'] = nums[0], nums[-1]
    return site, years


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def tpl(name):
    return (TEMPLATES / name).read_text(encoding='utf-8').rstrip('\n')


def jpeg_size(path):
    """(width, height) of a JPEG without Pillow."""
    b = path.read_bytes()
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7 or m == 0xFF:
            i += 1 if m == 0xFF else 2
            continue
        (n,) = struct.unpack('>H', b[i + 2:i + 4])
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack('>HH', b[i + 5:i + 9])
            return w, h
        i += 2 + n
    raise ValueError(f'no JPEG size in {path}')


# ------------------------------------------------------------ renderers ----

def render_title(site, e):
    return f'<title>{e["year"]} · {esc(site["name"])}</title>'


def render_head(site, e):
    y, base = e['year'], site['base_url']
    desc = esc(f'{e["description"]} {site["description_suffix"].format(**site)}')
    img = f'{base}/img/og/{y}.jpg'
    lines = [
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<meta name="description" content="{desc}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{esc(site["name"])}">',
        f'<meta property="og:title" content="IZOLYATSIA holiday greeting {y}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{base}/{y}/">',
        f'<meta property="og:image" content="{img}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="IZOLYATSIA holiday postcard {y}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="IZOLYATSIA holiday greeting {y}">',
        f'<meta name="twitter:description" content="{desc}">',
        f'<meta name="twitter:image" content="{img}">',
        '<script src="../nav.js"></script>',
        '<link rel="stylesheet" href="../nav.css" type="text/css" charset="utf-8"/>',
    ]
    return '\n' + ''.join(f'    {l}\n' for l in lines) + '    '


ARROW_PREV = ('<a class="year-arrow prev" href="../{y}/" rel="prev" aria-label="Previous year: {y}"><svg viewBox="0 0 24 24" '
              'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
              'aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg><span class="year-arrow-label">{y}</span></a>')
ARROW_NEXT = ('<a class="year-arrow next" href="../{y}/" rel="next" aria-label="Next year: {y}"><svg viewBox="0 0 24 24" '
              'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
              'aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg><span class="year-arrow-label">{y}</span></a>')


def render_nav(years, e):
    nums = [x['year'] for x in years]
    i = nums.index(e['year'])
    out = ['<div class="cont">', '<ul>', tpl('nav-home.html')]
    for n in nums:
        cls = ' class="active"' if n == e['year'] else ''
        out.append(f'\t<li><a href="../{n}"{cls}>{n}</a></li>')
    out += ['</ul>', '</div>']
    if i > 0:
        out.append(ARROW_PREV.format(y=nums[i - 1]))
    if i < len(nums) - 1:
        out.append(ARROW_NEXT.format(y=nums[i + 1]))
    out.append(tpl('keydown.html'))
    return '\n' + '\n'.join(out) + '\n'


def render_home_head(site):
    desc = esc(site['home_description'].format(**site))
    base, name = site['base_url'], esc(site['name'])
    alt = f'{name}, {site["first"]}–{site["last"]}'
    lines = [
        f'<meta name="description" content="{desc}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{name}">',
        f'<meta property="og:title" content="{name}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{base}/">',
        f'<meta property="og:image" content="{base}/img/og/home.jpg">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{alt}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{name}">',
        f'<meta name="twitter:description" content="{desc}">',
        f'<meta name="twitter:image" content="{base}/img/og/home.jpg">',
    ]
    return '\n' + ''.join(f'  {l}\n' for l in lines) + '  '


def render_cards(years):
    out = []
    for pos, e in enumerate(sorted(years, key=lambda x: -x['year'])):
        y = e['year']
        if not e.get('card_bg'):
            raise SlotError(f'years.json {y}: no card_bg (run: make images)')
        lines = ['    <li>', f'      <a class="card" href="./{y}/">',
                 f'        <span class="media" style="background:{e["card_bg"]}">']
        if e.get('thumb'):
            w, h = jpeg_size(PUBLIC / 'img' / 'cards' / f'{y}.jpg')
            loading = 'eager' if pos < EAGER_CARDS else 'lazy'
            cover = ' class="cover"' if e.get('thumb_fit') == 'cover' else ''
            lines.append(f'          <img src="./img/cards/{y}.jpg" width="{w}" height="{h}" '
                         f'alt="IZOLYATSIA holiday greeting {y}" loading="{loading}"{cover}>')
        else:
            lines.append(f'          <span class="placeholder" aria-hidden="true">{y}</span>')
        if e.get('video'):
            lines.append('        <span class="badge">&#9654; Video</span>')
        lines += ['        </span>', f'        <span class="year">{y}</span>', '      </a>', '    </li>']
        out += lines
    return '\n' + '\n'.join(out) + '\n    '


# ---------------------------------------------------------------- slots ----

class SlotError(Exception):
    pass


def slot_rx(name):
    return re.compile(r'(<!-- @%s -->)(.*?)(<!-- /@%s -->)' % (name, name), re.S)


def count_slot(text, name):
    return len(re.findall(r'<!-- @%s -->' % name, text)), len(re.findall(r'<!-- /@%s -->' % name, text))


def fill(text, name, content, nl):
    a, b = count_slot(text, name)
    if (a, b) != (1, 1):
        raise SlotError(f'slot "{name}": found {a} open / {b} close markers, expected 1/1')
    content = content.replace('\n', nl)
    return slot_rx(name).sub(lambda m: m.group(1) + content + m.group(3), text, count=1)


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return f.read()


def render_year_page(site, years, e, text):
    nl = '\r\n' if '\r\n' in text else '\n'
    text = fill(text, 'title', render_title(site, e), nl)
    text = fill(text, 'head', render_head(site, e), nl)
    text = fill(text, 'nav', render_nav(years, e), nl)
    for key in ('credit', 'credit_bottom'):
        has_slot = count_slot(text, key) != (0, 0)
        if key in e:
            text = fill(text, key, e[key], nl)
        elif has_slot:
            raise SlotError(f'slot "{key}" present but years.json has no "{key}" for {e["year"]}')
    for key in ('credit', 'credit_bottom'):
        if key in e and count_slot(text, key) != (1, 1):
            raise SlotError(f'years.json has "{key}" but the page has no slot')
    return text


def render_home_page(site, years, text):
    nl = '\r\n' if '\r\n' in text else '\n'
    text = fill(text, 'head', render_home_head(site), nl)
    return fill(text, 'cards', render_cards(years), nl)


def render_all(site, years):
    """-> ({path: new_text}, [errors])"""
    out, errors = {}, []
    for e in years:
        p = PUBLIC / str(e['year']) / 'index.html'
        if not p.exists():
            errors.append(f'{p.relative_to(ROOT)}: missing (create it from templates/year.html)')
            continue
        try:
            out[p] = render_year_page(site, years, e, read(p))
        except SlotError as ex:
            errors.append(f'{p.relative_to(ROOT)}: {ex}')
    p = PUBLIC / 'index.html'
    try:
        out[p] = render_home_page(site, years, read(p))
    except (SlotError, FileNotFoundError) as ex:
        errors.append(f'{p.relative_to(ROOT)}: {ex}')
    return out, errors


# ---------------------------------------------------------------- check ----

REF_RX = re.compile(r'''(?:\bsrc|\bhref|\bposter|\bdata-src)\s*=\s*(?:"([^"]*)"|'([^']*)')|url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]*))\s*\)''', re.I)
SCHEME_RX = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#)', re.I)


def local_refs(text):
    # drop comments (conditional comments, our slot markers) before scanning
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    for m in REF_RX.finditer(text):
        ref = next(g for g in m.groups() if g is not None).strip()
        if ref and not SCHEME_RX.match(ref) and '{' not in ref:
            yield re.split(r'[?#]', ref, maxsplit=1)[0]


def ref_exists(page_dir, ref):
    if not ref:
        return True
    target = page_dir / ref.lstrip('/') if not ref.startswith('/') else PUBLIC / ref.lstrip('/')
    if target.is_dir():
        return (target / 'index.html').exists()
    return target.exists()


def check(site, years):
    problems = []
    nums = [e['year'] for e in years]
    rendered, errs = render_all(site, years)
    problems += errs

    for d in sorted(PUBLIC.iterdir()):
        if d.is_dir() and re.fullmatch(r'\d{4}', d.name) and int(d.name) not in nums:
            problems.append(f'public/{d.name}/: not listed in years.json')

    for e in years:
        y = e['year']
        p = PUBLIC / str(y) / 'index.html'
        rel = f'public/{y}/index.html'
        if not p.exists():
            continue
        text = read(p)
        # slots present
        for name in ('title', 'head', 'nav'):
            if count_slot(text, name) != (1, 1):
                problems.append(f'{rel}: slot "{name}" missing or duplicated')
        # nav structure (parsed from the page itself)
        m = slot_rx('nav').search(text)
        if m:
            nav = m.group(2)
            links = re.findall(r'<li><a href="\.\./(\d{4})"([^>]*)>', nav)
            if [int(a) for a, _ in links] != nums:
                problems.append(f'{rel}: nav does not link to every year in order')
            active = [int(a) for a, attrs in links if 'class="active"' in attrs]
            if active != [y]:
                problems.append(f'{rel}: nav active item is {active}, expected [{y}]')
            prev = re.findall(r'class="year-arrow prev" href="\.\./(\d{4})/"', nav)
            nxt = re.findall(r'class="year-arrow next" href="\.\./(\d{4})/"', nav)
            i = nums.index(y)
            want_prev = [nums[i - 1]] if i > 0 else []
            want_next = [nums[i + 1]] if i < len(nums) - 1 else []
            if [int(a) for a in prev] != want_prev:
                problems.append(f'{rel}: prev arrow {prev}, expected {want_prev}')
            if [int(a) for a in nxt] != want_next:
                problems.append(f'{rel}: next arrow {nxt}, expected {want_next}')
        # og:image / twitter:image files
        for prop in ('og:image', 'twitter:image'):
            mm = re.search(r'(?:property|name)="%s" content="([^"]+)"' % prop, text)
            if not mm:
                problems.append(f'{rel}: no {prop} meta tag')
                continue
            url = mm.group(1)
            if not url.startswith(site['base_url'] + '/'):
                problems.append(f'{rel}: {prop} {url} is not under {site["base_url"]}')
                continue
            f = PUBLIC / url[len(site['base_url']) + 1:]
            if not f.is_file():
                problems.append(f'{rel}: {prop} file missing: {f.relative_to(ROOT)}')
        # local references
        for ref in sorted(set(local_refs(text))):
            if not ref_exists(p.parent, ref):
                problems.append(f'{rel}: referenced file missing: {ref}')
        # thumbnail source
        if e.get('thumb') and not (PUBLIC / e['thumb']).is_file():
            problems.append(f'years.json {y}: thumb source missing: public/{e["thumb"]}')
        if e.get('thumb') and not (PUBLIC / 'img' / 'cards' / f'{y}.jpg').is_file():
            problems.append(f'public/img/cards/{y}.jpg missing (run: make images)')
        if not e.get('card_bg'):
            problems.append(f'years.json {y}: no card_bg (run: make images)')

    # home page
    home = PUBLIC / 'index.html'
    if home.exists():
        t = read(home)
        for n in nums:
            if f'<a class="card" href="./{n}/">' not in t:
                problems.append(f'public/index.html: no card for {n}')
        for ref in sorted(set(local_refs(t))):
            if not ref_exists(home.parent, ref):
                problems.append(f'public/index.html: referenced file missing: {ref}')
        if not (PUBLIC / 'img' / 'og' / 'home.jpg').is_file():
            problems.append('public/img/og/home.jpg missing')

    # up to date?
    for p, new in rendered.items():
        if read(p) != new:
            problems.append(f'{p.relative_to(ROOT)}: generated slots out of date (run: make build)')
    return problems


# --------------------------------------------------------------- images ----

def edge_colour(im):
    """Average colour of the 1px border, as #rrggbb."""
    im = im.convert('RGB')
    w, h = im.size
    px = im.load()
    pts = [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)] + \
          [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    n = len(pts)
    return '#%02x%02x%02x' % tuple(round(sum(c[i] for c in pts) / n) for i in range(3))


def make_thumbs(years):
    try:
        from PIL import Image
    except ImportError:
        sys.exit('--images needs Pillow (pip install Pillow)')
    changed_json = False
    (PUBLIC / 'img' / 'cards').mkdir(parents=True, exist_ok=True)
    for e in years:
        if not e.get('thumb'):
            continue
        src = PUBLIC / e['thumb']
        im = Image.open(src)
        im.seek(0)                                   # first frame of animated gifs
        if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
            im = im.convert('RGBA')
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        im = im.convert('RGB')
        if e.get('thumb_crop'):
            a, b = map(int, e['thumb_crop'].split(':'))
            w, h = im.size
            cw, ch = (w, round(w * b / a)) if h * a >= w * b else (round(h * a / b), h)
            l, t = (w - cw) // 2, (h - ch) // 2
            im = im.crop((l, t, l + cw, t + ch))
        scale = min(1.0, THUMB_MAX / max(im.size))
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        out = PUBLIC / 'img' / 'cards' / f'{e["year"]}.jpg'
        im.save(out, 'JPEG', quality=THUMB_QUALITY, optimize=True, progressive=True)
        print(f'thumb {e["year"]}: {im.size[0]}x{im.size[1]}')
        if not e.get('card_bg'):
            e['card_bg'] = edge_colour(im)
            changed_json = True
            print(f'  card_bg for {e["year"]} -> {e["card_bg"]}')
    if changed_json:
        # only reached when a year had no card_bg; rewrite keeping the one-entry-per-line layout
        data = json.loads(YEARS_JSON.read_text(encoding='utf-8'))
        by = {e['year']: e for e in years}
        for ent in data['years']:
            ent['card_bg'] = by[ent['year']]['card_bg']
        head = YEARS_JSON.read_text(encoding='utf-8').split('  "years": [')[0]
        body = ',\n'.join('    ' + json.dumps(x, ensure_ascii=False) for x in data['years'])
        YEARS_JSON.write_text(head + '  "years": [\n' + body + '\n  ]\n}\n', encoding='utf-8')


def make_og():
    script = ROOT / 'scripts' / 'og.mjs'
    r = subprocess.run(['node', str(script), str(YEARS_JSON), str(PUBLIC)])
    if r.returncode:
        sys.exit('og image generation failed (needs node + playwright with chromium)')


# ----------------------------------------------------------------- main ----

def new_year(year, site, years):
    if any(e['year'] == year for e in years):
        sys.exit(f'{year} is already in years.json')
    p = PUBLIC / str(year) / 'index.html'
    if p.exists():
        sys.exit(f'{p.relative_to(ROOT)} already exists')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((TEMPLATES / 'year.html').read_text(encoding='utf-8').replace('{{year}}', str(year)), encoding='utf-8')
    print(f'created {p.relative_to(ROOT)}')
    print(f'next: add a {year} entry to years.json, drop the postcard image next to the page, then `make images`')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='verify only; exit 1 on problems')
    ap.add_argument('--images', action='store_true', help='regenerate thumbnails and share images first')
    ap.add_argument('--new', type=int, metavar='YEAR', help='create public/YEAR/index.html from the template')
    args = ap.parse_args()

    site, years = load()
    if args.new:
        return new_year(args.new, site, years)
    if args.images and not args.check:
        make_thumbs(years)
        site, years = load()          # card_bg may have been filled in
        make_og()

    if args.check:
        problems = check(site, years)
        for p in problems:
            print('ERROR', p)
        print(f'{len(problems)} problem(s)' if problems else f'ok: {len(years)} year pages + home')
        sys.exit(1 if problems else 0)

    out, errors = render_all(site, years)
    if errors:
        for er in errors:
            print('ERROR', er)
        sys.exit(1)
    n = 0
    for p, new in out.items():
        if read(p) != new:
            with open(p, 'w', newline='', encoding='utf-8') as f:
                f.write(new)
            print('updated', p.relative_to(ROOT))
            n += 1
    print(f'{n} file(s) changed, {len(out) - n} up to date')


if __name__ == '__main__':
    main()
