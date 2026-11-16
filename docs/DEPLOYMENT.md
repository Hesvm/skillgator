# Running Skillgator as a Background Daemon

## macOS (launchd)
You can create a user agent plist at `~/Library/LaunchAgents/com.skillgator.monitor.plist` to start Skillgator automatically on login:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.skillgator.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```
