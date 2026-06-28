import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_ui_test():
    # Paths to generated mock documents for TC004 (Rajesh Kumar Clean Consultation)
    prescription_path = os.path.abspath("data/test_suite/F007.pdf")
    bill_path = os.path.abspath("data/test_suite/F008.pdf")
    
    if not os.path.exists(prescription_path) or not os.path.exists(bill_path):
        print("Error: Mock documents not found. Please run 'python3 eval/generate_mock_docs.py' first.")
        sys.exit(1)
        
    print("Starting Playwright Web UI Test...")
    
    with sync_playwright() as p:
        # Launch Chromium (headed mode so the user can watch the browser automate)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        try:
            # 1. Open Streamlit App
            url = "http://localhost:8501"
            print(f"Navigating to Streamlit: {url}")
            page.goto(url)
            page.wait_for_load_state("networkidle")
            
            # 2. Navigate to Submit Claim page via sidebar
            print("Clicking 'Submit Claim' page in sidebar...")
            # Click by text link matching Streamlit's sidebar layout
            page.click("text=Submit Claim")
            page.wait_for_timeout(2000)
            
            # 3. Enter Member ID (Search Bar)
            print("Entering Member ID 'EMP001'...")
            page.fill("input[aria-label*='Search Member']", "EMP001")
            page.press("input[aria-label*='Search Member']", "Enter")
            page.wait_for_timeout(1000)
            
            # 4. Enter Claim Details
            # Category select is default Consultation, which is correct
            print("Entering claimed amount (1500) and hospital name...")
            page.fill("input[aria-label*='Hospital']", "City Clinic")
            page.fill("input[aria-label*='Claimed Amount']", "1500")
            
            print("Entering Treatment Date '2024/11/01'...")
            date_input = page.locator("div[data-testid='stDateInput'] input")
            date_input.focus()
            page.keyboard.press("Control+A")
            page.keyboard.press("Meta+A")
            page.keyboard.type("2024/11/01")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            
            # Click title to blur date input and commit state to Streamlit
            page.click("h1:has-text('Submit Health Claim')")
            page.wait_for_timeout(1000)
            
            # 5. Upload files
            print("Uploading prescription and bill PDF files...")
            file_input = page.locator("input[type='file']")
            file_input.set_input_files([prescription_path, bill_path])
            page.wait_for_timeout(4000)
            
            # 6. Submit Claim
            print("Clicking Submit button...")
            page.click("button:has-text('Submit and Process Claim')", force=True)
            
            # 7. Wait for decision card to render
            print("Waiting for claims pipeline execution...")
            page.wait_for_selector(".card-approved", timeout=60000)
            
            # 8. Check result content
            approved_card = page.locator(".card-approved")
            card_text = approved_card.inner_text()
            print("="*50)
            print("PIPELINE RESULT DISCOVERED:")
            print(card_text)
            print("="*50)
            
            assert "Claim Approved" in card_text
            assert "Approved Amount: ₹1,350.00" in card_text
            print("✅ Playwright UI claim submission test passed successfully!")
            
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            os.makedirs("data", exist_ok=True)
            page.screenshot(path="data/playwright_failure.png")
            print("Screenshot saved to data/playwright_failure.png")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run_ui_test()
