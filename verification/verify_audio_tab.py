from playwright.sync_api import sync_playwright

def verify_audio_tab():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("http://localhost:8501")

            # Navigate to the Audio Loader page
            # Streamlit usually puts pages in the sidebar
            # Wait for sidebar to load
            page.wait_for_selector("[data-testid='stSidebarNav']")

            # Click on "Audio Loader" in sidebar
            # The name in sidebar is derived from filename "7_Audio_Loader.py" -> "Audio Loader"
            page.get_by_text("Audio Loader").click()

            # Wait for page load
            page.wait_for_selector("h1:has-text('Audio Data Loader')")

            # Check for Dataset directory warning or success
            # We want to see the select box
            page.wait_for_selector("text=Select Audio File")

            # Check default selection
            # It should be "long_depressed_sample_nobreak.wav" or "performance_test.wav"
            # We can check if the selectbox contains one of them
            content = page.content()
            if "long_depressed_sample_nobreak.wav" in content or "performance_test.wav" in content:
                print("Default selection found.")
            else:
                print("Default selection NOT found.")

            # Take screenshot
            page.screenshot(path="verification/audio_loader.png")
            print("Screenshot saved to verification/audio_loader.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_audio_tab()
