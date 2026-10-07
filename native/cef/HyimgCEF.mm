// Chromium (CEF) behind HyimgCEF.h. One process-wide CEF started once; one HYCefView per open project, each with its own
// request context (cache and localStorage of that project only, as the WKWebView data stores were). The message loop is
// pumped from the AppKit run loop (external_message_pump), so the app keeps its own NSApp.run and termination flow.
#import "HyimgCEF.h"

#include <atomic>
#include <set>
#include "include/cef_app.h"
#include "include/cef_application_mac.h"
#include "include/cef_browser.h"
#include "include/cef_client.h"
#include "include/cef_request_context.h"
#include "include/cef_version.h"
#include "include/wrapper/cef_library_loader.h"

// ---------- the NSApplication Chromium wants on macOS ----------
@interface HyimgApplication () <CefAppProtocol> { BOOL _handlingSendEvent; }
@end
@implementation HyimgApplication
- (BOOL)isHandlingSendEvent { return _handlingSendEvent; }
- (void)setHandlingSendEvent:(BOOL)v { _handlingSendEvent = v; }
- (void)sendEvent:(NSEvent *)event { CefScopedSendingEvent scoper; [super sendEvent:event]; }
@end

// ---------- process-wide state ----------
static CefScopedLibraryLoader *gLoader = nullptr;
static bool gRunning = false;
static std::set<int> gBrowsers;                 // live browser ids
static NSMutableArray *gCloseWaiters;           // blocks waiting for every browser to close
static NSTimer *gPump;
static std::atomic<bool> gPumpScheduled{false};

static void PumpWork() {
  gPumpScheduled = false;
  if (gRunning) CefDoMessageLoopWork();
}

class HYApp : public CefApp, public CefBrowserProcessHandler {
 public:
  CefRefPtr<CefBrowserProcessHandler> GetBrowserProcessHandler() override { return this; }
  // Chromium asks for a slice of the main thread; a short timer also runs, so nothing waits long
  void OnScheduleMessagePumpWork(int64_t delay_ms) override {
    if (delay_ms <= 0) {
      if (gPumpScheduled.exchange(true)) return;
      dispatch_async(dispatch_get_main_queue(), ^{ PumpWork(); });
    } else {
      dispatch_after(dispatch_time(DISPATCH_TIME_NOW, delay_ms * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{ PumpWork(); });
    }
  }
  void OnBeforeCommandLineProcessing(const CefString &process_type, CefRefPtr<CefCommandLine> command_line) override {
    if (!process_type.empty()) return;
    command_line->AppendSwitch("use-mock-keychain");   // no macOS keychain prompt for Chromium's own storage
    command_line->AppendSwitchWithValue("autoplay-policy", "no-user-gesture-required");
    // the HTTP cache of each board's profile at most 256 MB (owner 2026-10-07, docs/storage-plan.md): it held 800 MB of copies of
    // thumbnails the board's server already keeps on disk; Chromium drops the oldest entries itself
    command_line->AppendSwitchWithValue("disk-cache-size", "268435456");
  }
 private:
  IMPLEMENT_REFCOUNTING(HYApp);
};
static CefRefPtr<HYApp> gApp;

// ---------- one browser ----------
@interface HYCefView ()
- (void)browserCreated:(CefRefPtr<CefBrowser>)browser;
- (void)browserClosed;
- (void)pageFullscreen:(BOOL)on;
@end

class HYClient : public CefClient, public CefLifeSpanHandler, public CefLoadHandler, public CefDisplayHandler,
                 public CefRequestHandler, public CefContextMenuHandler, public CefKeyboardHandler {
 public:
  explicit HYClient(HYCefView *view) : view_(view) {}
  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override { return this; }
  CefRefPtr<CefLoadHandler> GetLoadHandler() override { return this; }
  CefRefPtr<CefDisplayHandler> GetDisplayHandler() override { return this; }
  CefRefPtr<CefRequestHandler> GetRequestHandler() override { return this; }
  CefRefPtr<CefContextMenuHandler> GetContextMenuHandler() override { return this; }
  CefRefPtr<CefKeyboardHandler> GetKeyboardHandler() override { return this; }

  void OnAfterCreated(CefRefPtr<CefBrowser> browser) override { gBrowsers.insert(browser->GetIdentifier()); [view_ browserCreated:browser]; }
  // a board's browser lies inside the app's one window. Left to itself, its close sends that window performClose:, and closing the
  // main window quits Hyimg: «Remove board…» and a tab's × closed the board and the whole app with it (owner 2026-10-06: «приложение
  // вылетело опять»). Its own view leaves the window instead, which ends the browser, and OnBeforeClose follows
  bool DoClose(CefRefPtr<CefBrowser> browser) override {
    NSView *v = (__bridge NSView *)browser->GetHost()->GetWindowHandle();
    dispatch_async(dispatch_get_main_queue(), ^{ [v removeFromSuperview]; });
    return true;
  }
  void OnBeforeClose(CefRefPtr<CefBrowser> browser) override {
    gBrowsers.erase(browser->GetIdentifier());
    [view_ browserClosed];
    if (gBrowsers.empty() && gCloseWaiters.count) {
      NSArray *w = [gCloseWaiters copy]; [gCloseWaiters removeAllObjects];
      for (void (^b)(void) in w) b();
    }
  }
  // a page element asks for full screen (a video's ⤢, owner 2026-10-06): the window goes full screen, so the element fills the whole display
  void OnFullscreenModeChange(CefRefPtr<CefBrowser>, bool fullscreen) override { [view_ pageFullscreen:fullscreen ? YES : NO]; }
  // links that open a new window (target=_blank, a picture's source on Instagram) go to the system browser
  bool OnBeforePopup(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, int, const CefString &target_url, const CefString &,
                     WindowOpenDisposition, bool, const CefPopupFeatures &, CefWindowInfo &, CefRefPtr<CefClient> &,
                     CefBrowserSettings &, CefRefPtr<CefDictionaryValue> &, bool *) override {
    NSURL *u = [NSURL URLWithString:[NSString stringWithUTF8String:target_url.ToString().c_str()]];
    if (u && ([u.scheme isEqualToString:@"http"] || [u.scheme isEqualToString:@"https"] || [u.scheme isEqualToString:@"mailto"])) [[NSWorkspace sharedWorkspace] openURL:u];
    return true;
  }
  bool OnBeforeBrowse(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, CefRefPtr<CefRequest> request, bool, bool) override {
    if (!frame->IsMain() || !view_.allowNavigation) return false;
    NSString *url = [NSString stringWithUTF8String:request->GetURL().ToString().c_str()];
    return !view_.allowNavigation(url);   // true cancels
  }
  void OnLoadStart(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, TransitionType) override {
    if (frame->IsMain() && view_.onLoadStart) view_.onLoadStart([NSString stringWithUTF8String:frame->GetURL().ToString().c_str()]);
  }
  void OnLoadEnd(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, int) override {
    if (frame->IsMain() && view_.onLoad) view_.onLoad(YES, [NSString stringWithUTF8String:frame->GetURL().ToString().c_str()], nil);
  }
  void OnLoadError(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame> frame, ErrorCode code, const CefString &text, const CefString &url) override {
    if (!frame->IsMain() || code == ERR_ABORTED || !view_.onLoad) return;
    view_.onLoad(NO, [NSString stringWithUTF8String:url.ToString().c_str()], [NSString stringWithUTF8String:text.ToString().c_str()]);
  }
  bool OnConsoleMessage(CefRefPtr<CefBrowser>, cef_log_severity_t, const CefString &message, const CefString &, int) override {
    std::string m = message.ToString();
    if (m.rfind("HYIMG_", 0) != 0) return false;
    if (view_.onMessage) view_.onMessage([NSString stringWithUTF8String:m.c_str()]);
    return true;
  }
  void OnRenderProcessTerminated(CefRefPtr<CefBrowser>, TerminationStatus, int, const CefString &) override {
    if (view_.onCrash) view_.onCrash();
  }
  // the canvas has its own right-click menu; Chromium's (Back, Reload, Inspect) would only get in the way
  void OnBeforeContextMenu(CefRefPtr<CefBrowser>, CefRefPtr<CefFrame>, CefRefPtr<CefContextMenuParams> params, CefRefPtr<CefMenuModel> model) override {
    if (!(params->GetTypeFlags() & CM_TYPEFLAG_EDITABLE)) model->Clear();
  }
  // keys the page did not take (⌘W, ⌘⇧H, ⌘R...) go to the app's menu, as they would from a WKWebView
  bool OnKeyEvent(CefRefPtr<CefBrowser>, const CefKeyEvent &event, CefEventHandle os_event) override {
    if (os_event && event.type == KEYEVENT_RAWKEYDOWN && (event.modifiers & (EVENTFLAG_COMMAND_DOWN | EVENTFLAG_CONTROL_DOWN)))
      return [[NSApp mainMenu] performKeyEquivalent:(__bridge NSEvent *)os_event];
    return false;
  }
 private:
  __weak HYCefView *view_;
  IMPLEMENT_REFCOUNTING(HYClient);
};

static unsigned int gGround = 0x17171a;   // the board's paper (ui/paper.js BOARD), set from the app's theme
@implementation HYCefView {
  CefRefPtr<CefBrowser> _browser;
  CefRefPtr<HYClient> _client;
  NSString *_cachePath;
  NSString *_pending;        // a URL asked for before the browser exists
  NSString *_pendingHTML;
  BOOL _creating;
  BOOL _enteredFS;           // the window went full screen because the page asked: it goes back when the page leaves
}
+ (void)setGround:(unsigned int)rgb { gGround = rgb; [NSNotificationCenter.defaultCenter postNotificationName:@"HYCefGround" object:nil]; }
// the view under Chromium's own is the paper too: before Chromium has a frame (a reload, a new page) it showed black (owner 2026-10-04)
- (void)paintGround {
  self.layer.backgroundColor = CGColorCreateSRGB(((gGround >> 16) & 0xff) / 255.0, ((gGround >> 8) & 0xff) / 255.0, (gGround & 0xff) / 255.0, 1);
}

- (instancetype)initWithCachePath:(NSString *)path {
  if ((self = [super initWithFrame:NSMakeRect(0, 0, 800, 600)])) {
    _cachePath = [path copy]; self.wantsLayer = YES; [self paintGround];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(paintGround) name:@"HYCefGround" object:nil];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(closeBrowser) name:@"HYCefCloseAll" object:nil];
  }
  return self;
}
- (BOOL)isFlipped { return YES; }

- (void)viewDidMoveToWindow {
  [super viewDidMoveToWindow];
  if (self.window && !_browser && !_creating && (_pending || _pendingHTML)) [self create];
}
- (void)create {
  if (!gRunning) return;
  _creating = YES;
  CefWindowInfo info;
  NSRect b = self.bounds;
  info.SetAsChild((__bridge void *)self, CefRect(0, 0, (int)b.size.width, (int)b.size.height));
  info.runtime_style = CEF_RUNTIME_STYLE_ALLOY;
  CefBrowserSettings settings;
  settings.background_color = CefColorSetARGB(255, (gGround >> 16) & 0xff, (gGround >> 8) & 0xff, gGround & 0xff);   // the paper of the app's theme while loading
  CefRequestContextSettings rs;
  CefString(&rs.cache_path) = _cachePath.UTF8String;
  rs.persist_session_cookies = true;
  CefRefPtr<CefRequestContext> context = CefRequestContext::CreateContext(rs, nullptr);
  _client = new HYClient(self);
  std::string url = _pending ? _pending.UTF8String : "about:blank";
  CefBrowserHost::CreateBrowser(info, _client, url, settings, nullptr, context);
}
- (void)browserCreated:(CefRefPtr<CefBrowser>)browser {
  _browser = browser; _creating = NO;
  NSView *v = (__bridge NSView *)browser->GetHost()->GetWindowHandle();
  v.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
  v.frame = self.bounds;
  if (_pendingHTML) { NSString *h = _pendingHTML; _pendingHTML = nil; [self loadHTML:h]; }
  _pending = nil;
  if (!self.isHiddenOrHasHiddenAncestor && self.superview.subviews.lastObject == self) [self focusPage];   // a page loading under Home does not take the keys
}
- (void)browserClosed { _browser = nullptr; _client = nullptr; }
- (void)pageFullscreen:(BOOL)on {
  NSWindow *w = self.window; if (!w) return;
  BOOL isFS = (w.styleMask & NSWindowStyleMaskFullScreen) != 0;
  if (on && !isFS) { _enteredFS = YES; [w toggleFullScreen:nil]; }
  else if (!on && _enteredFS) { _enteredFS = NO; if (isFS) [w toggleFullScreen:nil]; }
}
- (void)resizeSubviewsWithOldSize:(NSSize)old { [super resizeSubviewsWithOldSize:old]; for (NSView *v in self.subviews) v.frame = self.bounds; }

- (void)loadURL:(NSString *)url {
  if (_browser) { _browser->GetMainFrame()->LoadURL(url.UTF8String); return; }
  _pending = [url copy]; _pendingHTML = nil;
  if (self.window && !_creating) [self create];
}
- (void)loadHTML:(NSString *)html {
  NSString *data = [@"data:text/html;charset=utf-8," stringByAppendingString:[html stringByAddingPercentEncodingWithAllowedCharacters:NSCharacterSet.URLQueryAllowedCharacterSet]];
  if (_browser) { _browser->GetMainFrame()->LoadURL(data.UTF8String); return; }
  if (!_pending) _pending = data;
  if (self.window && !_creating) [self create];
}
- (void)reload { if (_browser) _browser->ReloadIgnoreCache(); }
- (void)runJavaScript:(NSString *)js { if (_browser) _browser->GetMainFrame()->ExecuteJavaScript(js.UTF8String, "hyimg://app", 0); }
- (void)focusPage { if (_browser) { _browser->GetHost()->SetFocus(true); NSView *v = (__bridge NSView *)_browser->GetHost()->GetWindowHandle(); [self.window makeFirstResponder:v]; } }
- (void)closeBrowser { if (_browser) _browser->GetHost()->CloseBrowser(true); }
- (NSString *)currentURL { return _browser ? [NSString stringWithUTF8String:_browser->GetMainFrame()->GetURL().ToString().c_str()] : nil; }
@end

// ---------- start and stop ----------
@implementation HYCef
+ (BOOL)available {
  NSString *fw = [NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:@"Chromium Embedded Framework.framework"];
  return [NSFileManager.defaultManager fileExistsAtPath:fw];
}
+ (BOOL)running { return gRunning; }
+ (BOOL)startWithCachePath:(NSString *)root {
  if (gRunning) return YES;
  if (![self available]) return NO;
  if (!gLoader) { gLoader = new CefScopedLibraryLoader(); if (!gLoader->LoadInMain()) return NO; }
  NSArray<NSString *> *argsList = NSProcessInfo.processInfo.arguments;
  static std::vector<std::string> store; static std::vector<char *> argv;
  store.clear(); argv.clear();
  for (NSString *a in argsList) store.push_back(a.UTF8String);
  for (auto &s : store) argv.push_back(s.data());
  CefMainArgs args((int)argv.size(), argv.data());
  CefSettings settings;
  settings.no_sandbox = true;
  settings.external_message_pump = true;
  settings.persist_session_cookies = true;
  settings.log_severity = LOGSEVERITY_WARNING;
  CefString(&settings.root_cache_path) = root.UTF8String;
  CefString(&settings.cache_path) = [root stringByAppendingPathComponent:@"Default"].UTF8String;
  CefString(&settings.log_file) = [root stringByAppendingPathComponent:@"chromium.log"].UTF8String;
  std::string product = "Chrome/" + std::to_string(CHROME_VERSION_MAJOR) + "." + std::to_string(CHROME_VERSION_MINOR) + "." +
                        std::to_string(CHROME_VERSION_BUILD) + "." + std::to_string(CHROME_VERSION_PATCH) + " HyimgCEF/1";
  CefString(&settings.user_agent_product) = product;   // the canvas shows «Движок» by this
  CefString(&settings.locale) = "ru";
  settings.background_color = CefColorSetARGB(255, 0x11, 0x11, 0x13);
  gApp = new HYApp();
  if (!CefInitialize(args, settings, gApp.get(), nullptr)) return NO;
  gRunning = true;
  gCloseWaiters = [NSMutableArray array];
  gPump = [NSTimer timerWithTimeInterval:1.0 / 30 repeats:YES block:^(NSTimer *t) { PumpWork(); }];
  [NSRunLoop.mainRunLoop addTimer:gPump forMode:NSRunLoopCommonModes];   // keeps running during scrolls and window drags
  return YES;
}
+ (void)closeAllThen:(void (^)(void))done {
  if (!gRunning || gBrowsers.empty()) { done(); return; }
  [gCloseWaiters addObject:[done copy]];
  // CloseBrowser per browser is asked by each HYCefView; here every live one is closed through the views' hosts
  [NSNotificationCenter.defaultCenter postNotificationName:@"HYCefCloseAll" object:nil];
  // a browser that never answers must not keep the app from quitting
  dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 3 * NSEC_PER_SEC), dispatch_get_main_queue(), ^{
    if (![gCloseWaiters count]) return;
    NSArray *w = [gCloseWaiters copy]; [gCloseWaiters removeAllObjects];
    for (void (^b)(void) in w) b();
  });
}
+ (void)shutdown {
  if (!gRunning) return;
  [gPump invalidate]; gPump = nil;
  for (int i = 0; i < 10; i++) CefDoMessageLoopWork();
  gRunning = false;
  CefShutdown();
}
@end
