// The helper processes Chromium starts next to the app (renderer, GPU, network, plugins, alerts): build.sh puts one binary
// into five "Hyimg Helper*.app" bundles inside Hyimg.app/Contents/Frameworks, as CEF expects on macOS.
#include "include/cef_app.h"
#include "include/wrapper/cef_library_loader.h"

int main(int argc, char *argv[]) {
  CefScopedLibraryLoader loader;
  if (!loader.LoadInHelper()) return 1;
  CefMainArgs args(argc, argv);
  return CefExecuteProcess(args, nullptr, nullptr);
}
