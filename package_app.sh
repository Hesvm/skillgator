#!/bin/bash
set -e

PROJECT_DIR="/Users/hesam/Projects/skillgator"
APP_NAME="Skillgator.app"
APPLICATIONS_DIR="/Applications"
DESKTOP_DIR="/Users/hesam/Desktop"

echo "1. Compiling Swift Mach-O native binary..."
swiftc -O -framework Cocoa -framework WebKit "$PROJECT_DIR/app_main.swift" -o "$PROJECT_DIR/Skillgator_bin"

echo "2. Building app bundle structure..."
BUILD_APP="$PROJECT_DIR/$APP_NAME"
rm -rf "$BUILD_APP"
mkdir -p "$BUILD_APP/Contents/MacOS"
mkdir -p "$BUILD_APP/Contents/Resources"

cp "$PROJECT_DIR/Skillgator_bin" "$BUILD_APP/Contents/MacOS/Skillgator"
chmod +x "$BUILD_APP/Contents/MacOS/Skillgator"

# Copy Icon
if [ -f "$PROJECT_DIR/assets/AppIcon.icns" ]; then
    cp "$PROJECT_DIR/assets/AppIcon.icns" "$BUILD_APP/Contents/Resources/AppIcon.icns"
fi

# Create Info.plist
cat << 'PLIST' > "$BUILD_APP/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>Skillgator</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.hesam.skillgator</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Skillgator</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
</dict>
</plist>

PLIST

echo "3. Signing ad-hoc for macOS Gatekeeper..."
codesign --force --deep --sign - "$BUILD_APP"

echo "4. Deploying to /Applications and ~/Desktop..."
rm -rf "$APPLICATIONS_DIR/$APP_NAME"
cp -R "$BUILD_APP" "$APPLICATIONS_DIR/"

rm -rf "$DESKTOP_DIR/$APP_NAME"
cp -R "$BUILD_APP" "$DESKTOP_DIR/"

echo "5. Refreshing macOS LaunchServices..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APPLICATIONS_DIR/$APP_NAME" || true

echo "Done! Native Skillgator.app deployed successfully."
