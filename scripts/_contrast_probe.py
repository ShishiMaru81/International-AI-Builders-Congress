def lum(hexv):
    h = hexv.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def c(x):
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = map(c, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    L1, L2 = lum(a), lum(b)
    hi, lo = max(L1, L2), min(L1, L2)
    return (hi + 0.05) / (lo + 0.05)


for m in ['#5c6b61', '#55665a', '#4f5f54', '#4a594f', '#445348']:
    print('muted', m, 'white', round(ratio(m, '#ffffff'), 3), 'canvas', round(ratio(m, '#f5f8f3'), 3))
for p in ['#0f6a47', '#0e6544', '#0d5f40', '#127a52', '#0c583c', '#0b5338']:
    print('white on', p, round(ratio('#ffffff', p), 3))
print('landing old', round(ratio('#778471', '#f7faf3'), 3), 'new', round(ratio('#556555', '#f7faf3'), 3))
print('demo old', round(ratio('#79816b', '#eff1e6'), 3), 'new', round(ratio('#565e4c', '#eff1e6'), 3))
