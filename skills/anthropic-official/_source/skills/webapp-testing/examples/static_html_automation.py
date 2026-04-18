"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: anthropic-official._source.skills.webapp-testing
script_name: static_html_automation.py
script_purpose: [TODO: one sentence — what this script does and when it is invoked]
why: [TODO: why this script exists — what problem it solves vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block the parent skill.
apex_version: v00.36.0
"""
from playwright.sync_api import sync_playwright
import os

# Example: Automating interaction with static HTML files using file:// URLs

html_file_path = os.path.abspath('path/to/your/file.html')
file_url = f'file://{html_file_path}'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})

    # Navigate to local HTML file
    page.goto(file_url)

    # Take screenshot
    page.screenshot(path='/mnt/user-data/outputs/static_page.png', full_page=True)

    # Interact with elements
    page.click('text=Click Me')
    page.fill('#name', 'John Doe')
    page.fill('#email', 'john@example.com')

    # Submit form
    page.click('button[type="submit"]')
    page.wait_for_timeout(500)

    # Take final screenshot
    page.screenshot(path='/mnt/user-data/outputs/after_submit.png', full_page=True)

    browser.close()

print("Static HTML automation completed!")