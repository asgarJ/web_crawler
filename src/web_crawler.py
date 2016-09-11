#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ConfigParser
import ast
import logging
import time
import codecs
from collections import deque

import urllib2
from urlparse import urljoin
from bs4 import BeautifulSoup

script_start = time.time()
print 'Running script...'
print 'Reading configurations...'

conf = ConfigParser.ConfigParser()
conf.readfp(codecs.open("config.conf", 'r', 'utf8'))

data_file = conf.get("web_crawler", "output_file")
urls = ast.literal_eval(conf.get("web_crawler","urls"))
parser = conf.get("web_crawler", "parser")
pages_max_limit = conf.getint("web_crawler", "pages_limit")
lang_verbose = conf.getboolean("web_crawler", "lang_verbose")
stop_urls = ast.literal_eval(conf.get("web_crawler", "stop_urls"))
stop_texts = ast.literal_eval(conf.get("web_crawler", "stop_texts"))
timeout = conf.getint("web_crawler", "timeout")

def getLogger(config):
  logger = logging.getLogger(__name__)
  handler = logging.StreamHandler()
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.INFO)
  return logger
  
logger = getLogger(conf)

print 'data_file %s\ninitial_url %s\nparser\t%s\npages_limit\t%s' % (data_file, ' '.join(urls), parser, pages_max_limit)

output_file = codecs.open(data_file, 'a', 'utf-8')
stats_file = codecs.open("stats.txt", 'a', 'utf-8')

def concat_urls(current, href):
  if href.startswith("/"):
    if current[-1] == "/":
      print 'CONCAT: %s %s' % (current, href)
      return current[:-1] + href
    else:
      return current + href
  else:
    return href

filter_text = lambda s: not any(stop_text in s for stop_text in stop_texts)

def BFS(url, stop_urls, timeout=timeout, output_file=output_file, 
                                         stats_file=stats_file, 
                                         max_limit=pages_max_limit, 
                                         lang_verbose=True):
  '''
    Breadth-first Search for traversing webpages
  '''
  print 'BFS started with "%s"' % url

  counter = 0
  visited = set()
  queue = deque()
  queue.append(url)
  
  while counter < max_limit and len(queue) > 0:
    link = queue.popleft()
    print '\n>> %s' % link
    visited.add(link)
    if not link.startswith("http"):
      print "INVALID LINK"
      continue
      
    if any(stop_url in link for stop_url in stop_urls):
      print 'Found in the black list of urls.'
      continue

    start_time = time.time()

    # visit page
    try:
      response = urllib2.urlopen(link, timeout=timeout)
      webpage = response.read()
      response.close()
    except urllib2.HTTPError as e:
      print 'Error: "urllib2.HTTPError"'
      print str(e)
      continue
    except urllib2.URLError as e:
      print 'Error: "urllib2.URLError"'
      print str(e)
      continue
    except Exception as e:
      print "Exception on %s" % link
      print str(e)
      continue

    soup = BeautifulSoup(webpage, parser, from_encoding='utf-8')

    # inspect language attribute
    if 'lang' in soup.html.attrs:
      lang = soup.html["lang"]
      print 'lang[%s] for %s' % (lang, link)
      if not any(l in lang for l in ["az", "en"]):
        print 'Unknown language[%s]. Skipping...' % lang
        continue
      if lang_verbose:
        continue

    # remove scripts
    while soup.script is not None:
      soup.script.extract()

    # collect valid links
    anchors = soup.find_all('a')
    anchors = filter(lambda a: (a.has_attr("href")) and not (a["href"].startswith("#")), anchors)

    links = set([urljoin(link, anchor["href"]) for anchor in anchors])

    if len(queue) < max_limit:
      for child_link in links:
        if not child_link in visited:
          queue.append(child_link)

    # write text to data file
    pars = soup.find_all("p")
    filter_pars = filter(lambda tag: not any(["footer" in parent.name for parent in tag.parents]), pars)
    all_par_texts = map(lambda p: p.get_text(strip=True), filter_pars)
    all_par_texts = filter(filter_text, all_par_texts)
    
    if len(all_par_texts) > 0 and (not any(u"Mövcud olmayan səhifəyə keçid etdiniz." in t for t in all_par_texts)):
      source_text = reduce(lambda s1, s2: s1+'\n'+s2, all_par_texts)
      source_text.replace(u'\xa0', ' ')
      output_file.write(source_text)
      output_file.write("\n\n")
    else :
      print 'NO PARAGRAPH in page.'
      continue

    end_time = time.time()
    counter += 1

    log_message = '''
        ID         :  %i
        Link       :  %s
        Time spent :  %.3f secs.
        queue len  :  %i
        ----------------------------------
              ''' % (counter, link, (end_time - start_time), len(queue))
    print log_message

    stats_file.write("Link       :  %s\n" % link)
    stats_file.write("Time spent :  %.3f secs.\n" % (end_time - start_time))
    stats_file.write("----------------------------------\n")

for url in urls:
  BFS(url, stop_urls, max_limit=pages_max_limit, lang_verbose=lang_verbose)

script_finish = time.time()
overall_duration = script_finish - script_start

print 'Script ran for %i mins, %i secs.' % (overall_duration/60, overall_duration%60)
print 'overall duration:', overall_duration

stats_file.close()
output_file.close()   

def process_url(url):
  '''
    Process all paragraphs
  '''
  print 'Processing url: %s', url
  try:
    response = urllib2.urlopen(url, timeout=5)
    webpage = response.read()
    response.close()
    soup = BeautifulSoup(webpage, 'html.parser', from_encoding='utf-8')

    print '\n'
    print reduce(lambda s1, s2: s1+'\n*\n'+s2, map(lambda p: p.get_text(strip=True), soup.find_all("p")))

  except Exception as e:
    print e.message
    print 'Error'
