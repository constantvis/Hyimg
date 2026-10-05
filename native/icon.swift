import AppKit
guard CommandLine.arguments.count == 3 else {
    fputs("Usage: icon canonical.svg output-directory\n", stderr)
    exit(1)
}
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let destination = CommandLine.arguments[2]
guard let image = NSImage(contentsOf: source), image.size.width > 0, image.size.height > 0 else {
    fputs("Cannot load SVG: \(source.path)\n", stderr)
    exit(1)
}
image.cacheMode = .never
try FileManager.default.createDirectory(atPath: destination, withIntermediateDirectories: true)
for size in [16, 32, 64, 128, 256, 512, 1024] {
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
          let context = NSGraphicsContext(bitmapImageRep: bitmap) else { exit(1) }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.imageInterpolation = .high
    image.draw(in: NSRect(x: 0, y: 0, width: size, height: size), from: .zero, operation: .copy, fraction: 1)
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else { exit(1) }
    try png.write(to: URL(fileURLWithPath: destination).appendingPathComponent("\(size).png"))
}
var entries = Data()
func bigEndian(_ value: UInt32) -> Data {
    var number = value.bigEndian
    return withUnsafeBytes(of: &number) { Data($0) }
}
for (type, size) in [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256), ("ic09", 512), ("ic10", 1024), ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512)] {
    let png = try Data(contentsOf: URL(fileURLWithPath: destination).appendingPathComponent("\(size).png"))
    entries.append(Data(type.utf8))
    entries.append(bigEndian(UInt32(png.count + 8)))
    entries.append(png)
}
var icon = Data("icns".utf8)
icon.append(bigEndian(UInt32(entries.count + 8)))
icon.append(entries)
try icon.write(to: URL(fileURLWithPath: destination).appendingPathComponent("Hyimg.icns"))
