import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from openai import AzureOpenAI
import os
from urllib.parse import urljoin, urlparse
from datetime import datetime


def setup_azure_openai_client():
    """
    Setup Azure OpenAI client using the RepFirmKey environment variable
    """
    api_key = os.getenv('RepFirmKey')
    if not api_key:
        raise ValueError("RepFirmKey environment variable not found")
    
    client = AzureOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint="https://repfirm.openai.azure.com/"
    )
    return client


def extract_website_data(url):
    """
    Extract all text content from a rep firm's line sheet website
    
    Args:
        url (str): The URL of the rep firm's line sheet page
        
    Returns:
        str: All extracted text content from the website
    """
    print(f"Extracting data from: {url}")
    
    # Setup Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        # Initialize the webdriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Navigate to the URL
        driver.get(url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Try to find common line sheet navigation elements
        line_sheet_selectors = [
            "a[href*='line']",
            "a[href*='product']", 
            "a[href*='catalog']",
            "a[href*='equipment']",
            "a[href*='brand']",
            "a[href*='manufacturer']"
        ]
        
        # Look for line sheet links and click if found
        for selector in line_sheet_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.lower()
                    if any(keyword in text for keyword in ['line', 'product', 'catalog', 'equipment', 'brand']):
                        print(f"Found line sheet link: {element.text}")
                        element.click()
                        time.sleep(2)
                        break
                else:
                    continue
                break
            except Exception as e:
                continue
        
        # Get the page source after potential navigation
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract all text content
        text_content = soup.get_text()
        
        # Clean up the text
        lines = (line.strip() for line in text_content.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text_content = ' '.join(chunk for chunk in chunks if chunk)
        
        print(f"Extracted {len(text_content)} characters of text content")
        
        return text_content
        
    except Exception as e:
        print(f"Error extracting data: {str(e)}")
        raise
    finally:
        try:
            driver.quit()
        except:
            pass


def process_with_chatgpt(text_content, rep_firm_name=None):
    """
    Process the extracted text through Azure OpenAI to categorize the information
    
    Args:
        text_content (str): The extracted text from the website
        rep_firm_name (str): Optional name of the rep firm
        
    Returns:
        str: Structured table data from ChatGPT
    """
    print("Processing data through Azure OpenAI...")
    
    client = setup_azure_openai_client()
    
    # Construct the prompt based on the context requirements
    prompt = f"""can you break this out into a table of Rep Firm Name - Brand Carried (one at a time) - Product Covered - Space for space, keep it to broad categories for steps in water/wastewater treatment. So for example, aerators, flocculators, or coagulators but not Spike Aerators, Paddle Wheel Flocculators, or Inorganic Coagulants (for example). it's from a website and is unstructured data so please format only what's relevant.

Please format the output as a clean table with these columns:
- Rep Firm Name
- Brand Carried  
- Product Covered
- Space (water/wastewater treatment category)

{f"Rep Firm Name: {rep_firm_name}" if rep_firm_name else ""}

Website content:
{text_content}"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or your specific model name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts and categorizes rep firm line sheet information into structured tables."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        print("Successfully processed data through Azure OpenAI")
        return result
        
    except Exception as e:
        print(f"Error processing with ChatGPT: {str(e)}")
        raise


def parse_chatgpt_response_to_dataframe(chatgpt_response):
    """
    Parse the ChatGPT response into a pandas DataFrame
    
    Args:
        chatgpt_response (str): The response from ChatGPT
        
    Returns:
        pd.DataFrame: Structured data
    """
    print("Parsing ChatGPT response to DataFrame...")
    
    # Try to extract table data from the response
    lines = chatgpt_response.strip().split('\n')
    
    # Find the table data (look for lines with multiple columns separated by | or tabs)
    table_data = []
    headers = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this looks like a header row
        if any(keyword in line.lower() for keyword in ['rep firm', 'brand', 'product', 'space']):
            # Extract headers
            if '|' in line:
                headers = [h.strip() for h in line.split('|')]
            else:
                # Try to split by multiple spaces
                headers = re.split(r'\s{2,}', line)
            continue
            
        # Check if this looks like data row
        if '|' in line:
            row_data = [cell.strip() for cell in line.split('|')]
            if len(row_data) >= 4:  # Should have at least 4 columns
                table_data.append(row_data)
        elif re.search(r'\s{2,}', line):
            # Split by multiple spaces
            row_data = re.split(r'\s{2,}', line)
            if len(row_data) >= 4:
                table_data.append(row_data)
    
    # If we couldn't parse the table properly, try a different approach
    if not table_data:
        # Look for patterns in the text that might indicate product information
        pattern = r'([A-Z][a-zA-Z\s&]+)\s*[-–]\s*([A-Z][a-zA-Z\s&]+)\s*[-–]\s*([A-Z][a-zA-Z\s&]+)'
        matches = re.findall(pattern, chatgpt_response)
        
        if matches:
            table_data = []
            for match in matches:
                if len(match) >= 3:
                    table_data.append(list(match))
    
    # Create DataFrame
    if table_data:
        if headers and len(headers) >= 4:
            df = pd.DataFrame(table_data, columns=headers[:4])
        else:
            df = pd.DataFrame(table_data, columns=['Rep Firm Name', 'Brand Carried', 'Product Covered', 'Space'])
    else:
        # Create empty DataFrame with proper columns
        df = pd.DataFrame(columns=['Rep Firm Name', 'Brand Carried', 'Product Covered', 'Space'])
    
    # Clean up the data
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    df = df.dropna(how='all')
    
    print(f"Created DataFrame with {len(df)} rows")
    return df


def save_to_excel(df, output_filename=None):
    """
    Save the DataFrame to an Excel file
    
    Args:
        df (pd.DataFrame): The data to save
        output_filename (str): Optional filename, will generate one if not provided
        
    Returns:
        str: The filename of the saved Excel file
    """
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"rep_firm_line_sheet_{timestamp}.xlsx"
    
    # Ensure the filename has .xlsx extension
    if not output_filename.endswith('.xlsx'):
        output_filename += '.xlsx'
    
    try:
        df.to_excel(output_filename, index=False, engine='openpyxl')
        print(f"Data saved to: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Error saving to Excel: {str(e)}")
        raise


def scrape_rep_firm_line_sheet(url, rep_firm_name=None, output_filename=None):
    """
    Main function to scrape a rep firm's line sheet and process it
    
    Args:
        url (str): The URL of the rep firm's website
        rep_firm_name (str): Optional name of the rep firm
        output_filename (str): Optional output filename
        
    Returns:
        str: The filename of the saved Excel file
    """
    print(f"Starting rep firm line sheet scraping for: {url}")
    
    try:
        # Step 1: Extract website data
        text_content = extract_website_data(url)
        
        # Step 2: Process with ChatGPT
        chatgpt_response = process_with_chatgpt(text_content, rep_firm_name)
        
        # Step 3: Parse response to DataFrame
        df = parse_chatgpt_response_to_dataframe(chatgpt_response)
        
        # Step 4: Save to Excel
        output_file = save_to_excel(df, output_filename)
        
        print("Scraping completed successfully!")
        return output_file
        
    except Exception as e:
        print(f"Error in scraping process: {str(e)}")
        raise


# Example usage
if __name__ == "__main__":
    # Example usage - replace with actual URL
    example_url = "https://example-rep-firm.com"
    
    try:
        output_file = scrape_rep_firm_line_sheet(
            url=example_url,
            rep_firm_name="Example Rep Firm",
            output_filename="example_output.xlsx"
        )
        print(f"Results saved to: {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}")

