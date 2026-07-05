#!/usr/bin/env python3
"""
Wikybook Auto News Generator
Monitors RSS feeds, generates 5-language articles using Gemini API,
and pushes them to the News repository automatically.
"""

import feedparser
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import hashlib
from datetime import datetime, timezone

# Configure Gemini
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# RSS feeds by country
RSS_FEEDS = {
    'indonesia': [
        'https://www.thejakartapost.com/feed',
        'https://www.antaranews.com/rss/terkini.xml',
        'https://feeds.feedburner.com/detikcom',
    ],
    'jepang': [
        'https://www.japantimes.co.jp/feed/',
        'https://www3.nhk.or.jp/rss/news/cat0.xml',
    ],
    'tiongkok': [
        'https://www.scmp.com/rss/91/feed',
        'https://www.chinadaily.com.cn/rss/china_rss.xml',
    ],
    'korea': [
        'https://www.koreaherald.com/rss.php?mode=realtime',
        'https://en.yna.co.kr/RSS/news.xml',
    ],
    'india': [
        'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms',
        'https://www.ndtv.com/rss/news',
    ],
    'inggris': [
        'https://feeds.bbci.co.uk/news/world/rss.xml',
        'https://www.theguardian.com/world/rss',
    ],
    'prancis': [
        'https://www.france24.com/en/rss',
        'https://www.france24.com/fr/rss',
    ],
    'jerman': [
        'https://rss.dw.com/rdf/rss-en-all',
        'https://www.thelocal.de/rss/',
    ],
    'spanyol': [
        'https://www.elmundo.es/rss/rss.html',
        'https://feeds.elconfidencial.com/espana',
    ],
    'portugal': [
        'https://feeds.feedburner.com/portugalnews',
        'https://www.theportugalnews.com/feed',
    ],
    'mesir': [
        'https://www.egypttoday.com/RSS',
        'https://english.ahram.org.eg/NewsRSS.aspx',
    ],
    'romawi': [
        'https://www.ansa.it/english/notizie/ansait_english.xml',
        'https://www.repubblica.it/rss/homepage.xml',
    ],
}

# Country metadata
COUNTRIES = {
    'indonesia': {'id': 'indonesia', 'names': {'id': 'Indonesia', 'en': 'Indonesia', 'ja': 'インドネシア', 'ko': '인도네시아', 'zh': '印度尼西亚'}, 'flag': '🇮🇩'},
    'jepang': {'id': 'jepang', 'names': {'id': 'Jepang', 'en': 'Japan', 'ja': '日本', 'ko': '일본', 'zh': '日本'}, 'flag': '🇯🇵'},
    'tiongkok': {'id': 'tiongkok', 'names': {'id': 'Tiongkok', 'en': 'China', 'ja': '中国', 'ko': '중국', 'zh': '中国'}, 'flag': '🇨🇳'},
    'korea': {'id': 'korea', 'names': {'id': 'Korea Selatan', 'en': 'South Korea', 'ja': '韓国', 'ko': '한국', 'zh': '韩国'}, 'flag': '🇰🇷'},
    'india': {'id': 'india', 'names': {'id': 'India', 'en': 'India', 'ja': 'インド', 'ko': '인도', 'zh': '印度'}, 'flag': '🇮🇳'},
    'inggris': {'id': 'inggris', 'names': {'id': 'Inggris', 'en': 'United Kingdom', 'ja': 'イギリス', 'ko': '영국', 'zh': '英国'}, 'flag': '🇬🇧'},
    'prancis': {'id': 'prancis', 'names': {'id': 'Prancis', 'en': 'France', 'ja': 'フランス', 'ko': '프랑스', 'zh': '法国'}, 'flag': '🇫🇷'},
    'jerman': {'id': 'jerman', 'names': {'id': 'Jerman', 'en': 'Germany', 'ja': 'ドイツ', 'ko': '독일', 'zh': '德国'}, 'flag': '🇩🇪'},
    'spanyol': {'id': 'spanyol', 'names': {'id': 'Spanyol', 'en': 'Spain', 'ja': 'スペイン', 'ko': '스페인', 'zh': '西班牙'}, 'flag': '🇪🇸'},
    'portugal': {'id': 'portugal', 'names': {'id': 'Portugal', 'en': 'Portugal', 'ja': 'ポルトガル', 'ko': '포르투갈', 'zh': '葡萄牙'}, 'flag': '🇵🇹'},
    'mesir': {'id': 'mesir', 'names': {'id': 'Mesir', 'en': 'Egypt', 'ja': 'エジプト', 'ko': '이집트', 'zh': '埃及'}, 'flag': '🇪🇬'},
    'romawi': {'id': 'romawi', 'names': {'id': 'Italia', 'en': 'Italy', 'ja': 'イタリア', 'ko': '이탈리아', 'zh': '意大利'}, 'flag': '🇮🇹'},
}

def load_processed_ids():
    """Load already processed article IDs to avoid duplicates."""
    try:
        with open('scripts/processed_articles.json', 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_processed_ids(ids):
    """Save processed article IDs."""
    with open('scripts/processed_articles.json', 'w') as f:
        json.dump(list(ids)[-500:], f)  # Keep last 500

def generate_article_id(country, title):
    """Generate a unique article ID from country and title."""
    # Clean title for URL
    clean = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    clean = re.sub(r'\s+', '-', clean.strip())[:60]
    # Add date prefix
    date_str = datetime.now().strftime('%Y%m%d')
    return f"{country}-{clean}-{date_str}"

def fetch_article_content(url):
    """Fetch and extract main text content from a news URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Remove scripts, styles, ads
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Try common article containers
        article = soup.find('article') or soup.find('div', class_=re.compile('article|content|post-body'))
        if article:
            paragraphs = article.find_all('p')
        else:
            paragraphs = soup.find_all('p')
        
        text = ' '.join([p.get_text(strip=True) for p in paragraphs[:20]])
        return text[:5000]  # Limit to 5000 chars
    except Exception as e:
        print(f"  Error fetching content: {e}")
        return ""

def generate_multilang_article(news_title, news_desc, news_content, source_name, source_url, country):
    """Use Gemini to generate a 5-language article from news content."""
    
    prompt = f"""You are a professional news journalist and translator. Based on the following news article, create a complete news article in 5 languages: Indonesian (id), English (en), Japanese (ja), Korean (ko), and Chinese (zh).

For EACH language, provide:
1. title: A compelling news headline (max 100 chars)
2. desc: A brief description/summary (max 200 chars)
3. content: Full article body in HTML format with <p> tags, minimum 3 paragraphs, comprehensive and factual

Source title: {news_title}
Source description: {news_desc}
Source content: {news_content[:3000]}
Source: {source_name}
Source URL: {source_url}
Country category: {country}

IMPORTANT RULES:
- Content must be factual and based on the source material
- Each language version must be a proper translation/adaptation, not a literal translation
- Use professional journalistic tone
- Wrap content in <p> tags
- Include 3-5 paragraphs per language
- Do NOT include any markdown formatting

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "id": {{"title": "...", "desc": "...", "content": "<p>...</p>"}},
  "en": {{"title": "...", "desc": "...", "content": "<p>...</p>"}},
  "ja": {{"title": "...", "desc": "...", "content": "<p>...</p>"}},
  "ko": {{"title": "...", "desc": "...", "content": "<p>...</p>"}},
  "zh": {{"title": "...", "desc": "...", "content": "<p>...</p>"}}
}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Remove markdown code blocks if present
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
        else:
            print(f"  No JSON found in response")
            return None
    except Exception as e:
        print(f"  Gemini API error: {e}")
        return None

def escape_js_string(s):
    """Escape string for safe inclusion in JavaScript."""
    if not s:
        return ''
    s = s.replace('\\', '\\\\')
    s = s.replace("'", "\\'")
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '')
    s = s.replace('\t', ' ')
    return s

def add_article_to_data_file(country, article_data):
    """Add a new article to the country's data file."""
    filepath = f'data_{country}.js'
    
    # Read existing file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Build the new article JS object
    langs_js = []
    for lang in ['id', 'en', 'ja', 'ko', 'zh']:
        if lang in article_data['langs']:
            ld = article_data['langs'][lang]
            langs_js.append(f"""        '{lang}': {{
          title: "{escape_js_string(ld['title'])}",
          desc: "{escape_js_string(ld['desc'])}",
          content: "{escape_js_string(ld['content'])}",
          source: "{escape_js_string(article_data.get('source', ''))}",
          sourceUrl: "{escape_js_string(article_data.get('sourceUrl', ''))}",
          sourceSnippet: "{escape_js_string(article_data.get('sourceSnippet', ''))}",
          source2: "{escape_js_string(article_data.get('source2', ''))}",
          sourceUrl2: "{escape_js_string(article_data.get('sourceUrl2', ''))}",
          sourceSnippet2: "{escape_js_string(article_data.get('sourceSnippet2', ''))}",
          source3: "{escape_js_string(article_data.get('source3', ''))}",
          sourceUrl3: "{escape_js_string(article_data.get('sourceUrl3', ''))}",
          sourceSnippet3: "{escape_js_string(article_data.get('sourceSnippet3', ''))}"
        }}""")
    
    article_js = f"""      {{
        id: '{escape_js_string(article_data["id"])}',
        langs: {{
{','.join(langs_js)}
        }}
      }}"""
    
    # Find the last article in the file and insert after it
    # Look for the pattern: "      }" followed by newline and "    ]"
    # We need to add a comma after the last article and insert the new one
    
    # Find "    ]" (end of articles array)
    pattern = r"(\s*\}\s*\n\s*)(\]\s*\n\s*\}\s*\)\s*;?\s*$)"
    match = re.search(pattern, content)
    
    if match:
        # Insert new article before the closing bracket
        insert_pos = match.start()
        # Check if there's a comma after the last article
        before = content[:insert_pos]
        after = content[insert_pos:]
        
        # Ensure last article has a trailing comma
        before = before.rstrip()
        if not before.endswith(','):
            before += ','
        before += '\n'
        
        content = before + article_js + '\n' + after
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    else:
        print(f"  Could not find insertion point in {filepath}")
        return False

def update_sitemap(country, article_id):
    """Add new article URL to sitemap.xml."""
    try:
        with open('sitemap.xml', 'r', encoding='utf-8') as f:
            sitemap = f.read()
        
        url = f"https://news.hypeemart.my.id/{country}/{article_id}"
        lastmod = datetime.now().strftime('%Y-%m-%d')
        
        new_entry = f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
        
        sitemap = sitemap.replace('</urlset>', new_entry)
        
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(sitemap)
    except Exception as e:
        print(f"  Sitemap update error: {e}")

def create_static_html(country, article_id, langs_data):
    """Create static HTML version for SEO and direct access."""
    os.makedirs(f'{country}', exist_ok=True)
    
    # Use Indonesian as default for static HTML
    lang_data = langs_data.get('id', langs_data.get('en', {}))
    title = lang_data.get('title', article_id)
    desc = lang_data.get('desc', '')
    content = lang_data.get('content', '')
    
    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_js_string(title)} - Wikybook News</title>
<meta name="description" content="{escape_js_string(desc)}">
<meta property="og:title" content="{escape_js_string(title)}">
<meta property="og:description" content="{escape_js_string(desc)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Wikybook News">
<link rel="canonical" href="https://news.hypeemart.my.id/{country}/{article_id}">
<script>
window.location.href = '/#{country}/{article_id}';
</script>
</head>
<body>
<h1>{escape_js_string(title)}</h1>
<p>{escape_js_string(desc)}</p>
{content}
</body>
</html>"""
    
    filepath = f'{country}/{article_id}'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

def process_feed(country, feed_url, processed_ids):
    """Process a single RSS feed and return new articles."""
    new_articles = []
    
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:5]:  # Check top 5 entries
            # Create unique ID from entry URL/title
            entry_hash = hashlib.md5(
                (entry.get('link', '') + entry.get('title', '')).encode()
            ).hexdigest()
            
            if entry_hash in processed_ids:
                continue
            
            title = entry.get('title', '')
            desc = entry.get('summary', entry.get('description', ''))
            url = entry.get('link', '')
            source_name = feed.feed.get('title', url.split('/')[2] if url else 'Unknown')
            
            if not title or not url:
                continue
            
            print(f"  New article found: {title[:60]}...")
            
            # Fetch full content
            full_content = fetch_article_content(url)
            if not full_content:
                full_content = desc
            
            # Generate 5-language article using Gemini
            article_langs = generate_multilang_article(
                title, desc, full_content, source_name, url, country
            )
            
            if article_langs:
                article_id = generate_article_id(country, title)
                
                # Get 3 sources (use the same source for all, but we can try to find more)
                article_data = {
                    'id': article_id,
                    'langs': article_langs,
                    'source': source_name,
                    'sourceUrl': url,
                    'sourceSnippet': f"{title} — {source_name}",
                    'source2': '',
                    'sourceUrl2': '',
                    'sourceSnippet2': '',
                    'source3': '',
                    'sourceUrl3': '',
                    'sourceSnippet3': '',
                }
                
                new_articles.append(article_data)
                processed_ids.add(entry_hash)
            else:
                print(f"  Failed to generate article for: {title[:40]}")
                processed_ids.add(entry_hash)  # Mark as processed even if failed
            
            time.sleep(2)  # Rate limit for Gemini API
            
    except Exception as e:
        print(f"  Feed error ({feed_url}): {e}")
    
    return new_articles

def main():
    print(f"=== Wikybook Auto News Generator ===")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    if not os.environ.get('GEMINI_API_KEY'):
        print("ERROR: GEMINI_API_KEY not set!")
        return
    
    processed_ids = load_processed_ids()
    print(f"Processed articles in memory: {len(processed_ids)}")
    
    total_new = 0
    
    for country, feeds in RSS_FEEDS.items():
        print(f"\n--- Checking {country} ---")
        for feed_url in feeds:
            print(f"  Feed: {feed_url}")
            new_articles = process_feed(country, feed_url, processed_ids)
            
            for article in new_articles:
                # Add to data file
                if add_article_to_data_file(country, article):
                    # Update sitemap
                    update_sitemap(country, article['id'])
                    # Create static HTML
                    create_static_html(country, article['id'], article['langs'])
                    total_new += 1
                    print(f"  ✓ Published: {article['id']}")
                else:
                    print(f"  ✗ Failed to add: {article['id']}")
    
    # Save processed IDs
    save_processed_ids(processed_ids)
    
    print(f"\n=== Done: {total_new} new articles published ===")

if __name__ == '__main__':
    main()
