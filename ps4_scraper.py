import requests
import pandas as pd
import time
import hashlib
import hmac
import xml.etree.ElementTree as ET
import json
import os
import sys
from pathlib import Path
import random
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️  Selenium not available. Installing...")
    os.system("pip install selenium")

requests.packages.urllib3.disable_warnings()

class PS4TitlesScraper:
    """Enhanced PS4 Titles scraper for the new endpoint"""
    
    def __init__(self):
        self.base_url = "https://www.serialstation.com/titles/"
        self.params = {
            'systems': '97ec53a2-f676-4c89-8172-e653dce5eed1',  # PS4 system ID
            'title_id_type': 'CUSA'  # Filter CUSA only
        }
        self.games_data = []
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver"""
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium not available for scraping")
            return
            
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ Chrome driver initialized successfully")
        except Exception as e:
            print(f"❌ Error setting up driver: {e}")
            self.driver = None
    
    def scrape_page(self, page_num):
        """Scraper une page de titles"""
        if not self.driver:
            print("❌ Chrome driver not available")
            return []
        
        # Construire l'URL pour cette page
        url = f"{self.base_url}?systems={self.params['systems']}&title_id_type={self.params['title_id_type']}&page={page_num}"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🔗 Loading page {page_num}...")
                self.driver.get(url)
                
                # Attendre que la page se charge
                time.sleep(3)
                
                # Trouver la table des titres
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                
                if not tables:
                    print(f"❌ No table found on page {page_num}")
                    if attempt == max_retries - 1:
                        return []
                    time.sleep(5)
                    continue
                
                # Prendre la première table (principale)
                table = tables[0]
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                if len(rows) <= 1:
                    print(f"❌ No data rows on page {page_num}")
                    if attempt == max_retries - 1:
                        return []
                    time.sleep(5)
                    continue
                
                page_games = []
                
                # Parcourir les lignes (sauf l'en-tête)
                for row_idx, row in enumerate(rows[1:], 1):
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        # Vérifier qu'on a au moins 3 colonnes (Title ID, Name, Editions)
                        if len(cells) >= 3:
                            title_id = cells[0].text.strip()
                            name = cells[1].text.strip()
                            editions = cells[2].text.strip()
                            
                            if title_id and name:
                                # Nettoyer le Title ID
                                if title_id.startswith('CUSA-'):
                                    title_id = title_id.replace('CUSA-', 'CUSA')
                                
                                game_data = {
                                    'Title_ID': title_id,
                                    'Name': name,
                                    'Editions': editions
                                }
                                page_games.append(game_data)
                    
                    except Exception as e:
                        print(f"⚠️ Error parsing row {row_idx}: {e}")
                        continue
                
                print(f"✅ Page {page_num}: {len(page_games)} titles found")
                return page_games
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed for page {page_num}: {e}")
                if attempt == max_retries - 1:
                    return []
                time.sleep(random.uniform(3, 6))
        
        return []
    
    def scrape_all_titles(self, max_pages=433, start_page=1):
        """Scraper toutes les pages de titles"""
        if start_page == 1:
            self.games_data = []
        
        # Charger les données existantes si on reprend
        if start_page > 1:
            try:
                df = pd.read_csv('ps4_titles_partial.csv')
                self.games_data = df.to_dict('records')
                print(f"📂 Resuming from page {start_page}, loaded {len(self.games_data)} existing titles")
            except FileNotFoundError:
                print("📂 No partial data found, starting fresh")
                self.games_data = []
        
        consecutive_empty_pages = 0
        
        print(f"🚀 Starting to scrape titles pages {start_page} to {max_pages}")
        print(f"🎯 Expected total: ~43,245 PS4 titles")
        print("=" * 60)
        
        start_time = time.time()
        
        for page in range(start_page, max_pages + 1):
            # Calculer le progrès
            progress = ((page - start_page + 1) / (max_pages - start_page + 1)) * 100
            elapsed = time.time() - start_time
            estimated_total = elapsed / (page - start_page + 1) * (max_pages - start_page + 1) if page > start_page else 0
            remaining = estimated_total - elapsed if page > start_page else 0
            
            print(f"\n📄 Page {page}/{max_pages} ({progress:.1f}%) - ETA: {remaining/60:.1f} min")
            
            page_data = self.scrape_page(page)
            
            if not page_data:
                consecutive_empty_pages += 1
                print(f"⚠️  Empty page {page} (consecutive: {consecutive_empty_pages})")
                
                if consecutive_empty_pages >= 5:
                    print(f"🛑 Hit {consecutive_empty_pages} consecutive empty pages, stopping")
                    break
            else:
                consecutive_empty_pages = 0
                self.games_data.extend(page_data)
                print(f"📊 Total titles collected: {len(self.games_data)}")
            
            # Sauvegarder tous les 20 pages
            if page % 20 == 0:
                self.save_to_csv('ps4_titles_partial.csv')
                print(f"💾 Saved checkpoint at page {page}")
            
            # Rate limiting
            time.sleep(random.uniform(1, 3))
        
        return self.games_data
    
    def save_to_csv(self, filename='ps4_titles.csv'):
        """Sauvegarder en CSV"""
        if self.games_data:
            try:
                df = pd.DataFrame(self.games_data)
                original_count = len(df)
                
                # Supprimer les doublons par Title_ID
                df = df.drop_duplicates(subset=['Title_ID'], keep='first')
                final_count = len(df)
                
                df.to_csv(filename, index=False, encoding='utf-8')
                
                if original_count != final_count:
                    print(f"💾 Saved {final_count} unique titles (removed {original_count - final_count} duplicates)")
                else:
                    print(f"💾 Saved {final_count} titles to {filename}")
                
                return final_count
            except Exception as e:
                print(f"❌ Error saving to CSV: {e}")
                return 0
        else:
            print("⚠️  No data to save")
            return 0
    
    def close_driver(self):
        """Fermer le driver"""
        if self.driver:
            self.driver.quit()
            print("🔒 Driver closed")

class PS4UpdateDownloader:
    """PS4 update downloader pour les titles"""
    
    def __init__(self, download_path='./ps4_titles_updates/'):
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
    
    def request_update(self, title_id):
        """Request PS4 update info from Sony servers"""
        try:
            # Clean and format title_id
            title_id = title_id.strip().upper()
            if not title_id.startswith('CUSA'):
                if title_id.startswith('CUSA-'):
                    title_id = title_id.replace('CUSA-', 'CUSA')
                elif title_id.isdigit():
                    title_id = f"CUSA{title_id.zfill(5)}"
                else:
                    title_id = f"CUSA{title_id.upper()}"
            
            # Remove any dashes
            title_id = title_id.replace('-', '')
            
            id_bytes = bytes('np_' + title_id, 'UTF-8')
            key = bytearray.fromhex('AD62E37F905E06BC19593142281C112CEC0E7EC3E97EFDCAEFCDBAAFA6378D84')
            hash_val = hmac.new(key, id_bytes, hashlib.sha256).hexdigest()
            xml_url = f'https://gs-sec.ww.np.dl.playstation.net/plo/np/{title_id}/{hash_val}/{title_id}-ver.xml'
            
            response = self.session.get(xml_url, verify=False, timeout=30)
            if response.status_code == 200 and response.text:
                root = ET.fromstring(response.content)
                name_elem = root.find('./tag/package/paramsfo/')
                name = name_elem.text.replace('\n', ' ') if name_elem is not None else title_id
                return root, name
            else:
                return None, f"No updates available (HTTP {response.status_code})"
        except Exception as e:
            return None, f"Error: {e}"
    
    def get_filename_from_url(self, url):
        """Extract filename from URL"""
        if not url:
            return "unknown_file.pkg"
        
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        
        if not filename or not filename.endswith('.pkg'):
            path_parts = parsed.path.split('/')
            for part in reversed(path_parts):
                if '.pkg' in part:
                    filename = part
                    break
            else:
                filename = "ps4_update.pkg"
        
        return filename
    
    def get_update_info(self, title_id):
        """Get update information for a PS4 title - Enhanced for multiple versions"""
        root, game_name = self.request_update(title_id)
        
        if root is None:
            return None
        
        updates = []
        versions_found = set()
        
        # Parcourir TOUS les packages (versions)
        for item in root.iter('package'):
            ver = item.get('version')
            man_url = item.get('manifest_url')
            
            if man_url and ver:
                try:
                    json_response = self.session.get(man_url, timeout=30)
                    json_cont = json.loads(json_response.content)
                    
                    # Pour chaque version, récupérer TOUS les fichiers
                    version_files = []
                    for piece in json_cont.get('pieces', []):
                        update_info = {
                            'game_name': game_name,
                            'version': ver,
                            'url': piece.get('url'),
                            'hash': piece.get('hashValue'),
                            'size': piece.get('fileSize'),
                            'title_id': title_id,
                            'filename': self.get_filename_from_url(piece.get('url'))
                        }
                        version_files.append(update_info)
                        updates.append(update_info)
                    
                    if version_files:
                        versions_found.add(ver)
                        print(f"      🔍 Version {ver}: {len(version_files)} files, "
                              f"{sum(f['size'] for f in version_files if f['size'])/(1024*1024):.1f} MB")
                
                except Exception as e:
                    print(f"⚠️ Error parsing manifest for {title_id} v{ver}: {e}")
                    continue
        
        if updates:
            print(f"    📦 Total: {len(versions_found)} versions, {len(updates)} files")
        
        return updates if updates else None
    
    def process_single_title(self, title_data):
        """Process a single title and return update links"""
        title_id = title_data['Title_ID']
        title_name = title_data['Name']
        editions = title_data['Editions']
        
        try:
            updates = self.get_update_info(title_id)
            
            if updates:
                total_size = sum(u['size'] for u in updates if u['size'])
                
                result = {
                    'title_id': title_id,
                    'title_name': title_name,
                    'sony_game_name': updates[0]['game_name'],
                    'editions': editions,
                    'has_updates': True,
                    'update_count': len(updates),
                    'latest_version': updates[0]['version'],
                    'total_size_bytes': total_size,
                    'total_size_mb': total_size / (1024 * 1024),
                    'updates': updates,
                    'status': 'found'
                }
            else:
                result = {
                    'title_id': title_id,
                    'title_name': title_name,
                    'editions': editions,
                    'has_updates': False,
                    'update_count': 0,
                    'status': 'no_updates'
                }
            
            return result
            
        except Exception as e:
            return {
                'title_id': title_id,
                'title_name': title_name,
                'editions': editions,
                'has_updates': False,
                'status': 'error',
                'error': str(e)
            }
    
    def batch_get_update_links(self, csv_file='ps4_titles.csv', max_workers=8, max_titles=None, chunk_size=1000):
        """Get update links for all titles in CSV with chunked processing"""
        try:
            df = pd.read_csv(csv_file)
            if max_titles:
                df = df.head(max_titles)
            
            titles = df.to_dict('records')
            total_titles = len(titles)
            
            print(f"🚀 Starting update links collection for {total_titles:,} PS4 titles")
            print(f"📁 Results will be saved to: {self.download_path}")
            print(f"🔧 Using {max_workers} worker threads")
            print(f"📦 Processing in chunks of {chunk_size}")
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return []
        
        all_results = []
        stats = {
            'total_titles': total_titles,
            'processed': 0,
            'found_updates': 0,
            'total_size_bytes': 0,
            'errors': 0
        }
        
        start_time = time.time()
        
        # Process in chunks to avoid memory issues
        for chunk_start in range(0, total_titles, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_titles)
            chunk_titles = titles[chunk_start:chunk_end]
            
            print(f"\n🔄 Processing chunk {chunk_start//chunk_size + 1}/{(total_titles-1)//chunk_size + 1}")
            print(f"   📋 Titles {chunk_start+1} to {chunk_end}")
            
            chunk_results = []
            
            # Process chunk with threading
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_title = {executor.submit(self.process_single_title, title): title for title in chunk_titles}
                
                for i, future in enumerate(as_completed(future_to_title), 1):
                    title = future_to_title[future]
                    
                    try:
                        result = future.result()
                        chunk_results.append(result)
                        all_results.append(result)
                        
                        stats['processed'] += 1
                        if result['has_updates']:
                            stats['found_updates'] += 1
                            stats['total_size_bytes'] += result.get('total_size_bytes', 0)
                        
                        # Progress update
                        overall_progress = (stats['processed'] / total_titles) * 100
                        chunk_progress = (i / len(chunk_titles)) * 100
                        elapsed = time.time() - start_time
                        eta = (elapsed / stats['processed']) * (total_titles - stats['processed']) if stats['processed'] > 0 else 0
                        
                        status_icon = "✅" if result['has_updates'] else "❌"
                        print(f"{status_icon} {stats['processed']:5d}/{total_titles} ({overall_progress:5.1f}%) - "
                              f"{result['title_id']} - {result['title_name'][:30]:<30} - "
                              f"ETA: {eta/60:.1f}m")
                        
                        if result['has_updates']:
                            version_info = f"{result['version_count']} versions" if result.get('version_count', 0) > 1 else f"v{result['latest_version']}"
                            print(f"      📦 {result['update_count']} files, {version_info}, "
                                  f"{result['total_size_mb']:.1f} MB")
                        
                    except Exception as e:
                        print(f"❌ Error processing {title['Title_ID']}: {e}")
                        stats['errors'] += 1
                    
                    # Rate limiting
                    time.sleep(random.uniform(0.3, 0.8))
            
            # Save chunk progress
            self.save_progress(all_results, stats)
            print(f"💾 Chunk completed, {len(all_results)} total results saved")
        
        # Final save
        self.save_final_results(all_results, stats)
        self.print_final_stats(stats, time.time() - start_time)
        
        return all_results
    
    def save_progress(self, results, stats):
        """Save current progress"""
        if not results:
            return
        
        progress_file = self.download_path / "titles_update_links_progress.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': stats,
                'results_count': len(results),
                'last_processed': results[-1]['title_id'] if results else None
            }, f, indent=2, ensure_ascii=False)
    
    def save_final_results(self, results, stats):
        """Save final comprehensive results"""
        if not results:
            print("❌ No results to save")
            return
        
        # 1. Detailed JSON report (sample only for large datasets)
        if len(results) > 5000:
            sample_results = results[:1000] + results[-1000:]  # First and last 1000
            detailed_file = self.download_path / "ps4_titles_sample_with_updates.json"
            with open(detailed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'stats': stats,
                    'note': 'Sample of first and last 1000 results due to file size',
                    'results': sample_results
                }, f, indent=2, ensure_ascii=False)
        else:
            detailed_file = self.download_path / "ps4_titles_with_updates.json"
            with open(detailed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'stats': stats,
                    'results': results
                }, f, indent=2, ensure_ascii=False)
        
        # 2. Summary CSV
        summary_data = []
        for result in results:
            summary_data.append({
                'Title_ID': result['title_id'],
                'Title_Name': result['title_name'],
                'Sony_Game_Name': result.get('sony_game_name', ''),
                'Editions': result.get('editions', ''),
                'Has_Updates': result['has_updates'],
                'Update_Count': result.get('update_count', 0),
                'Latest_Version': result.get('latest_version', ''),
                'Total_Size_MB': result.get('total_size_mb', 0),
                'Status': result['status']
            })
        
        summary_file = self.download_path / "ps4_titles_update_summary.csv"
        pd.DataFrame(summary_data).to_csv(summary_file, index=False, encoding='utf-8')
        
        # 3. Update links CSV (MOST IMPORTANT!)
        titles_with_updates = [r for r in results if r['has_updates']]
        if titles_with_updates:
            links_data = []
            for result in titles_with_updates:
                for update in result.get('updates', []):
                    links_data.append({
                        'Title_ID': result['title_id'],
                        'Title_Name': result['title_name'],
                        'Sony_Game_Name': result['sony_game_name'],
                        'Editions': result.get('editions', ''),
                        'Version': update['version'],
                        'Size_MB': update['size'] / (1024 * 1024) if update['size'] else 0,
                        'Size_Bytes': update['size'],
                        'Filename': update['filename'],
                        'Download_URL': update['url'],
                        'SHA1_Hash': update['hash']
                    })
            
            links_file = self.download_path / "ps4_titles_download_links.csv"
            pd.DataFrame(links_data).to_csv(links_file, index=False, encoding='utf-8')
        
        # 4. Statistics CSV
        stats_data = [{
            'Total_Titles_Processed': stats['processed'],
            'Titles_With_Updates': stats['found_updates'],
            'Total_Errors': stats['errors'],
            'Success_Rate_Percent': (stats['found_updates']/stats['processed'])*100 if stats['processed'] > 0 else 0,
            'Total_Update_Size_GB': stats['total_size_bytes']/(1024**3),
            'Average_Update_Size_MB': (stats['total_size_bytes']/stats['found_updates'])/(1024**2) if stats['found_updates'] > 0 else 0
        }]
        
        stats_file = self.download_path / "ps4_titles_statistics.csv"
        pd.DataFrame(stats_data).to_csv(stats_file, index=False, encoding='utf-8')
        
        print(f"\n📊 Results saved:")
        print(f"   📄 Detailed data: {detailed_file}")
        print(f"   📊 Summary: {summary_file}")
        print(f"   📈 Statistics: {stats_file}")
        if titles_with_updates:
            print(f"   🔗 Download links: {links_file}")
    
    def print_final_stats(self, stats, duration):
        """Print final statistics"""
        print(f"\n" + "=" * 80)
        print(f"🎉 PS4 TITLES UPDATE LINKS COLLECTION COMPLETED!")
        print(f"=" * 80)
        print(f"⏱️  Duration: {duration/3600:.1f} hours")
        print(f"🎮 Total titles processed: {stats['processed']:,}")
        print(f"📦 Titles with updates: {stats['found_updates']:,}")
        print(f"❌ Errors: {stats['errors']:,}")
        if stats['processed'] > 0:
            print(f"📈 Success rate: {(stats['found_updates']/stats['processed'])*100:.1f}%")
        print(f"💾 Total update size: {stats['total_size_bytes']/(1024**3):.2f} GB")
        
        if stats['found_updates'] > 0:
            avg_size = (stats['total_size_bytes'] / stats['found_updates']) / (1024**2)
            print(f"📊 Average update size: {avg_size:.1f} MB per title")

def print_banner():
    """Print application banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║           PS4 Titles Scraper & Update Tool                ║
    ║              SerialStation.com - Titles Section           ║
    ║             43,245 PS4 Titles on 433 Pages               ║
    ║              With Sony Update Links Collection            ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

def print_menu():
    """Print main menu"""
    menu = """
    📋 Main Menu:
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. 🕷️  Start full titles scraping (433 pages)              │
    │ 2. ⏭️  Resume titles scraping from last position           │
    │ 3. 📂 Load existing titles CSV data                        │
    │ 4. 🔍 Search for PS4 updates by CUSA ID                    │
    │ 5. 🔗 Get update links for first 50 titles (test)         │
    │ 6. 📦 Get update links for ALL titles (~43k)              │
    │ 7. 📊 Show statistics from loaded data                     │
    │ 8. 🧪 Test scraping on page 1 of titles                   │
    │ 9. 🚪 Exit                                                 │
    └─────────────────────────────────────────────────────────────┘
    """
    print(menu)

def main():
    """Main CLI application"""
    print_banner()
    
    # N'initialiser le scraper que si nécessaire
    scraper = None
    downloader = PS4UpdateDownloader()
    titles_data = []
    
    try:
        while True:
            print_menu()
            
            try:
                choice = input("Enter your choice (1-9): ").strip()
                
                if choice in ['1', '2', '8']:
                    # Options qui nécessitent Selenium
                    if not SELENIUM_AVAILABLE:
                        print("❌ Selenium not available. Please install: pip install selenium")
                        continue
                    
                    if scraper is None:
                        scraper = PS4TitlesScraper()
                        if not scraper.driver:
                            print("❌ Could not initialize Chrome driver. Please check your installation.")
                            continue
                
                if choice == '1':
                    print("\n🚀 Starting full scrape of PS4 Titles...")
                    print("🎯 Target: 43,245 titles across 433 pages")
                    print("⚠️  This will take several hours to complete!")
                    print("💡 The script will save progress every 20 pages and can be resumed later.")
                    confirm = input("Continue? (y/N): ").strip().lower()
                    
                    if confirm == 'y':
                        start_time = time.time()
                        titles_data = scraper.scrape_all_titles(max_pages=433)
                        final_count = scraper.save_to_csv('ps4_titles.csv')
                        
                        end_time = time.time()
                        duration = end_time - start_time
                        print(f"\n✅ Titles scraping complete in {duration/3600:.1f} hours!")
                        print(f"📊 Total unique titles found: {final_count:,}")
                    
                elif choice == '2':
                    try:
                        df = pd.read_csv('ps4_titles_partial.csv')
                        # Estimer la page basée sur le nombre de titres (100 par page environ)
                        last_page = len(df) // 100 + 1
                        
                        print(f"\n⏭️  Resuming from approximately page {last_page}")
                        print(f"📊 Currently have {len(df):,} titles in partial data")
                        confirm = input("Continue? (y/N): ").strip().lower()
                        
                        if confirm == 'y':
                            titles_data = scraper.scrape_all_titles(max_pages=433, start_page=last_page)
                            final_count = scraper.save_to_csv('ps4_titles.csv')
                            print(f"\n✅ Scraping complete! Total unique titles: {final_count:,}")
                            
                    except FileNotFoundError:
                        print("❌ No partial data found. Use option 1 to start fresh.")
                
                elif choice == '3':
                    try:
                        csv_files = ['ps4_titles.csv', 'ps4_titles_partial.csv']
                        csv_file = None
                        
                        for file in csv_files:
                            if os.path.exists(file):
                                csv_file = file
                                break
                        
                        if csv_file:
                            df = pd.read_csv(csv_file)
                            titles_data = df.to_dict('records')
                            print(f"\n✅ Loaded {len(titles_data):,} titles from {csv_file}")
                            
                            # Show sample
                            print("\n📋 Sample titles:")
                            print("-" * 80)
                            print(f"{'Title_ID':<15} {'Name':<40} {'Editions':<25}")
                            print("-" * 80)
                            for i, title in enumerate(titles_data[:5]):
                                name = title['Name'][:37] + '...' if len(title['Name']) > 40 else title['Name']
                                editions = title['Editions'][:22] + '...' if len(title['Editions']) > 25 else title['Editions']
                                print(f"{title['Title_ID']:<15} {name:<40} {editions:<25}")
                            if len(titles_data) > 5:
                                print(f"\n... and {len(titles_data) - 5:,} more titles")
                        else:
                            print("❌ No CSV files found. Scrape titles first.")
                            
                    except Exception as e:
                        print(f"❌ Error loading CSV: {e}")
                
                elif choice == '4':
                    cusa_id = input("\n🔍 Enter CUSA ID (e.g., CUSA12345): ").strip()
                    if cusa_id:
                        if not cusa_id.upper().startswith('CUSA'):
                            if cusa_id.isdigit():
                                cusa_id = f"CUSA{cusa_id.zfill(5)}"
                            else:
                                cusa_id = f"CUSA{cusa_id.upper()}"
                        
                        print(f"\n🔍 Searching for updates for {cusa_id}...")
                        updates = downloader.get_update_info(cusa_id)
                        
                        if updates:
                            print(f"\n✅ Found {len(updates)} updates for {cusa_id}:")
                            print("=" * 60)
                            
                            for i, update in enumerate(updates):
                                size_mb = update['size'] / (1024 * 1024) if update['size'] else 0
                                print(f"\nUpdate {i+1}:")
                                print(f"  🎮 Game: {update['game_name']}")
                                print(f"  📦 Version: {update['version']}")
                                print(f"  📏 Size: {size_mb:.1f} MB")
                                print(f"  📁 Filename: {update['filename']}")
                                print(f"  🔗 URL: {update['url']}")
                                print(f"  🔐 Hash: {update['hash']}")
                        else:
                            print(f"❌ No updates found for {cusa_id}")
                
                elif choice == '5':
                    print("\n🔗 Getting update links for first 50 titles (test)...")
                    csv_files = ['ps4_titles_test.csv', 'ps4_titles.csv', 'ps4_titles_partial.csv']
                    csv_file = None
                    
                    print("🔍 Searching for CSV files...")
                    for file in csv_files:
                        print(f"   Checking: {file} - {'✅ Found' if os.path.exists(file) else '❌ Not found'}")
                        if os.path.exists(file):
                            csv_file = file
                            break
                    
                    if csv_file:
                        print(f"📁 Using CSV file: {csv_file}")
                        
                        # Vérifier le contenu
                        try:
                            df = pd.read_csv(csv_file)
                            print(f"✅ Loaded {len(df)} titles from {csv_file}")
                            
                            confirm = input("Continue with update links collection for first 50 titles? (y/N): ").strip().lower()
                            
                            if confirm == 'y':
                                results = downloader.batch_get_update_links(csv_file, max_workers=5, max_titles=50)
                                with_updates = [r for r in results if r['has_updates']]
                                print(f"\n✅ Test completed! Found updates for {len(with_updates)}/50 titles")
                        
                        except Exception as e:
                            print(f"❌ Error reading CSV: {e}")
                    else:
                        print("❌ No CSV file found. Available files in directory:")
                        for f in os.listdir('.'):
                            if f.endswith('.csv'):
                                print(f"   • {f}")
                
                elif choice == '6':
                    csv_files = ['ps4_titles.csv', 'ps4_titles_partial.csv']
                    csv_file = None
                    
                    for file in csv_files:
                        if os.path.exists(file):
                            csv_file = file
                            break
                    
                    if not csv_file:
                        print("❌ No CSV file found. Please scrape titles first.")
                        continue
                    
                    df = pd.read_csv(csv_file)
                    print(f"\n📦 Getting update links for ALL {len(df):,} titles...")
                    print("🎯 This is the complete PS4 titles database!")
                    print("⚠️  This will take MANY hours to complete (~6-12 hours)!")
                    print("🔗 Only links will be collected, no downloads")
                    print("💾 Progress will be saved regularly")
                    confirm = input("Continue? (y/N): ").strip().lower()
                    
                    if confirm == 'y':
                        results = downloader.batch_get_update_links(csv_file, max_workers=10, chunk_size=500)
                        
                        with_updates = [r for r in results if r['has_updates']]
                        total_size_gb = sum(r.get('total_size_bytes', 0) for r in with_updates) / (1024**3)
                        
                        print(f"\n🎉 COMPLETE DATABASE COLLECTION FINISHED!")
                        print(f"   ✅ Titles with updates: {len(with_updates):,}/{len(df):,}")
                        print(f"   💾 Total size available: {total_size_gb:.2f} GB")
                        print(f"   📁 Results saved in: {downloader.download_path}")
                
                elif choice == '7':
                    if titles_data:
                        print(f"\n📊 Titles Statistics:")
                        print("=" * 40)
                        print(f"Total titles: {len(titles_data):,}")
                        
                        # Analyze editions
                        editions_count = {}
                        for title in titles_data:
                            editions = title.get('Editions', 'Unknown').split(',')
                            for edition in editions:
                                edition = edition.strip()
                                editions_count[edition] = editions_count.get(edition, 0) + 1
                        
                        print(f"\n📋 Top 10 Edition Types:")
                        for edition, count in sorted(editions_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                            print(f"  {edition}: {count:,}")
                            
                    else:
                        print("❌ No data loaded. Load CSV first or scrape new data.")
                
                elif choice == '8':
                    print("\n🧪 Testing titles scraping on page 1...")
                    titles = scraper.scrape_page(1)
                    
                    if titles:
                        print(f"\n✅ Test successful! Found {len(titles)} titles on page 1")
                        print("\n📋 Sample titles:")
                        print("-" * 80)
                        print(f"{'Title_ID':<15} {'Name':<40} {'Editions':<25}")
                        print("-" * 80)
                        for i, title in enumerate(titles[:5]):
                            name = title['Name'][:37] + '...' if len(title['Name']) > 40 else title['Name']
                            editions = title['Editions'][:22] + '...' if len(title['Editions']) > 25 else title['Editions']
                            print(f"{title['Title_ID']:<15} {name:<40} {editions:<25}")
                        
                        # Option pour sauvegarder
                        save_test = input(f"\n💾 Save these {len(titles)} titles as test CSV? (y/N): ").strip().lower()
                        if save_test == 'y':
                            df = pd.DataFrame(titles)
                            df.to_csv('ps4_titles_test.csv', index=False, encoding='utf-8')
                            print(f"✅ Saved to ps4_titles_test.csv")
                    else:
                        print("❌ Test failed! No titles found on page 1")
                
                elif choice == '9':
                    print("\n👋 Exiting...")
                    break
                
                else:
                    print("❌ Invalid choice. Please enter 1-9.")
            
            except KeyboardInterrupt:
                print("\n\n⚠️  Operation cancelled by user")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
            
            input("\nPress Enter to continue...")
            print("\n" + "="*60)
    
    finally:
        if scraper:
            scraper.close_driver()

if __name__ == "__main__":
    main()