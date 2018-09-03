#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-
from articleDateExtractor import extractArticlePublishedDate

from corpus_converter import CorpusConverter
from enhanced_downloader import WarcDownloader, WarcReader
from extractor import extract_article_urls_from_page
from logger import Logger
from news_archive_crawler import NewsArchiveCrawler


class NewsArticleCrawler:
    """
        1) Get the list of articles (eg. NewsArchiveCrawler)
        2) Download article pages
        3) Extract the text of articles from raw HTML
        4) save them in corpus format
    """
    def __init__(self, atricles_filename, archive_filename, download, settings):
        self._settings = settings
        self._logger_ = Logger(self._settings['log_file_articles'])

        self._file_out = open(self._settings['output_file'], 'a+', encoding=self._settings['encoding'])
        self._converter = CorpusConverter(self._settings,  self._file_out, self._logger_)

        # Create new archive while downloading, or simulate download and read the archive
        if download:
            self._downloader = WarcDownloader(atricles_filename, self._logger_)
        else:
            self._downloader = WarcReader(atricles_filename, self._logger_)

        self._archive_downloader = NewsArchiveCrawler(self._settings, download, archive_filename)

        self._new_urls = set()

    def __del__(self):
        self._file_out.close()

    def process_urls(self, it):
        for url in it:
            # "Download" article
            article_raw_html = self._downloader.download_url(url)
            # Filter: time filtering when archive page URLs are not generated by date
            is_ok = self._filter_urls_by_date(url, article_raw_html)

            # Extract text to corpus
            if is_ok:
                self._converter.article_to_corpus(url, article_raw_html)

            # Extract links to other articles...
            extracted_article_urls = extract_article_urls_from_page(article_raw_html, self._settings)

            # Check for already extracted urls!
            for extracted_url in extracted_article_urls:
                if extracted_url not in self._archive_downloader.good_urls and \
                        extracted_url not in self._archive_downloader.problematic_urls:
                    self._new_urls.add(extracted_url)

    def _filter_urls_by_date(self, url, raw_html):
        ret = True
        if self._settings['ARTICLE_LIST_URLS_BY_ID'] and not self._settings['ARTICLE_LIST_URLS_BY_DATE'] and \
                self._settings['DATE_INTERVAL_USED']:
            article_date = extractArticlePublishedDate(url, html=raw_html)
            date_before_interval = self._settings['DATE_FROM'] > article_date.date()
            date_after_interval = article_date.date() > self._settings['DATE_UNTIL']

            if date_before_interval or date_after_interval:
                ret = False  # Not OK
                self._logger_.log(url, 'Date ({0}) not in the specified interval: {1}-{2} didn\'t use it in the corpus'.
                                  format(article_date, self._settings['DATE_FROM'], self._settings['DATE_UNTIL']))
        return ret

    def download_and_extract_all_articles(self):
        self.process_urls(self._archive_downloader.url_iterator())
        self.download_gathered_new_urls()

    def download_gathered_new_urls(self):
        # Recheck new urls
        self._new_urls = {url for url in self._new_urls
                          if url not in self._archive_downloader.good_urls and
                          url not in self._archive_downloader.problematic_urls}
        while len(self._new_urls) > 0:  # TODO: Maybe log it! Article URL-s not in the arhive... Shouldn't be any!
            new_urls = self._new_urls
            self._new_urls = set()
            self.process_urls(new_urls)