import sys
import threading
import time

from playwright.sync_api import Page, expect

from live_reload.__main__ import main


def test_main(page: Page):
    sys.argv = ["live-reload", "./tests/assets"]

    server_thread = threading.Thread(target=main, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(2.0)

    page.goto("http://127.0.0.1:8000/test.html")

    expect(page.get_by_role("heading", name="Hello"))

    with open("./tests/assets/test.html") as fp:
        test_file_content = fp.read()

    with open("./tests/assets/test.html", "w") as fp:
        fp.write(test_file_content.replace("Hello", "Hello World"))

    # Wait a bit for the file to be reloaded
    time.sleep(0.5)

    expect(page.get_by_role("heading", name="Hello World"))

    with open("./tests/assets/test.html", "w") as fp:
        fp.write(test_file_content)
