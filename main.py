# Make the cutest picture — make.fun bounty cutest-picture-01
#
# 3D version of the entry: the same chubby cream cat ("Mochi") hugging a
# glossy pink heart, rendered to LOOK 3D — like a clay / animated-film
# character: round volumes with soft shading, glossy highlights, a soft
# drop shadow, depth between layers (heart in front of the body, arms
# wrapping it with shadow), big sparkling eyes with reflections.
#
# STATUS (12 Nov 2026): final design follows the champion style (top-3
# entries viewed directly: w1 kitten+chick, w2 otter+duck, w3 rabbit+
# strawberry). Same style, ORIGINAL composition: Mochi the chubby cream
# cat hugging a glossy pink heart (our differentiator), small pink bow
# accessory, huge amber eyes, no outlines, plain ivory background.
#
# Pure Python 3.13 standard library only (math, os, struct, zlib) — no
# network, no third-party packages, no randomness, no time. The program
# is fully deterministic: two runs write byte-identical output.
# NOTE: RULES.txt says the harness runs "standard library only: nothing
# is installed before it runs", so PIL/numpy must NOT be used here even
# though they exist on this dev VM.
#
# How the 3D look works: a tiny software rasterizer with per-pixel
# spherical shading. For every pixel inside a shape, the surface normal
# is rebuilt from its normalized position and shaded with a diffuse +
# specular (Blinn-style) light from the top-left, plus ambient. Soft
# shadows/highlights are layered translucent ellipses (a cheap, fully
# deterministic fake blur). Final PNG is encoded by hand (zlib level 9)
# so the bytes are identical on every run.
#
# Run locally:
#   mkdir -p out3d && MAKEFUN_OUTPUT_DIR=out3d python3 main-3d.py
#   -> writes out3d/entry.png (copy to entry-3d-preview.png)
#
# Judge rubric it is drawn for (most important first):
#   1. cute at one glance: one big clear subject (a chubby cat)
#   2. the subject itself is cute: soft round shapes, big bright eyes,
#      small chubby proportions, a smile that makes you smile
#   3. charm: head tilt, a tiny accessory, clumsy oversized paws
#      hugging a pink heart
#   4. craft: clean 3D clay look, right number of eyes/ears/limbs,
#      no text, no smears
#   5. reads small: the subject fills most of the frame

import math
import os
import struct
import zlib

W = 1024
H = 1024


# ---------------------------------------------------------------- canvas

class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    # -- low-level ------------------------------------------------------
    def _blend_px(self, x, y, r, g, b, a):
        """Blend one pixel; a is 0..255."""
        if a <= 0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = (y * self.w + x) * 3
        if a >= 255:
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b
            return
        inv = 255 - a
        px = self.px
        px[i] = (r * a + px[i] * inv) // 255
        px[i + 1] = (g * a + px[i + 1] * inv) // 255
        px[i + 2] = (b * a + px[i + 2] * inv) // 255

    def _fill_span(self, y, x0, x1, r, g, b, a):
        """Fill row y, pixels x0..x1 inclusive, with alpha a (0..255)."""
        if y < 0 or y >= self.h or x1 < x0:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x1 < x0:
            return
        if a >= 255:
            n = x1 - x0 + 1
            i = (y * self.w + x0) * 3
            self.px[i:i + n * 3] = bytes((r, g, b)) * n
            return
        for x in range(x0, x1 + 1):
            self._blend_px(x, y, r, g, b, a)

    def _fill_row_aa(self, y, xl, xr, r, g, b, a):
        """Fill the continuous interval [xl, xr] on row y with edge AA."""
        if xr <= xl:
            return
        xs = int(math.floor(xl))
        xe = int(math.floor(xr))
        if xs == xe:
            cov = xr - xl
            if cov > 0:
                self._blend_px(xs, y, r, g, b, int(a * cov))
            return
        cov_l = (xs + 1) - xl
        if cov_l > 0:
            self._blend_px(xs, y, r, g, b, int(a * cov_l))
        if xe - 1 >= xs + 1:
            self._fill_span(y, xs + 1, xe - 1, r, g, b, a)
        cov_r = xr - xe
        if cov_r > 0:
            self._blend_px(xe, y, r, g, b, int(a * cov_r))

    # -- flat primitives (same approach as the 2D entry) ----------------
    def vgrad(self, top, bottom):
        """Vertical linear gradient background."""
        for y in range(self.h):
            t = y / (self.h - 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            self._fill_span(y, 0, self.w - 1, r, g, b, 255)

    def ellipse(self, cx, cy, rx, ry, color, alpha=255, angle=0.0):
        """Filled ellipse, optionally rotated by angle (radians).

        Analytic anti-aliasing: for each row the exact x-interval of the
        (rotated) ellipse is solved from its quadratic, and the two edge
        pixels are blended by their coverage.
        """
        r, g, b = color
        c = math.cos(angle)
        s = math.sin(angle)
        rx2 = rx * rx
        ry2 = ry * ry
        qa = c * c / rx2 + s * s / ry2
        qb_factor = 2.0 * c * s * (1.0 / rx2 - 1.0 / ry2)
        qc_factor = s * s / rx2 + c * c / ry2
        y0 = int(math.floor(cy - max(rx, ry) - 1))
        y1 = int(math.ceil(cy + max(rx, ry) + 1))
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            yy = (y + 0.5) - cy
            qb = qb_factor * yy
            qc = qc_factor * yy * yy - 1.0
            disc = qb * qb - 4.0 * qa * qc
            if disc <= 0.0:
                continue
            sq = math.sqrt(disc)
            xl = (-qb - sq) / (2.0 * qa) + cx
            xr = (-qb + sq) / (2.0 * qa) + cx
            self._fill_row_aa(y, xl, xr, r, g, b, alpha)

    def circle(self, cx, cy, rad, color, alpha=255):
        self.ellipse(cx, cy, rad, rad, color, alpha)

    def circle_chain(self, points, radii, color, alpha=255):
        """A thick smooth curve: overlapping circles along `points`."""
        for (x, y), rad in zip(points, radii):
            self.circle(x, y, rad, color, alpha)

    def bezier_chain(self, p0, p1, p2, n, r0, r1, color, alpha=255):
        """A thick smooth curve along a quadratic Bezier."""
        for i in range(n + 1):
            t = i / n
            u = 1.0 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            rad = r0 + (r1 - r0) * t
            self.circle(x, y, rad, color, alpha)

    def shaded_bezier_chain(self, p0, p1, p2, n, r0, r1, color,
                            light=(-0.32, -0.45), ambient=0.72,
                            diffuse=0.28, spec_strength=0.38,
                            spec_power=20.0):
        """A volumetric tube along a quadratic Bezier: overlapping
        sphere-shaded discs sampled densely, so the tube reads as a
        bent cylinder with a continuous sheen instead of a flat band."""
        for i in range(n + 1):
            t = i / n
            u = 1.0 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            rad = r0 + (r1 - r0) * t
            self.shaded_ellipse(x, y, rad, rad, color, light=light,
                                ambient=ambient, diffuse=diffuse,
                                spec_strength=spec_strength,
                                spec_power=spec_power)

    def heart_rows(self, cx, cy, size, tilt=0.0):
        """Scanline intervals of the classic parametric heart; returns a
        dict row -> (xl, xr). Shared by heart() and shaded_heart()."""
        c = math.cos(tilt)
        s = math.sin(tilt)
        scale = size / 32.0
        rows = {}
        n = 3600
        for i in range(n):
            t = 2.0 * math.pi * i / n
            x = 16.0 * math.sin(t) ** 3
            y = -(13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
                 - 2.0 * math.cos(3 * t) - math.cos(4 * t))
            xr = (x * c - y * s) * scale + cx
            yr = (x * s + y * c) * scale + cy
            row = int(math.floor(yr))
            if row < 0 or row >= self.h:
                continue
            bucket = rows.get(row)
            if bucket is None:
                rows[row] = [xr, xr]
            else:
                if xr < bucket[0]:
                    bucket[0] = xr
                if xr > bucket[1]:
                    bucket[1] = xr
        return rows

    def heart(self, cx, cy, size, color, alpha=255, tilt=0.0):
        """Filled flat heart from the classic parametric curve."""
        r, g, b = color
        for y, (xl, xr) in self.heart_rows(cx, cy, size, tilt).items():
            self._fill_row_aa(y, xl, xr, r, g, b, alpha)

    def plus_star(self, cx, cy, size, color, alpha=255):
        """A tiny 4-point sparkle (two crossed bars)."""
        half = size / 2.0
        bar = max(1.5, size / 5.0)
        self.ellipse(cx, cy, half, bar, color, alpha)
        self.ellipse(cx, cy, bar, half, color, alpha)

    def arc_chain(self, cx, cy, rad, a0, a1, color, radius, alpha=255):
        """Small circles along an arc (used for the smile / brows).
        Sampled densely so the stroke is continuous, not dotted."""
        steps = max(2, int(abs(a1 - a0) * rad / 3.0))
        pts = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        self.circle_chain(pts, [radius] * len(pts), color, alpha)

    # -- 3D helpers ------------------------------------------------------
    def soft_blob(self, cx, cy, rx, ry, color, alpha, angle=0.0,
                  layers=12):
        """A soft-edged ellipse (fake blur): several concentric ellipses
        with falling alpha, so shadows and glows feather out instead of
        having a hard edge. Fully deterministic. The cubic falloff and
        small growth step keep the layering invisible."""
        for k in range(layers, 0, -1):
            f = k / layers
            a = int(alpha * (1.0 - f) ** 3 + 0.5)
            if a <= 0:
                continue
            # outer layers are bigger and fainter
            grow = 1.0 + (1.0 - f) * 0.4
            self.ellipse(cx, cy, rx * grow, ry * grow, color, a,
                         angle=angle)

    def fur_fringe(self, cx, cy, rx, ry, color_light, color_dark,
                   angle=0.0, arc=(3.3, 6.1), n=110, seed=7):
        """Deterministic fine fur hairs along an ellipse silhouette:
        short thin strokes sticking out of the boundary, length/tilt
        varied by an integer hash of the index (no random module, no
        time). `arc` is the parametric-angle range to fringe."""
        ca = math.cos(angle)
        sa = math.sin(angle)
        for i in range(n):
            t = arc[0] + (arc[1] - arc[0]) * i / max(1, n - 1)
            # base point on the (unrotated) ellipse, then rotate it
            bx0 = rx * math.cos(t)
            by0 = ry * math.sin(t)
            bx = cx + bx0 * ca - by0 * sa
            by = cy + bx0 * sa + by0 * ca
            # outward normal of the unrotated ellipse, then rotate it
            nx0 = math.cos(t) / rx
            ny0 = math.sin(t) / ry
            nl = math.hypot(nx0, ny0)
            nx0 /= nl
            ny0 /= nl
            nx = nx0 * ca - ny0 * sa
            ny = nx0 * sa + ny0 * ca
            # deterministic variation from an integer hash
            h1 = ((i * 2654435761 + seed * 40503) % 1000) / 1000.0
            h2 = ((i * 40503 + seed * 2654435761) % 1000) / 1000.0
            length = 3.0 + 5.0 * h1
            spread = (h2 - 0.5) * 0.5
            dx = nx * math.cos(spread) - ny * math.sin(spread)
            dy = nx * math.sin(spread) + ny * math.cos(spread)
            ex = bx + dx * length
            ey = by + dy * length
            col = color_light if h1 > 0.5 else color_dark
            ang = math.atan2(dy, dx)
            self.ellipse((bx + ex) / 2.0, (by + ey) / 2.0,
                         length / 2.0 + 1.0, 1.6, col,
                         int(55 + 40 * h2), angle=ang)

    def shaded_ellipse(self, cx, cy, rx, ry, color, angle=0.0,
                       light=(-0.32, -0.45), ambient=0.72, diffuse=0.28,
                       spec_strength=0.5, spec_power=24.0):
        """A filled ellipse shaded like a 3D ball lit from the top-left.

        For each pixel the surface normal is rebuilt from its normalized
        position inside the ellipse (z = sqrt(1 - r^2)) and shaded with
        diffuse + specular against a fixed light. Edge pixels get
        analytic anti-aliasing. `light` is the 2D light direction in
        screen space (x right, y down); its z is derived so |L| = 1.
        """
        lx, ly = light
        lz2 = 1.0 - lx * lx - ly * ly
        lz = math.sqrt(lz2) if lz2 > 0.0 else 0.0
        # light in the ellipse's local (unrotated) coordinates
        ca = math.cos(-angle)
        sa = math.sin(-angle)
        llx = lx * ca - ly * sa
        lly = lx * sa + ly * ca
        r, g, b = color
        w = self.w
        px = self.px
        c = math.cos(angle)
        s = math.sin(angle)
        rx2 = rx * rx
        ry2 = ry * ry
        qa = c * c / rx2 + s * s / ry2
        qb_factor = 2.0 * c * s * (1.0 / rx2 - 1.0 / ry2)
        qc_factor = s * s / rx2 + c * c / ry2
        y0 = int(math.floor(cy - max(rx, ry) - 1))
        y1 = int(math.ceil(cy + max(rx, ry) + 1))
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            yy = (y + 0.5) - cy
            qb = qb_factor * yy
            qc = qc_factor * yy * yy - 1.0
            disc = qb * qb - 4.0 * qa * qc
            if disc <= 0.0:
                continue
            sq = math.sqrt(disc)
            xl = (-qb - sq) / (2.0 * qa) + cx
            xr = (-qb + sq) / (2.0 * qa) + cx
            xs = int(math.floor(xl))
            xe = int(math.floor(xr))
            if xe < 0 or xs >= w:
                continue
            # pixel range with edge coverage
            x_start = max(0, xs)
            x_end = min(w - 1, xe)
            for x in range(x_start, x_end + 1):
                if x == xs:
                    cov = (xs + 1) - xl
                    if xs == xe:
                        cov = xr - xl
                elif x == xe:
                    cov = xr - xe
                else:
                    cov = 1.0
                if cov <= 0.0:
                    continue
                # local coords (rotate point by -angle around centre)
                dx = (x + 0.5) - cx
                dy = (y + 0.5) - cy
                lx_ = dx * ca - dy * sa
                ly_ = dx * sa + dy * ca
                nx = lx_ / rx
                ny = ly_ / ry
                rr = nx * nx + ny * ny
                if rr >= 1.0:
                    continue
                nz = math.sqrt(1.0 - rr)
                ndotl = nx * llx + ny * lly + nz * lz
                if ndotl < 0.0:
                    ndotl = 0.0
                shade = ambient + diffuse * ndotl
                # specular: R.z = 2 * (N.L) * N.z - L.z, view = (0,0,1)
                rz = 2.0 * ndotl * nz - lz
                if rz > 0.0:
                    spec = (rz ** spec_power) * spec_strength
                else:
                    spec = 0.0
                a = cov * 255.0
                # shaded colour, specular added as white
                sr = r * shade + 255.0 * spec
                sg = g * shade + 255.0 * spec
                sb = b * shade + 255.0 * spec
                if sr > 255.0:
                    sr = 255.0
                if sg > 255.0:
                    sg = 255.0
                if sb > 255.0:
                    sb = 255.0
                i = (y * w + x) * 3
                if a >= 255.0:
                    px[i] = int(sr)
                    px[i + 1] = int(sg)
                    px[i + 2] = int(sb)
                else:
                    ai = int(a)
                    inv = 255 - ai
                    px[i] = (int(sr) * ai + px[i] * inv) // 255
                    px[i + 1] = (int(sg) * ai + px[i + 1] * inv) // 255
                    px[i + 2] = (int(sb) * ai + px[i + 2] * inv) // 255

    def shaded_heart(self, cx, cy, size, color, tilt=0.0,
                     ambient=0.70, diffuse=0.30, spec_strength=0.45,
                     spec_power=22.0):
        """A heart shaded like a puffy 3D cushion: brightness domes
        around the heart's centre and a specular kiss near the top-left.
        Uses the same light as shaded_ellipse (top-left, mostly frontal)."""
        lx, ly = -0.32, -0.45
        lz = math.sqrt(max(0.0, 1.0 - lx * lx - ly * ly))
        r, g, b = color
        w = self.w
        px = self.px
        half = size / 2.0
        rows = self.heart_rows(cx, cy, size, tilt)
        for y in sorted(rows.keys()):
            if y < 0 or y >= self.h:
                continue
            xl, xr = rows[y]
            xs = int(math.floor(xl))
            xe = int(math.floor(xr))
            for x in range(max(0, xs), min(w - 1, xe) + 1):
                if x == xs:
                    cov = (xs + 1) - xl
                    if xs == xe:
                        cov = xr - xl
                elif x == xe:
                    cov = xr - xe
                else:
                    cov = 1.0
                if cov <= 0.0:
                    continue
                # dome shading: distance from heart centre, normalized
                dx = ((x + 0.5) - cx) / half
                dy = ((y + 0.5) - cy) / half
                rr = dx * dx + dy * dy
                if rr >= 1.0:
                    nz = 0.05
                    nx = dx
                    ny = dy
                else:
                    nz = math.sqrt(1.0 - rr)
                    nx = dx
                    ny = dy
                ndotl = nx * lx + ny * ly + nz * lz
                if ndotl < 0.0:
                    ndotl = 0.0
                shade = ambient + diffuse * ndotl
                rz = 2.0 * ndotl * nz - lz
                spec = ((rz ** spec_power) * spec_strength
                        if rz > 0.0 else 0.0)
                sr = r * shade + 255.0 * spec
                sg = g * shade + 255.0 * spec
                sb = b * shade + 255.0 * spec
                if sr > 255.0:
                    sr = 255.0
                if sg > 255.0:
                    sg = 255.0
                if sb > 255.0:
                    sb = 255.0
                a = cov * 255.0
                i = (y * w + x) * 3
                if a >= 255.0:
                    px[i] = int(sr)
                    px[i + 1] = int(sg)
                    px[i + 2] = int(sb)
                else:
                    ai = int(a)
                    inv = 255 - ai
                    px[i] = (int(sr) * ai + px[i] * inv) // 255
                    px[i + 1] = (int(sg) * ai + px[i + 1] * inv) // 255
                    px[i + 2] = (int(sb) * ai + px[i + 2] * inv) // 255

    def shaded_leaf(self, cx, cy, length, width, angle, color,
                    light=(-0.32, -0.45), ambient=0.72, diffuse=0.28,
                    spec_strength=0.4, spec_power=20.0):
        """A pointed leaf/teardrop shape (for feline ears): widest near
        the base, tapering to a point at the tip (local -y). Per-pixel
        spherical shading with 2x2 supersampled coverage for smooth
        edges. `width` is the max half-width at the widest point."""
        lx, ly = light
        lz = math.sqrt(max(0.0, 1.0 - lx * lx - ly * ly))
        ca = math.cos(-angle)
        sa = math.sin(-angle)
        r, g, b = color
        w = self.w
        px = self.px
        half_len = length / 2.0
        ext = max(length, width * 2.0) / 2.0 + 2
        y0 = int(math.floor(cy - ext))
        y1 = int(math.ceil(cy + ext))
        x0 = int(math.floor(cx - ext))
        x1 = int(math.ceil(cx + ext))
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            for x in range(max(0, x0), min(w - 1, x1) + 1):
                # 2x2 supersample coverage
                cov = 0
                for sy in (0.25, 0.75):
                    for sx in (0.25, 0.75):
                        dx = (x + sx) - cx
                        dy = (y + sy) - cy
                        lx_ = dx * ca - dy * sa
                        ly_ = dx * sa + dy * ca
                        t = (half_len - ly_) / length
                        if t < 0.0 or t > 1.0:
                            continue
                        s = math.sin(math.pi * t)
                        if s < 0.0:
                            s = 0.0
                        half = width * (s ** 0.7)
                        if abs(lx_) <= half:
                            cov += 1
                if cov == 0:
                    continue
                # shade at pixel centre
                dx = (x + 0.5) - cx
                dy = (y + 0.5) - cy
                lx_ = dx * ca - dy * sa
                ly_ = dx * sa + dy * ca
                nx = lx_ / width
                ny = ly_ / half_len
                rr = nx * nx + ny * ny
                if rr >= 1.0:
                    nz = 0.05
                else:
                    nz = math.sqrt(1.0 - rr)
                ndotl = nx * lx + ny * ly + nz * lz
                if ndotl < 0.0:
                    ndotl = 0.0
                shade = ambient + diffuse * ndotl
                rz = 2.0 * ndotl * nz - lz
                spec = ((rz ** spec_power) * spec_strength
                        if rz > 0.0 else 0.0)
                sr = r * shade + 255.0 * spec
                sg = g * shade + 255.0 * spec
                sb = b * shade + 255.0 * spec
                if sr > 255.0:
                    sr = 255.0
                if sg > 255.0:
                    sg = 255.0
                if sb > 255.0:
                    sb = 255.0
                a = cov * 63.75
                i = (y * w + x) * 3
                if a >= 255.0:
                    px[i] = int(sr)
                    px[i + 1] = int(sg)
                    px[i + 2] = int(sb)
                else:
                    ai = int(a)
                    inv = 255 - ai
                    px[i] = (int(sr) * ai + px[i] * inv) // 255
                    px[i + 1] = (int(sg) * ai + px[i + 1] * inv) // 255
                    px[i + 2] = (int(sb) * ai + px[i + 2] * inv) // 255


# ---------------------------------------------------------------- colors
# Warm pastel palette in the winners' style: cream fur, amber eyes,
# pink heart / bow / pads, plain ivory background.
CREAM_TOP = (255, 248, 236)
CREAM_BOTTOM = (250, 238, 224)
FUR = (250, 236, 214)         # cream fur
FUR_DARK = (222, 196, 160)    # fur shadow / outline tone
FUR_DEEP = (198, 168, 130)
BELLY = (255, 246, 228)
INNER_EAR = (255, 183, 197)
EYE = (30, 18, 12)
AMBER = (206, 134, 42)        # golden-amber iris
AMBER_RIM = (96, 58, 20)      # dark iris rim
NOSE = (238, 125, 142)
BLUSH = (255, 150, 170)
HEART_PINK = (255, 140, 175)
HEART_DEEP = (230, 88, 132)
BOW = (255, 150, 180)
BOW_CENTER = (232, 90, 133)
PAD = (255, 175, 190)         # pink paw pads
MOUTH = (165, 95, 85)


def rot_point(x, y, cx, cy, angle):
    """Rotate point (x, y) around (cx, cy) by angle radians."""
    c = math.cos(angle)
    s = math.sin(angle)
    dx = x - cx
    dy = y - cy
    return (cx + dx * c - dy * s, cy + dx * s + dy * c)


def draw():
    """Mochi the chubby cream cat, front close-up in the winners' style:
    huge head (~half the frame), huge amber eyes, tiny pink nose, small
    smile, blush; body below; glossy pink heart hugged in front with big
    paws (pink pads) on it; feet with pink pads at the bottom corners;
    small pink bow on the head. Plain ivory background, soft studio
    light, no outlines, no hard shadows."""
    cv = Canvas(W, H)

    # -- background: plain warm ivory, barely-there gradient + glow -----
    cv.vgrad(CREAM_TOP, CREAM_BOTTOM)
    cv.soft_blob(512, 480, 430, 430, (255, 255, 255), 34)
    # floor shadow: very soft and light
    cv.soft_blob(512, 962, 330, 34, (150, 118, 92), 40)

    tilt = math.radians(-8)
    hx, hy = 512, 360  # head centre

    # -- body (big round torso) + lighter belly -------------------------
    cv.shaded_ellipse(512, 815, 258, 188, FUR,
                      spec_strength=0.22, spec_power=18)
    cv.shaded_ellipse(512, 855, 168, 128, BELLY,
                      spec_strength=0.22, spec_power=18)
    # soft contact shadow where the chin will rest on the body
    cv.soft_blob(512, 648, 175, 34, (120, 90, 70), 18)

    # -- feet at the bottom corners, pads facing the camera -------------
    for fx in (335, 689):
        cv.shaded_ellipse(fx, 925, 84, 58, FUR,
                          spec_strength=0.22, spec_power=18)
        # pink pads: three small toes + one big pad
        for (tx, ty) in [(fx - 26, 912), (fx, 906), (fx + 26, 912)]:
            cv.ellipse(tx, ty, 12, 15, PAD)
        cv.ellipse(fx, 938, 26, 18, PAD)

    # -- the glossy pink heart, hugged in front of the belly ------------
    cv.shaded_heart(512, 750, 280, HEART_PINK, tilt=math.radians(-4),
                    spec_strength=0.62, spec_power=22)
    # gloss on the heart's upper-left lobe + a sparkle
    cv.soft_blob(455, 700, 52, 28, (255, 255, 255), 120,
                 angle=math.radians(-25))
    cv.plus_star(448, 692, 17, (255, 255, 255), 230)
    # soft contact shadow under the heart's lower edge
    cv.soft_blob(512, 878, 140, 22, (150, 90, 100), 26)

    # -- arms wrapping from the body sides to paws on the heart ---------
    # Volumetric tubes: sphere-shaded discs along the Bezier, so the
    # arms read as bent cylinders with a continuous sheen (no dark
    # outline, like the winners). Plus a soft contact shadow on the
    # heart where each arm rests.
    for (p0, p1, p2, sgn) in [((302, 726), (362, 778), (438, 798), -1),
                              ((722, 726), (662, 778), (586, 798), 1)]:
        # one smooth capsule per arm: the arm is nearly straight, so a
        # single sphere-shaded rotated ellipse reads as a solid
        # volumetric bar with a continuous sheen (a disc chain showed
        # visible ribs along the tube)
        cx = (p0[0] + p2[0]) / 2.0
        cy = (p0[1] + p2[1]) / 2.0
        ang = math.atan2(p2[1] - p0[1], p2[0] - p0[0])
        cv.shaded_ellipse(cx, cy, 84, 33, FUR, angle=ang,
                          spec_strength=0.3, spec_power=20)
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2 + 22
        cv.soft_blob(mx, my, 52, 12, (150, 95, 105), 30,
                     angle=math.radians(30 * sgn))
    # big round paws on the heart, pink pads facing the camera
    for (px, py) in [(440, 798), (584, 798)]:
        cv.shaded_ellipse(px, py, 56, 50, FUR,
                          spec_strength=0.22, spec_power=18)
        for (tx, ty) in [(px - 17, py + 16), (px, py + 20),
                         (px + 17, py + 16)]:
            cv.ellipse(tx, ty, 8, 10, PAD)
        cv.ellipse(px, py + 6, 17, 12, PAD)

    # -- ears (drawn before the head so the head overlaps their base) ---
    # Pointed leaf shapes, not ovals: wide near the base (hidden under
    # the head), tapering to a tip. The pink inner ear is a smaller
    # leaf toward the tip, so it stays clearly visible.
    for (ex, ey, ang, sgn) in [(344, 168, math.radians(-27), -1),
                               (676, 154, math.radians(27), 1)]:
        ex, ey = rot_point(ex, ey, hx, hy, tilt)
        cv.shaded_leaf(ex, ey, 215, 58, ang + tilt, FUR,
                       spec_strength=0.22, spec_power=18)
        # pink inner ear, smaller leaf up toward the tip
        ix, iy = rot_point(ex + sgn * 12, ey - 48, hx, hy, tilt)
        cv.shaded_leaf(ix, iy, 118, 26, ang + tilt, INNER_EAR,
                       spec_strength=0.35, spec_power=16)

    # -- head: huge, tilted a little (the charm tilt) --------------------
    cv.shaded_ellipse(hx, hy, 295, 275, FUR, angle=tilt,
                      spec_strength=0.20, spec_power=16)
    # soft light muzzle patch + cheek fluff tufts at the silhouette edge
    mx, my = rot_point(512, 488, hx, hy, tilt)
    cv.soft_blob(mx, my, 100, 70, (255, 250, 240), 30)
    for (fx, fy) in [(212, 432), (812, 420)]:
        fx, fy = rot_point(fx, fy, hx, hy, tilt)
        cv.soft_blob(fx, fy, 20, 34, (255, 248, 235), 22,
                     angle=math.radians(18))
    # fine fur fringe along the head silhouette (top arc) + a warm
    # light lift on the chin (the head shading greys it slightly)
    cv.fur_fringe(hx, hy, 295, 275, (255, 246, 232), (233, 209, 176),
                  angle=tilt, arc=(3.3, 6.1), n=110, seed=7)
    chx, chy = rot_point(512, 592, hx, hy, tilt)
    cv.soft_blob(chx, chy, 120, 52, (255, 248, 238), 42)

    # -- small pink bow on the head, near the right ear ------------------
    bx, by = rot_point(642, 198, hx, hy, tilt)
    for (lx, ly, ang) in [(bx - 36, by - 3, math.radians(-32)),
                          (bx + 36, by - 3, math.radians(32))]:
        cv.shaded_ellipse(lx, ly, 44, 26, BOW, angle=ang + tilt,
                          spec_strength=0.5, spec_power=20)
    cv.shaded_ellipse(bx, by, 15, 15, BOW_CENTER,
                      spec_strength=0.5, spec_power=20)
    cv.circle(bx - 4, by - 4, 4, (255, 255, 255))

    # face feature centres, rotated with the head
    le = rot_point(432, 348, hx, hy, tilt)   # left eye
    re_ = rot_point(592, 340, hx, hy, tilt)  # right eye
    nose = rot_point(512, 472, hx, hy, tilt)
    mouth_c = rot_point(512, 492, hx, hy, tilt)

    # -- blush ------------------------------------------------------------
    for (bx2, by2) in [rot_point(392, 468, hx, hy, tilt),
                       rot_point(632, 460, hx, hy, tilt)]:
        cv.soft_blob(bx2, by2, 44, 24, BLUSH, 62, angle=tilt)

    # -- eyes: VERY big, amber, glossy ------------------------------------
    for (ex, ey) in (le, re_):
        # white of the eye (barely visible at the corners, like winners)
        cv.ellipse(ex, ey, 56, 66, (255, 255, 255), angle=tilt)
        # dark rim + golden-amber iris with a dome shine
        cv.ellipse(ex, ey, 54, 62, AMBER_RIM, angle=tilt)
        cv.shaded_ellipse(ex, ey, 51, 59, AMBER, angle=tilt,
                          spec_strength=0.35, spec_power=16)
        # pupil
        cv.ellipse(ex, ey, 27, 36, EYE, angle=tilt)
        # big white highlight + star sparkle + small lower dot
        cv.circle(ex - 20, ey - 24, 17, (255, 255, 255))
        cv.plus_star(ex - 30, ey - 32, 16, (255, 255, 255), 230)
        cv.circle(ex + 16, ey + 20, 6, (255, 255, 255), 200)
        # faint upper-lid shadow
        cv.soft_blob(ex, ey - 52, 52, 16, (120, 90, 60), 16, angle=tilt)

    # -- faint eyebrows: thin soft strokes, not dots ----------------------
    for (ex, ey) in (le, re_):
        bx2, by2 = rot_point(ex, ey - 88, hx, hy, tilt)
        cv.ellipse(bx2, by2, 24, 4, (190, 150, 105), 100, angle=tilt)

    # -- whiskers: very faint, light, starting clear of the nose ---------
    # Densely sampled so they read as thin lines, not dots.
    for sgn in (-1, 1):
        wx0, wy0 = rot_point(512 + sgn * 42, 482, hx, hy, tilt)
        for (dx, dy) in [(sgn * -118, -34), (sgn * -122, -2),
                         (sgn * -118, 30)]:
            pts = []
            for i in range(17):
                t = 0.15 + 0.85 * i / 16
                pts.append((wx0 + dx * t,
                            wy0 + dy * t + 6 * math.sin(t * math.pi)))
            cv.circle_chain(pts, [1.8] * len(pts), (238, 224, 203), 150)

    # -- tiny pink nose (little heart) + small smile -----------------------
    cv.heart(nose[0], nose[1], 46, NOSE, tilt=tilt)
    cv.circle(nose[0] - 5, nose[1] - 7, 4, (255, 255, 255))
    for (mx2, my2) in [(mouth_c[0] - 15, mouth_c[1]),
                       (mouth_c[0] + 15, mouth_c[1])]:
        cv.arc_chain(mx2, my2, 15, math.radians(15),
                     math.radians(165), MOUTH, 4, 230)

    return cv


# ------------------------------------------------------------------- png

def write_png(path, cv):
    raw = bytearray()
    row_len = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: None
        raw += cv.px[y * row_len:(y + 1) * row_len]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        c += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = draw()
    size = write_png(os.path.join(out_dir, "entry.png"), cv)
    print("wrote %s (%d bytes, %dx%d)"
          % (os.path.join(out_dir, "entry.png"), size, W, H))


if __name__ == "__main__":
    main()
