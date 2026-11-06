#!/usr/bin/env python3
"""Ground-truth vision battery: rank vision-capable models by capability, not flags.

Use when model selection needs vision accuracy and no index measures it
(references/model-selection-workflow.md Step 5). Generates test images with known
answers, calls each candidate over its own protocol surface, grades against
ground truth with facts and formatting checked separately.

Dependencies: PIL. Keys: read by name from ~/.hermes/.env, never printed.
Edit CANDIDATES to the current lineup. Built-in pitfalls: max_tokens >= 1000
(thinking models emit empty content on a tight budget -- EMPTY is 'no data', not
a miss; 429/ERR cells likewise score 'no data'), fact-vs-format grading (models
drop hyphens; that is a format miss, not a perception miss), and a hard round
(low-contrast rotated OCR, dense chart, tiny UI text) because an easy battery
saturates and cannot rank.
"""
import base64, io, json, re, sys, time, urllib.request, pathlib
from PIL import Image, ImageDraw, ImageFont

def load_key(name):
    for line in (pathlib.Path.home() / '.hermes/.env').read_text(errors='replace').splitlines():
        m = re.match(rf'\s*(?:export\s+)?{name}\s*=\s*(.*)$', line)
        if m:
            v = m.group(1).strip()
            if len(v) > 1 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            return v
    return ''

def font(sz):
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', sz)
    except Exception:
        return ImageFont.load_default()

# ---------- fixtures (ground truth lives in the task check functions) ----------
def img_chart():
    vals = [('L01',41),('L02',87),('L03',63),('L04',29),('L05',95),('L06',54),
            ('L07',72),('L08',38),('L09',81),('L10',46),('L11',67),('L12',58)]
    im = Image.new('RGB', (1300, 480), 'white'); d = ImageDraw.Draw(im)
    for i, (k, v) in enumerate(vals):
        x = 45 + i * 104
        d.rectangle([x, 410 - v * 3.6, x + 62, 410], fill='#2e7d32')
        d.text((x + 12, 418), k, fill='black', font=font(15))
        d.text((x + 18, 410 - v * 3.6 - 20), str(v), fill='black', font=font(15))
    d.text((420, 15), 'Inventory Turns by Lane', fill='black', font=font(24))
    return im

def img_shapes():
    im = Image.new('RGB', (800, 500), 'white'); d = ImageDraw.Draw(im)
    for x, y in [(100,100),(250,100),(400,100),(550,100),(700,100),(170,250),(320,250)]:
        d.ellipse([x-40, y-40, x+40, y+40], fill='red')
    for x, y in [(500,250),(650,250),(250,400)]:
        d.polygon([(x, y-45), (x-45, y+40), (x+45, y+40)], fill='green')
    for x, y in [(450, 400), (620, 400)]:
        d.rectangle([x-40, y-40, x+40, y+40], fill='blue')
    return im

def img_serial():
    im = Image.new('RGB', (700, 120), 'white'); d = ImageDraw.Draw(im)
    d.text((60, 35), 'SN-K4X9-72QW', fill='black', font=font(40))
    return im

def img_rot_ocr():
    im = Image.new('RGB', (700, 160), '#8a8a8a'); d = ImageDraw.Draw(im)
    d.text((60, 50), '7KQ-2M4X-91B', fill='#606060', font=font(44))
    return im.rotate(8, expand=True, fillcolor='#8a8a8a')

def img_table():
    im = Image.new('RGB', (760, 320), 'white'); d = ImageDraw.Draw(im)
    rows = [('12','44','7'),('8','15','22'),('19','6','31'),('12','33','9')]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            d.text((80 + c * 200, 50 + r * 60), cell, fill='black', font=font(28))
    return im

def img_ui():
    im = Image.new('RGB', (900, 560), '#f0f0f0'); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 900, 44], fill='#2b2b3a')
    d.text((16, 12), 'report_v3_final.xlsx', fill='white', font=font(19))
    for i, t in enumerate(('Save', 'Export', 'Share')):
        d.rectangle([20 + i * 110, 60, 110 + i * 110, 96], outline='#999', width=2)
        d.text((35 + i * 110, 68), t, fill='#333', font=font(14))
    rows = [('T-1042', 'alpha', 'done'), ('T-1057', 'beta', 'open'), ('T-1063', 'gamma', 'pending')]
    d.rectangle([20, 130, 880, 160], fill='#d8d8e8')
    for i, h in enumerate(('ID', 'Name', 'Status')):
        d.text((40 + i * 250, 136), h, fill='black', font=font(14))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            d.text((40 + c * 250, 175 + r * 38), cell, fill='#111', font=font(14))
    return im

# each check returns ((facts_ok, format_ok), extra) -- facts and format graded apart
def g_chart(a):
    return ((('l07' in a), True), (bool(re.search(r'l0?9', a)) and ('81' in a), True))
def g_shapes(a):
    counts = all(re.search(rf'\b{x}\b', re.sub(r'\D', ' ', a)) for x in ('7', '3', '2'))
    pos = ('rot' in a or 'red' in a) and ('kreis' in a or 'circle' in a)
    return ((counts, True), (pos, True))
def g_serial(a):
    flat = a.replace(' ', '')
    return ((('sn-k4x9-72qw' in flat), ('sn-k4x9-72qw' in a)), True)
def g_rotocr(a):
    flat = a.replace(' ', '').replace('-', '')
    return ((('7kq2m4x91b' in flat), ('7kq-2m4x-91b' in a.replace(' ', ''))), True)
def g_table(a):
    return ((('54' in a), True), True)
def g_ui(a):
    flat = a.replace(' ', '')
    return ((('report_v3_final.xlsx' in flat), True), (('t-1057' in flat), True))

TASKS = [
    ('chart', img_chart, g_chart,
     'Welches Label hat den Balken mit Wert 72? Und welches Label hat den dritthoechsten Balken (und welchen Wert)?'),
    ('shapes', img_shapes, g_shapes,
     'Wie viele rote Kreise, gruene Dreiecke, blaue Quadrate? Welche Form und Farbe liegt oben links? Gib vier kurze Antworten.'),
    ('ocr', img_serial, g_serial,
     'Welche Seriennummer steht auf dem Etikett? Antworte exakt.'),
    ('rotocr', img_rot_ocr, g_rotocr,
     'Welche Zeichenkette steht da (Seriennummer)? Antworte exakt.'),
    ('table', img_table, g_table,
     'Was ist die Summe der drei Zahlen in der untersten Zeile?'),
    ('ui', img_ui, g_ui,
     "Welcher Dateiname steht in der Titelleiste? Und welche ID hat die Zeile mit Status 'open'?"),
]

# ---------- callers per protocol shape ----------
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/126.0'}

def call_chat(base, key, model, q, img):
    payload = json.dumps({'model': model, 'max_tokens': 1000, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': q},
        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img}'}}]}]}).encode()
    h = {**UA, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
         'x-opencode-session': f'cap-{int(time.time())}'}
    req = urllib.request.Request(base + '/chat/completions', data=payload, headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        msg = json.loads(r.read())['choices'][0]['message']
        if msg.get('content'):
            return msg['content']
        rz = msg.get('reasoning') or ''
        return f'(empty content; reasoning chars={len(rz)})' if rz else '(empty content)'

def call_anthropic(base, key, model, q, img):
    payload = json.dumps({'model': model, 'max_tokens': 1000, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': q},
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': img}}]}]}).encode()
    h = {**UA, 'x-api-key': key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json',
         'x-opencode-session': f'cap-{int(time.time())}'}
    req = urllib.request.Request(base + '/messages', data=payload, headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read())
        txt = ''.join(b.get('text', '') for b in j.get('content', []) if b.get('type') == 'text')
        if txt:
            return txt
        th = sum(len(b.get('thinking', '')) for b in j.get('content', []) if b.get('type') == 'thinking')
        return f'(empty content; thinking chars={th})' if th else '(empty content)'

def call_responses(base, key, model, q, img):
    payload = json.dumps({'model': model, 'max_output_tokens': 1000, 'input': [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': q},
        {'type': 'input_image', 'image_url': f'data:image/png;base64,{img}'}}]}]}).encode()
    h = {**UA, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
         'x-opencode-session': f'cap-{int(time.time())}'}
    req = urllib.request.Request(base, data=payload, headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read())
        out = []
        for item in j.get('output', []):
            for c in item.get('content', []) or []:
                if c.get('type') in ('output_text', 'text'):
                    out.append(c.get('text', ''))
        return ''.join(out) or '(empty content)'

# ---------- edit per current lineup: (label, model, caller, base_url, key_env) ----------
CANDIDATES = [
    ('ollama', 'mimo-v2.6-pro', call_chat, 'https://ollama.com/v1', 'OLLAMA_API_KEY'),
    ('ollama', 'kimi-k3.1-pro', call_chat, 'https://ollama.com/v1', 'OLLAMA_API_KEY'),
    ('go-chat', 'step-5-preview', call_chat, 'https://opencode.ai/zen/go/v1', 'OPENCODE_GO_API_KEY'),
    ('go-anth', 'claude-haiku-5-5', call_anthropic, 'https://opencode.ai/zen/go/v1', 'OPENCODE_GO_API_KEY'),
    ('go-anth', 'qwen3.8-max', call_anthropic, 'https://opencode.ai/zen/go/v1', 'OPENCODE_GO_API_KEY'),
    ('go-resp', 'grok-4.7', call_responses, 'https://opencode.ai/inference/go/openai/v1/responses', 'OPENCODE_GO_API_KEY'),
]

def main():
    keys = {}
    only = set(sys.argv[1:])
    print(f"{'model':26} " + ' '.join(f'{t[0]:>7}' for t in TASKS) + '  clean')
    details = {}
    for lane, model, fn, base, key_env in CANDIDATES:
        if only and model not in only:
            continue
        if key_env not in keys:
            keys[key_env] = load_key(key_env)
        row, det = [], []
        for name, img_fn, check, q in TASKS:
            buf = io.BytesIO(); img_fn().save(buf, format='PNG')
            img = base64.b64encode(buf.getvalue()).decode()
            try:
                ans = fn(base, keys[key_env], model, q, img)
            except Exception as e:
                ans = f'ERROR {type(e).__name__}: {str(e)[:80]}'
            if ans.startswith('ERROR') or ans.startswith('(empty'):
                g = 'NODATA'
            else:
                (facts, fmt), _extra = check(ans.lower())
                g = 'OK' if (facts and fmt) else ('FMT' if facts else 'FAIL')
            row.append(g)
            if g != 'OK':
                det.append((name, g, ans.replace('\n', ' ')[:220]))
            time.sleep(1)
        clean = sum(1 for g in row if g == 'OK')
        details[model] = det
        print(f"{lane + ':' + model:26} " + ' '.join(f'{g:>7}' for g in row) + f'  {clean}/{len(TASKS)}')
    print('\n===== non-OK cells (FMT = facts right, formatting off; NODATA = no quality statement) =====')
    for model, det in details.items():
        for name, g, ans in det:
            print(f'[{model} / {name} / {g}] {ans}')

if __name__ == '__main__':
    main()
