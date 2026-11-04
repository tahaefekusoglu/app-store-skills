// apptest-store-assets: rewrites PNG images as sRGB PNG WITHOUT alpha (the App Store does not
// accept images with an alpha channel). macOS only (CoreGraphics). Usage:
//   swiftc -O noalpha.swift -o <temp>/noalpha && <temp>/noalpha <input_folder> <output_folder>
// The input is not changed; the output folder gets the same subfolder structure.
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let src = URL(fileURLWithPath: CommandLine.arguments[1])
let dst = URL(fileURLWithPath: CommandLine.arguments[2])
let fm = FileManager.default
let e = fm.enumerator(at: src, includingPropertiesForKeys: nil)!
var n = 0
for case let url as URL in e where url.pathExtension == "png" {
  let rel = url.path.replacingOccurrences(of: src.path + "/", with: "")
  let out = dst.appendingPathComponent(rel)
  try? fm.createDirectory(at: out.deletingLastPathComponent(), withIntermediateDirectories: true)
  guard let s = CGImageSourceCreateWithURL(url as CFURL, nil),
        let img = CGImageSourceCreateImageAtIndex(s, 0, nil) else { continue }
  let cs = CGColorSpace(name: CGColorSpace.sRGB)!
  let ctx = CGContext(data: nil, width: img.width, height: img.height, bitsPerComponent: 8,
                      bytesPerRow: 0, space: cs, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
  ctx.draw(img, in: CGRect(x: 0, y: 0, width: img.width, height: img.height))
  let d = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
  CGImageDestinationAddImage(d, ctx.makeImage()!, nil)
  CGImageDestinationFinalize(d)
  n += 1
}
print("\(n) images")
