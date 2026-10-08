import AppKit
import Foundation

let output = URL(fileURLWithPath: CommandLine.arguments[1])
var chunks = Data()
func lengthBytes(_ value: Int) -> Data {
    var size = UInt32(value).bigEndian
    return withUnsafeBytes(of: &size) { Data($0) }
}
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
                                  bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                  isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        let transform = AffineTransform(scale: Double(pixels) / 1024)
        (transform as NSAffineTransform).concat()
        let square = NSBezierPath(roundedRect: NSRect(x: 60, y: 60, width: 904, height: 904), xRadius: 202, yRadius: 202)
        NSGradient(starting: NSColor(calibratedRed: 0.13, green: 0.64, blue: 0.68, alpha: 1),
                   ending: NSColor(calibratedRed: 0.08, green: 0.28, blue: 0.62, alpha: 1))!.draw(in: square, angle: -60)
        let card = NSBezierPath(roundedRect: NSRect(x: 238, y: 240, width: 548, height: 544), xRadius: 96, yRadius: 96)
        NSColor.white.withAlphaComponent(0.13).setFill()
        card.fill()
        if let symbol = NSImage(systemSymbolName: "arrow.triangle.2.circlepath", accessibilityDescription: nil) {
            let configuration = NSImage.SymbolConfiguration(pointSize: 320, weight: .medium)
                .applying(NSImage.SymbolConfiguration(paletteColors: [.white]))
            symbol.withSymbolConfiguration(configuration)?.draw(in: NSRect(x: 308, y: 308, width: 408, height: 408))
        }
        NSGraphicsContext.restoreGraphicsState()
        let types = scale == 1
            ? [16: "icp4", 32: "icp5", 128: "ic07", 256: "ic08", 512: "ic09"]
            : [16: "ic11", 32: "ic12", 128: "ic13", 256: "ic14", 512: "ic10"]
        let png = rep.representation(using: .png, properties: [:])!
        chunks.append(types[size]!.data(using: .ascii)!)
        chunks.append(lengthBytes(png.count + 8))
        chunks.append(png)
    }
}

var icon = Data("icns".utf8)
icon.append(lengthBytes(chunks.count + 8))
icon.append(chunks)
try icon.write(to: output)
