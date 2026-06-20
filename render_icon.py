#!/usr/bin/env python3
"""
Convert SVG to multiple crisp raster PNGs using Cairo+Rsvg (headless).
Usage: python3 render_icon.py <svg_path> <hicolor_dir>
"""
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Usage: render_icon.py <svg_path> <hicolor_dir>")
        sys.exit(1)

    svg_path = os.path.abspath(sys.argv[1])
    hicolor_dir = os.path.expanduser(sys.argv[2])

    if not os.path.isfile(svg_path):
        print(f"SVG not found: {svg_path}")
        sys.exit(1)

    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo

    icon_name = "com.mc.gdk.launcher"
    handle = Rsvg.Handle.new_from_file(svg_path)

    # Get intrinsic viewBox dimensions
    ok, w, h = handle.get_intrinsic_size_in_pixels()
    if not ok or w == 0 or h == 0:
        w, h = 680.0, 480.0

    for size in [32, 64, 128, 256, 512]:
        out_dir = os.path.join(hicolor_dir, f"{size}x{size}", "apps")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{icon_name}.png")

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)

        # Scale uniformly to fit within size x size, centering it
        scale = min(size / w, size / h)
        tx = (size - w * scale) / 2.0
        ty = (size - h * scale) / 2.0

        ctx.translate(tx, ty)
        ctx.scale(scale, scale)

        vp = Rsvg.Rectangle()
        vp.x = 0
        vp.y = 0
        vp.width = w
        vp.height = h
        handle.render_document(ctx, vp)

        surface.write_to_png(out_path)
        fsize = os.path.getsize(out_path)
        print(f"  [{size}x{size}] {fsize} bytes -> {out_path}")

if __name__ == "__main__":
    main()
