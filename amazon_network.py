import argparse
import json
import time

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

import networkx as nx


def main(amazon_url, graph):
    books = scrape_books(amazon_url=amazon_url)
    relationships = scrape_relationships(books)

    export_graph(books, relationships, graph)


def scrape_books(amazon_url):
    """
    Scrape book data from an "Top 100" list
    """
    browser = webdriver.Chrome()
    # go to the "Top 100" list home page
    browser.get(amazon_url)

    books = []
    for page_number in range(1, 6, 1):
        # go to the page
        try:
            link = browser.find_element_by_id('zg_page' + str(page_number))
        except NoSuchElementException:
            break
        link.click()
        time.sleep(2)

        print('Scraping books from page number: "{}"'.format(page_number))

        soup = BeautifulSoup(browser.page_source, 'lxml')
        book_divs = soup.find_all('div', 'zg_itemImmersion')

        for book in book_divs:
            books.append(_parse_book(book))

    browser.close()
    print('Scraped books: {}'.format(len(books)))
    return books


def scrape_relationships(books):
    """
    Scrape the relationships between books based on the amazon
    "Customers who bought this item also bought" feature
    """
    browser = webdriver.Chrome()
    relationships = []

    for book in books:
        print('Scraping relationships for book: "{}"'.format(book['title']))

        browser.get('https://amazon.com' + book['url'])

        soup = BeautifulSoup(browser.page_source, 'lxml')
        relationship_header = soup.find('h2', text='Customers who bought this item also bought')

        if relationship_header:
            relationship_div = relationship_header.parent.parent.parent
        else:
            print('No relationships found for: "{}"'.format(book['title']))
            continue

        meta_data = json.loads(relationship_div['data-a-carousel-options'])
        related_book_ids = meta_data['ajax']['id_list']

        relationships.extend([(related_book_id, book['id']) for related_book_id in related_book_ids])

        print('Relationships found: {}'.format(len(related_book_ids)))

    browser.close()
    return relationships


def export_graph(books, relationships, graph_file_path, min_degrees=0):

    if not graph_file_path.endswith('.graphml'):
        graph_file_path += '.graphml'

    graph = nx.Graph()
    graph.add_edges_from(relationships)

    # append book data to correct node
    # missing data handled by try / excepts
    for book_id in graph.nodes_iter():
        try:
            graph.node[book_id]['title'] = list(filter(lambda book: book['id'] == book_id, books))[0]['title']
        except IndexError:
            pass

        try:
            graph.node[book_id]['rank'] = list(filter(lambda book: book['id'] == book_id, books))[0]['rank']
        except IndexError:
            pass

        try:
            graph.node[book_id]['url'] = list(filter(lambda book: book['id'] == book_id, books))[0]['url']
        except IndexError:
            pass

        try:
            graph.node[book_id]['price'] = list(filter(lambda book: book['id'] == book_id, books))[0]['price']
        except IndexError:
            pass

    # trim nodes with few connections
    trimmed_graph = graph.copy()
    trimmed_graph.remove_nodes_from((n for n, d in graph.degree_iter() if d <= min_degrees))

    nx.write_graphml(trimmed_graph, graph_file_path)


def _parse_book(book):
    # some book listings have truncated text content, if that's the case get the title attribute
    #       rather than the div content
    title_div = book.find('div', 'p13n-sc-truncated')
    if title_div.has_attr('title'):
        title = title_div['title']
    else:
        title = title_div.string.strip()

    try:
        price = book.find('span', 'p13n-sc-price').string.strip()
    except:
        price = '£0.00'

    meta_data = book.find('div', 'a-section a-spacing-none p13n-asin')['data-p13n-asin-metadata']

    return {'rank': book.find('span', 'zg_rankNumber').string.strip(),
            'title': title,
            'id': json.loads(meta_data)['asin'],
            'price': price,
            'url': book.find('a', 'a-link-normal', href=True)['href']}


if __name__ == '__main__':
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--amazon_url', type=str,
                                 default='https://www.amazon.co.uk/Best-Sellers-Books-Government-Politics/zgbs/books/275870',
                                 help='Enter an "Amazon Best Sellers" url')

    argument_parser.add_argument('--graph', type=str,
                                 default='graph.graphml',
                                 help='Enter output graph file name')

    args = argument_parser.parse_args()

    main(args.amazon_url, args.graph)
