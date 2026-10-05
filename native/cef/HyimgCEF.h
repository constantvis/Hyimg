// Chromium inside the Hyimg window (owner 2026-10-01): WebKit paints the board on the CPU and stutters with hundreds of
// pictures, Chromium draws it on the GPU. This is the Objective-C face of the Chromium Embedded Framework (CEF) for Swift:
// HyimgCEF.mm when the app is built with CEF (build.sh finds the SDK), HyimgCEFStub.m otherwise, so Hyimg always builds and
// simply stays on WebKit. Removing the engine: delete native/cef, its lines in build.sh and the "CEF" lines in main.swift.
#import <AppKit/AppKit.h>

NS_ASSUME_NONNULL_BEGIN

/// The application class Chromium needs on macOS (it tracks event dispatch); set as NSPrincipalClass in Info.plist.
@interface HyimgApplication : NSApplication
@end

@interface HYCef : NSObject
/// Whether this build carries Chromium at all.
+ (BOOL)available;
/// Loads the framework from the app bundle and starts Chromium once; NO when it is not in the bundle or did not start.
+ (BOOL)startWithCachePath:(NSString *)root;
+ (BOOL)running;
/// Closes every browser, then calls done (on the main thread); after that shutdown may run.
+ (void)closeAllThen:(void (^)(void))done;
+ (void)shutdown;
@end

/// One project page: a Chromium browser filling this view.
@interface HYCefView : NSView
/// path: the project's own storage (localStorage, cache), a folder under the root given to startWithCachePath.
- (instancetype)initWithCachePath:(NSString *)path NS_DESIGNATED_INITIALIZER;
- (instancetype)initWithFrame:(NSRect)frameRect NS_UNAVAILABLE;
- (nullable instancetype)initWithCoder:(NSCoder *)coder NS_UNAVAILABLE;
- (void)loadURL:(NSString *)url;
- (void)loadHTML:(NSString *)html;
- (void)reload;
- (void)runJavaScript:(NSString *)js;
- (void)focusPage;
- (void)closeBrowser;
/// the colour a page shows before its first paint (0xRRGGBB): the board's paper of the app's theme, so opening never flashes another colour
+ (void)setGround:(unsigned int)rgb;
@property (nonatomic, readonly, nullable) NSString *currentURL;
/// main frame finished (ok) or failed (ok == NO, error text)
@property (nonatomic, copy, nullable) void (^onLoad)(BOOL ok, NSString *url, NSString *_Nullable error);
/// a main-frame navigation started
@property (nonatomic, copy, nullable) void (^onLoadStart)(NSString *url);
/// console lines starting with "HYIMG_" (the page's messages to the app: flush answers, actions)
@property (nonatomic, copy, nullable) void (^onMessage)(NSString *line);
/// the page's renderer process ended
@property (nonatomic, copy, nullable) void (^onCrash)(void);
/// a navigation away from the project server: return YES to let it load inside, NO to cancel (the app opens it outside)
@property (nonatomic, copy, nullable) BOOL (^allowNavigation)(NSString *url);
@end

NS_ASSUME_NONNULL_END
