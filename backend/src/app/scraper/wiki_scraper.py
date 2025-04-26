#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cyberpunk 2077 Wiki Scraper
---------------------------
Extracts metadata from the Cyberpunk 2077 Wiki:
- Characters data with descriptions
- Items, vehicles, locations
- Categories and article relationships
- Images and media

Uses fandom.py and MediaWiki API for efficient data retrieval.
"""

import fandom
import requests
import logging
import re
import json
import os
from typing import List, Dict, Any, Optional, Union, Set
from datetime import datetime
from pathlib import Path

from src.core.config import settings

# Configuration
WIKI_SLUG = settings.WIKI_SLUG
LANGUAGE = settings.WIKI_LANGUAGE
API_URL: Optional[str] = None
OUTPUT_DIR = settings.TEMP_DIR
CATEGORIES = settings.CATEGORIES

# Setup logging
def setup_logging(level=logging.INFO) -> logging.Logger:
    """Configure the logging system."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Create logger
logger = setup_logging(level=logging.INFO)

def initialize_wiki(slug: str = WIKI_SLUG, lang: str = LANGUAGE) -> None:
    """
    Initialize fandom.py and set up the API URL.
    """
    fandom.set_wiki(slug)
    fandom.set_lang(lang)
    global API_URL
    API_URL = f"https://{slug}.fandom.com/api.php"  
    
    # Check API availability
    try:
        resp = requests.get(API_URL, params={"action": "query", "meta": "siteinfo", "format": "json"})
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error accessing API {API_URL}: {e}")
        raise
    
    logger.info(f"Wiki initialized: {slug}, language: {lang}, API URL: {API_URL}")

def fetch_category_members(category: str, limit: int = 500) -> List[Dict]:
    """
    Return all members of a category with ns=0 (articles).
    Handles pagination for large sets of data.
    """
    members: List[Dict] = []
    session = requests.Session()
    session.timeout = (5, 30)  # (connect timeout, read timeout)
    cmcontinue = None
    
    logger.info(f"Loading members from category: {category}")

    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": limit,
            "cmnamespace": "0"  # Articles only
        }
        
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        try:
            resp = session.get(API_URL, params=params, timeout=session.timeout)
            resp.raise_for_status()
            data = resp.json()

            for p in data.get("query", {}).get("categorymembers", []):
                members.append(p)
            
            cont = data.get("continue", {})
            cmcontinue = cont.get("cmcontinue")
            if not cmcontinue:
                break
        
        except requests.exceptions.Timeout:
            logger.error("Timeout while loading category members")
            break
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while loading category members: {e}")
            break
        except Exception as e:
            logger.error(f"Error while loading category members: {e}")
            break

    logger.info(f"Loaded {len(members)} articles from category {category}")
    return members

def get_page_metadata(title: str) -> Dict[str, Any]:
    """
    Get comprehensive metadata for a wiki page, including:
    - Basic info (title, id, url)
    - Description/content
    - Categories
    - Images
    - Related pages
    
    Returns a dictionary with all available metadata.
    """
    metadata = {
        "title": title,
        "url": f"https://{WIKI_SLUG}.fandom.com/wiki/{title.replace(' ', '_')}",
        "description": None,
        "categories": [],
        "images": [],
        "infobox": {},
        "sections": [],
        "related_pages": []
    }
    
    try:
        # Method 1: Get detailed page info through fandom-py
        try:
            page = fandom.page(title)
            metadata["id"] = page.pageid
            
            # Get description
            metadata["description"] = get_page_extract(title)
            
            # Get infobox and sections
            content = page.content
            if isinstance(content, dict):
                # Process infobox if available
                if content.get('infobox'):
                    try:
                        if isinstance(content['infobox'], dict):
                            metadata["infobox"] = content['infobox']
                        elif isinstance(content['infobox'], str):
                            # Sometimes infobox comes as HTML string
                            metadata["infobox_raw"] = content['infobox'].strip()
                    except:
                        pass
                
                # Process sections
                if content.get('sections'):
                    for section in content['sections']:
                        if section.get('title') and section.get('content'):
                            metadata["sections"].append({
                                "title": section['title'],
                                "content": clean_description(section['content'])
                            })
        except Exception as e:
            logger.debug(f"Error getting page through fandom-py: {str(e)}")
        
        # Method 2: Get categories
        try:
            params = {
                'action': 'query',
                'format': 'json',
                'titles': title,
                'prop': 'categories',
                'cllimit': 50,
                'formatversion': 2
            }
            response = requests.get(API_URL, params=params, timeout=10)
            data = response.json()
            
            if 'query' in data and 'pages' in data['query'] and data['query']['pages']:
                page = data['query']['pages'][0]
                if 'categories' in page:
                    metadata["categories"] = [cat['title'].replace('Category:', '') 
                                            for cat in page['categories']]
        except Exception as e:
            logger.debug(f"Error getting categories: {str(e)}")
        
        # Method 3: Get images
        try:
            params = {
                'action': 'query',
                'format': 'json',
                'titles': title,
                'prop': 'images',
                'imlimit': 20,
                'formatversion': 2
            }
            response = requests.get(API_URL, params=params, timeout=10)
            data = response.json()
            
            if 'query' in data and 'pages' in data['query'] and data['query']['pages']:
                page = data['query']['pages'][0]
                if 'images' in page:
                    for img in page['images']:
                        img_title = img['title']
                        if img_title.startswith('File:'):
                            # Get image URL
                            try:
                                params = {
                                    'action': 'query',
                                    'format': 'json',
                                    'titles': img_title,
                                    'prop': 'imageinfo',
                                    'iiprop': 'url',
                                    'formatversion': 2
                                }
                                img_response = requests.get(API_URL, params=params, timeout=10)
                                img_data = img_response.json()
                                if ('query' in img_data and 'pages' in img_data['query'] and 
                                    img_data['query']['pages'] and 'imageinfo' in img_data['query']['pages'][0]):
                                    img_url = img_data['query']['pages'][0]['imageinfo'][0]['url']
                                    metadata["images"].append({
                                        "title": img_title.replace('File:', ''),
                                        "url": img_url
                                    })
                            except Exception as e:
                                logger.debug(f"Error getting image URL: {str(e)}")
        except Exception as e:
            logger.debug(f"Error getting images: {str(e)}")
            
        # Method 4: Get links
        try:
            params = {
                'action': 'query',
                'format': 'json',
                'titles': title,
                'prop': 'links',
                'pllimit': 50,
                'formatversion': 2
            }
            response = requests.get(API_URL, params=params, timeout=10)
            data = response.json()
            
            if 'query' in data and 'pages' in data['query'] and data['query']['pages']:
                page = data['query']['pages'][0]
                if 'links' in page:
                    metadata["related_pages"] = [link['title'] for link in page['links']]
        except Exception as e:
            logger.debug(f"Error getting links: {str(e)}")
            
        return metadata
    
    except Exception as e:
        logger.error(f"Error getting metadata for '{title}': {str(e)}")
        return metadata

def get_page_extract(title: str) -> Optional[str]:
    """
    Get comprehensive page description using multiple methods.
    Returns None if no valid description is found.
    """
    try:
        # Method 1: Try getting the page directly through fandom-py
        try:
            page = fandom.page(title)
            
            description = None
            
            # If page has an infobox, combine it with summary for comprehensive description
            content = page.content
            if isinstance(content, dict):
                description_parts = []
                
                # Add summary if available
                if page.summary and not page.summary.startswith('Sub-Pages'):
                    description_parts.append(page.summary)
                
                # Add general content if available
                if content.get('content') and content['content'].strip():
                    description_parts.append(content['content'].strip())
                
                # Look for key sections
                important_sections = ['Description', 'Biography', 'Background', 'Personality', 'Appearance', 'History']
                
                if content.get('sections'):
                    for section in content['sections']:
                        if section.get('title') and section['title'] in important_sections and section.get('content'):
                            section_text = f"{section['content'].strip()}"
                            description_parts.append(section_text)
                
                # Combine all parts
                if description_parts:
                    description = ' '.join(description_parts)
                    
                    # Clean up the description
                    description = clean_description(description)
                    
                    # Limit to 5 sentences if too long
                    sentences = description.split('. ')
                    if len(sentences) > 5:
                        description = '. '.join(sentences[:5]) + '.'
                    
                    return description
                
                # If no complete description built yet, try individual parts
                if page.summary and not page.summary.startswith('Sub-Pages'):
                    return clean_description(page.summary)
                
                if content.get('content') and content['content'].strip():
                    return clean_description(content['content'].strip())
                
                # Try first section content
                if content.get('sections'):
                    for section in content['sections']:
                        if section.get('content'):
                            text = section['content'].strip()
                            if text:
                                return clean_description(text)
                
                # Try infobox if exists
                if content.get('infobox'):
                    text = content['infobox'].strip()
                    if text:
                        return clean_description(text)
        except Exception as e:
            pass

        # Method 2: Try API extract as fallback
        params = {
            'action': 'query',
            'format': 'json',
            'titles': title,
            'prop': 'extracts',
            'exintro': 0,  # Get full extract, not just intro
            'explaintext': 1,
            'formatversion': 2
        }
        response = requests.get(API_URL, params=params, timeout=10)
        data = response.json()
        
        if 'query' in data and 'pages' in data['query']:
            pages = data['query']['pages']
            if pages and 'extract' in pages[0]:
                extract = pages[0]['extract']
                if extract:
                    extract = clean_description(extract)
                    
                    # Limit to 5 sentences if too long
                    sentences = extract.split('. ')
                    if len(sentences) > 5:
                        extract = '. '.join(sentences[:5]) + '.'
                    return extract

        # Method 3: Try search as last resort
        search_results = fandom.search(title, results=1)
        if search_results and len(search_results) > 0:
            result_title = search_results[0][0]
            if result_title == title:  # Only use if exact match
                try:
                    page = fandom.page(result_title)
                    if page.summary:
                        return clean_description(page.summary)
                except:
                    pass

        # Method 4: Try parsing the HTML directly as last resort
        try:
            session = requests.Session()
            resp = session.get(f"https://cyberpunk.fandom.com/wiki/{title.replace(' ', '_')}")
            if resp.status_code == 200:
                text = resp.text
                
                # Try to extract the first paragraph after article-header
                match = re.search(r'<div class="mw-parser-output">(.*?)<p>(.*?)</p>', text, re.DOTALL)
                if match and match.group(2):
                    # Clean HTML tags
                    paragraph = re.sub(r'<[^>]+>', '', match.group(2))
                    if paragraph.strip():
                        return clean_description(paragraph.strip())
        except:
            pass

        return None

    except Exception as e:
        logger.debug(f"Error getting extract for '{title}': {str(e)}")
        return None

def clean_description(text: str) -> str:
    """
    Clean up text by removing service messages, duplicated info, and other unwanted parts.
    """
    if not text:
        return text
        
    # Remove common prefixes
    text = re.sub(r'^Sub-Pages:[A-Za-z0-9]+\s*', '', text)
    
    # Remove "This section requires expanding" notes
    text = re.sub(r'This section requires expanding\. Click here to add more\.📝', '', text)
    
    # Remove "This article requires cleanup" notes
    text = re.sub(r'This article requires cleanup\.', '', text)
    
    # Remove any HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Fix newlines and whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Remove duplicated sentences
    sentences = text.split('. ')
    unique_sentences = []
    for sentence in sentences:
        # Add sentence only if not already in the list (case insensitive comparison)
        if not any(sentence.lower() == s.lower() for s in unique_sentences):
            unique_sentences.append(sentence)
    
    text = '. '.join(unique_sentences)
    
    return text.strip()

def get_all_wiki_categories() -> List[str]:
    """
    Get a list of all categories available in the wiki.
    """
    categories = []
    acfrom = None
    
    logger.info("Getting list of all wiki categories...")
    
    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "allcategories",
            "aclimit": 500,
            "formatversion": 1  # Using format version 1 for consistent response format
        }
        
        if acfrom:
            params["acfrom"] = acfrom
            
        try:
            session = requests.Session()
            resp = session.get(API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if 'query' in data and 'allcategories' in data['query']:
                for cat in data['query']['allcategories']:
                    # The category name is directly in the '*' key in format version 1
                    if '*' in cat:
                        categories.append(cat['*'])
                
            if 'continue' in data and 'accontinue' in data['continue']:
                acfrom = data['continue']['accontinue']
            else:
                break
                
        except Exception as e:
            logger.error(f"Error getting category list: {str(e)}")
            break
            
    logger.info(f"Found {len(categories)} categories")
    return categories

def scrape_category(category_name: str, limit: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    """
    Scrape all articles from a specific category and collect their metadata.
    
    Args:
        category_name: Name of the category to scrape
        limit: Optional limit of articles to process
    
    Returns:
        Dictionary of article titles and their metadata
    """
    results = {}
    
    # Get all members of the category
    members = fetch_category_members(category_name)
    
    # Apply limit if specified
    if limit is not None:
        members = members[:limit]
    
    total = len(members)
    logger.info(f"Processing {total} articles from category '{category_name}'")
    
    # Process each member
    for i, member in enumerate(members, 1):
        title = member.get("title")
        logger.info(f"Processing article {i}/{total}: {title}")
        
        # Get detailed metadata
        metadata = get_page_metadata(title)
        results[title] = metadata
        
        # Show progress every 10 articles
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{total} articles processed")
    
    return results

def save_to_json(data: Any, filename: str) -> None:
    """
    Save data to a JSON file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Data saved to {filepath}")
    except Exception as e:
        logger.error(f"Error saving data to {filepath}: {e}")

def main():
    """
    Main entry point for the scraper.
    """
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize wiki
    initialize_wiki()
    
    # Get all wiki categories (for reference)
    all_categories = get_all_wiki_categories()
    save_to_json(all_categories, "all_categories.json")
    
    # Process each defined category
    for category_key, category_name in CATEGORIES.items():
        logger.info(f"Starting scraping for category: {category_name}")
        
        # Get all data for the category (limit to 100 items per category for testing)
        data = scrape_category(category_name, limit=2)
        
        # Save to JSON
        save_to_json(data, f"{category_key}.json")
        
        logger.info(f"Completed scraping {len(data)} items for category: {category_name}")
    
    logger.info("Scraping completed")

if __name__ == "__main__":
    main()
