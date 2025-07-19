# Rep Firm Line Sheet Scraper

A comprehensive tool for extracting and categorizing rep firm line sheet information from websites using Azure OpenAI.

## Overview

This scraper is designed to extract information from rep firm websites (independent sales companies for engineered products) and process the data through Azure OpenAI to categorize products into structured tables. The tool specifically focuses on water/wastewater treatment equipment categories.

## Features

- **Web Scraping**: Extracts all text content from rep firm line sheet pages
- **Smart Navigation**: Automatically looks for line sheet/product/catalog links
- **AI Processing**: Uses Azure OpenAI to categorize unstructured data
- **Excel Output**: Generates structured Excel files with categorized data
- **Flexible Input**: Works with various rep firm website structures

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Azure OpenAI API Key**:
   - Set the environment variable `RepFirmKey` with your Azure OpenAI API key
   - On Windows: `set RepFirmKey=your_api_key_here`
   - On Linux/Mac: `export RepFirmKey=your_api_key_here`

## Usage

### Basic Usage

```python
from new_single_scraper import scrape_rep_firm_line_sheet

# Simple usage with just a URL
output_file = scrape_rep_firm_line_sheet("https://example-rep-firm.com")
print(f"Results saved to: {output_file}")
```

### Advanced Usage

```python
from new_single_scraper import scrape_rep_firm_line_sheet

# With rep firm name and custom output filename
output_file = scrape_rep_firm_line_sheet(
    url="https://example-rep-firm.com",
    rep_firm_name="ABC Rep Firm",
    output_filename="abc_rep_firm_line_sheet.xlsx"
)
```

### Individual Functions

You can also use the individual functions for more control:

```python
from new_single_scraper import (
    extract_website_data,
    process_with_chatgpt,
    parse_chatgpt_response_to_dataframe,
    save_to_excel
)

# Step 1: Extract website data
text_content = extract_website_data("https://example-rep-firm.com")

# Step 2: Process with ChatGPT
chatgpt_response = process_with_chatgpt(text_content, "ABC Rep Firm")

# Step 3: Parse to DataFrame
df = parse_chatgpt_response_to_dataframe(chatgpt_response)

# Step 4: Save to Excel
output_file = save_to_excel(df, "output.xlsx")
```

## Output Format

The scraper generates Excel files with the following columns:

- **Rep Firm Name**: Name of the rep firm
- **Brand Carried**: Individual brand/manufacturer (one per row)
- **Product Covered**: Specific product or product category
- **Space**: Water/wastewater treatment category (e.g., aerators, flocculators, coagulators)

## How It Works

1. **Website Extraction**: Uses Selenium WebDriver to navigate to the rep firm website and extract all text content
2. **Smart Navigation**: Automatically looks for common line sheet navigation elements (line sheet, products, catalog, equipment, brands)
3. **AI Processing**: Sends the extracted text to Azure OpenAI with a specific prompt to categorize the information
4. **Data Parsing**: Converts the AI response into a structured pandas DataFrame
5. **Excel Export**: Saves the categorized data to an Excel file

## Requirements

- Python 3.7+
- Chrome browser (for Selenium WebDriver)
- Azure OpenAI API key
- Internet connection

## Dependencies

- `requests`: HTTP requests
- `beautifulsoup4`: HTML parsing
- `pandas`: Data manipulation
- `openpyxl`: Excel file handling
- `selenium`: Web browser automation
- `webdriver-manager`: Chrome driver management
- `openai`: Azure OpenAI API client
- `python-dotenv`: Environment variable management
- `lxml`: XML/HTML parser

## Configuration

### Azure OpenAI Settings

The scraper is configured to use:
- **Endpoint**: `https://repfirm.openai.azure.com/`
- **API Version**: `2024-02-15-preview`
- **Model**: `gpt-4` (configurable in the code)

### Chrome Options

The scraper runs Chrome in headless mode with the following options:
- No sandbox
- Disabled GPU
- Window size: 1920x1080
- Custom user agent

## Error Handling

The scraper includes comprehensive error handling for:
- Missing API keys
- Network connectivity issues
- Website access problems
- AI processing errors
- File saving issues

## Example Output

The generated Excel file will contain rows like:

| Rep Firm Name | Brand Carried | Product Covered | Space |
|---------------|---------------|-----------------|-------|
| ABC Rep Firm  | Brand A       | Surface Aerators | Aerators |
| ABC Rep Firm  | Brand A       | Paddle Mixers   | Mixers |
| ABC Rep Firm  | Brand B       | Flocculators    | Flocculators |

## Troubleshooting

### Common Issues

1. **"RepFirmKey environment variable not found"**
   - Make sure you've set the environment variable correctly
   - Restart your terminal/command prompt after setting it

2. **Chrome driver issues**
   - The scraper automatically downloads the appropriate Chrome driver
   - Make sure Chrome is installed on your system

3. **Website not loading**
   - Check your internet connection
   - Verify the URL is correct and accessible
   - Some websites may block automated access

4. **AI processing errors**
   - Verify your Azure OpenAI API key is valid
   - Check your API quota and billing status
   - Ensure the endpoint URL is correct

### Debug Mode

To see more detailed output, you can modify the print statements in the code or add logging.

## License

This project is provided as-is for educational and business use.

## Support

For issues or questions, please check the troubleshooting section above or review the code comments for additional guidance. 