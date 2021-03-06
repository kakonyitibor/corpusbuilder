Corpus generator program to download content of Hungarian online newspapers and convert it to plaintext or xml.
Thanks to Balázs Indig for the contribution.

Documentation in Hungarian:
https://docs.google.com/document/d/1-gGSFltEU1gRcdhj4zznWW9BDm4yymvehPkqILN9aDY/edit?usp=sharing

The program is being developed continously.
More detailed English documentation is coming soon.

# Requirements

Before installing requirements from `requirements.txt` the following packages are needed to be installed:

- For Newspaper3k: python3-dev libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev libpng12-dev

# Config schema

The config is divided into three parts arccording to the task to be done. The used REs can be freely configured by adding inline flags e.g. for multiline matching

## Crawl config

Specifies configuration for the current crawling process

Basic information:

- `site_name`: The site name as in `site_shemas`
- `site_schemas`: name of the required `site_schemas.yaml` stores the information on specific sites
- `tags`: name of the required `tags.yaml` when creating corpora from articles

Corpus information:

- `create_corpus`: boolean, true if we want to create a corpus from the downloaded articles
- `output_file`: the name of the output file where the corpus will be put

Logging information
	
- `log_file_archive`: the logfile for the archive crawler
- `log_file_articles`: the logfile for the article crawler

Crawling timespan (optional)

- `date_from`: the inclusive minimal date of the required articles in ISO 8601 form YYYY-MM-DD
- `date_until`: the inclusive maximal date of the required articles in ISO 8601 form YYYY-MM-DD

## Tags (fileds)

In tags.yaml every required filed (title, date, author, text, keywords, etc.) is described with three REs:

- `open`: RE describes the left context of the required filed in the HTML
- `inside`: RE describes the content of the required filed in the HTML
- `close`:  RE describes the right context of the required filed in the HTML

From this three the `open-inside-close` RE is build by concatenation and used to find the field.
The `open` and `close` part is then substituted by the field name in xml form. e.g.

    <field> content </field>

The whole article is enclosed with the approprpiate entries of the `common` key currently which
 is __REQUIRED__ to present when `create_corpus` is true,
 `common` key also stores the `general_cleaing_rules` section which is optional:
	
- `article_begin_mark`: the begin mark of a downloaded article (should be in XML form)
- `article_end_mark`:  the end mark of a downloaded article (should be in XML form)
- `general_cleaing_rules`: the dictionary of general rules applied to clean the HTML output in the form of 
RE and REPL pairs

# Site Schemas

For every site a number of fields, mostly REs must be defined, which are the following:

Basic information:

- `date_first_article`: The date of the first article on the site (aslo used for archive crawling)
- `archive_url_format`: The RE for the archive URLs of the site
 (supply `#year`, `#month`, `#day` tags to be replaced with the actual field of date
 and `#pagenum` is replaced with the actual page number during crawling)

The description of the required fields:	

- Article URL:
    - `article_url_format`: the RE for the article URLs. Transformed to `ARTICLE_URL_FORMAT_RE`
    - `before_article_url`: the RE for the left context of the article URLs. Transformed to `BEFORE_ARTICLE_URL_RE`
    - `before_article_url_repl`: the optional replacement for the left context of the arcticle URLs (e.g. domain)
    - `after_article_url`: the RE for the right context of the article URLs. Transformed to `AFTER_ARTICLE_URL_RE`
    - `after_article_url_repl`: the optional replacement for the right context of the arcticle URLs
- Next page URL:
    - `next_page_url_format`: the RE for the article URLs. Transformed to `NEXT_PAGE_URL_FORMAT_RE`
    - `before_next_page_url`: the RE for the left context of the article URLs. Transformed to `BEFORE_NEXT_PAGE_URL_RE`
    - `before_next_page_url_repl`: the optional replacement for the left context of the arcticle URLs (e.g. domain)
    - `after_next_page_url`: the RE for the right context of the article URLs. Transformed to `AFTER_NEXT_PAGE_URL_RE`
    - `after_next_page_url_repl`: the optional replacement for the right context of the arcticle URLs
- Article date:
    - `article_date_format`: the RE for the article URLs. Transformed to `ARTICLE_DATE_FORMAT_RE`
    - `before_article_date`: the RE for the left context of the article URLs. Transformed to `BEFORE_ARTICLE_DATE_RE`
    - `before_article_date_repl`: the optional replacement for the left context of the arcticle URLs (e.g. domain)
    - `after_article_date`: the RE for the right context of the article URLs. Transformed to `AFTER_ARTICLE_DATE_RE`
    - `after_article_date_repl`: the optional replacement for the right context of the arcticle URLs
    - `article_date_formatting`: the date format specification string used for parsing the date

Some bool features to describe the site:

- `next_url_by_regex`: Is there a next link on the archive page?
- `next_url_by_pagenum`: Use page numbering for pagination of archive e.g. infinite scrolling (false means no pages)
- `archive_page_urls_by_date`: Archive page URLs are grouped by their date
- `archive_page_urls_by_id`: Archive page URLs are grouped by IDs
- `ignore_archive_cache`: Ignore archive cache (for portals with only pagination)
- `go_reverse_in_archive`: Go reverse in the archive by date (when the earliest article is not known)

Numbers regarding pagination:

- `min_pagenum`: The first page number to increment
- `max_pagenum`: The upper bound of the number of pages for safety or for stop criteria
- `new_article_url_threshold`: How many already new urls on a page are required at minimum (e.g. the pages slided due to new articles)

Misc features:

- `tags_key`: the key for the required tags when building a corpus

# Licence

This project is licensed under the terms of the LGPL 3 license.

# References

If you use this program, please cite the following paper:

* [**Crawling in Reverse – Lightweight Targeted Crawling of News Portals** Indig B.; Kákonyi T. and Novák, A. *In Proceedings of the 9th Language & Technology Conference: Human Language Technologies as a Challenge for Computer Science and Linguistics (LTC'19)*, page 81–86, Poznań, Poland, 2019.](http://ltc.amu.edu.pl/)

```
@inproceedings{indig2019b,
  author       = {Indig, Bal\'azs and K\'akonyi, Tibor and Nov\'ak, Attila},
  editor       = {Kubis, Marek},
  title        = {Crawling in Reverse -- Lightweight Targeted Crawling of News Portals},
  date         = {2019},
  booktitle    = {Proceedings of the 9th Language \& Technology Conference: Human Language Technologies as a Challenge for Computer Science and Linguistics (LTC'19)},
  eventdate    = {2019-05-19/2019-05-21},
  venue        = {Pozna\'n, Poland},
  publisher    = {Wydawnictwo Nauka I Innowacje},
  location     = {Pozna\'n, Poland},
  pages        = {81--86},
}
```
