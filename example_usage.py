#!/usr/bin/env python3
"""
Example usage script for the Rep Firm Line Sheet Scraper

This script demonstrates how to use the scraper to extract and process
rep firm line sheet information from a website.
"""

from new_single_scraper import scrape_rep_firm_line_sheet
import os


def main():
    """
    Example usage of the rep firm line sheet scraper
    """
    
    # Make sure the RepFirmKey environment variable is set
    if not os.getenv('RepFirmKey'):
        print("Error: RepFirmKey environment variable not set!")
        print("Please set it using: set RepFirmKey=your_api_key_here")
        return
    
    # Example 1: Basic usage with just a URL
    print("=== Example 1: Basic Usage ===")
    try:
        # Replace with actual rep firm URL
        url = "https://example-rep-firm.com"
        
        output_file = scrape_rep_firm_line_sheet(url)
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error in example 1: {str(e)}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Usage with rep firm name and custom output filename
    print("=== Example 2: With Rep Firm Name and Custom Output ===")
    try:
        # Replace with actual rep firm URL
        url = "https://another-rep-firm.com"
        rep_firm_name = "ABC Rep Firm"
        output_filename = "abc_rep_firm_line_sheet.xlsx"
        
        output_file = scrape_rep_firm_line_sheet(
            url=url,
            rep_firm_name=rep_firm_name,
            output_filename=output_filename
        )
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error in example 2: {str(e)}")


if __name__ == "__main__":
    main() 