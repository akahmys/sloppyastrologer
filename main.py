#!/usr/bin/env python
# vim:fileencoding=utf-8

import sys
import urllib2

from datetime import datetime, timedelta
from xml.etree import ElementTree

import webapp2

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import ndb


def fetch_and_parse_xml(url):
    result = urlfetch.fetch(url)
    if result.status_code != 200:
        return

    return ElementTree.fromstring(result.content)


def extract_date(xml_tree):
    today = datetime.now() + timedelta(hours=9)

    date = xml_tree.find('.//date')
    if date is None:
        return

    [month, day] = [int(i) for i in date.text[:-1].split(u'\u6708')]
    if month != today.month or day != today.day:
        return

    return "%d%02d%02d" % (today.year, month, day)


def extract_ranking(xml_tree):
    id = xml_tree.findall('.//id')
    if id is None:
        return

    order = [int(i.text) for i in id]
    if len(set(order)) != 12:
        return

    ranking = [0] * 12
    for i, j in enumerate(order):
        ranking[j - 1] = i + 1

    return ''.join(['%x' % i for i in ranking])


def alert_mail(message):
    sender = "sloppyastrologer@appspot.gserviceaccount.com"
    to = "akahmys@gmail.com",
    subject = "Something bad seems to have happened."

    mail.send_mail(sender, to, subject, message)


def generate_data():
    data = memcache.get("data")
    if data is not None:
        return data
    else:
        query = Ranking.query().order(Ranking.key)
        rankings = query.fetch()

        data = []
        for ranking in rankings:
            date = ranking.key.id()
            buf = [int(i) for i in [date[0:4], date[4:6], date[6:8]]]
            buf.extend([int(i, 16) for i in list(ranking.ranking)])
            data.append(buf)

        memcache.add('data', data)

        return data


class Ranking(ndb.Model):
    ranking = ndb.StringProperty(required=True, indexed=False)


class UpdateHandler(webapp2.RequestHandler):
    def get(self):
        url = "http://www.fujitv.co.jp/meza/uranai/uranai.xml"

        xml_tree = fetch_and_parse_xml(url)
        if xml_tree is None:
            message = "Failed to get the XML file."
            alert_mail(message)
            return

        date = extract_date(xml_tree)
        if date is None:
            message = "Failed to extract the date."
            alert_mail(message)
            return

        ranking = extract_ranking(xml_tree)
        if ranking is None:
            message = "Failed to extract the ranking."
            alert_mail(message)
            return

        Ranking.get_or_insert(date, ranking=ranking)

        memcache.flush_all()


class JSONPHandler(webapp2.RequestHandler):
    def get(self):

        callback = self.request.get("callback", default_value="callback")
        data = generate_data()

        self.response.headers["Content-Type"] = "application/javascript"
        self.response.write("%s(%s)" % (callback, data))


class CSVHandler(webapp2.RequestHandler):
    def get(self):

        data = generate_data()

        self.response.headers["Content-Type"] = "text/csv"
        self.response.write("year,month,day,ari,tau,gem,cnc,leo,vir,lib,sco,sgr,cap,aqr,psc\n")
        for line in data:
            self.response.write(",".join(map(str, line)))
            self.response.write("\n")


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('Hello world!')


app = webapp2.WSGIApplication([
    ('/update', UpdateHandler),
    ('/jsonp', JSONPHandler),
    ('/csv', CSVHandler),
    ('/', MainHandler)
    ], debug=True)
