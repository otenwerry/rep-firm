#!/usr/bin/env python3
"""
Test script to demonstrate the comprehensive scraping approach
on bgagurney.com which has a "Manufacturers" tab with sub-links
"""

import sys
import os
from simple_rep_firm_scraper import SimpleRepFirmScraper

def test_improved_brand_association():
    """Test the improved brand association logic on specific bgagurney.com pages"""
    
    # Azure OpenAI configuration
    ##cut the key
    azure_endpoint = "https://adity-mczs6jhv-eastus2.cognitiveservices.azure.com/"
    
    # Initialize scraper
    scraper = SimpleRepFirmScraper(azure_key, azure_endpoint)
    
    # Test URLs - specific bgagurney.com pages with product information
    test_urls = [
        "https://www.bgagurney.com/blank-1",  # Wastewater Process Equipment/Technology
        "https://www.bgagurney.com/blank"     # Flow Measurement/Instrumentation
    ]
    
    print("🧪 Testing Improved Brand Association Logic")
    print("=" * 60)
    print("Target URLs:")
    for url in test_urls:
        print(f"   - {url}")
    print("Expected: Extract specific products and brands, avoid 'General Representation'")
    print("=" * 60)
    
    try:
        all_products = []
        
        for i, url in enumerate(test_urls, 1):
            print(f"\n📄 Processing URL {i}/{len(test_urls)}: {url}")
            
            # Scrape the specific page
            products = scraper.scrape_rep_firm(url)
            
            if products:
                all_products.extend(products)
                print(f"✅ Extracted {len(products)} products from {url}")
            else:
                print(f"⚠️ No products found on {url}")
        
        if all_products:
            print(f"\n✅ Successfully extracted {len(all_products)} total products")
            
            # Look specifically for "Chopper" entries
            chopper_entries = [p for p in all_products if "chopper" in p.get('Product Covered', '').lower()]
            
            if chopper_entries:
                print(f"\n🔍 Found {len(chopper_entries)} 'Chopper' entries:")
                for entry in chopper_entries:
                    print(f"   Product: {entry.get('Product Covered', 'N/A')}")
                    print(f"   Brand: {entry.get('Brand Carried', 'N/A')}")
                    print(f"   Space: {entry.get('Space', 'N/A')}")
                    print(f"   Confidence: {entry.get('Confidence', 'N/A')}")
                    print("   ---")
            else:
                print("\n⚠️ No 'Chopper' entries found")
            
            # Show all brands found
            all_brands = set(p.get('Brand Carried', '') for p in all_products if p.get('Brand Carried'))
            print(f"\n🏷️ All brands found ({len(all_brands)}):")
            for brand in sorted(all_brands):
                if brand and brand != 'Unknown':
                    print(f"   - {brand}")
            
            # Check for "General Representation" entries
            general_entries = [p for p in all_products if "general" in p.get('Brand Carried', '').lower() or "general" in p.get('Product Covered', '').lower()]
            if general_entries:
                print(f"\n⚠️ Found {len(general_entries)} 'General' entries that may need OCR:")
                for entry in general_entries:
                    print(f"   Brand: {entry.get('Brand Carried', 'N/A')}")
                    print(f"   Product: {entry.get('Product Covered', 'N/A')}")
                    print("   ---")
            
            # Save results
            output_path = scraper.save_to_excel(all_products, rep_firm_name="Bert_Gurney_Associates")
            print(f"\n📊 Results saved to: {output_path}")
            
        else:
            print("❌ No products extracted from any URL")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    test_improved_brand_association() 