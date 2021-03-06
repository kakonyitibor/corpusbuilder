#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

from html import unescape as html_unescape
from datetime import datetime

from newspaper import Article

strptime = datetime.strptime

"""Here comes the stuff to extract data from a specific downloaded webpage"""


def extract_article_urls_from_page(archive_page_raw_html, settings):
    """
        extracts and returns as a list the URLs belonging to articles from an HTML code
    """
    urls = set()
    article_url_format_re = settings['ARTICLE_URL_FORMAT_RE']
    for code_line in article_url_format_re.findall(archive_page_raw_html):
        code_line = settings['BEFORE_ARTICLE_URL_RE'].sub(settings['before_article_url_repl'], code_line)
        code_line = settings['AFTER_ARTICLE_URL_RE'].sub(settings['after_article_url_repl'], code_line)
        code_line = html_unescape(code_line)
        urls.add(code_line)
    return urls


def extract_next_page_url(archive_page_raw_html, settings):
    """
        extracts and returns next page URL from an HTML code if there is one...
    """
    next_page_url_format_re = settings['NEXT_PAGE_URL_FORMAT_RE']
    code_line = next_page_url_format_re.search(archive_page_raw_html)
    if code_line is not None:
        code_line = code_line.group(0)
        code_line = settings['BEFORE_NEXT_PAGE_URL_RE'].sub(settings['before_next_page_url_repl'], code_line)
        code_line = settings['AFTER_NEXT_PAGE_URL_RE'].sub(settings['after_next_page_url_repl'], code_line)
        code_line = html_unescape(code_line)
    return code_line


def extract_article_date(article_raw_html, settings):
    """
        extracts and returns next page URL from an HTML code if there is one...
    """
    article_date_format_re = settings['ARTICLE_DATE_FORMAT_RE']
    code_line = article_date_format_re.search(article_raw_html)
    if code_line is not None:
        code_line = code_line.group(0)
        code_line = settings['BEFORE_ARTICLE_DATE_RE'].sub(settings['before_article_date_repl'], code_line)
        code_line = settings['AFTER_ARTICLE_DATE_RE'].sub(settings['after_article_date_repl'], code_line)
        try:
            code_line = strptime(code_line, settings['article_date_formatting']).date()
        except (UnicodeError, ValueError, KeyError):  # In case of any error log outside of this function...
            code_line = None
    return code_line


def identify_site_scheme(logger_, settings, url):
    for site_re, tag_key_readable in settings['TAGS_KEYS'].items():
        if site_re.search(url):
            return tag_key_readable

    logger_.log('ERROR', '\t'.join((url, str([regexp.pattern for regexp in settings['TAGS_KEYS'].keys()]),
                                    'NO MATCHING TAG_KEYS PATTERN! IGNORING ARTICLE!')))
    return None


class CorpusConverter:
    """
        Extract text and metadata from the downloaded raw html by using site specific REs from the config
    """
    def __init__(self, settings, file_out, logger_):
        self._settings = settings
        self._article_begin_mark = settings['COMMON_SITE_TAGS']['article_begin_mark']
        self._article_end_mark = settings['COMMON_SITE_TAGS']['article_end_mark']
        self._file_out = file_out
        self._logger_ = logger_

    def article_to_corpus(self, url, doc_in, site_tag_scheme):
        """
        converts the raw HTML code of an article to corpus format and saves it to the output file
        :param doc_in: the document to convert
        :param url: the URL. Not used here, just for logging
        :param site_tag_scheme: the identified scheme of the article to load the appropriate tags

        :return:
        """
        if site_tag_scheme is not None:
            site_tags = self._settings['SITE_TAGS'][site_tag_scheme]

            # Build the article in corpus format by sequentially adding elements described by open-close REs
            doc_out = ''.join(self._check_regex(json_tags_key_vals['open'],
                                                json_tags_key_vals['close'],
                                                json_tags_key_vals['open-inside-close'], t, doc_in)
                              for t, json_tags_key_vals in site_tags.items())

            # Apply general cleaning rules to remove unneeded parts
            for rule_name, rule in self._settings['GENERAL_CLEANING_RULES'].items():
                doc_out = rule(doc_out)

            # Write the result into the output file
            print(self._article_begin_mark, doc_out, self._article_end_mark, sep='', end='', file=self._file_out)
            self._logger_.log('INFO', '\t'.join((url, site_tag_scheme, 'Article extraction OK')))
        return

    @staticmethod
    def _check_regex(old_tag_open, old_tag_close, old_tag, new_tag, doc_in):
        """
            keeps parts of input file that match patterns specified in JSON and
            then changes their HTML/CSS tags to our corpus markup tags
        """
        match = old_tag.search(doc_in)
        matched_part = ''
        if match is not None:
            matched_part = match.group(0)
            matched_part = old_tag_open.sub('<'+new_tag+'>\n', matched_part)
            matched_part = old_tag_close.sub(' </'+new_tag+'>\n', matched_part)
        return matched_part


class CorpusConverterNewspaper:  # Mimic CorpusConverter
    def __init__(self, settings, file_out, logger_):
        self._file_out = file_out
        self._logger_ = logger_
        self._settings = settings

    def article_to_corpus(self, url, page_str, _):
        article = Article(url, memoize_articles=False, language='hu')
        article.download(input_html=page_str)
        article.parse()
        article.nlp()

        html_date = '<html-date> {0} </html-date>'.format(article.publish_date.date())
        html_description_lead = '<html-lead>\n </html-lead>'
        html_charset = '<html-charset> utf-8 </html-charset>'
        html_url = '<html-url> {0} </html-url>'.format(url)
        html_keywords = '<html-keywords> {0} </html-keywords>'.format(', '.join(article.keywords))
        html_title = '<html-title> {0} </html-title>'.format(article.title)
        html_body = '<html-body>\n{0} </html-body>\n'.format(article.text)

        print(self._settings['article_begin_flag'], '\n'.join((html_date,
                                                               html_description_lead,
                                                               html_charset,
                                                               html_url,
                                                               html_keywords,
                                                               html_title,
                                                               html_body)),
              self._settings['article_end_flag'], sep='', end='', file=self._file_out)
        self._logger_.log('INFO', '\t'.join((url, 'Article extraction OK')))
