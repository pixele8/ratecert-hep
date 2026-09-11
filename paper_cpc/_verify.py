import fitz, re

d = fitz.open('ratecert_hep_cpc.pdf')
full = '\n'.join(p.get_text() for p in d)
flat = re.sub(r'\s+', ' ', full)

print('--- Program Summary fields (whitespace-normalised) ---')
fields = [
    'Program Title:',
    'CPC Library link to program files:',
    "Developer's repository link:",
    'Licensing provisions:',
    'Programming language:',
    'Nature of problem:',
    'Solution method:',
    'Additional comments including restrictions',
    'References:',
]
for f in fields:
    print(('  OK  ' if f in flat else '  !!  MISSING  ') + f)

print()
print('--- K=n boundary wording ---')
print('   "special case":', 'special case' in flat, '| "degenerates":', 'degenerates' in flat)

print()
print('--- figures: vector drawings + raster images per page ---')
tot_draw = tot_img = 0
for i, p in enumerate(d):
    dr = len(p.get_drawings())
    im = len(p.get_images(full=True))
    tot_draw += dr
    tot_img += im
    if dr > 200 or im:
        print('   page %2d: drawings=%-5d images=%d' % (i + 1, dr, im))
print('   TOTAL drawings=%d images=%d' % (tot_draw, tot_img))

print()
print('--- figure captions ---')
for m in re.findall(r'Figure\s*\d+[.:][^\n]{0,68}', full):
    print('   ', m.strip())

print()
print('--- section headings ---')
for m in re.finditer(r'(?m)^(\d{1,2})\.\s+([A-Z][^\n]{3,60})$', full):
    print('   %s. %s' % (m.group(1), m.group(2)))
