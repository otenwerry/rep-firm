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

class SimpleRepFirmScraper:
    def __init__(self, azure_key, azure_endpoint):
        """Initialize the scraper with Azure OpenAI credentials"""
        self.azure_key = azure_key
        self.azure_endpoint = azure_endpoint
        self.client = AzureOpenAI(
            api_key=azure_key,
            api_version="2024-12-01-preview",
            azure_endpoint=azure_endpoint
        )
        self.driver = None
        
    def generate_standardized_filename(self, rep_firm_name=None, batch_size=None, 
                                     success_count=None, total_count=None, 
                                     file_type="single", custom_suffix=None):
        """
        Generate standardized filenames for Excel outputs
        
        Args:
            rep_firm_name: Name of the rep firm (for single scrapes)
            batch_size: Number of URLs in batch (for batch scrapes)
            success_count: Number of successful scrapes
            total_count: Total number of URLs attempted
            file_type: "single", "batch", or "consolidated"
            custom_suffix: Additional custom suffix
            
        Returns:
            Standardized filename string
        """
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Base filename components
        components = []
        
        # Add file type prefix
        if file_type == "single":
            components.append("SINGLE")
        elif file_type == "batch":
            components.append("BATCH")
        elif file_type == "consolidated":
            components.append("CONSOLIDATED")
        
        # Add rep firm name for single scrapes
        if rep_firm_name and file_type == "single":
            # Clean rep firm name for filename
            clean_name = re.sub(r'[^\w\s-]', '', rep_firm_name)
            clean_name = re.sub(r'[-\s]+', '_', clean_name).strip('_')
            components.append(clean_name)
        
        # Add batch information for batch scrapes
        if batch_size and file_type in ["batch", "consolidated"]:
            components.append(f"{batch_size}_URLs")
        
        # Add success rate for batch scrapes
        if success_count is not None and total_count and total_count > 0:
            success_rate = int((success_count / total_count) * 100)
            if success_rate == 100:
                status = "SUCCESS"
            elif success_rate >= 50:
                status = "PARTIAL"
            else:
                status = "FAILED"
            components.append(f"{success_rate}pct_{status}")
        
        # Add timestamp
        components.append(timestamp)
        
        # Add custom suffix if provided
        if custom_suffix:
            components.append(custom_suffix)
        
        # Join components and add extension
        filename = "_".join(components) + ".xlsx"
        
        return filename
    
    def create_output_directory(self, directory_name="rep_firm_data"):
        """Create organized output directory structure"""
        # Create main directory
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)
        
        # Create subdirectories for different types
        subdirs = ["single_scrapes", "batch_scrapes", "consolidated_results"]
        for subdir in subdirs:
            subdir_path = os.path.join(directory_name, subdir)
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
        
        return directory_name
    
    def get_output_path(self, filename, file_type="single"):
        """Get the appropriate output path for the file type"""
        base_dir = self.create_output_directory()
        
        if file_type == "single":
            return os.path.join(base_dir, "single_scrapes", filename)
        elif file_type == "batch":
            return os.path.join(base_dir, "batch_scrapes", filename)
        elif file_type == "consolidated":
            return os.path.join(base_dir, "consolidated_results", filename)
        else:
            return os.path.join(base_dir, filename)
        
    def setup_driver(self):
        """Set up Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        return self.driver
    
    def extract_all_links_from_website(self, base_url, max_depth=2, max_links_per_page=50):
        """
        Extract ALL links from a website recursively, up to a certain depth
        Args:
            base_url: The starting URL
            max_depth: How deep to crawl (1 = homepage only, 2 = homepage + one level down)
            max_links_per_page: Maximum links to extract per page to avoid overwhelming
        Returns:
            List of dictionaries with 'text', 'href', 'depth', and 'source_page'
        """
        if not self.driver:
            print("❌ Driver not initialized")
            return []
        all_links = []
        visited_urls = set()
        urls_to_visit = [(base_url, 0)]  # (url, depth)
        print(f"🔍 Starting comprehensive link extraction from {base_url}")
        print(f"📊 Max depth: {max_depth}, Max links per page: {max_links_per_page}")
        while urls_to_visit:
            current_url, current_depth = urls_to_visit.pop(0)
            # Skip if already visited or too deep
            if current_url in visited_urls or current_depth > max_depth:
                continue
            visited_urls.add(current_url)
            try:
                print(f"🔗 Extracting links from depth {current_depth}: {current_url}")
                self.driver.get(current_url)
                time.sleep(2)
                page_links = self.driver.find_elements(By.TAG_NAME, "a")
                page_links_found = 0
                for link in page_links:
                    if page_links_found >= max_links_per_page:
                        break
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip() if link.text else ""
                        # More permissive filtering - capture more links
                        if (href and href.startswith('http') and not href.endswith(('.pdf', '.jpg', '.png', '.gif', '.zip', '.doc', '.docx', '.css', '.js'))):
                            is_internal = base_url.split('//')[1].split('/')[0] in href
                            # For internal links, be more permissive about text
                            if is_internal:
                                link_info = {
                                    'text': text if text else f"Link_{page_links_found}",
                                    'href': href,
                                    'depth': current_depth,
                                    'source_page': current_url
                                }
                                if not any(existing['href'] == href for existing in all_links):
                                    all_links.append(link_info)
                                    page_links_found += 1
                                    # Add to visit queue if not at max depth and not already queued
                                    if current_depth < max_depth and href not in visited_urls and (href, current_depth + 1) not in urls_to_visit:
                                        urls_to_visit.append((href, current_depth + 1))
                            # For external links, only include if they have meaningful text
                            elif text and len(text) > 0 and len(text) < 100:
                                link_info = {
                                    'text': text,
                                    'href': href,
                                    'depth': current_depth,
                                    'source_page': current_url
                                }
                                if not any(existing['href'] == href for existing in all_links):
                                    all_links.append(link_info)
                                    page_links_found += 1
                    except Exception as e:
                        continue
            except Exception as e:
                print(f"❌ Error extracting links from {current_url}: {e}")
                continue
        print(f"✅ Extracted {len(all_links)} unique links from {len(visited_urls)} pages (up to depth {max_depth})")
        return all_links
    
    def ai_identify_relevant_pages(self, all_links, base_url, rep_firm_name):
        """
        Use AI to identify which pages are most likely to contain product information
        Args:
            all_links: List of all extracted links
            base_url: Base URL of the website
            rep_firm_name: Name of the rep firm
        Returns:
            List of URLs to scrape for product information
        """
        if not all_links:
            return []
        # Prepare link data for AI analysis
        link_data = []
        for link in all_links[:100]:  # Limit to first 100 links to avoid token limits
            link_text = link.get('text', '') if link.get('text') else ''
            link_data.append(f"Link: '{link_text}' -> {link['href']} (Depth: {link['depth']})")
        link_text = "\n".join(link_data)
        prompt = f"""
        I'm analyzing a rep firm website ({rep_firm_name}) to find pages containing product information, line sheets, or manufacturer catalogs.
        Here are the links found on the website:
        {link_text}
        For rep firm websites, product information is typically found on pages with:
        1. Manufacturer/Brand pages: Pages listing manufacturers, brands, or product lines
        2. Product category pages: Pages for specific equipment types (aerators, filters, pumps, etc.)
        3. Application pages: Pages organized by water/wastewater treatment processes
        4. Equipment pages: Pages with specific product listings
        5. Catalog/Line sheet pages: Direct product catalogs
        Please analyze these links and identify ALL URLs that are likely to contain detailed product information. Return a list of the most relevant URLs (one per line, up to 10). If you are unsure, err on the side of including more. Prefer links with keywords like manufacturers, products, equipment, brands, catalog, line sheet, etc. If no clear product pages are found, return the main website URL as a fallback. Do not return external links.
        """
        try:
            response = self.client.chat.completions.create(
                model="model-router-2",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            result = (response.choices[0].message.content or "").strip()
            # Extract URLs from the response
            urls_to_scrape = []
            lines = result.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('http'):
                    url_match = re.search(r'https?://[^\s]+', line)
                    if url_match:
                        url = url_match.group()
                        # Only include internal URLs
                        if base_url.split('//')[1].split('/')[0] in url:
                            urls_to_scrape.append(url)
                elif line and not line.startswith('http') and base_url.split('//')[1].split('/')[0] in line:
                    url_match = re.search(r'https?://[^\s]+', line)
                    if url_match:
                        url = url_match.group()
                        if base_url.split('//')[1].split('/')[0] in url:
                            urls_to_scrape.append(url)
            # Remove duplicates and limit to reasonable number
            urls_to_scrape = list(set(urls_to_scrape))[:10]  # Max 10 pages
            print(f"🤖 AI identified {len(urls_to_scrape)} relevant pages to scrape:")
            for url in urls_to_scrape:
                print(f"   📄 {url}")
            # Fallback: if AI returns no URLs, include links with relevant keywords
            if not urls_to_scrape:
                print("⚠️  AI returned no URLs, using fallback keyword-based selection.")
                keywords = ["manufacturer", "product", "equipment", "brand", "catalog", "line sheet"]
                fallback_urls = []
                for link in all_links:
                    href = link.get('href', '').lower()
                    text = link.get('text', '').lower()
                    if any(kw in href or kw in text for kw in keywords):
                        # Only include internal URLs
                        if base_url.split('//')[1].split('/')[0] in href:
                            fallback_urls.append(link['href'])
                fallback_urls = list(set(fallback_urls))[:10]
                for url in fallback_urls:
                    print(f"   🟡 Fallback: {url}")
                if fallback_urls:
                    return fallback_urls
                else:
                    return [base_url]
            return urls_to_scrape
        except Exception as e:
            print(f"❌ Error in AI page identification: {e}")
            # Fallback: include links with relevant keywords
            keywords = ["manufacturer", "product", "equipment", "brand", "catalog", "line sheet"]
            fallback_urls = []
            for link in all_links:
                href = link.get('href', '').lower()
                text = link.get('text', '').lower()
                if any(kw in href or kw in text for kw in keywords):
                    if base_url.split('//')[1].split('/')[0] in href:
                        fallback_urls.append(link['href'])
            fallback_urls = list(set(fallback_urls))[:10]
            for url in fallback_urls:
                print(f"   🟡 Fallback: {url}")
            if fallback_urls:
                return fallback_urls
            else:
                return [base_url]
    
    def scrape_multiple_pages(self, urls_to_scrape, rep_firm_name):
        """
        Scrape multiple pages and combine the results using intelligent structure analysis
        """
        all_products = []
        
        print(f"🔄 Scraping {len(urls_to_scrape)} pages for {rep_firm_name}")
        
        for i, url in enumerate(urls_to_scrape, 1):
            print(f"\n📄 Scraping page {i}/{len(urls_to_scrape)}: {url}")
            
            try:
                # Use intelligent structure analysis instead of basic text extraction
                products = self.extract_products_with_brand_association(url, rep_firm_name)
                
                if products:
                    all_products.extend(products)
                    print(f"✅ Extracted {len(products)} products from {url}")
                else:
                    print(f"⚠️  No products found on {url}")
                    
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
        
        print(f"📊 Total products extracted from all pages: {len(all_products)}")
        return all_products

    def get_navigation_links(self, url):
        """Extract navigation links (website tabs) from the homepage - LEGACY METHOD"""
        if not self.driver:
            print("❌ Driver not initialized for get_navigation_links")
            return []
        try:
            print(f"Accessing {url}...")
            self.driver.get(url)
            time.sleep(3)
            
            # Get all navigation links
            nav_links = []
            
            # Look for navigation elements
            nav_selectors = [
                "nav a", "header a", ".navigation a", ".nav a", ".menu a",
                "#navigation a", "#nav a", ".navbar a", ".main-menu a"
            ]
            
            for selector in nav_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for link in links:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        if href and text and len(text) > 0 and len(text) < 50:
                            nav_links.append({
                                'text': text,
                                'href': href
                            })
                except:
                    continue
            
            # Also get all links from the page
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                href = link.get_attribute('href')
                text = link.text.strip() if link.text else ""
                if href and text and len(text) > 0 and len(text) < 50:
                    # Check if this link is already in nav_links
                    if not any(nl['href'] == href for nl in nav_links):
                        nav_links.append({
                            'text': text,
                            'href': href
                        })
            
            return nav_links
            
        except Exception as e:
            print(f"Error getting navigation links: {e}")
            return []
    
    def ai_identify_line_sheet_page(self, nav_links, base_url):
        """Use AI to identify which navigation link is most likely to lead to the line sheet - LEGACY METHOD"""
        if not nav_links:
            return None
        if not self.driver:
            print("❌ Driver not initialized for ai_identify_line_sheet_page")
            return None
            
        # Prepare the navigation data for AI analysis
        nav_data = []
        for link in nav_links[:20]:  # Limit to first 20 links
            link_text = link.get('text', '') if link.get('text') else ''
            nav_data.append(f"Link text: '{link_text}', URL: {link['href']}")
        
        nav_text = "\n".join(nav_data)
        
        prompt = f"""
        I'm analyzing a rep firm website to find the page that contains their line sheet or product catalog.
        
        Here are the navigation links from the website:
        {nav_text}
        
        For a rep firm website, the line sheet/product information is typically found under links like:
        - "Products", "Equipment", "Catalog", "Line Sheet", "Brands", "Manufacturers"
        - "By Process", "By Category", "Solutions", "Applications"
        
        Please analyze these navigation links and identify which ONE link is most likely to contain the line sheet or product catalog. 
        Return only the exact link text of the most promising option, or "NONE" if none seem relevant.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="model-router-2",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            selected_link_text = (response.choices[0].message.content or "").strip()
            print(f"AI selected: {selected_link_text}")
            
            # Find the matching link
            for link in nav_links:
                link_text = link.get('text', '') if link.get('text') else ''
                if link_text.lower() == selected_link_text.lower():
                    return link
            
            return None
            
        except Exception as e:
            print(f"Error in AI identification: {e}")
            return None
    
    def extract_page_content(self, url):
        """Extract all text content from a webpage (select all and copy)"""
        if not self.driver:
            print("❌ Driver not initialized for extract_page_content")
            return ""
        try:
            print(f"Extracting content from: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Get page source and extract text
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text_content = soup.get_text()
            
            # Clean up the text
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = ' '.join(chunk for chunk in chunks if chunk)
            
            return text_content
            
        except Exception as e:
            print(f"Error extracting page content: {e}")
            return ""
    
    def ai_extract_products(self, page_content, rep_firm_name):
        """Use AI to extract product information from the page content"""
        # Truncate content if too long
        content_preview = page_content[:10000] if len(page_content) > 10000 else page_content
        
        prompt = f"""
        Please extract a table with the following columns:
        - Rep Firm Name (must be the official, properly capitalized name of the rep firm, not an abbreviation, domain, or placeholder)
        - Brand Carried (must be the official, properly capitalized brand/manufacturer name, not a filename, abbreviation, or unclear string)
        - Product Covered (extract the exact products listed or mentioned on the page; be as specific as possible)
        - Product Space (use broad water/wastewater treatment process steps, e.g., Flow Control, Clarification, Disinfection, Aeration, Filtration, Chemical Feed, etc. Do NOT use specific model names or chemicals. If you cannot be specific, use 'Water Treatment' or 'Wastewater Treatment' as a catch-all, but only as a last resort)

        Rep Firm Name: {rep_firm_name}

        Website content (select all and copy):
        {content_preview}

        Please analyze this content carefully and extract any information about:
        1. Manufacturers or brands the rep firm represents (official, properly capitalized names only)
        2. Equipment categories or product types they offer (exact products listed; be as specific as possible)
        3. Water/wastewater treatment process steps they cover (broad categories only; be as specific as possible)

        IMPORTANT:
        - Do NOT include any entries where the Rep Firm Name or Brand Carried is not a proper, official, and capitalized name.
        - Do NOT include filenames, placeholders, or unclear strings (e.g., 'top of page', 'Sig 3-14-22.png', etc.) in any field.
        - Do NOT use generic terms like 'Various Steps...' for Product Space. If you cannot be specific, use 'Water Treatment' or 'Wastewater Treatment' as a catch-all, but only if no specificity is possible.
        - Only include entries where you can identify relevant, specific information.
        - If no clear product information is found, return a single entry with the official rep firm name and a general description, but do NOT include any unclear or irrelevant data.

        Please return the data in JSON format as a list of dictionaries with keys: "Rep Firm Name", "Brand Carried", "Product Covered", "Product Space".
        Only include valid, relevant entries as described above.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="model-router-2",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            
            result = (response.choices[0].message.content or "").strip()
            
            # Try to extract JSON from the response
            try:
                # Look for JSON in the response
                json_match = re.search(r'\[.*\]', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    products = json.loads(json_str)
                else:
                    # If no JSON found, try to parse the entire response
                    products = json.loads(result)
                
                return products
                
            except json.JSONDecodeError:
                print("Could not parse AI response as JSON, creating fallback entry")
                # Create a fallback entry
                return [{
                    "Rep Firm Name": rep_firm_name,
                    "Brand Carried": "Information not available on website",
                    "Product Covered": "Water/Wastewater Treatment Equipment",
                    "Space": "General"
                }]
                
        except Exception as e:
            print(f"Error in AI extraction: {e}")
            # Create a fallback entry
            return [{
                "Rep Firm Name": rep_firm_name,
                "Brand Carried": "Information not available on website",
                "Product Covered": "Water/Wastewater Treatment Equipment",
                "Space": "General"
            }]
    
    def normalize_products_data(self, products):
        """Normalize products data by splitting multiple products and spaces into separate rows"""
        normalized_products = []
        
        for product in products:
            rep_firm_name = product.get("Rep Firm Name", "")
            brand_carried = product.get("Brand Carried", "")
            product_covered = product.get("Product Covered", "")
            space = product.get("Space", "")
            
            # Split multiple products (separated by commas, semicolons, or "and")
            products_list = []
            if product_covered:
                # Split by common separators
                products_split = re.split(r'[,;]|\sand\s', product_covered)
                for p in products_split:
                    p = p.strip()
                    if p and len(p) > 2:  # Only add non-empty products
                        products_list.append(p)
            
            # If no products were split, use the original
            if not products_list:
                products_list = [product_covered] if product_covered else [""]
            
            # Split multiple spaces (separated by slashes, commas, or "and")
            spaces_list = []
            if space:
                # Split by common separators
                spaces_split = re.split(r'[/,]|\sand\s', space)
                for s in spaces_split:
                    s = s.strip()
                    if s and len(s) > 2:  # Only add non-empty spaces
                        spaces_list.append(s)
            
            # If no spaces were split, use the original
            if not spaces_list:
                spaces_list = [space] if space else [""]
            
            # Create separate rows for each product-space combination
            for product_item in products_list:
                for space_item in spaces_list:
                    normalized_products.append({
                        "Rep Firm Name": rep_firm_name,
                        "Brand Carried": brand_carried,
                        "Product Covered": product_item,
                        "Space": space_item
                    })
        
        return normalized_products
    
    def scrape_rep_firm(self, url):
        """Main function to scrape a rep firm website using comprehensive link extraction"""
        try:
            print(f"🚀 Starting comprehensive scrape of: {url}")
            
            # Setup driver
            self.setup_driver()
            
            # Extract rep firm name from URL
            domain = urlparse(url).netloc
            rep_firm_name = domain.replace("www.", "").replace(".com", "").replace(".org", "")
            rep_firm_name = rep_firm_name.replace("-", " ").title()
            print(f"🏢 Rep Firm Name: {rep_firm_name}")
            
            # Step 1: Extract ALL links from the website (comprehensive approach)
            print(f"\n🔍 Step 1: Extracting all links from {rep_firm_name}")
            all_links = self.extract_all_links_from_website(url, max_depth=2, max_links_per_page=50)
            
            if not all_links:
                print("❌ No links found on the website")
                return []
            
            # Step 2: Use AI to identify the most relevant pages for product information
            print(f"\n🤖 Step 2: AI analyzing {len(all_links)} links to identify product pages")
            urls_to_scrape = self.ai_identify_relevant_pages(all_links, url, rep_firm_name)
            
            if not urls_to_scrape:
                print("❌ AI could not identify any relevant pages")
                return []
            
            # Step 3: Scrape multiple relevant pages and combine results
            print(f"\n📄 Step 3: Scraping {len(urls_to_scrape)} identified pages")
            all_products = self.scrape_multiple_pages(urls_to_scrape, rep_firm_name)
            
            if not all_products:
                print("❌ No products found on any of the scraped pages")
                return []
            
            # Step 4: Normalize the data for database filtering
            print(f"\n🔄 Step 4: Normalizing {len(all_products)} products for database filtering")
            normalized_products = self.normalize_products_data(all_products)
            print(f"✅ Normalized to {len(normalized_products)} rows for database filtering")
            
            return normalized_products
            
        except Exception as e:
            print(f"❌ Error in scrape_rep_firm: {e}")
            return []
        
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_to_excel(self, products, filename=None, rep_firm_name=None, file_type="single"):
        """Save extracted products to Excel file with standardized naming"""
        headers = ["Rep Firm Name", "Brand Carried", "Product Covered", "Space"]
        
        # Generate standardized filename if not provided
        if not filename:
            filename = self.generate_standardized_filename(
                rep_firm_name=rep_firm_name,
                file_type=file_type
            )
        
        # Get appropriate output path
        output_path = self.get_output_path(filename, file_type)
        
        if not products:
            print("No products to save, creating empty Excel with headers.")
            df = pd.DataFrame(columns=headers)
        else:
            df = pd.DataFrame(products)
            # Ensure all columns are present
            for col in headers:
                if col not in df.columns:
                    df[col] = ""
            df = df[headers]
        
        df.to_excel(output_path, index=False)
        print(f"\n📊 Excel file created: {os.path.abspath(output_path)}")
        print(f"📈 Total products found: {len(df)}")
        if len(df) > 0:
            print("\n📋 Extracted Products:")
            print(df.to_string(index=False))
        else:
            print("⚠️  No product data extracted, but Excel file with headers is available.")
        return output_path

    def scrape_multiple_rep_firms(self, urls, output_filename=None):
        """Scrape multiple rep firm websites and consolidate results"""
        all_products = []
        
        if not output_filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_filename = f"multiple_rep_firms_{timestamp}.xlsx"
        
        print(f"Starting batch scrape of {len(urls)} rep firm websites...")
        
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*60}")
            print(f"Processing {i}/{len(urls)}: {url}")
            print(f"{'='*60}")
            
            try:
                products = self.scrape_rep_firm(url)
                if products:
                    all_products.extend(products)
                    print(f"✅ Successfully extracted {len(products)} products from {url}")
                else:
                    print(f"❌ No products found for {url}")
            except Exception as e:
                print(f"❌ Error processing {url}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"BATCH COMPLETE: Total products extracted: {len(all_products)}")
        print(f"{'='*60}")
        
        # Save consolidated results
        if all_products:
            filename = self.save_to_excel(all_products, output_filename)
            print(f"📊 Consolidated results saved to: {filename}")
        else:
            print("❌ No products found across all websites")
        
        return all_products

    def add_urls_to_batch(self, new_urls, existing_urls=None):
        """Helper function to add new URLs to the batch processing list"""
        if existing_urls is None:
            existing_urls = []
        
        # Add new URLs, avoiding duplicates
        for url in new_urls:
            if url not in existing_urls:
                existing_urls.append(url)
        
        return existing_urls

    def analyze_page_structure(self, url):
        """
        Analyze the underlying HTML/JavaScript structure to determine data format
        Returns: dict with structure type and extraction strategy
        """
        if not self.driver:
            print("❌ Driver not initialized for page structure analysis")
            return None
            
        try:
            print(f"🔍 Analyzing page structure: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Get the full page source including JavaScript
            page_source = self.driver.page_source
            
            # Extract all image elements and their properties
            images = self.driver.find_elements(By.TAG_NAME, "img")
            image_data = []
            
            for img in images:
                try:
                    src = img.get_attribute('src') or ""
                    alt = img.get_attribute('alt') or ""
                    title = img.get_attribute('title') or ""
                    parent_link = img.find_element(By.XPATH, "..").get_attribute('href') if img.find_element(By.XPATH, "..").tag_name == 'a' else ""
                    
                    # Get surrounding text context
                    try:
                        parent_element = img.find_element(By.XPATH, "..")
                        surrounding_text = parent_element.text.strip()
                    except:
                        surrounding_text = ""
                    
                    image_data.append({
                        'src': src,
                        'alt': alt,
                        'title': title,
                        'parent_link': parent_link,
                        'surrounding_text': surrounding_text
                    })
                except Exception as e:
                    continue
            
            # Extract all text content for analysis
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Remove script and style elements for text analysis
            for script in soup(["script", "style"]):
                script.decompose()
            
            text_content = soup.get_text()
            
            # Prepare data for AI analysis
            image_summary = []
            for i, img in enumerate(image_data[:20]):  # Limit to first 20 images
                image_summary.append(f"Image {i+1}: src={img['src'][:50]}..., alt='{img['alt']}', title='{img['title']}', parent_link={img['parent_link']}, context='{img['surrounding_text'][:100]}...'")
            
            analysis_prompt = f"""
            I'm analyzing a rep firm website page to understand its structure for product/brand extraction.
            
            PAGE URL: {url}
            
            TEXT CONTENT PREVIEW (first 2000 chars):
            {text_content[:2000]}
            
            IMAGE ELEMENTS FOUND:
            {chr(10).join(image_summary)}
            
            FULL HTML SOURCE (for detailed analysis):
            {page_source[:5000]}
            
            Please analyze this page structure and determine:
            
            1. **Data Format Type**:
               - "TEXT_ONLY": Products and brands are all in text format
               - "TEXT_PRODUCTS_IMAGE_BRANDS": Products in text, brands shown as images/logos
               - "MIXED": Combination of both approaches
            
            2. **Brand Extraction Strategy**:
               - If TEXT_ONLY: Use normal text scraping
               - If TEXT_PRODUCTS_IMAGE_BRANDS: 
                 * Check if brand images have clickable links (extract brand names from URLs)
                 * If no links, use OCR to read brand names from images
               - If MIXED: Use combination approach
            
            3. **Image Link Analysis**:
               - Are brand logos clickable (have href attributes)?
               - Do the image links contain brand names in the URL?
               - Are there alt/title attributes with brand names?
            
            Return your analysis in this exact JSON format:
            {{
                "structure_type": "TEXT_ONLY|TEXT_PRODUCTS_IMAGE_BRANDS|MIXED",
                "extraction_strategy": "TEXT_SCRAPING|IMAGE_LINK_EXTRACTION|OCR|COMBINATION",
                "has_clickable_brand_images": true/false,
                "brand_images_with_links": ["list of image URLs that are clickable"],
                "recommended_approach": "detailed explanation of how to extract data"
            }}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="model-router-2",
                    messages=[{"role": "user", "content": analysis_prompt}],
                    max_tokens=1000,
                    temperature=0.1
                )
                
                result = (response.choices[0].message.content or "").strip()
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    print(f"🤖 AI Analysis: {analysis['structure_type']} - {analysis['extraction_strategy']}")
                    return analysis
                else:
                    print("⚠️ Could not parse AI analysis, using fallback")
                    return {
                        "structure_type": "TEXT_ONLY",
                        "extraction_strategy": "TEXT_SCRAPING",
                        "has_clickable_brand_images": False,
                        "brand_images_with_links": [],
                        "recommended_approach": "Standard text scraping"
                    }
                    
            except Exception as e:
                print(f"❌ Error in AI structure analysis: {e}")
                return {
                    "structure_type": "TEXT_ONLY",
                    "extraction_strategy": "TEXT_SCRAPING",
                    "has_clickable_brand_images": False,
                    "brand_images_with_links": [],
                    "recommended_approach": "Standard text scraping (fallback)"
                }
                
        except Exception as e:
            print(f"❌ Error analyzing page structure: {e}")
            return None
    
    def extract_brands_from_image_links(self, url):
        """
        Extract brand information from ALL images near products, not just clickable ones
        """
        if not self.driver:
            return []
            
        try:
            print(f"🔗 Extracting brands from ALL images: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Get all images on the page
            all_images = self.driver.find_elements(By.TAG_NAME, "img")
            brand_data = []
            
            for img in all_images:
                try:
                    # Get image properties
                    src = img.get_attribute('src') or ""
                    alt = img.get_attribute('alt') or ""
                    title = img.get_attribute('title') or ""
                    
                    # Skip very small images (likely icons)
                    width = img.get_attribute('width')
                    height = img.get_attribute('height')
                    if width and height:
                        if int(width) < 30 or int(height) < 30:
                            continue
                    
                    # Get surrounding context (parent element and siblings)
                    try:
                        parent_element = img.find_element(By.XPATH, "..")
                        surrounding_text = parent_element.text.strip()
                        
                        # Also get text from sibling elements
                        try:
                            siblings = parent_element.find_elements(By.XPATH, "following-sibling::*")
                            for sibling in siblings[:3]:  # Check next 3 siblings
                                sibling_text = sibling.text.strip()
                                if sibling_text:
                                    surrounding_text += " " + sibling_text
                        except:
                            pass
                            
                    except:
                        surrounding_text = ""
                    
                    # Check if this image is clickable
                    is_clickable = False
                    parent_link = ""
                    try:
                        parent_link_element = img.find_element(By.XPATH, "..")
                        if parent_link_element.tag_name == 'a':
                            parent_link = parent_link_element.get_attribute('href') or ""
                            is_clickable = True
                    except:
                        pass
                    
                    # Extract brand name from various sources
                    brand_name = ""
                    
                    # 1. Try to extract from URL if clickable
                    if is_clickable and parent_link:
                        if any(keyword in parent_link.lower() for keyword in ['brand', 'manufacturer', 'company']):
                            url_parts = parent_link.split('/')
                            for part in url_parts:
                                if part and len(part) > 2 and not part.startswith('http'):
                                    brand_name = part.replace('-', ' ').replace('_', ' ').title()
                                    break
                    
                    # 2. Try alt text
                    if not brand_name and alt:
                        brand_name = alt.strip()
                    
                    # 3. Try title attribute
                    if not brand_name and title:
                        brand_name = title.strip()
                    
                    # 4. Try to extract from image filename
                    if not brand_name and src:
                        filename = src.split('/')[-1].split('.')[0]
                        if len(filename) > 2:
                            # Clean up filename
                            brand_name = filename.replace('-', ' ').replace('_', ' ').title()
                    
                    # 5. Use AI to analyze surrounding context for brand names
                    if not brand_name and surrounding_text:
                        context_prompt = f"""
                        I'm analyzing text surrounding a brand logo image on a rep firm website.
                        
                        Surrounding text: "{surrounding_text}"
                        
                        Please identify any brand names or manufacturer names in this text.
                        Return only the brand name, or "UNKNOWN" if no clear brand is mentioned.
                        Focus on water/wastewater treatment equipment manufacturers.
                        """
                        
                        try:
                            response = self.client.chat.completions.create(
                                model="model-router-2",
                                messages=[{"role": "user", "content": context_prompt}],
                                max_tokens=50,
                                temperature=0.1
                            )
                            
                            ai_brand = response.choices[0].message.content.strip()
                            if ai_brand and ai_brand.upper() != "UNKNOWN":
                                brand_name = ai_brand
                                
                        except Exception as e:
                            print(f"⚠️ AI brand analysis failed: {e}")
                    
                    if brand_name:
                        brand_data.append({
                            'brand_name': brand_name,
                            'image_url': src,
                            'link_url': parent_link if is_clickable else "",
                            'context': surrounding_text,
                            'is_clickable': is_clickable,
                            'extraction_method': 'IMAGE_ANALYSIS'
                        })
                        
                except Exception as e:
                    continue
            
            print(f"✅ Extracted {len(brand_data)} brands from image analysis")
            return brand_data
            
        except Exception as e:
            print(f"❌ Error extracting brands from images: {e}")
            return []
    
    def extract_brands_with_ocr(self, url):
        """
        Use OCR to extract brand names from images (fallback method)
        """
        if not self.driver:
            return []
            
        try:
            print(f"📸 Using OCR to extract brands from images: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Find all images that might be brand logos
            images = self.driver.find_elements(By.TAG_NAME, "img")
            brand_data = []
            
            for img in images:
                try:
                    src = img.get_attribute('src') or ""
                    
                    # Skip small images, icons, etc.
                    width = img.get_attribute('width')
                    height = img.get_attribute('height')
                    
                    if width and height:
                        if int(width) < 50 or int(height) < 50:
                            continue
                    
                    # Get surrounding context
                    try:
                        parent_element = img.find_element(By.XPATH, "..")
                        surrounding_text = parent_element.text.strip()
                    except:
                        surrounding_text = ""
                    
                    # For now, we'll use a placeholder for OCR
                    # In a real implementation, you'd use a library like pytesseract
                    # or an OCR API service
                    
                    # Create a prompt for AI to analyze the image context
                    ocr_prompt = f"""
                    I'm analyzing an image that appears to be a brand logo on a rep firm website.
                    
                    Image URL: {src}
                    Surrounding text context: {surrounding_text}
                    
                    Based on the image URL and surrounding context, can you identify what brand this logo represents?
                    Return only the brand name, or "UNKNOWN" if you cannot determine it.
                    """
                    
                    try:
                        response = self.client.chat.completions.create(
                            model="model-router-2",
                            messages=[{"role": "user", "content": ocr_prompt}],
                            max_tokens=50,
                            temperature=0.1
                        )
                        
                        brand_name = response.choices[0].message.content.strip()
                        
                        if brand_name and brand_name.upper() != "UNKNOWN":
                            brand_data.append({
                                'brand_name': brand_name,
                                'image_url': src,
                                'context': surrounding_text,
                                'extraction_method': 'OCR_AI'
                            })
                            
                    except Exception as e:
                        print(f"⚠️ OCR analysis failed for image {src}: {e}")
                        continue
                        
                except Exception as e:
                    continue
            
            print(f"✅ Extracted {len(brand_data)} brands using OCR/AI analysis")
            return brand_data
            
        except Exception as e:
            print(f"❌ Error in OCR extraction: {e}")
            return []
    
    def extract_products_with_brand_association(self, url, rep_firm_name):
        """
        Extract products and intelligently associate them with nearby brands
        """
        print(f"🧠 Using intelligent brand association for: {url}")
        
        # Step 1: Analyze page structure
        structure_analysis = self.analyze_page_structure(url)
        
        if not structure_analysis:
            print("⚠️ Structure analysis failed, using standard text extraction")
            return self.ai_extract_products(self.extract_page_content(url), rep_firm_name)
        
        structure_type = structure_analysis.get('structure_type', 'TEXT_ONLY')
        
        print(f"📊 Structure Type: {structure_type}")
        
        if structure_type == "TEXT_ONLY":
            # Use standard text extraction
            print("📝 Using standard text extraction")
            page_content = self.extract_page_content(url)
            return self.ai_extract_products(page_content, rep_firm_name)
            
        elif structure_type in ["TEXT_PRODUCTS_IMAGE_BRANDS", "MIXED"]:
            # Extract brands from ALL images
            print("🖼️ Extracting brands from ALL images and associating with products")
            
            # Get text content for products
            page_content = self.extract_page_content(url)
            text_products = self.ai_extract_products(page_content, rep_firm_name)
            
            # Extract ALL brands from images
            brand_data = self.extract_brands_from_image_links(url)
            
            # Use AI to intelligently associate products with brands
            if brand_data and text_products:
                print(f"🔗 Using AI to associate {len(text_products)} products with {len(brand_data)} brands")
                
                # Create a comprehensive prompt for brand association
                association_prompt = f"""
                I'm analyzing a rep firm website page to associate products with their corresponding brands.
                
                REP FIRM: {rep_firm_name}
                PAGE URL: {url}
                
                EXTRACTED PRODUCTS:
                {chr(10).join([f"- {p.get('Product Covered', 'Unknown')} (Space: {p.get('Space', 'Unknown')})" for p in text_products])}
                
                EXTRACTED BRANDS:
                {chr(10).join([f"- {b['brand_name']} (Context: {b['context'][:100]}...)" for b in brand_data])}
                
                PAGE CONTENT PREVIEW:
                {page_content[:2000]}
                
                Please analyze which brands are associated with which products. Consider:
                1. Proximity of brand logos to product descriptions
                2. Context clues in surrounding text
                3. Industry knowledge of which brands make which products
                4. Water/wastewater treatment equipment manufacturers
                
                Return your analysis as a JSON list where each product gets associated with its likely brands:
                [
                    {{
                        "product": "Product Name",
                        "brands": ["Brand1", "Brand2", "Brand3"],
                        "confidence": "HIGH|MEDIUM|LOW"
                    }}
                ]
                
                If you cannot determine brand associations, return an empty list.
                """
                
                try:
                    response = self.client.chat.completions.create(
                        model="model-router-2",
                        messages=[{"role": "user", "content": association_prompt}],
                        max_tokens=1000,
                        temperature=0.1
                    )
                    
                    result = response.choices[0].message.content.strip()
                    
                    # Extract JSON from response
                    json_match = re.search(r'\[.*\]', result, re.DOTALL)
                    if json_match:
                        associations = json.loads(json_match.group())
                        
                        # Apply associations to products
                        enhanced_products = []
                        
                        for product in text_products:
                            product_name = product.get('Product Covered', '')
                            
                            # Find matching association
                            matching_association = None
                            for assoc in associations:
                                if assoc.get('product', '').lower() in product_name.lower() or product_name.lower() in assoc.get('product', '').lower():
                                    matching_association = assoc
                                    break
                            
                            if matching_association and matching_association.get('brands'):
                                # Create separate entries for each brand
                                for brand in matching_association['brands']:
                                    enhanced_products.append({
                                        'Rep Firm Name': rep_firm_name,
                                        'Brand Carried': brand,
                                        'Product Covered': product.get('Product Covered', ''),
                                        'Space': product.get('Space', ''),
                                        'Confidence': matching_association.get('confidence', 'MEDIUM')
                                    })
                            else:
                                # Keep original product if no brand association found
                                enhanced_products.append(product)
                        
                        print(f"✅ Enhanced {len(text_products)} products to {len(enhanced_products)} brand-product associations")
                        return enhanced_products
                        
                    else:
                        print("⚠️ Could not parse brand associations, using fallback")
                        return self._fallback_brand_association(text_products, brand_data, rep_firm_name)
                        
                except Exception as e:
                    print(f"❌ Error in brand association: {e}")
                    return self._fallback_brand_association(text_products, brand_data, rep_firm_name)
            
            else:
                # Fallback if no brands or products found
                return text_products
        
        else:
            # Fallback to standard text extraction
            print("⚠️ Unknown structure type, using standard text extraction")
            page_content = self.extract_page_content(url)
            return self.ai_extract_products(page_content, rep_firm_name)
    
    def _fallback_brand_association(self, text_products, brand_data, rep_firm_name):
        """
        Fallback method for brand association when AI analysis fails
        """
        print("🔄 Using fallback brand association method")
        
        enhanced_products = []
        
        # Add products with any available brand information
        for product in text_products:
            if product.get('Brand Carried') and product.get('Brand Carried') != 'Unknown':
                enhanced_products.append(product)
            else:
                # Try to match with extracted brands based on context
                for brand in brand_data:
                    if brand['brand_name'].lower() in product.get('Product Covered', '').lower():
                        enhanced_products.append({
                            'Rep Firm Name': rep_firm_name,
                            'Brand Carried': brand['brand_name'],
                            'Product Covered': product.get('Product Covered', ''),
                            'Space': product.get('Space', ''),
                            'Confidence': 'LOW'
                        })
                        break
                else:
                    # Keep original product if no match found
                    enhanced_products.append(product)
        
        # Add standalone brand entries
        for brand in brand_data:
            # Check if this brand is already represented in products
            brand_in_products = any(
                brand['brand_name'].lower() in product.get('Brand Carried', '').lower() 
                for product in enhanced_products
            )
            
            if not brand_in_products:
                enhanced_products.append({
                    'Rep Firm Name': rep_firm_name,
                    'Brand Carried': brand['brand_name'],
                    'Product Covered': 'General equipment line',
                    'Space': 'General',
                    'Confidence': 'LOW'
                })
        
        return enhanced_products

def main():
    """Main function to test the simple scraper"""
    print("[INFO] Starting Simple Rep Firm Scraper...")
    
    # Azure OpenAI credentials
    ##cut the key
    azure_endpoint = "https://adity-mczs6jhv-eastus2.cognitiveservices.azure.com/"
    
    # Initialize scraper
    print("[INFO] Initializing SimpleRepFirmScraper...")
    scraper = SimpleRepFirmScraper(azure_key, azure_endpoint)
    
    # Only scrape the ShapeCal site
    rep_firm_urls = [
        "https://shapecal.com/"
    ]
    
    # Scrape the single rep firm and save to a specific Excel file
    try:
        all_products = scraper.scrape_multiple_rep_firms(rep_firm_urls, "SINGLE_ShapeCal_Test.xlsx")
        print(f"[INFO] Scrape completed. Total products: {len(all_products)}")
    except Exception as e:
        print(f"[ERROR] Exception during scrape: {e}")
    
    print("[INFO] Simple scraper completed.")

if __name__ == "__main__":
    main() 