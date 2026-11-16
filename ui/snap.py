"""Прилипання під час руху і зміни розміру: до сітки, країв екрана і сусідніх віджетів.
Чиста математика без вікон — перевіряється офлайн."""

NEAR = 8          # на якій відстані «примагнічує» до краю (пікселі)


def _snap_value(v, targets, grid):
    """Найближча ціль у межах NEAR, інакше — крок сітки."""
    best = None
    for t in targets:
        d = abs(v - t)
        if d <= NEAR and (best is None or d < abs(v - best)):
            best = t
    if best is not None:
        return best
    return round(v / grid) * grid if grid > 1 else v


def _targets(others, screen, gap):
    """Лінії, до яких можна прилипнути: (вертикальні x, горизонтальні y)."""
    sx, sy, sw, sh = screen
    xs = [sx + gap, sx + sw - gap, sx + sw / 2]
    ys = [sy + gap, sy + sh - gap, sy + sh / 2]
    for ox, oy, ow, oh in others:
        xs += [ox, ox + ow, ox - gap, ox + ow + gap]
        ys += [oy, oy + oh, oy - gap, oy + oh + gap]
    return xs, ys


def snap_move(rect, others, screen, grid=10, gap=12):
    """rect=(x,y,w,h) → нове (x, y). Липне лівим/правим/центром і верхом/низом/центром."""
    x, y, w, h = rect
    xs, ys = _targets(others, screen, gap)
    cands = []
    for edge, off in ((x, 0), (x + w, w), (x + w / 2, w / 2)):
        t = _snap_value(edge, xs, 0)
        if t != edge:
            cands.append((abs(t - edge), t - off))
    nx = min(cands)[1] if cands else (round(x / grid) * grid if grid > 1 else x)
    cands = []
    for edge, off in ((y, 0), (y + h, h), (y + h / 2, h / 2)):
        t = _snap_value(edge, ys, 0)
        if t != edge:
            cands.append((abs(t - edge), t - off))
    ny = min(cands)[1] if cands else (round(y / grid) * grid if grid > 1 else y)
    return int(round(nx)), int(round(ny))


def snap_resize(rect, edges, others, screen, grid=10, gap=12, min_w=40, min_h=30):
    """rect=(x,y,w,h), edges — які краї тягнуть: підрядок із 'l','r','t','b'. → новий (x,y,w,h)."""
    x, y, w, h = rect
    xs, ys = _targets(others, screen, gap)
    l, r, t, b = x, x + w, y, y + h
    if "l" in edges:
        l = min(_snap_value(l, xs, grid), r - min_w)
    if "r" in edges:
        r = max(_snap_value(r, xs, grid), l + min_w)
    if "t" in edges:
        t = min(_snap_value(t, ys, grid), b - min_h)
    if "b" in edges:
        b = max(_snap_value(b, ys, grid), t + min_h)
    return int(round(l)), int(round(t)), int(round(r - l)), int(round(b - t))
