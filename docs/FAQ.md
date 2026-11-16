# Frequently Asked Questions (FAQ)

### Does Skillgator send any telemetry or code to remote servers?
No. Skillgator runs 100% locally on your machine (`localhost:4949`) and does not transmit any code, file names, or metadata externally.

### Do I need Node.js or npm to run Skillgator?
No. Skillgator is designed with zero external runtime dependencies. It only requires Python 3.9+.

### How do I change the default port?
You can start the server with a custom port argument:
```bash
python3 server.py --port 8080
```
