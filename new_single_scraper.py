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
        azure_endpoint="https://adity-mczs6jhv-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
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
        
        # Get the page source
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
    
    # Create a preview of the content (first 2000 characters) to avoid token limits
    content_preview = text_content[:2000] + "..." if len(text_content) > 2000 else text_content
    
    # Construct the detailed prompt for better extraction
    prompt = f"""Please extract information with the following columns:
        - Rep Firm Name (must be the official, properly capitalized name of the rep firm, not an abbreviation, domain, or placeholder)
        - Brand Carried (must be the official, properly capitalized brand/manufacturer name, not a filename, abbreviation, or unclear string)
        - Product Covered (extract the exact products listed or mentioned on the page; be as specific as possible)
        - Product Space (use broad water/wastewater treatment process steps, e.g., Flow Control, Clarification, Disinfection, Aeration, Filtration, Chemical Feed, etc. Do NOT use specific model names or chemicals. If you cannot be specific, use 'Water Treatment' or 'Wastewater Treatment' as a catch-all, but only as a last resort)

        Rep Firm Name: {rep_firm_name if rep_firm_name else "Extract from content"}

        Website content (select all and copy):
        {content_preview}

        Please analyze this content carefully and extract any information about:
        1. Manufacturers or brands the rep firm represents (official, properly capitalized names only)
        2. Equipment categories or product types they offer (exact products listed; be as specific as possible)
        3. Water/wastewater treatment process steps they cover (broad categories only; be as specific as possible)

        IMPORTANT: Each individual product should be on its own row. If a brand carries multiple products, create separate rows for each product. For example:
        - If you see "Brand A carries pumps, valves, and filters", create 3 separate rows
        - If you see "Brand B offers Surface Aerators and Submersible Mixers", create 2 separate rows
        - Do not combine multiple products into a single cell

        Format the output as CSV with exactly these 4 columns: Rep Firm Name, Brand Carried, Product Covered, Product Space
        Include the header row. Do not include any other text, comments, or formatting."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or your specific model name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts and categorizes rep firm line sheet information. Always return data in CSV format with exactly 4 columns: Rep Firm Name, Brand Carried, Product Covered, Product Space. Each individual product should be on its own row, even if multiple products are mentioned together."},
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
    
    try:
        # Use pandas to read CSV directly from the string
        from io import StringIO
        df = pd.read_csv(StringIO(chatgpt_response), skip_blank_lines=True)
        
        # Ensure we have the correct column names
        expected_columns = ['Rep Firm Name', 'Brand Carried', 'Product Covered', 'Product Space']
        if list(df.columns) != expected_columns:
            # If column names don't match, rename them
            if len(df.columns) >= 4:
                df = df.iloc[:, :4]  # Take only first 4 columns
                df.columns = expected_columns
        
        # Clean up the data
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(how='all')
        
        print(f"Created DataFrame with {len(df)} rows")
        return df
        
    except Exception as e:
        print(f"Error parsing CSV: {str(e)}")
        print("Raw ChatGPT response:")
        print(chatgpt_response)
        
        # Fallback: create empty DataFrame
        df = pd.DataFrame(columns=['Rep Firm Name', 'Brand Carried', 'Product Covered', 'Product Space'])
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
    example_url = "https://shapecal.com/equipment/"
    
    try:
        output_file = scrape_rep_firm_line_sheet(
            url=example_url,
            rep_firm_name="Example Rep Firm",
            output_filename="example_output.xlsx"
        )
        print(f"Results saved to: {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}")

