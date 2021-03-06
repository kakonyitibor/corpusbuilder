#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

from datetime import timedelta

from corpusbuilder.corpus_converter import CorpusConverter, extract_article_urls_from_page,\
    extract_next_page_url, extract_article_date, identify_site_scheme
from corpusbuilder.enhanced_downloader import WarcCachingDownloader
from corpusbuilder.utils import Logger

corpus_converter_class = {'rule-based': CorpusConverter}


class NewsArchiveCrawler:
    """
        Using the provided regexes
        1) Generates URLs of lists of articles
        2) Extracts URLs of articles from these lists
    """
    def __init__(self, settings, existing_archive_filename, new_archive_filename, known_article_urls=None,
                 program_name='corpusbuilder 1.0', user_agent=None, overwrite_warc=True, err_threshold=10,
                 known_bad_urls=None, new_problematic_archive_urls=None, new_good_archive_urls=None,
                 max_no_of_calls_in_period=2, limit_period=1, proxy_url=None, allow_cookies=False, just_cache=False):
        self._settings = settings
        self._logger = Logger(self._settings['log_file_archive'])

        # For external use
        self.good_urls = set()
        self.problematic_urls = set()

        if new_problematic_archive_urls is not None:
            new_problematic_archive_urls = open(new_problematic_archive_urls, 'w', encoding='UTF-8')
        if new_good_archive_urls is not None:
            new_good_archive_urls = open(new_good_archive_urls, 'w', encoding='UTF-8')
        self._new_urls_file_handles = (new_problematic_archive_urls, new_good_archive_urls)

        # Setup the list of cached article URLs to stop archive crawling in time
        if known_article_urls is not None and isinstance(known_article_urls, str):
            with open(known_article_urls, encoding='UTF-8') as fh:
                self.known_article_urls = {line.strip() for line in fh}
        elif known_article_urls is not None and isinstance(known_article_urls, set):
            self.known_article_urls = known_article_urls
        else:
            self.known_article_urls = set()

        # Create new archive while downloading, or simulate download and read the archive
        self._downloader = WarcCachingDownloader(existing_archive_filename, new_archive_filename, self._logger,
                                                 program_name, user_agent, overwrite_warc, err_threshold,
                                                 known_bad_urls, max_no_of_calls_in_period, limit_period, proxy_url,
                                                 allow_cookies, just_cache)
        self.known_good_urls = self._downloader.url_index  # All URLs in the archive are known good!

    def __del__(self):  # Write newly found URLs to files when output files supplied...
        if hasattr(self, '_new_urls_filehandles') and hasattr(self, 'good_urls') and \
                hasattr(self, 'problematic_urls'):
            new_problematic_urls, new_good_urls = self._new_urls_file_handles
            if new_good_urls is not None and len(self.good_urls) > 0:
                new_good_urls.writelines('{0}\n'.format(good_url) for good_url in self.good_urls)

            if new_good_urls is not None:
                new_good_urls.close()

            if new_problematic_urls is not None and len(self.problematic_urls) > 0:
                new_problematic_urls.writelines('{0}\n'.format(problematic_url)
                                                for problematic_url in self.problematic_urls)

            if new_problematic_urls is not None:
                new_problematic_urls.close()

    def url_iterator(self):
        """
            The URL generation logic. We have a base URL to the archive and it is complete with portal-specific ending.
            The archive can be stored in groups (mostly the creation date) or ordered in a flat list paginated.
            This two main method can also be mixed.
        :return: Every page of the archive contain multiple URL to the actual articles,
             which are extrated and then returned as an iterator.
        """
        # if URLs of current website's archive pages are generated based on an ID,
        # which is a positive integer growing one by one
        archive_page_urls = []

        if self._settings['archive_page_urls_by_date']:
            date_from = self._settings['date_from']
            date_until = self._settings['date_until']
            url_format = self._settings['archive_url_format']

            # Unique the generated archive page URLs using every day from date_from to the end of date_until
            archive_page_urls = list(set(self._gen_archive_page_url_from_date(date_from + timedelta(days=curr_day),
                                                                              url_format)
                                         for curr_day in range((date_until - date_from).days + 1)))
            # Sort the generated archive page URLs
            archive_page_urls.sort(reverse=self._settings['go_reverse_in_archive'])

        # Stored in groups represented by ID only, the IDs are generated on-demand while new articles are found
        if self._settings['archive_page_urls_by_id'] and len(archive_page_urls) == 0:  # not URL_BY_DATE and URLS_BY_ID
                archive_page_urls.append(self._settings['archive_url_format'])  # Only the base URL is added

        if len(archive_page_urls) == 0:  # There should not be empty list for the archive, because it means an error.
            raise ValueError('There is no existing case where settings[\'archive_page_urls_by_date\'] and'
                             ' settings[\'archive_page_urls_by_id\'] are both False')

        for archive_page_url in archive_page_urls:  # Run through the list of archive URLs
            yield from self._gen_article_urls_from_archive_page_url_including_subpages(archive_page_url)
        # Stored in groups represented by date

    @staticmethod
    def _gen_archive_page_url_from_date(curr_date, url_format):
        """
            Generates and returns the URLs of a page the contains URLs of articles published that day.
            This function allows URLs to be grouped by years or month as there is no guarantee that all fields exists.
        """
        art_list_url = url_format.replace('#year', '{0:04d}'.format(curr_date.year)).\
            replace('#month', '{0:02d}'.format(curr_date.month)).\
            replace('#day', '{0:02d}'.format(curr_date.day))
        return art_list_url

    def _gen_article_urls_from_archive_page_url_including_subpages(self, archive_page_url_base):
        """
            Generates article URLs from a supplied URL inlcuding the sub-pages that contains article URLs
        """
        page_num = self._settings['min_pagenum']
        max_pagenum = self._settings['max_pagenum']
        next_url_use_regex = self._settings['next_url_by_regex']
        next_url_use_pagenum = self._settings['next_url_by_pagenum']
        new_article_url_threshold = self._settings['new_article_url_threshold']
        ignore_archive_cache = self._settings['ignore_archive_cache']

        archive_page_next_page_url = archive_page_url_base.replace('#pagenum', '')
        while archive_page_next_page_url is not None:
            article_urls = []
            archive_page_raw_html = self._downloader.download_url(archive_page_next_page_url,
                                                                  ignore_cache=ignore_archive_cache)
            if archive_page_raw_html is not None:  # Download succeeded
                if archive_page_next_page_url not in self.known_good_urls:
                    self.good_urls.add(archive_page_next_page_url)
                article_urls = extract_article_urls_from_page(archive_page_raw_html, self._settings)
                archive_page_next_page_url = self._extract_next_page_url(archive_page_raw_html, archive_page_url_base,
                                                                         article_urls, page_num, max_pagenum,
                                                                         next_url_use_regex, next_url_use_pagenum,
                                                                         new_article_url_threshold)
            else:  # Download failed
                if archive_page_next_page_url not in self._downloader.bad_urls:
                    self.problematic_urls.add(archive_page_next_page_url)  # New possibly bad URL
                archive_page_next_page_url = None
            page_num += 1
            yield from article_urls

    def _extract_next_page_url(self, archive_page_raw_html, archive_page_url_base, article_urls, page_num,
                               max_pagenum, use_regex, use_pagenum, new_article_url_threshold):
        """
            The next URL can be determined by various conditions (no matter how the pages are grouped):
                1) If there is a "next page" link, find it with REs and use that
                2) If there is "infinite scrolling" use pagenum from base to specified maximum or to infinity
                3) If there is no pagination return None
        """
        if use_regex:  # Method #1
            # We can not tell if the RE is bad, or we are on the last page...
            archive_page_next_page_url = extract_next_page_url(archive_page_raw_html, self._settings)
        elif use_pagenum and len(article_urls) > 0 and \
                (len(self.known_article_urls) == 0 or
                 # We allow some intersecting element as the archive may have been moved
                 len(article_urls.minus(self.known_article_urls)) > new_article_url_threshold) \
                and (max_pagenum is None or page_num < max_pagenum):  # Method #2
            archive_page_next_page_url = archive_page_url_base.replace('#pagenum', str(page_num))  # must generate URL
        else:  # Method #3
            archive_page_next_page_url = None

        return archive_page_next_page_url


class NewsArchiveDummyCrawler:
    def __init__(self, url_index_keys, *_, **__):
        self._url_index_keys = url_index_keys

    def url_iterator(self):
        return self._url_index_keys


class NewsArticleCrawler:
    """
        1) Get the list of articles (eg. NewsArchiveCrawler)
        2) Download article pages
        3) Extract the text of articles from raw HTML
        4) save them in corpus format
    """
    def __init__(self, settings, articles_existing_warc_filename, articles_new_warc_filename,
                 archive_existing_warc_filename, archive_new_warc_filename, known_article_urls=None,
                 program_name='corpusbuilder 1.0', user_agent=None, overwrite_warc=True, err_threshold=10,
                 corpus_converter='rule-based', known_bad_urls=None, new_problematic_urls=None, new_good_urls=None,
                 new_problematic_archive_urls=None, new_good_archive_urls=None, max_no_of_calls_in_period=2,
                 limit_period=1, proxy_url=None, allow_cookies=False, archive_just_cache=False,
                 articles_just_cache=False):
        self._settings = settings
        self._logger = Logger(self._settings['log_file_articles'])

        self.good_article_urls = set()
        self.problematic_article_urls = set()
        self._new_urls = set()

        self._create_corpus = self._settings['create_corpus']
        self._file_out = None
        if self._create_corpus:
            self._file_out = open(self._settings['output_file'], 'a+', encoding='UTF-8')  # Output file for corpus

        self._filter_by_date = self._settings['filter_articles_by_date']

        # Create new corpus converter class from the available methods...
        converter = corpus_converter_class[corpus_converter]
        self._converter = converter(self._settings, self._file_out, self._logger)

        # Create new archive while downloading, or simulate download and read the archive
        self._downloader = WarcCachingDownloader(articles_existing_warc_filename, articles_new_warc_filename,
                                                 self._logger, program_name, user_agent, overwrite_warc,
                                                 err_threshold, known_bad_urls, max_no_of_calls_in_period,
                                                 limit_period, proxy_url, allow_cookies, articles_just_cache)

        self.known_good_article_urls = self._downloader.url_index  # All URLs in the archive are known good!
        if known_article_urls is None:  # If None is supplied put the ones from the article archive
            known_article_urls = self.known_good_article_urls

        if new_problematic_urls is not None:
            new_problematic_urls = open(new_problematic_urls, 'a+', encoding='UTF-8')
        if new_good_urls is not None:
            new_good_urls = open(new_good_urls, 'a+', encoding='UTF-8')
        self._new_urls_filehandles = (new_problematic_urls, new_good_urls)

        if archive_just_cache and articles_just_cache:
            self._archive_downloader = NewsArchiveDummyCrawler(self._downloader.url_index.keys())
        else:
            # known_bad_urls are common between the NewsArchiveCrawler and the NewsArticleCrawler
            self._archive_downloader = NewsArchiveCrawler(self._settings, archive_existing_warc_filename,
                                                          archive_new_warc_filename, known_article_urls, program_name,
                                                          user_agent, overwrite_warc, err_threshold, known_bad_urls,
                                                          new_problematic_archive_urls, new_good_archive_urls,
                                                          max_no_of_calls_in_period, limit_period, proxy_url,
                                                          allow_cookies, archive_just_cache)

    def __del__(self):
        if hasattr(self, '_file_out') and self._file_out is not None:
            self._file_out.close()
        if hasattr(self, '_archive_downloader'):  # Make sure that the previous files are closed...
            del self._archive_downloader

        # Save the new urls...
        if hasattr(self, '_new_urls_filehandles') and hasattr(self, '_new_urls') and \
                hasattr(self, 'problematic_article_urls'):
            problematic_article_urls, new_good_urls = self._new_urls_filehandles
            if new_good_urls is not None and len(self._new_urls) > 0:
                new_good_urls.writelines('{0}\n'.format(good_url) for good_url in self._new_urls)

            if new_good_urls is not None:
                new_good_urls.close()

            if problematic_article_urls is not None and len(self.problematic_article_urls) > 0:
                problematic_article_urls.writelines('{0}\n'.format(problematic_url)
                                                    for problematic_url in self.problematic_article_urls)

            if problematic_article_urls is not None:
                problematic_article_urls.close()

    def process_urls(self, it):
        create_corpus = self._create_corpus
        filter_by_date = self._filter_by_date
        for url in it:
            # Check if it is a duplicate (we do not count those in the archive)
            if url not in self.known_good_article_urls and url not in self._archive_downloader.known_article_urls \
                    and not self._is_new_url(url):
                self._logger.log('WARNING', '\t'.join((url, 'Not processing article, because it is already processed'
                                                            ' in this session!')))
                continue

            # "Download" article
            article_raw_html = self._downloader.download_url(url)
            if article_raw_html is None:
                self._logger.log('ERROR', '\t'.join((url, 'Article were not processed because download failed!')))
                if url not in self._downloader.bad_urls:
                    self.problematic_article_urls.add(url)  # New problematic URL for manual checking
                continue

            # Note downloaded url, but only when it is truly new URL (ie. not in the old archive)
            if url not in self.known_good_article_urls:
                self.good_article_urls.add(url)

            # Filter: time filtering when archive page URLs are not generated by date if needed
            if filter_by_date:
                # a) Retrieve the date
                article_date = extract_article_date(article_raw_html, self._settings)
                if article_date is None:
                    self._logger.log('ERROR', '\t'.join((url, 'DATE COULD NOT BE PARSED!')))
                    continue

                # b) Check date interval
                if not self._settings['date_from'] <= article_date <= self._settings['date_until']:
                    self._logger.log('WARNING', '\t'.join((url, 'Date ({0}) not in the specified interval: {1}-{2} '
                                                                'didn\'t use it in the corpus'.
                                     format(article_date, self._settings['date_from'], self._settings['date_until']))))
                    continue

            # Identify the site scheme of the article to be able to look up the appropriate extracting method
            sheme = identify_site_scheme(self._logger, self._settings, url)

            # Extract text to corpus
            if create_corpus:
                self._converter.article_to_corpus(url, article_raw_html, sheme)

            # Extract links to other articles...
            extracted_article_urls = extract_article_urls_from_page(article_raw_html, self._settings)

            # Check for already extracted urls (also in the archive)!
            for extracted_url in extracted_article_urls:
                if self._is_new_url(extracted_url):
                    self._new_urls.add(extracted_url)

    def download_and_extract_all_articles(self):
        self.process_urls(self._archive_downloader.url_iterator())
        self.download_gathered_new_urls()

    def download_gathered_new_urls(self):
        # Recheck new urls (also in the archive!)
        self._new_urls = {url for url in self._new_urls if self._is_new_url(url)}
        while len(self._new_urls) > 0:  # Article URL-s not in the archive... Shouldn't be any!
            for url in self._new_urls:
                self._logger.log('ERROR', '\t'.join((url, 'TRUE NEW URL')))
            new_urls, self._new_urls = self._new_urls, set()
            self.process_urls(new_urls)  # Recursively get all new urls...

    def _is_new_url(self, url):
        return \
            (url not in self.good_article_urls and         # Downloaded succesfully in this session
             url not in self.known_good_article_urls and   # Present in old archive
             url not in self.problematic_article_urls and  # Download failed in this session (requries manual check)
             url not in self._downloader.bad_urls and      # Explicit bad URLs (supplied as parameter)
             url not in self._archive_downloader.good_urls and  # Archive URLs succesfully downloaded in this session
             url not in self._archive_downloader.problematic_urls and  # Archive URLs failed to download in this session
             url not in self._archive_downloader.known_article_urls)  # Article URLs explicitly known (as parameter)
