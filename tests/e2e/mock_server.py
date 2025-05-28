#!/usr/bin/env python3
"""
Mock HTTP server for e2e tests.
Provides fake documentation endpoints for testing.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class MockHTTPHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for mock documentation."""

    def log_message(self, format, *args):
        """Suppress server logs during tests."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # Route to appropriate handler
        if path == "/":
            self.send_index()
        elif path == "/docs/python":
            self.send_python_docs()
        elif path == "/docs/javascript":
            self.send_javascript_docs()
        elif path == "/api/library":
            self.send_library_info(query)
        elif path == "/html":
            self.send_html_page()
        elif path == "/markdown":
            self.send_markdown_page()
        elif path.startswith("/depth"):
            self.send_depth_test_page(path)
        elif path == "/timeout":
            self.send_timeout_response()
        elif path == "/large":
            self.send_large_document()
        else:
            self.send_404()

    def send_index(self):
        """Send index page with links."""
        content = """
        <!DOCTYPE html>
        <html>
        <head><title>Mock Documentation Server</title></head>
        <body>
            <h1>Documentation Index</h1>
            <ul>
                <li><a href="/docs/python">Python Documentation</a></li>
                <li><a href="/docs/javascript">JavaScript Documentation</a></li>
                <li><a href="/html">HTML Example</a></li>
                <li><a href="/markdown">Markdown Example</a></li>
            </ul>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_python_docs(self):
        """Send mock Python documentation."""
        content = """
        <!DOCTYPE html>
        <html>
        <head><title>Python Documentation</title></head>
        <body>
            <h1>Python String Methods</h1>
            <section id="string-methods">
                <h2>Common String Methods</h2>
                <p>Python provides many built-in methods for string manipulation.</p>
                <h3>str.upper()</h3>
                <pre><code>
text = "hello"
print(text.upper())  # HELLO
                </code></pre>
                <h3>str.lower()</h3>
                <pre><code>
text = "HELLO"
print(text.lower())  # hello
                </code></pre>
            </section>
            <section id="best-practices">
                <h2>Best Practices</h2>
                <ul>
                    <li>Use f-strings for formatting in Python 3.6+</li>
                    <li>Prefer str.join() over concatenation in loops</li>
                </ul>
            </section>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_javascript_docs(self):
        """Send mock JavaScript documentation."""
        content = """
        <!DOCTYPE html>
        <html>
        <head><title>JavaScript Array Methods</title></head>
        <body>
            <h1>JavaScript Array Methods</h1>
            <section>
                <h2>Array.prototype.map()</h2>
                <p>Creates a new array with the results of calling a function on every element.</p>
                <pre><code>
const numbers = [1, 2, 3];
const doubled = numbers.map(x => x * 2);
console.log(doubled); // [2, 4, 6]
                </code></pre>
            </section>
            <section>
                <h2>Array.prototype.filter()</h2>
                <p>Creates a new array with all elements that pass the test.</p>
                <pre><code>
const numbers = [1, 2, 3, 4, 5];
const evens = numbers.filter(x => x % 2 === 0);
console.log(evens); // [2, 4]
                </code></pre>
            </section>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_library_info(self, query):
        """Send library information for API endpoints."""
        lib_name = query.get("name", [""])[0]
        version = query.get("version", ["latest"])[0]

        libraries = {
            "requests": {
                "name": "requests",
                "version": "2.31.0" if version == "latest" else version,
                "description": "HTTP library for Python",
                "docs_url": "https://docs.python-requests.org/",
            },
            "numpy": {
                "name": "numpy",
                "version": "1.24.0" if version == "latest" else version,
                "description": "Numerical computing library",
                "docs_url": "https://numpy.org/doc/stable/",
            },
            "express": {
                "name": "express",
                "version": "4.18.0" if version == "latest" else version,
                "description": "Web framework for Node.js",
                "docs_url": "https://expressjs.com/",
            },
        }

        if lib_name in libraries:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(libraries[lib_name]).encode())
        else:
            self.send_404()

    def send_html_page(self):
        """Send a simple HTML page."""
        content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>HTML Test Page</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>Test HTML Document</h1>
            <p>This is a test paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
            <h2>Code Example</h2>
            <pre><code>
def hello_world():
    print("Hello, World!")
            </code></pre>
            <h2>Lists</h2>
            <ul>
                <li>First item</li>
                <li>Second item</li>
                <li>Third item</li>
            </ul>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_markdown_page(self):
        """Send a markdown formatted page."""
        content = """# Markdown Test Document

This is a test document in **Markdown** format.

## Features

- Easy to read
- Easy to write
- Converts to HTML

## Code Example

```python
def greet(name):
    return f"Hello, {name}!"
```

## Links

Visit [DocVault](https://github.com/docvault/docvault) for more information.
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_depth_test_page(self, path):
        """Send pages for depth testing."""
        depth = int(path.split("/")[-1]) if path.split("/")[-1].isdigit() else 0

        content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Depth Test - Level {depth}</title></head>
        <body>
            <h1>Page at Depth {depth}</h1>
            <p>This is content at depth level {depth}.</p>
        """

        if depth < 3:
            # Add links to deeper pages
            content += f"""
            <h2>Links to Deeper Pages</h2>
            <ul>
                <li><a href="/depth/{depth + 1}">Go to depth {depth + 1}</a></li>
                <li><a href="/depth/{depth + 2}">Go to depth {depth + 2}</a></li>
            </ul>
            """

        content += """
        </body>
        </html>
        """

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_timeout_response(self):
        """Simulate a slow response for timeout testing."""
        time.sleep(5)  # Sleep for 5 seconds
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"This response was delayed")

    def send_large_document(self):
        """Send a large document for testing."""
        content = "# Large Document\n\n"
        # Generate 1000 paragraphs
        for i in range(1000):
            content += f"## Section {i}\n\n"
            content += f"This is paragraph {i}. " * 50 + "\n\n"

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_404(self):
        """Send 404 Not Found response."""
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"404 Not Found")


class MockServer:
    """Mock HTTP server for testing."""

    def __init__(self, port=8888):
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """Start the mock server in a separate thread."""
        if self.running:
            return

        self.server = HTTPServer(("localhost", self.port), MockHTTPHandler)
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        self.running = True

        # Wait for server to be ready
        time.sleep(0.5)

    def _run_server(self):
        """Run the server."""
        self.server.serve_forever()

    def stop(self):
        """Stop the mock server."""
        if self.server and self.running:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.running = False

    def get_url(self, path=""):
        """Get URL for the mock server."""
        return f"http://localhost:{self.port}{path}"


if __name__ == "__main__":
    # Run standalone for testing
    server = MockServer()
    print(f"Starting mock server on http://localhost:{server.port}")
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping mock server...")
        server.stop()
