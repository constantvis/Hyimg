// Hyimg built without the Chromium SDK: the same interface, Chromium simply is not there and projects stay on WebKit.
#import "HyimgCEF.h"

@implementation HyimgApplication
@end

@implementation HYCef
+ (BOOL)available { return NO; }
+ (BOOL)startWithCachePath:(NSString *)root { return NO; }
+ (BOOL)running { return NO; }
+ (void)closeAllThen:(void (^)(void))done { done(); }
+ (void)shutdown {}
@end

@implementation HYCefView
- (instancetype)initWithCachePath:(NSString *)path { return [super initWithFrame:NSZeroRect]; }
+ (void)setGround:(unsigned int)rgb {}
- (void)loadURL:(NSString *)url {}
- (void)loadHTML:(NSString *)html {}
- (void)reload {}
- (void)runJavaScript:(NSString *)js {}
- (void)focusPage {}
- (void)closeBrowser {}
- (NSString *)currentURL { return nil; }
@end
