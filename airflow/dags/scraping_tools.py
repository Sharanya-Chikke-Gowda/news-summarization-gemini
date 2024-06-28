import re
import requests
import logging
import concurrent.futures

from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from tldextract import extract


def get_links_recursive(
        url:str, # url of webpage 
        company:str, # company name to extract news for 
        max_depth:int=2, # maximum depth o look for sites recursively
        current_depth:int=0, # current depth at which we are scraping
)->List:
    links = []
    logger = logging.getLogger(__name__)
    
    logger.info(f"Scraping {url} at depth {current_depth}")

    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=re.compile(rf'-*{company}-*'))

        unwanted = ['reddit', 'facebook', 'whatsapp',
                    'twitter', 'linkedin', 'mailto',
                    'checkout', 'login', 'create',
                    'forgot']
        
        filtered_links = []
        for link in links:
            if not any(not_needed in link['href'] for not_needed in unwanted):
                filtered_links.append(link['href'])
        filtered_links = list(set(filtered_links))

        if current_depth < max_depth:
            for link in filtered_links:
                new_links = get_links_recursive(link, company, max_depth, current_depth+1)
                filtered_links.extend(new_links)
        filtered_links = list(set(filtered_links))

    except requests.RequestException as e:
        print(f"Error in fetching {url}: {e}")
        return []
    
    return filtered_links
            
def scrape_sites(
        url:str, # url to scrape news
)->dict:
    logger = logging.getLogger(__name__)

    response = requests.get(url)
    response.raise_for_status()

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract the news title
        if 'yahoo' in url:
            title = soup.find('h1', id='caas-lead-header-undefined').text
        elif 'washingtonpost' in url:
            title = soup.find('span', {'data-qa':'headline-opinion-text'}).text
        else:
            title = soup.find('h1').text

        # Extract date of publication
        if 'yahoo' in url:
            pub_date = soup.find('time').text
            pub_date = datetime.strptime(pub_date, '%a, %b %d, %Y, %I:%M %p').strftime('%Y-%m-%d %H:%M')
        elif 'nypost' in url:
            pub_date = soup.find('div', class_='date meta meta--byline date--updated').text.replace('\n', '')[31:].replace('.','')
            pub_date = datetime.strptime(pub_date, '%B %d, %Y, %I:%M %p ET').strftime('%Y-%m-%d %H:%M')
        elif 'businessinsider' in url:
            pub_date = soup.find('time').text.strip()
            pub_date = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d %H:%M')
        elif 'washingtonpost' in url:
            pub_date = soup.find('span', {'data-testid':'display-date'}).text.replace('.','')
            pub_date = datetime.strptime(pub_date, '%B %d, %Y at %I:%M %p EDT').strftime('%Y-%m-%d %H:%M')
        elif 'cnn' in url:
            pub_date = soup.find('div', class_='timestamp').text.strip()[-30:]
            pub_date = datetime.strptime(pub_date, '%H:%M %p EDT, %a %B %d, %Y').strftime('%Y-%m-%d %H:%M')
        elif 'pcworld' in url:
            pub_date = soup.find('span', class_='posted-on').text
            pub_date = datetime.strptime(pub_date, '%b %d, %Y %H:%M %p PDT').strftime('%Y-%m-%d %H:%M')
        elif 'economist' in url:
            pub_date = re.sub(r'(\d)(th|nd|rd|st)', r'\1', soup.find('time').text.strip())
            pub_date = datetime.strptime(pub_date, '%b %d %Y').strftime('%Y-%m-%d %H:%M')
        elif 'foxbusiness' in url:
            pub_date = soup.find('time').text.strip()
            pub_date = datetime.strptime(pub_date, '%B %d, %Y %I:%M%p EDT').strftime('%Y-%m-%d %H:%M')
        elif 'cnbc' in url:
            pub_date = soup.find('time').text[10:]
            pub_date = datetime.strptime(pub_date, "%a, %b %d %Y%I:%M %p EDT").strftime('%Y-%m-%d %H:%M')

        # Extract the content of the news article
        if 'yahoo' in url:
            article_body = soup.find('div', {'class': 'caas-body'})
        elif 'nypost' in url:
            article_body = soup.find('div', class_='single__content entry-content m-bottom')
        elif 'businessinsider' in url:
            article_body = soup.find('div', class_='content-lock-content')
        elif 'washingtonpost' in url:
            article_body = soup.find('div', class_='meteredContent grid-center')
        elif 'cnn' in url:
            article_body = soup.find('div', class_='article__content')
        elif 'pcworld' in url:
            article_body = soup.find('div', id='link_wrapped_content')
        elif 'economist' in url:
            article_body = soup.find('div', class_='css-1x0aq03 e13topc92')
        elif 'foxbusiness' in url:
            article_body = soup.find('div', class_='article-body')
        elif 'cnbc' in url:
            article_body = soup.find('div', class_='ArticleBody-articleBody')

        paragraphs = article_body.find_all('p')
        content = " ".join([para.text for para in paragraphs])

        # Print the scraped data
        return {"title": title.replace('\n', ''),
                "author": extract(url).domain.title(),
                "publishedAt": pub_date, 
                "content": content}
    else:
        logger.info("Failed to retrieve the page")
        return {}

def get_everything(
        webpages:List, # list of webpages to scrape 
        company:str # name of the company,
)->List:
    logger = logging.getLogger(__name__)
    scraped_links = []

    for website in webpages:
        url = website['url']
        max_depth = website['max_depth']

        links = get_links_recursive(url=url, company=company, max_depth=max_depth)
        scraped_links.extend(links)
    scraped_links = list(set(scraped_links))
    
    articles = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_url = {executor.submit(scrape_sites, link): link for link in scraped_links}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                articles.append(future.result())
            except Exception as e:
                logger.error(f"Error processing article from {url} due to {e}")

    return articles