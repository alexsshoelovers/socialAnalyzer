# -*- coding: utf-8 -*-

"""
    A real simple app for using webapp2 with auth and session.

    It just covers the basics. Creating a user, login, logout
    and a decorator for protecting certain handlers.

    Routes are setup in routes.py and added in main.py
"""
# standard library imports
import re
import logging
# related third party imports
import webapp2
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from webapp2_extras.auth import InvalidAuthIdError, InvalidPasswordError
from webapp2_extras.i18n import gettext as _
from bp_includes.external import httpagentparser
# local application/library specific imports
import bp_includes.lib.i18n as i18n
from bp_includes.lib.basehandler import BaseHandler
from bp_includes.lib.decorators import user_required
from bp_includes.lib.decorators import taskqueue_method
from bp_includes.lib import captcha, utils
import bp_includes.models as models_boilerplate
import forms as forms
import models as localmodels
import json
from google.appengine.api import urlfetch
import urllib
import MySQLdb
import os
from google.appengine.api import taskqueue
from datetime import datetime
from datetime import timedelta
from bp_includes.lib import facebook
import time
import itertools
from jsonconv import Json2Html
import base64

SQLIP = '146.148.107.179'
SQLINSTANCE_NAME='socialanalyzer-157404:us-central1:abejita'
PROXY_FB_URL = 'deletefbcomments.appspot.com'
PROXY_FB_TOKEN = 'om50rLGpWqVma39mfYhUp7hnoYehdXxoaWZXd2CfaZE='

class PagesConfigHandler(BaseHandler):
    @user_required
    def get(self, page_id):
        params = {}
        params['page_id'] = page_id
        self.render_template("page_config.html", **params)



class taskGetPublicPageFans(BaseHandler):
    def post(self):
        page_id = self.request.get('page_id')
        app_id = self.app.config.get('fb_api_key')
        app_secret = self.app.config.get('fb_secret')
        app_access_token = getGeneralFBAccessToken()
        # app_access_token = facebook.get_app_access_token(app_id, app_secret)
        page_likes=getFBFans(page_id)
        now_date = datetime.now()
        int_day  = now_date.day
        int_month = now_date.month
        int_year =  now_date.year
        sqlstr1 = "delete from fbpage_fans where page_id='%s' and date='%s-%02d-%02d' and country='%s';" % (page_id, int_year,int_month,int_day,'total')
        sqlstr2 = "insert into fbpage_fans(page_id,date,fans,country) values ('%s','%s-%02d-%02d',%s,'%s')" % (  page_id, int_year,int_month,int_day, int(page_likes), 'total')
        sqlupdatetaskurl = self.uri_for('update-mysql-handler')
        database='abejita'
        taskqueue.add(queue_name='db-update',url=sqlupdatetaskurl, params={
                    'sql_string':[sqlstr1,sqlstr2],
                    'database': database,
                    # '_csrf_token': self.csrf_token()
                })
            # except:
            #     pass


class taskGetDailyLastPageFans(BaseHandler):
    def get(self):
        pages = localmodels.Page.query()
        processed_pages_set = set()
        for page in pages:
            taskurl = self.uri_for('get_public_page_fans')
            user  =page.user
            user_id = str(user.id())
            page_id = page.page_id
            logging.info("User: %s , Page_id: %s" % ( user_id, page_id ) )
            if page_id  not in processed_pages_set:
                taskqueue.add(url=taskurl, params={
                  'page_id': page_id
                  })
                processed_pages_set.add(page_id)


class taskGetLastPageFans(BaseHandler):
    def get(self):
        page_id = self.request.get('page_id','')
        day = self.request.get('day','')
        month = self.request.get('month','')
        year = self.request.get('year','')
        taskurl = self.uri_for('get_page_fans')
        pages = localmodels.Page.query()
        processed_pages_set = set()
        for page in pages:
            taskurl = self.uri_for('get_page_fans')
            user  =page.user
            user_id = str(user.id())
            page_id = page.page_id
            logging.info("User: %s , Page_id: %s" % ( user_id, page_id ) )
            if page_id  not in processed_pages_set:
                taskqueue.add(url=taskurl, params={
                  'page_id': page_id,
                  'day' : day,
                  'month': month,
                  'year': year,
                  'just_one':'True'
                  })
                processed_pages_set.add(page_id)


def getFBFans(page_id):
    # first try to get page fans with access token (if there is a personal access token, then do it with that, else, and if there is a page token, use that, else, use the general fb access_token... )
    # the logic says... if the page has a token use that, if the page owner has a token use that else.... use the general token
    # second try to get the public fan count
    # third try to get the public page_fans_country .... and sum all countries... might not work for every page (the count will not sum )

    app_access_token = getGeneralFBAccessToken()
    url = 'https://graph.facebook.com/%s/?fields=fan_count&access_token=%s' % (page_id, app_access_token)
    logging.info(url)
    r = urlfetch.fetch(url)
    logging.info(r.content)
    fancount=0
    try:
        if r.status_code==200:
            j = json.loads(r.content)
            fancount = j.get('fan_count',0)
            logging.info('fan_count_success: %s' % fancount)
    except:
        logging.info('fan_count_error')
    return fancount

class taskGetPageFansInDate(BaseHandler):
    def get(self):
        page_id = self.request.get('page_id','')
        day = self.request.get('day','')
        month = self.request.get('month','')
        year = self.request.get('year','')
        taskurl = self.uri_for('get_page_fans')
        taskqueue.add(url=taskurl, params={
          'page_id': page_id,
          'day' : day,
          'month': month,
          'year': year
          })
        _message = 'Task started'
        self.add_message(_message, 'info')
        self.redirect_to('page_config', page_id=page_id)

    @taskqueue_method
    def post(self):
        logging.info('post')
        logging.info(self.request.POST.items())
        page_id = self.request.get('page_id','')
        day = self.request.get('day','')
        month = self.request.get('month','')
        year = self.request.get('year','')
        just_one = self.request.get('just_one','')
        if page_id=='':
            return 0
        now_date = datetime.now()
        int_day  = 1
        int_month = now_date.month
        int_year =  now_date.year
        if day!='' and month!=''  and year!='':
            int_day = 1
            int_month = int(month)
            int_year = int(year)

        url = 'http://%s/proxy_fb_call/%s/insights/page_fans_country?access_token=%s&date=%s-%s-%s' % (PROXY_FB_URL,page_id, PROXY_FB_TOKEN, int_day, int_month, int_year)
        logging.info(url)
        r = urlfetch.fetch(url)
        logging.info(r.content)
        j = json.loads(r.content)
        d = j.get('data',[])
        sum =0
        if len(d)>0:
            v=d[0].get('values',[])
            if len(v)>0:
                value = v[0]
                res =  value.get('value',{})
                sum = 0
                for key in res:
                    sum = sum + res[key]
                    sqlstr1 = "delete from fbpage_fans where page_id='%s' and date='%s-%02d-%02d' and country='%s';" % (page_id, int_year,int_month,int_day,key)
                    sqlstr2 = "insert into fbpage_fans(page_id,date,fans,country) values ('%s','%s-%02d-%02d',%s,'%s')" % (  page_id, int_year,int_month,int_day, int(res[key]), key)
                    logging.info(sqlstr1)
                    logging.info(sqlstr2)
                    sqlupdatetaskurl = self.uri_for('update-mysql-handler')
                    database='abejita'
                    taskqueue.add(queue_name='db-update',url=sqlupdatetaskurl, params={
                            'sql_string':[sqlstr1, sqlstr2],
                            'database': database,
                            # '_csrf_token': self.csrf_token()
                        })


        initmonth =int_month -1
        logging.info('sum: %s' % sum )
        logging.info('initmonth: %s' % initmonth)
        if sum==0 or just_one=='True':
            return 0
        elif initmonth == 0:
            initmonth=12
            inityear = int_year -1

        taskurl = self.uri_for('get_page_fans')
        taskqueue.add(url=taskurl, params={
          'page_id': page_id,
          'day' : int_day,
          'month': initmonth,
          'year': int_year
          })


class fetchNewPostsDaysHandler(BaseHandler):
    def get(self, number_of_days):
        number_of_days_validated =0
        try:
            number_of_days_validated = int(number_of_days, 10)
        except:
            pass

        # pages = localmodels.Page.query(localmodels.Page.frequent_post_insight_update==True)
        pages = localmodels.Page.query()
        processed_pages_set = set()
        for page in pages:
            taskurl = self.uri_for('task-download-page-handler')
            user  =page.user
            user_id = str(user.id())
            page_id = page.page_id
            logging.info("User: %s , Page_id: %s" % ( user_id, page_id ) )
            if page_id  not in processed_pages_set:
                taskqueue.add(url=taskurl, params={
                                  'page_id': page_id,
                                  'user_id' : user_id,
                                  'days': number_of_days_validated
                                  })
                processed_pages_set.add(page_id)

class fetchNewPostsHandler(BaseHandler):
    def get(self):
        pages = localmodels.Page.query()
        processed_pages_set = set()
        for page in pages:
            taskurl = self.uri_for('task-download-page-handler')
            user  =page.user
            user_id = str(user.id())
            page_id = page.page_id
            logging.info("User: %s , Page_id: %s" % ( user_id, page_id ) )
            if page_id  not in processed_pages_set:
                taskqueue.add(url=taskurl, params={
                                  'page_id': page_id,
                                  'user_id' : user_id,
                                  'days': 3
                                  })
                processed_pages_set.add(page_id)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            encoded_object = list(obj.timetuple())[0:6]
        else:
            # encoded_object =json.JSONEncoder.default(self, obj)
            encoded_object=  str(obj)
        return encoded_object


class jsonQuery(BaseHandler):
    @user_required
    def get(self, page_id):
        colors = ['#1f77b4','#aec7e8','#ff7f0e','#ffbb78','#2ca02c','#98df8a','#d62728','#ff9896','#9467bd','#c5b0d5','#8c564b','#c49c94','#e377c2','#f7b6d2','#7f7f7f','#c7c7c7','#bcbd22','#dbdb8d','#17becf','#9edae5']
        type_colors = ['link','photo','video','none']
        user = ndb.Key('User', int(self.user_id)).get()
        if user.report_timezone:
           timezone =user.report_timezone
        else:
            timezone = 0

        query_name = self.request.get('query_name','')
        result_format = self.request.get('result_format','')
        result = []
        logging.info(self.request.GET.items())
        if query_name == 'date_hour_posts':
            variables={'timezone':timezone, 'page_id':page_id}
            query = "select a.day,a.name, a.hour, count(*) as count,avg(ifnull(link_clicks,0)) as avg_link_clicks, avg(ifnull(post_impressions,0)) as avg_post_impressions,  avg(ifnull(post_video_views,0)) as avg_post_video_views, avg(ifnull(likes,0)) as avg_likes, avg(ifnull(shares,0)) as avg_shares, avg(ifnull(comments,0)) as avg_comments from  (select * from day a, hours b ) a left outer join fbposts_batch c on a.day= weekday(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR) ) and a.hour = hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR) )and c.page_id ='{page_id}' and datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000') ) <31 group by 1,3 ".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
        elif query_name=='days_recorded':
            variables={'timezone':timezone, 'page_id':page_id}
            query=" select max(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL -6.0 HOUR)) as maxdt, min(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL -6.0 HOUR)) as mindt, datediff(max(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL -6.0 HOUR)),min(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL -6.0 HOUR))) as days_recorded , count(*) as posts from fbposts_batch c where c.page_id='{page_id}' group by page_id".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
        elif query_name=='daily_date_hour_posts':
            post_type = self.request.get('post_type','')
            variables={'timezone':timezone, 'page_id':page_id, 'post_type':post_type}
            if post_type=='' or post_type=='undefined':
                # query="SELECT dayname(t1.date) AS name , t1.hour AS hour , sum(ifnull(COUNT,0))/COUNT(*) AS count , avg(ifnull(likes,0))AS likes, avg(ifnull(post_impressions,0)) AS post_impressions, avg(ifnull(shares,0)) AS shares, avg(ifnull(link_clicks,0)) AS link_clicks, avg(ifnull(comments,0))AS comments, avg(ifnull(post_video_views,0)) AS post_video_views FROM (SELECT a.Date AS date, b.hour AS hour FROM (SELECT curdate() - INTERVAL (a.a + (10 * b.a) + (100 * c.a)) DAY AS Date FROM (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS a CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS b CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS c) a , hours b WHERE a.Date BETWEEN DATE_ADD(now() ,INTERVAL -31 DAY) AND DATE_ADD(now() ,INTERVAL -1 DAY)) t1 LEFT OUTER JOIN (SELECT date(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))AS date , hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) AS hour, dayname(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) AS name , count(*) AS count, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM fbposts_batch c WHERE c.page_id ='{page_id}' AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) <31 AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) >0 GROUP BY c.created_time, date , hour) AS t2 ON t1.date=t2.date AND t1.hour =t2.hour GROUP BY dayname(t1.date), hour".format(**variables)
                query="SELECT hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as hour, weekday(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as weekday, count(*)/4 as count, avg(likes) as likes, avg(shares) as shares, avg(comments) as comments, avg(post_video_views) as post_video_views, avg(post_impressions) as post_impressions from fbposts_batch c where page_id= '{page_id}' and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour)) group by 2,1".format(**variables)
            else:
                if post_type in ['shared','with','live']:
                    # query="SELECT dayname(t1.date) AS name , t1.hour AS hour , sum(ifnull(count,0))/count(*) AS count , avg(ifnull(likes,0))AS likes, avg(ifnull(post_impressions,0)) AS post_impressions, avg(ifnull(shares,0)) AS shares, avg(ifnull(link_clicks,0)) AS link_clicks, avg(ifnull(comments,0))AS comments, avg(ifnull(post_video_views,0)) AS post_video_views FROM (SELECT a.Date AS date, b.hour AS hour FROM (SELECT curdate() - INTERVAL (a.a + (10 * b.a) + (100 * c.a)) DAY AS Date FROM (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS a CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS b CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS c) a , hours b WHERE a.Date BETWEEN DATE_ADD(now() ,INTERVAL -31 DAY) AND DATE_ADD(now() ,INTERVAL -1 DAY)) t1 LEFT OUTER JOIN (SELECT date(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))AS date , hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) AS hour, dayname(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) AS name , count(*) AS count, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM fbposts_batch c WHERE c.page_id ='{page_id}' and c.story like '% {post_type}%' AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) <31 AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) >0 GROUP BY c.created_time,  date , hour) AS t2 ON t1.date=t2.date AND t1.hour =t2.hour GROUP BY dayname(t1.date), hour".format(**variables)
                    query="SELECT hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as hour, weekday(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as weekday, count(*)/4 as count, avg(likes) as likes, avg(shares) as shares, avg(comments) as comments, avg(post_video_views) as post_video_views, avg(post_impressions) as post_impressions from fbposts_batch c where page_id= '{page_id}' and c.story like '% {post_type}%' and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour)) group by 2,1".format(**variables)
                else:
                    # query="SELECT dayname(t1.date) AS name , t1.hour AS hour , sum(ifnull(count,0))/count(*) AS count , avg(ifnull(likes,0))AS likes, avg(ifnull(post_impressions,0)) AS post_impressions, avg(ifnull(shares,0)) AS shares, avg(ifnull(link_clicks,0)) AS link_clicks, avg(ifnull(comments,0))AS comments, avg(ifnull(post_video_views,0)) AS post_video_views FROM (SELECT a.Date AS date, b.hour AS hour FROM (SELECT curdate() - INTERVAL (a.a + (10 * b.a) + (100 * c.a)) DAY AS Date FROM (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS a CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS b CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS c) a , hours b WHERE a.Date BETWEEN DATE_ADD(now() ,INTERVAL -31 DAY) AND DATE_ADD(now() ,INTERVAL -1 DAY)) t1 LEFT OUTER JOIN (SELECT date(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))AS date , hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) AS hour, dayname(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) AS name , count(*) AS count, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM fbposts_batch c WHERE c.page_id ='{page_id}' and c.post_type ='{post_type}' AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) <31 AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) >0 GROUP BY c.created_time, date , hour) AS t2 ON t1.date=t2.date AND t1.hour =t2.hour GROUP BY dayname(t1.date), hour".format(**variables)
                    query="SELECT hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as hour, weekday(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as weekday, count(*)/4 as count, avg(likes) as likes, avg(shares) as shares, avg(comments) as comments, avg(post_video_views) as post_video_views, avg(post_impressions) as post_impressions from fbposts_batch c where page_id= '{page_id}' and c.post_type like '%{post_type}%' and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour)) group by 2,1".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
            days_names = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            tmpdict = {}
            for single_result in result:
                str_weekday_hour = "%s_%s" % (single_result.get('weekday'), single_result.get('hour'))
                tmpdict[str_weekday_hour] = single_result
            new_arr = []
            for i in range(0,len(days_names)):
                for j in range(0,24):
                    strindex = "%s_%s" % (i,j)
                    empty_dict = {'comments': 0 ,'weekday': i, 'likes':0,'shares':0,'post_impressions':0,'count':0, 'post_video_views':0, 'hour':j}
                    tmpval = tmpdict.get(strindex,empty_dict)
                    tmpval['name'] = days_names[i]
                    logging.info(tmpval)
                    new_arr.append(tmpval)
            result = new_arr




        elif query_name=='post_type_distribution':
            variables = {'timezone':timezone, 'page_id':page_id}
            # query = "select post_type, count(*) as count from fbposts_batch c where  page_id='{page_id}' and datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000') ) <31  group by post_type".format(**variables)
            query = "select post_type, count(*) as count from fbposts_batch c where  page_id='{page_id}' and  DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour))  group by post_type".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
            labels = []
            values = []
            piecolors = []
            colorcount =0
            for row in result:
                logging.info(row)
                labels.append(row.get('post_type'))
                values.append(row.get('count'))
                if row.get('post_type') in type_colors:
                    piecolors.append(colors[type_colors.index(row.get('post_type'))])
                else:
                    colorcount =colorcount +1
                    piecolors.append(colors[3+colorcount])

            result = [{ "values": values, "labels": labels, "marker": {
    "colors": piecolors
  }}]

        elif query_name=='day_type_histogram':
            variables = {'timezone':timezone, 'page_id':page_id}
            # query = "select d.name,c.post_type,  weekday(str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) as day, count(*) as count from fbposts_batch c, day d where weekday(str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'))  = d.day and page_id='{page_id}' and datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000') ) <31  group by 1,2,3 order by d.`day` asc".format(**variables)
            # query = "SELECT name, ifnull(post_type,'none') as post_type, avg(COUNT) AS count , avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM (SELECT t1.date, dayname(t1.date) AS name , t1.hour AS hour , sum(ifnull(t2.COUNT,0)) AS COUNT, t2.post_type, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM (SELECT a.Date AS date, b.hour AS hour FROM (SELECT curdate() - INTERVAL (a.a + (10 * b.a) + (100 * c.a)) DAY AS Date FROM (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS a CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS b CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS c) a , hours b WHERE a.Date BETWEEN DATE_ADD(now() ,INTERVAL -31 DAY) AND DATE_ADD(now() ,INTERVAL -1 DAY)) t1 LEFT OUTER JOIN (SELECT date(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))AS date , hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) AS hour, dayname(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) AS name , c.post_type, COUNT(*) AS COUNT, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM fbposts_batch c WHERE c.page_id ='{page_id}' AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) <31 AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) >0 GROUP BY c.created_time, date(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) , hour(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')), c.post_type ) AS t2 ON t1.date=t2.date AND t1.hour =t2.hour GROUP BY t1.hour,date,post_type) AS t3 GROUP BY name, post_type".format(**variables)
            query="select post_type,  weekday(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as weekday, count(*) as count ,  avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments from fbposts_batch c where  page_id='{page_id}' and  DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour))  group by 1,2".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
            dayset= set()
            ordered_days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            ordered_abbr_days =  ['M','Tu','W','Th','F','Sa','Su']
            typeset = set()
            dict_vals = {}
            for row in result:
                day_num =row.get('weekday')
                day_name = ordered_days[day_num]
                post_type = row.get('post_type','')
                dayset.add(day_name)
                typeset.add(post_type)
                if dict_vals.get(day_name):
                    dict_vals[day_name][post_type] = row.get('count',0)/4.0
                else:
                    dict_vals[day_name] = {}
                    dict_vals[day_name][post_type] = row.get('count',0)/4.0
            result = dict_vals
            graph_data = []
            for post_type in typeset:
                range_values = []
                trace = {}
                for i in range(0,len(ordered_days)):
                    range_values.append(dict_vals.get(ordered_days[i],{}).get(post_type,0))
                # trace['x'] = ordered_abbr_days
                trace['x'] =ordered_abbr_days
                trace['y'] = ["%s" % value for value in range_values]
                trace['type'] = 'bar'
                trace['name'] = post_type
                if post_type in type_colors:
                    trace['marker'] = {}
                    trace['marker']['color'] =colors[type_colors.index(post_type)]
                graph_data.append(trace)
            result  = graph_data

        elif query_name=='hour_type_histogram':
            variables={'timezone':timezone, 'page_id':page_id}
            # query = "SELECT t1.date, dayname(t1.date) AS name , t1.hour AS hour , t1.pt as post_type, avg(ifnull(count,0)) as count FROM ( SELECT a.Date AS date, b.hour AS hour, pt.a as pt FROM (SELECT curdate() - INTERVAL (a.a + (10 * b.a) + (100 * c.a)) DAY AS Date FROM (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS a CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS b CROSS JOIN (SELECT 0 AS a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) AS c) a , hours b, (select 'link' as a union all select 'photo' as a union all select 'video ')as pt WHERE a.Date BETWEEN DATE_ADD(now() ,INTERVAL -31 DAY) AND DATE_ADD(now() ,INTERVAL -1 DAY) ) as t1 LEFT OUTER JOIN (SELECT date(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))AS date , hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) AS hour, dayname(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) AS name , COUNT(*) AS COUNT, post_type, avg(likes) AS likes, avg(post_video_views) AS post_video_views, avg(post_impressions) AS post_impressions, avg(shares) AS shares, avg(link_clicks) AS link_clicks, avg(comments) AS comments FROM fbposts_batch c WHERE c.page_id ='{page_id}' AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) <31 AND datediff(now(),str_to_date(c.created_time, '%Y-%m-%dT%H:%i:%s+0000')) >0 GROUP BY c.created_time, date , hour, c.post_type ) AS t2 ON t1.date=t2.date AND t1.hour =t2.hour and t1.pt=t2.post_type group by t1.date, hour, pt".format(**variables)
            query="select post_type,  hour(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)) as hour, count(*)/28 as count from fbposts_batch c where  page_id='{page_id}' and  DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))>=DATE_ADD(DATE(DATE_ADD(now(), interval {timezone} hour)), INTERVAL-29.0 DAY) and DATE(DATE_ADD(STR_TO_DATE(c.created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR))<DATE(DATE_ADD(now(), interval {timezone} hour))  group by 1,2".format(**variables)
            logging.info(query)
            result = returnCursor(query ,'abejita')
            ordered_hours = [  i for i in range(0,24)]
            typeset = set()
            dayset = set()
            dict_vals = {}
            for row in result:
                hour_name =row.get('hour')
                post_type = row.get('post_type')
                dayset.add(hour_name)
                typeset.add(post_type)
                if dict_vals.get(hour_name):
                    dict_vals[hour_name][post_type] = row.get('count',0)
                else:
                    dict_vals[hour_name] = {}
                    dict_vals[hour_name][post_type] = row.get('count',0)
            result = dict_vals
            graph_data = []
            color_count = -1
            for post_type in typeset:
                color_count = color_count+1
                range_values = []
                trace = {}
                for i in range(0,len(ordered_hours)):
                    range_values.append(dict_vals.get(ordered_hours[i],{}).get(post_type,0))
                # trace['x'] = ordered_abbr_days
                trace['x'] =ordered_hours
                trace['y'] = ["%s" % value for value in range_values]
                trace['type'] = 'bar'
                if post_type:
                    trace['name'] = post_type
                else:
                    trace['name'] = 'N/A'
                if post_type in type_colors:
                    trace['marker'] = {}
                    trace['marker']['color'] =colors[type_colors.index(post_type)]
                graph_data.append(trace)
            result  = graph_data
        else:
            pass


        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(result, cls=DateTimeEncoder ))

def getGeneralFBAccessToken():
    db_access_token = localmodels.FBAccess_Token.get_or_insert('root_access_token')
    return db_access_token.fb_access_token


class PageStatsClicksHandler(BaseHandler):

    @user_required
    def get(self, page_id):
        params ={}
        action = self.request.get('action','')
        user = ndb.Key('User', int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()

        params['pages']=pages
        params['page']=page
        params['page_id'] = page_id
        if action=='get_data':
            dataset = self.request.get('dataset')
            period = self.request.get('daterange_filter','twomonths')
            days = 62
            if period=='twomonths':
                days=62
            elif period=='month':
                days=31
            else:
                days=7
            range_date = datetime.today()-timedelta(days=days+1)
            range_year = "%02d" % range_date.year
            range_month = "%02d" % range_date.month
            range_day = "%02d" % range_date.day
            variables={'timezone':user.report_timezone, 'page_id':page_id,'year': range_year, 'month': range_month, 'day': range_day}
            if dataset =='clicks':
                str_sql="select  left( DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d'),10) as date, sum(link_clicks)as clicks from fbposts_batch where  page_id='{page_id}' and  DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')> '{year}-{month}-{day}' group by left( DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d'),10) order by 1 desc".format(**variables)
                logging.info (str_sql)
                clicks_cursor= returnCursor(str_sql ,'abejita')
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(clicks_cursor, cls=DateTimeEncoder))
            if dataset=='today_clicks':
                range_date = datetime.today()+timedelta(hours=(user.report_timezone))
                range_date_now = datetime.today()+timedelta(hours=(user.report_timezone ))
                logging.info(user.report_timezone)
                logging.info(range_date)

                range_year = "%02d" % range_date.year
                range_month = "%02d" % range_date.month
                range_day = "%02d" % range_date.day
                range_hour="%02d" % range_date.hour
                range_minute="%02d" % range_date.minute
                range_second= "%02d" % range_date.second
                variables={'timezone':user.report_timezone, 'page_id':page_id,'year': range_year, 'month': range_month, 'day': range_day}
                str_sql="select   DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%dT%H:%i:%s') as created_time,  link_clicks as clicks from fbposts_batch where  page_id='{page_id}' and  DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')>= '{year}-{month}-{day}'  order by 1 desc".format(**variables)
                logging.info(str_sql)
                clicks_cursor= returnCursor(str_sql ,'abejita')

                total_time =range_date_now.hour * 3600 + range_date_now.minute * 60 + range_date_now.second
                logging.info(range_date_now)
                logging.info(total_time)
                set_post_created_times = set()
                set_post_created_times_labels = set()
                set_post_created_times.add(total_time)
                set_post_created_times_labels.add("%02d:%02d:%02d" % (range_date_now.hour, range_date_now.minute, range_date_now.second ))
                if page.page_token!='' and page.page_token!='undefined':
                    fb_clicks = self.getFBGraphApiClicks(page_id, page.page_token)
                    if fb_clicks>0:
                        total_db_clicks = 0
                        for posts in clicks_cursor:
                            total_db_clicks= total_db_clicks + posts.get('clicks')
                        if fb_clicks-total_db_clicks>0:
                            clicks_cursor=list(clicks_cursor)
                            clicks_cursor.append({
                                                 'created_time':'0000-00-00T00:00:00',
                                                 'clicks': fb_clicks-total_db_clicks
                                                 })

                # logging.info(clicks_cursor)
                for post in clicks_cursor:
                    post_created_time = post.get('created_time').split('T')[1].split(':')
                    post_total_time = int(post_created_time[0])*3600 + int(post_created_time[1])*60 + int(post_created_time[1])
                    set_post_created_times.add(post_total_time)
                    set_post_created_times_labels.add(post.get('created_time').split('T')[1])
                    diff = total_time - post_total_time
                    post['diff'] = total_time - post_total_time
                    post['total_time'] = post_total_time
                    if diff>0:
                        clicks_per_time_unit = (float(post.get('clicks'))*1.0)/(float(diff)*1.0)
                    else:
                        clicks_per_time_unit =post.get('clicks')
                    post['clicks_per_time_unit']  = clicks_per_time_unit
                    # logging.info(post_total_time)
                logging.info(clicks_cursor)
                lst_post_created_times = list(set_post_created_times)
                lst_post_created_times_lables = list(set_post_created_times_labels)
                lst_post_created_times_lables.sort(reverse=False)
                lst_post_created_times.sort(reverse=False)
                last_time = 0
                lst_clicks_till_time = []
                for time in lst_post_created_times:
                    clicks_till_time=0
                    for post in clicks_cursor:
                        logging.info("total_time:%s  time:%s" % (post['total_time'] , time))
                        diff = time-post['total_time']
                        if diff>0 :
                            clicks_till_time =clicks_till_time + ( diff * post['clicks_per_time_unit'])
                        else:
                            logging.info('diff=0')
                    lst_clicks_till_time.append(clicks_till_time)
                    last_time = time
                data = [{
                                    'y': lst_clicks_till_time,
                                    'x': lst_post_created_times_lables,
                                    'type': 'line',
                                    'line': {'shape': 'spline'}
                                  }]
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(data, cls=DateTimeEncoder))
        else:
            self.render_template('stats_clicks.html',**params)

    def getFBGraphApiClicks(self,page_id,access_token):
        str_url = 'https://graph.facebook.com/v2.8/%s/insights?metric=page_consumptions_by_consumption_type&period=day&access_token=%s' % (page_id, access_token)
        rj={}
        count=0
        while True:
            count=count+1
            if count>20:
                break
            logging.info(str_url)
            r=urlfetch.fetch(str_url)
            if r.status_code==200:
                rj=json.loads(r.content)
                next_url = rj.get('paging',{}).get('next','')
                if next_url=='':
                    break
                str_url=next_url
        logging.info(rj)
        value =rj.get('data',[{}])[0].get('values',[{}])[-1].get('value',{}).get('link clicks',0)
        logging.info('value: %s' % value)
        return value

class PageStatsReachGeoHandler(BaseHandler):
    @user_required
    def get(self, page_id):
        params ={}
        action = self.request.get('action','')
        user = ndb.Key('User', int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()

        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()

        params['pages']=pages
        params['page']=page
        params['page_id'] = page.page_id
        if action=='get_data':
            dataset = self.request.get('dataset')
            if dataset=='page_reach_geo':
                access_token  =page.page_token
                countries_arr = []
                countries_arr.append(['Country','Fans'])
                str_url = 'https://graph.facebook.com/v2.8/%s/insights/page_impressions_by_country_unique/days_28?access_token=%s' % (page_id, page.page_token)
                logging.info(str_url)
                r = urlfetch.fetch(str_url)
                countries_data = json.loads(r.content).get('data',[])
                if len(countries_data)>0:
                    countries_values = countries_data[0].get('values',[])
                    if len(countries_values)>0:
                        final_values = countries_values[0].get('value')
                        # logging.info(final_values)
                        for key,val in final_values.iteritems():
                            countries_arr.append([key,val])
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(countries_arr, cls=DateTimeEncoder))
        else:
            self.render_template('stats_reach_geo.html',**params)



class PageStatsOverviewHandler(BaseHandler):
    @user_required
    def get(self,page_id):
        params ={}
        action = self.request.get('action','')
        user = ndb.Key('User', int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()

        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()

        params['pages']=pages
        params['page']=page
        params['page_id'] = page.page_id
        if action=='get_data':
            dataset = self.request.get('dataset')
            period = self.request.get('daterange_filter','twomonths')
            days = 62
            if period=='twomonths':
                days=62
            elif period=='month':
                days=31
            else:
                days=7
            range_date = datetime.today()-timedelta(days=days+1)
            range_year = "%02d" % range_date.year
            range_month = "%02d" % range_date.month
            range_day = "%02d" % range_date.day
            variables={'timezone':user.report_timezone, 'page_id':page_id,'year': range_year, 'month': range_month, 'day': range_day}
            if dataset =='page_fans':
                str_sql="select page_id, DATE_FORMAT(DATE_ADD(STR_TO_DATE(date, '%Y-%m-%d'), INTERVAL {timezone} HOUR), '%Y-%m-%d') as date, fans, country   from fbpage_fans where page_id='{page_id}' and country='total' and  date> '{year}-{month}-{day}' order by date asc ".format(**variables)
                page_fans= returnCursor(str_sql ,'abejita')
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(page_fans, cls=DateTimeEncoder))
                logging.info (str_sql)
            elif dataset =='page_countries':
                access_token  =getGeneralFBAccessToken()
                countries_arr = []
                countries_arr.append(['Country','Fans'])
                url_countries = 'https://graph.facebook.com/v2.8/%s/insights/page_fans_country/lifetime?access_token=%s'  % (page.page_id, access_token)
                logging.info(url_countries)
                r = urlfetch.fetch(url_countries)
                countries_data = json.loads(r.content).get('data',[])
                if len(countries_data)>0:
                    countries_values = countries_data[0].get('values',[])
                    if len(countries_values)>0:
                        final_values = countries_values[0].get('value')
                        # logging.info(final_values)
                        for key,val in final_values.iteritems():
                            countries_arr.append([key,val])
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(countries_arr, cls=DateTimeEncoder))
            elif dataset=='page_engagement_distribution':
                str_sql="select  sum(likes)as likes, sum(shares)as shares, sum(comments) as comments from fbposts_batch where  page_id='{page_id}' and  DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')> '{year}-{month}-{day}'".format(**variables)
                page_engagement_distribution = returnCursor(str_sql,'abejita')[0]
                logging.info(str_sql)
                labels=['likes','shares','comments']
                values = [page_engagement_distribution.get('likes'),page_engagement_distribution.get('shares'),page_engagement_distribution.get('comments') ]
                data = [{
                            'values': values,
                            'labels': labels,
                            'type': 'pie',
                            'hole': 0.4
                          }]
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(data, cls=DateTimeEncoder))
            elif dataset=='most_engaged_post_type':
                str_sql = "select fans from fbpage_fans where page_id='%s' and country='total' order by date desc limit 1" % page.page_id
                fans = returnCursor(str_sql, 'abejita')
                logging.info(fans)
                total_fans=0
                if len(fans)>0:
                    total_fans = fans[0].get('fans',0)
                else:
                    total_fans = 1

                if int(total_fans)==0:
                    total_fans=1
                logging.info('total_fans: %s' % total_fans)
                str_sql = "select  post_type, (sum(likes)+ sum(shares)+ sum(comments))/count(*) as interactions from fbposts_batch where  page_id='{page_id}' and  DATE_FORMAT(DATE_ADD( STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)  ,'%Y-%m-%d')> '{year}-{month}-{day}'  group by post_type order by (sum(likes)+ sum(shares)+ sum(comments) )/count(*) desc".format(**variables)
                post_engagement_by_post_type = returnCursor(str_sql,'abejita')
                labels = []
                values = []
                for row in post_engagement_by_post_type:
                    labels.append(row.get('post_type'))
                    values.append(float(row.get('interactions'))/(float(total_fans)/1000.0))
                data = [{
                                    'y': values,
                                    'x': labels,
                                    'type': 'bar'
                                  }]

                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(data, cls=DateTimeEncoder))
            elif dataset=='post_type_distribution':
                str_sql = "select post_type, count(*) as count  from fbposts_batch where page_id='{page_id}' and  DATE_FORMAT(DATE_ADD( STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)    ,'%Y-%m-%d')> '{year}-{month}-{day}' group by post_type order by post_type asc".format(**variables)
                post_types = returnCursor(str_sql, 'abejita')
                values =[]
                labels=[]
                for row in post_types:
                    labels.append(row.get('post_type'))
                    values.append(row.get('count'))
                data = [{
                                    'values': values,
                                    'labels': labels,
                                    'type': 'pie',
                                    'hole': 0.4
                                  }]
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(data, cls=DateTimeEncoder))
            elif dataset=='page_engagement_daily':
                str_sql = "select fans from fbpage_fans where page_id='%s' and country='total' order by date desc limit 1" % page.page_id
                fans = returnCursor(str_sql, 'abejita')
                total_fans=0
                if len(fans)>0:
                    total_fans = fans[0].get('fans')
                else:
                    total_fans = 1
                if int(total_fans)==0:
                    total_fans=1
                str_sql="select  DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d') as date, post_type,  sum(likes)as likes, sum(shares)as shares, sum(comments) as comments, sum(likes)+ sum(shares) + sum(comments)  as total from fbposts_batch where  page_id='{page_id}'  and  DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)  ,'%Y-%m-%d')> '{year}-{month}-{day}' group by DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d'), post_type".format(**variables)
                logging.info(str_sql)
                page_engagement = returnCursor(str_sql, 'abejita')
                dates_arr = []
                photo_arr = []
                link_arr= []
                total_arr=[]
                video_arr = []
                total_arr_per_1000=[]
                date_str = ''
                added_photo=False
                added_video=False
                added_link = False
                is_first_time=True
                for row in page_engagement:
                    if row.get('date') != date_str:
                        date_str=row.get('date')
                        if not is_first_time:
                            if not added_photo:
                                photo_arr.append(0)
                            if not added_video:
                                video_arr.append(0)
                            if not added_link:
                                link_arr.append(0)
                            added_photo=False
                            added_video=False
                            added_link = False
                            dates_arr.append(row.get('date'))
                        else:
                            is_first_time=False
                    if row.get('post_type','')=='photo':
                        photo_arr.append(row.get('total'))
                        added_photo=True
                    elif row.get('post_type','')=='link':
                        link_arr.append(row.get('total'))
                        added_link=True
                    elif row.get('post_type','')=='video':
                        video_arr.append(row.get('total'))
                        added_video=True
                    else:
                        pass

                for i in range(0,len(dates_arr)-1):
                    total_arr.append(photo_arr[i] + video_arr[i] + link_arr[i])
                    total_arr_per_1000.append(float(photo_arr[i] + video_arr[i] + link_arr[i])/(float(total_fans)/1000.0))
                post_type_data = [
                                    { 'x': dates_arr, 'y':photo_arr, 'type':'bar', 'name':'photo'},
                                    { 'x':dates_arr, 'y':link_arr, 'type':'bar', 'name':'link'},
                                    { 'x':dates_arr, 'y':video_arr,'type':'bar', 'name':'video'},
                                    { 'x':dates_arr, 'y':total_arr_per_1000,'type':'scatter', 'name':'x1000fans', 'yaxis': 'y2',},
                                    # { 'x':dates_arr, 'y':total_arr,'type':'scatter', 'name':'total'}
                                    ]

                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(post_type_data, cls=DateTimeEncoder))
            elif dataset=='page_reach_by_type':
                str_sql = "select fans from fbpage_fans where page_id='%s' and country='total' order by date desc limit 1" % page.page_id
                fans = returnCursor(str_sql, 'abejita')
                total_fans=0
                if len(fans)>0:
                    total_fans = fans[0].get('fans')
                else:
                    total_fans = 1
                if int(total_fans)==0:
                    total_fans=1
                str_sql="select DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d') as date, post_type,  sum(post_impressions)/count(*)  as reach from fbposts_batch where  page_id='{page_id}'and  DATE_FORMAT(DATE_ADD( STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')> '{year}-{month}-{day}' group by DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d'), post_type".format(**variables)
                page_engagement = returnCursor(str_sql, 'abejita')
                dates_arr = []
                photo_arr = []
                link_arr= []
                total_arr=[]
                video_arr = []
                total_arr_per_1000=[]
                date_str = ''
                added_photo=False
                added_video=False
                added_link = False
                is_first_time=True
                for row in page_engagement:
                    if row.get('date') != date_str:
                        date_str=row.get('date')
                        if not is_first_time:
                            if not added_photo:
                                photo_arr.append(0)
                            if not added_video:
                                video_arr.append(0)
                            if not added_link:
                                link_arr.append(0)
                            added_photo=False
                            added_video=False
                            added_link = False
                            dates_arr.append(row.get('date'))
                        else:
                            is_first_time=False
                    if row.get('post_type','')=='photo':
                        photo_arr.append(row.get('reach'))
                        added_photo=True
                    elif row.get('post_type','')=='link':
                        link_arr.append(row.get('reach'))
                        added_link=True
                    elif row.get('post_type','')=='video':
                        video_arr.append(row.get('reach'))
                        added_video=True
                    else:
                        pass

                for i in range(0,len(dates_arr)-1):
                    total_arr.append(photo_arr[i] + video_arr[i] + link_arr[i])
                    total_arr_per_1000.append(float(photo_arr[i] + video_arr[i] + link_arr[i])/(float(total_fans)/1000.0))
                post_type_data = [
                                    { 'x': dates_arr, 'y':photo_arr, 'type':'bar', 'name':'photo'},
                                    { 'x':dates_arr, 'y':link_arr, 'type':'bar', 'name':'link'},
                                    { 'x':dates_arr, 'y':video_arr,'type':'bar', 'name':'video'},
                                    { 'x':dates_arr, 'y':total_arr_per_1000,'type':'scatter', 'name':'x1000fans', 'yaxis': 'y2',},
                                    # { 'x':dates_arr, 'y':total_arr,'type':'scatter', 'name':'total'}
                                    ]

                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(post_type_data, cls=DateTimeEncoder))
            elif dataset=='post_type_count':
                # variables={'timezone':user.report_timezone, 'page_id':421584877978888,'year': range_year, 'month': range_month, 'day': range_day}
                str_sql = "select DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d') as date, post_type, count(*) as count  from fbposts_batch where page_id='{page_id}' and  DATE_FORMAT(DATE_ADD( STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)  ,'%Y-%m-%d')> '{year}-{month}-{day}' group by post_type, DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d') order by DATE_FORMAT(DATE_ADD(STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR), '%Y-%m-%d') asc, post_type asc".format(**variables)
                logging.info(str_sql)
                posts_types = returnCursor(str_sql, 'abejita')
                dates_arr = []
                photo_dict={}
                link_dict={}
                video_dict={}

                dates_arr = []
                photo_arr = []
                link_arr= []
                total_arr=[]
                video_arr = []
                date_str = ''

                for row in posts_types:
                    if row.get('date') in dates_arr:
                        pass
                    else:
                        dates_arr.append(row.get('date'))

                    if row.get('post_type','')=='photo':
                        photo_dict[row.get('date')]=row.get('count')
                    elif row.get('post_type','')=='link':
                        link_dict[row.get('date')]=row.get('count')
                    elif row.get('post_type','')=='video':
                        video_dict[row.get('date')]=row.get('count')
                    else:
                        pass

                for date in dates_arr:
                    total_arr.append(photo_dict.get(date,0) + link_dict.get(date,0) + video_dict.get(date,0))
                    if photo_dict.get(date):
                        photo_arr.append(photo_dict.get(date))
                    else:
                        photo_arr.append(0)
                    if link_dict.get(date):
                        link_arr.append(link_dict.get(date))
                    else:
                        link_arr.append(0)
                    if video_dict.get(date):
                        video_arr.append(video_dict.get(date))
                    else:
                        video_arr.append(0)

                post_type_data = [
                                    { 'x': dates_arr, 'y':photo_arr, 'type':'scatter', 'name':'photo'},
                                    { 'x':dates_arr, 'y':link_arr, 'type':'scatter', 'name':'link'},
                                    { 'x':dates_arr, 'y':video_arr,'type':'scatter', 'name':'video'},
                                    { 'x':dates_arr, 'y':total_arr,'type':'scatter', 'name':'total'}
                                    ]

                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(post_type_data, cls=DateTimeEncoder))
            else:
                pass
        else:
            self.render_template('stats_overview.html',**params)


    def post(self):
        pass

class PageStatsFansHandler(BaseHandler):
    def get(self,page_id):
        pass

    def post(self):
        pass


class PageStatsContentHandler(BaseHandler):
    @user_required
    def get(self,page_id):
        params ={}
        action = self.request.get('action','')
        user = ndb.Key('User', int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()
            # logging.info(page)
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()
            # logging.info(page)

        params['pages']=pages
        params['page_id'] = page.page_id
        params['page'] = page
        params['str_sql'] = ''
        dataset = self.request.get('dataset')
        logging.info(action)
        logging.info(dataset)
        if action=='get_data':
            period = self.request.get('daterange_filter','week')
            days = 62
            if period=='twomonths':
                days=62
            elif period=='month':
                days=31
            else:
                days=7
            logging.info('days: %s' % days)

            range_date = datetime.today()-timedelta(days=days+1)
            logging.info('ranbge_dagte: %s' % range_date)
            range_year = "%02d" % range_date.year
            range_month = "%02d" % range_date.month
            range_day = "%02d" % range_date.day
            variables={'timezone':user.report_timezone, 'page_id':page_id,'year': range_year, 'month': range_month, 'day': range_day}
            if dataset =='page_content':
                str_sql="select *   from fbpage_fans where page_id='%s' and country='total'  and  DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')> '{year}-{month}-{day}' order by date asc ".format(**variables)
                page_fans= returnCursor(str_sql ,'abejita')
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(page_fans, cls=DateTimeEncoder))
                logging.info (str_sql)
            elif dataset=='posts':
                sql_where= self.request.get('type_filter','all')
                sql_order= self.request.get('order_filter','total')
                sql_dates= self.request.get('daterange_filter','week')
                where_str=[]
                where_str.append(" page_id='%s' " % page_id )
                order_sql=""
                order_str=[]
                if sql_order=='total':
                    order_str.append(' likes + shares + comments desc ')
                elif sql_order!='':
                    order_str.append(' %s desc ' % sql_order)

                if len(order_str)>0:
                    order_sql =' order by %s ' %  ' and '.join(order_str)

                if sql_where =='all':
                    pass
                elif sql_where in ['with','shared','live']:
                    where_str.append(" story like '%%%s%%'" % sql_where)
                elif sql_where in ['photo', 'link', 'video']:
                    where_str.append(" post_type =  '%s'" % sql_where)

                where_str.append("DATE_FORMAT(DATE_ADD(  STR_TO_DATE(created_time, '%Y-%m-%dT%H:%i:%s+0000'), INTERVAL {timezone} HOUR)     ,'%Y-%m-%d')> '{year}-{month}-{day}'".format(**variables))

                concat_where = ' and '.join(where_str)
                str_sql = "select post_id, message, story, likes, shares, comments, likes+ shares + comments as total, post_impressions, link_clicks, post_video_views, link from fbposts_batch where  %s  %s limit 15" % (concat_where , order_sql)
                params['str_sql'] = str_sql
                logging.info (str_sql)
                posts = returnCursor(str_sql, 'abejita')
                results = {}
                results['posts'] =posts
                results['str_sql'] = str_sql
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(json.dumps(results, cls=DateTimeEncoder))
        else:
            self.render_template('stats_content.html',**params)

    def post(self):
        pass

class PageStatsEngagementHandler(BaseHandler):
    def get(self,page_id):
        pass

    def post(self):
        pass

class PageStatsLivesHandler(BaseHandler):
    def get(self,page_id):
        pass

    def post(self):
        pass


class PageStatsSharesHandler(BaseHandler):
    def get(self,page_id):
        pass

    def post(self):
        pass

class PageStatsWithHandler(BaseHandler):
    def get(self,page_id):
        pass

    def post(self):
        pass


class PageStatsPublishingHandler(BaseHandler):
    @user_required
    def get(self, page_id):
        params={}
        jsarr=[
            "//cdnjs.cloudflare.com/ajax/libs/jqueryui/1.11.4/jquery-ui.min.js",
            "//cdn.plot.ly/plotly-latest.min.js",
            "//cdnjs.cloudflare.com/ajax/libs/pivottable/2.3.0/pivot.min.js",
            # "//cdnjs.cloudflare.com/ajax/libs/pivottable/2.3.0/pivot.min.js.map",
            # "//cdnjs.cloudflare.com/ajax/libs/pivottable/2.3.0/d3_renderers.min.js.map",
            # "//cdnjs.cloudflare.com/ajax/libs/pivottable/2.3.0/d3_renderers.min.js",
        ]
        cssarr=[
            "https://cdnjs.cloudflare.com/ajax/libs/pivottable/2.3.0/pivot.min.css",
        ]
        params['js'] = jsarr
        params['css'] = cssarr
        params['page_id']=page_id
        user = ndb.Key('User',int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()

        access_token = ''
        if page.page_token!='undefined':
            access_token = page.page_token
        else:
            access_token = user.fb_access_token


        page_likes = getFBFans(page_id)

        logging.info(page)
        logging.info(pages)
        params['page']=page
        params['pages']=pages
        params['page_likes'] = page_likes
        self.render_template("page_stats.html",**params)


class trigger_downloadPageHandler(BaseHandler):
    @user_required
    def get(self,page_id):
        user = ndb.Key('User', int(self.user_id)).get()
        # page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
        page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
        ndays = self.request.get('ndays','3')
        try:
            ndays = int(ndays)
        except:
            ndays = 3
        taskurl = self.uri_for('task-download-page-handler')
        if (page and user):
            taskqueue.add(url=taskurl, params={
                          'page_id': page_id,
                          'user_id' : self.user_id,
                          'days': ndays
                          })
            self.response.out.write(json.dumps({'status':'ok','message':'process started'}))
        else:
            self.response.out.write(json.dumps({'status':'error','message':'page_not_found'}))

class task_downloadPageHandler(BaseHandler):
    def graphapi_2_csv(self, post, page_id):
        # logging.info('')
        csv_arr = []
        story =post.get('story','')
        permalink_url = post.get('permalink_url','')
        link  = post.get('link', '')
        message = post.get('message','')
        message = message[:2499]
        from_name =post.get('from',{}).get('name','')
        from_id =post.get('from',{}).get('id','')
        created_time = post.get('created_time','')

        weekday = post.get('weekday','')
        object_id = post.get('object_id','')
        picture = post.get('picture','')
        post_type = post.get('type','')
        post_id = post.get('id','')
        likes = post.get('likes',{}).get('summary',{}).get('total_count',0)
        comments = post.get('comments',{}).get('summary',{}).get('total_count',0)
        shares = post.get('shares',{}).get('count',0)
        attachment_description=''
        attachment_title=''
        link_clicks=0
        post_impressions=0
        post_video_views=0
        insights_data =post.get('insights',{}).get('data',[])
        if len(insights_data)>0:
            for insight in insights_data:
                insight_name = insight.get('name','')
                insight_period= insight.get('period','')
                insight_values= insight.get('values')
                if insight_name=='post_consumptions_by_type' and insight_period=='lifetime':
                    if len(insight_values)>0:
                        insight_value = insight_values[0]
                        link_clicks = insight_value.get('value',{}).get('link clicks',0)
                elif insight_name=='post_impressions' and insight_period=='lifetime':
                    if len(insight_values)>0:
                        insight_value = insight_values[0]
                        post_impressions = insight_value.get('value',0)
                elif insight_name=='post_video_views' and insight_period=='lifetime':
                    if len(insight_values)>0:
                        insight_value = insight_values[0]
                        post_video_views = insight_value.get('value',0)


        if len(post.get('attachments',{}).get('data',[]))>0:
            attachment_description = '%s' % post.get('attachments',{}).get('data',[])[0].get('description','')
            attachment_title = '%s' % post.get('attachments',{}).get('data',[])[0].get('title','')

        csv_headr =["shares","post_video_views","post_impressions","link_clicks","weekday","page_id","story","permalink_url","link","message","from_name","from_id","created_time","object_id","picture","post_type","post_id","likes","comments","attachment_description","attachment_title"]
        csv_arr=[shares, post_video_views,post_impressions, link_clicks, weekday,page_id,story,permalink_url,link,message,from_name,from_id,created_time,object_id,picture,post_type,post_id,likes,comments,attachment_description,attachment_title]
        csv_arr2 = [ (u"%s" % column).replace('"','').encode('utf-8') for column in csv_arr]
        return csv_headr, csv_arr2


    def get(self):
        # if we use cron, here would be it...
        pass
    def post(self):
        logging.info(self.request.POST.items())
        page_id = self.request.get('page_id')
        user_id = self.request.get('user_id')
        strnext = self.request.get('next_url','')
        days = self.request.get('days','0')
        intdays = int(days)
        using_page_token = False
        if strnext!="":
            edge_query=strnext
        else:
            # we need to check that at least we try to use a page that has an access token
            # we need to define a way to get user to provide page access token when available

            page = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',user_id), localmodels.Page.page_id==page_id).get()
            user  =ndb.Key('User',int(user_id)).get()
            access_token = ''
            shared_fields=["story","attachments","permalink_url","comments.limit(0).summary(true)","shares","likes.limit(0).summary(true)","link","message","from","created_time","object_id", "picture","type"]
            auth_fields=["insights.metric(post_consumptions_by_type,post_impressions,post_video_views)"]
            logging.info('page_token: %s' % page)
            if  page.page_token!='undefined':
                using_page_token  = True
                access_token=page.page_token
                fields = ','.join(shared_fields+auth_fields)
            else:
                access_token=user.fb_access_token
                fields=','.join(shared_fields)



            base_url="https://graph.facebook.com/v2.8"
            edge_query="%s/%s/posts?fields=%s&access_token=%s" % ( base_url, page_id ,fields,access_token)
        logging.info(edge_query)
        r=urlfetch.fetch(edge_query)
        logging.info(r.content)
        data_posts=json.loads( r.content).get('data',[])
        paging_posts=json.loads(r.content).get('paging',{})
        strnext =paging_posts.get('next','')
        datediff = 0
        now_date = datetime.now()
        epoch = now_date.strftime('%s')

        for post in data_posts:
            strtime = post.get('created_time').split('+')[0]
            umt_created_time =datetime.strptime(  strtime, "%Y-%m-%dT%H:%M:%S" )
            weekday =  umt_created_time.strftime("%A")
            post['weekday']=weekday
            datediff = abs((datetime.now() - umt_created_time).days)
            logging.info('datediff: %s' % datediff)
            # logging.info('created_time: %s' % strtime)
            csv_headr,csv_data = self.graphapi_2_csv(post, page_id)
            # logging.info(csv_headr)
            insert_fields = ','.join(['%s' % field for field in csv_headr ])
            insert_values = ','.join(['"%s"' % value for value in csv_data ])
            str_delete = "delete from fbposts_batch where post_id='%s'" % post.get('id')
            str_insert = "insert into fbposts_batch(%s) values(%s)" % (insert_fields, insert_values)

            filtered_fields = []
            filtered_values = []
            int_index = 0
            for field in csv_headr:
                if field in ['shares','post_video_views','post_impressions','link_clicks','post_type','post_id','likes','comments','dt']:
                    filtered_fields.append(field)
                    filtered_values.append(csv_data[int_index])
                int_index=int_index+1
            insert_fields = ','.join(['%s' % field for field in filtered_fields ])
            insert_values = ','.join(['"%s"' % value for value in filtered_values ])
            str_insert_inc = "insert into fbposts_incr(%s, dt) values(%s, %s)" % (insert_fields, insert_values, epoch)
            # logging.info(str_delete)
            # logging.info(str_insert)
            database='abejita'
            sqlupdatetaskurl = self.uri_for('update-mysql-handler')
            taskqueue.add(queue_name='db-update',url=sqlupdatetaskurl, params={
                    'sql_string':[str_delete,str_insert, str_insert_inc],
                    'database': database,
                    # '_csrf_token': self.csrf_token()
                })
        if datediff<intdays and strnext!='':
            self_task_url = self.uri_for('task-download-page-handler')
            taskqueue.add(queue_name='default',url=self_task_url, params={
                          'page_id': page_id,
                          'user_id': user_id,
                          'next_url' : strnext,
                          'days': days
                          })



def getServerIP():
    strsqlip = ''
    if (os.getenv('SERVER_SOFTWARE') and os.getenv('SERVER_SOFTWARE').startswith('Google App Engine/')):
        strsqlip =SQLIP
    else:
        strsqlip='127.0.0.1'
        # strsqlip='146.148.107.179'
    return strsqlip


def returnCursor(sqlstring, database):
    if sqlstring!='' and database!='':
        instance_name='crowdshoes-production:postsdata'
        if (os.getenv('SERVER_SOFTWARE') and os.getenv('SERVER_SOFTWARE').startswith('Google App Engine/')):
            db = MySQLdb.connect(unix_socket='/cloudsql/' + SQLINSTANCE_NAME, db=database, user='root',  passwd='UYxe9cxuYoQ8ctV',charset='utf8')
        else:
            # db = MySQLdb.connect(host='173.194.230.54', port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db=database)
            db = MySQLdb.connect(host=getServerIP(), port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db=database, charset='utf8')
        cursor = db.cursor (MySQLdb.cursors.DictCursor)
        logging.info("#"*40)
        logging.info(sqlstring)
        c= cursor.execute(sqlstring)
        d = cursor.fetchall()
        # logging.info('return cursor: %s ' %  json.dumps(d))
        return d
    else:
        return []


class UpdateMySQLHandler(BaseHandler):
    def post(self):
        # logging.info(self.request.POST.items())
        sqlstring = self.request.get_all('sql_string')
        logging.info('sqlstring: %s' % sqlstring)

        database = self.request.get('database','')
        logging.info('database: %s' % database)
        if sqlstring!='' and database!='':
            instance_name='crowdshoes-production:postsdata'
            if (os.getenv('SERVER_SOFTWARE') and os.getenv('SERVER_SOFTWARE').startswith('Google App Engine/')):
                db = MySQLdb.connect(unix_socket='/cloudsql/' + SQLINSTANCE_NAME, db=database, user='root', passwd='UYxe9cxuYoQ8ctV',charset='utf8')
            else:
                # db = MySQLdb.connect(host='173.194.230.54', port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db=database)
                db = MySQLdb.connect(host=getServerIP(), port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db=database, charset='utf8')

            cursor = db.cursor()
            cursor.execute('SET NAMES utf8mb4')
            cursor.execute("SET CHARACTER SET utf8mb4")
            cursor.execute("SET character_set_connection=utf8mb4")
            # logging.info("#"*40)
            # logging.info(json.dumps(sqlstring))
            for query in sqlstring:
                uquery= u"%s" % query
                # query = uquery.encode('iso-8859-1','ignore')
                query = uquery.encode('utf-8', errors='strict')
                logging.info('execute: %s' % query)
                cursor.execute(query)
            db.commit()
            db.close()


class UpdatePostTaxonomyHandler(BaseHandler):
    @user_required
    def get(self):
        pass

    @user_required
    def post(self):
        logging.info(self.request.POST.items())
        post_id =self.request.get('post_id')
        taxonomy=self.request.get('taxonomy')
        user_id =self.request.get('user_id','')
        bool_taxonomy=self.request.get('bool_taxonomy')
        sqlupdatetaskurl = self.uri_for('update-mysql-handler')
        if bool_taxonomy=='true':
            sql_string = ["delete from posts_taxonomies where post_id='%s' and post_taxonomy='%s'" % (post_id, taxonomy),"insert into posts_taxonomies(user_id,post_id,post_taxonomy) values('%s','%s','%s');" % (user_id, post_id, taxonomy)]
        elif bool_taxonomy=='false':
            sql_string = ["delete from posts_taxonomies where post_id='%s' and post_taxonomy='%s'" % (post_id, taxonomy)]
        database='abejita'
        taskqueue.add(queue_name='db-update',url=sqlupdatetaskurl, params={
                'sql_string':sql_string,
                'database': database,
                # '_csrf_token': self.csrf_token()
            })

class TestMySQL(BaseHandler):
    def get(self):
        # try:

        instance_name='crowdshoes-production:postsdata'
        if (os.getenv('SERVER_SOFTWARE') and os.getenv('SERVER_SOFTWARE').startswith('Google App Engine/')):
            db = MySQLdb.connect(unix_socket='/cloudsql/' + SQLINSTANCE_NAME, db='facebook_posts', user='root',passwd='UYxe9cxuYoQ8ctV', charset='utf8')
        else:
            # db = MySQLdb.connect(host='173.194.230.54', port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db='facebook_posts')
            db = MySQLdb.connect(host=getServerIP(), port=3306, user='dashboards',  passwd='DgLF8CKL8EZrYRt', db='abejita', charset='utf8')

        cursor = db.cursor()
        cursor.execute('select count(*) from FB_INSIGHTS')
        for row in cursor.fetchall():
            totalpins = row[0]

        # except:
        #     pass

        self.response.out.write('Total fb_insights: %s' % totalpins)

class GeneralConfigHandler(BaseHandler):
    @user_required
    def get(self):
        params={}
        user = ndb.Key('User', int(self.user_id)).get()
        params['timezone'] = user.report_timezone
        self.render_template('general_config.html',**params)

    @user_required
    def post(self):
        timezone=self.request.get('timezone','0')
        timezone = float(timezone)
        user = ndb.Key('User', int(self.user_id)).get()
        user.report_timezone = timezone
        user.put()
        self.add_message('Timezone Updated!', 'info')
        self.redirect_to('general-config')

class TaxonomyHandler(BaseHandler):
    def process_taxonomies(self,str_taxonomies):
        str_taxonomies = str_taxonomies.strip()
        arr_taxonomies = str_taxonomies.split(',')
        arr_taxonomies = [str_taxonomy.strip() for str_taxonomy in arr_taxonomies]
        return ','.join(arr_taxonomies)

    @user_required
    def get(self,page_id):
        params = {}
        user = ndb.Key('User',int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
        params['page'] = page
        params['page_id']=page.page_id
        self.render_template("taxonomy_admin.html",**params)

    @user_required
    def post(self,page_id):
        logging.info(self.request.POST.items())
        params = {}
        general_taxonomy = self.request.get('general_taxonomy','')
        link_taxonomy = self.request.get('link_taxonomy','')
        photo_taxonomy = self.request.get('photo_taxonomy','')
        video_taxonomy = self.request.get('video_taxonomy','')
        user = ndb.Key('User',int(self.user_id)).get()
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
        page.general_taxonomies = self.process_taxonomies(general_taxonomy)
        page.link_taxonomies = self.process_taxonomies(link_taxonomy)
        page.photo_taxonomies = self.process_taxonomies(photo_taxonomy)
        page.video_taxonomies = self.process_taxonomies(video_taxonomy)
        page.put()
        _message = 'Taxonomies saved'
        self.add_message(_message, 'info')
        self.redirect_to('taxonomy', page_id =page_id)

class CreateLiveCounter(BaseHandler):
    @user_required
    def get(self):
        params={}
        self.render_template('create_live_counter.html',**params)

    @user_required
    def post(self):
        pass

class ScheduleLiveHandler(BaseHandler):
    @user_required
    def get(self,page_id):
        params ={}
        params['page_id'] = page_id
        fb_api_key = self.app.config.get('fb_api_key')
        fb_secret = self.app.config.get('fb_secret')
        params['fb_api_key']=fb_api_key
        params['fb_secret']=fb_secret
        page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
        if not page:
            self.redirect_to('home')
        else:
            params['page_token'] = page.page_token
            self.render_template("schedule_live_video.html",**params)



    def post(self,page_id):
        self.redirect_to("available-posts", page_id=page_id)

class AvailablePostsHandler(BaseHandler):
    # 599478056788641/live_videos?fields=id,broadcast_start_time,creation_time,description,embed_html,is_manual_mode,live_views,permalink_url,planned_start_time,preview_url,status,title,stream_url,secure_stream_url
    @user_required
    def get(self, page_id):
        next_url = self.request.get('next','')
        logging.info('next_url: %s' % next_url)
        token = self.get_available_posts_token(page_id)
        if next_url=='':
            posts_url = 'https://graph.facebook.com/v2.6/%s/posts?fields=permalink_url,story,attachments,message,link,type,created_time,picture,id&access_token=%s' % (page_id, token)
        else:
            posts_url=next_url

        self.render_available_posts(page_id,posts_url, 'data')




    @user_required
    def post(self,page_id):
        logging.info(self.request.POST.items())
        action= self.request.get('action')
        post_ids=[]
        str_sql = ''
        if action=="get_data":
            str_taxonomies = self.request.get('taxonomies').split(',') if self.request.get('taxonomies').strip()!='' else []
            str_types = self.request.get('types').split(',') if self.request.get('types').strip()!='' else []
            str_query = self.request.get('str_query').strip()
            created_time_where = self.request.get('created_time_where').strip()
            created_time_comparator=self.request.get('created_time_comparator').strip()
            story_list =[]
            type_list=[]
            for type in str_types:
                if type in ['link','photo','video','all']:
                    type_list.append(type)
                elif type in ['with','shares','live']:
                    story_list.append(type)
                else:
                    pass
            if 'all' in type_list:
                type_list=[]
                story_list=[]
            type_list=["'%s'" % s for s in type_list]
            str_taxonomies=["'%s'" % s for s in str_taxonomies]
            logging.info(str_taxonomies)
            logging.info(type_list)
            logging.info(story_list)
            logging.info(str_query)
            tax_where=''
            total_where_list = []
            total_where_list.append("page_id ='%s'" % page_id)
            if len(str_taxonomies)>0:
                tax_where = 'post_taxonomy in (%s)' % ','.join(str_taxonomies)
                total_where_list.append("( %s ) " % tax_where)

            type_where=''
            if len(type_list)>0:
                type_where  = 'post_type in (%s)' % ','.join(type_list)
                total_where_list.append("( %s ) " % type_where)
            if len(story_list)>0:
                story_where = ' or '.join([" story like '%%%s%%' " % type for type in story_list])
                total_where_list.append("( %s ) " % story_where)
            message_where = []
            if len(str_query)>0:
                message_where =' or '.join( [" message like '%%%s%%' " %  str_query, " story like '%%%s%%' " %  str_query, " attachment_title like '%%%s%%' " %  str_query , " attachment_description like '%%%s%%' " %  str_query ])
                total_where_list.append("( %s ) " % message_where)

            if created_time_where!='' and created_time_comparator!='':
                total_where_list.append("( a.created_time %s '%s' ) " % ( created_time_comparator , created_time_where))

            if len(total_where_list) >0:
                total_where = ' and '.join(total_where_list)
                str_sql = "select a.post_id, a.created_time from fbposts_batch a left join posts_taxonomies b on a.post_id=b.post_id where %s order by created_time desc limit 10 " % total_where


            posts_queried= returnCursor(str_sql ,'abejita')

            post_ids = ['%s' % post.get('post_id') for post in  posts_queried]
        # post_ids.append('1')
        comma_ids = ','.join(post_ids)
        logging.info(comma_ids)
        token = self.get_available_posts_token(page_id)
        posts_url = 'https://graph.facebook.com/v2.6/?ids=%s&fields=permalink_url,story,attachments,message,link,type,created_time,picture,id&access_token=%s' % (comma_ids, token)
        logging.info(posts_url)
        return self.render_available_posts(page_id,posts_url, 'query', str_sql,post_ids )

    def get_available_posts_token(self, page_id):
        user = ndb.Key('User', int(self.user_id)).get()

        fb_user_token = ''
        token = ''
        if user:
            fb_user_token = user.fb_access_token

        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()

        if page.page_token =='' or page.page_token=='undefined':
            token = fb_user_token
        else:
            token = page.page_token

        if not token:
            token = getGeneralFBAccessToken()
        logging.info('Token: %s' % token)
        return token


    def render_available_posts(self,page_id,posts_url, method='data', str_sql='', posts_ordered=[]):
        params ={}
        params['str_sql'] = str_sql
        user = ndb.Key('User', int(self.user_id)).get()
        user_timezone = user.report_timezone
        if user.isadmin:
            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
        else:
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id)).get()
        fb_api_key = self.app.config.get('fb_api_key')
        fb_secret = self.app.config.get('fb_secret')
        params['fb_api_key']=fb_api_key
        params['fb_secret']=fb_secret

        action=self.request.get('action','')
        status=self.request.get('status','')
        video_id =self.request.get('video_id','')
        print '#'*30
        print action,status
        print 'posts_url: %s ' % posts_url
        r  =urlfetch.fetch(posts_url)
        if method=='data':
            data_posts=json.loads( r.content).get('data',[])
            paging_posts=json.loads(r.content).get('paging',{})
        elif method=='query':
            logging.info(json.loads( r.content).get('error',''))
            if json.loads( r.content).get('error','')!='':
                data_posts=[]
            else:
                data_posts=[ value for key, value in  json.loads( r.content).iteritems()]
            paging_posts={}
        logging.info('*'*30)
        # logging.info(data_posts)
        transformed_posts = []
        post_id_list = []
        for post in data_posts:
            post_id_list.append(post.get('id'))
            transformed_posts.append(post)
            attachments = post.get('attachments',{}).get('data',[])
            story = post.get('story','')
            strtime = post.get('created_time').split('+')[0]
            # logging.info('created_time str: %s' % strtime)
            umt_created_time =datetime.strptime(  strtime, "%Y-%m-%dT%H:%M:%S" )
            display_time = umt_created_time + timedelta(hours=user_timezone)
            post['story']=story
            if len(attachments)>0:
                attachment = attachments[0]
                attachment_description = attachment.get('description','')
                attachment_title = attachment.get('title','')
                post['attachment_description']=attachment_description
                post['attachment_title']=attachment_title
                post['created_time'] =display_time
        post_id_list.append('1')
        quoted_taxonomy_arr = ["'%s'" % post for post in  post_id_list]

        tax_query="select post_id, post_taxonomy from posts_taxonomies where post_id in (%s)" % ','.join(quoted_taxonomy_arr)

        # logging.info('tax_query: %s' % tax_query)
        taxonomy_arr = returnCursor(tax_query ,'abejita')
        taxonomy_dict ={}
        for row in taxonomy_arr:
            r_post_id = row.get('post_id')
            d_post_id=taxonomy_dict.get(r_post_id)
            if d_post_id:
                taxonomy_dict[r_post_id]['taxonomies'].append(row.get('post_taxonomy'))
            else:
                taxonomy_dict[r_post_id]={
                    'taxonomies':[ row.get('post_taxonomy')]
                }

        joined_transformed_posts = []

        for post in transformed_posts:
            post['taxonomies'] = taxonomy_dict.get( post.get('id'),{}).get('taxonomies',[])
            # logging.info('taxonomies: %s' % post['taxonomies'])
            joined_transformed_posts.append(post)
        joined_transformed_posts=sorted(joined_transformed_posts, key=lambda post: post["created_time"], reverse=True)
        first_created_time=''
        last_created_time=''

        if len(joined_transformed_posts)>0:
            first_created_time=joined_transformed_posts[0].get('created_time','')
            last_created_time=joined_transformed_posts[-1].get('created_time','')


        params['first_created_time']=first_created_time
        params['last_created_time']=last_created_time
        params['str_taxonomies'] = self.request.get('taxonomies').split(',') if self.request.get('taxonomies').strip()!='' else []
        params['str_types'] = self.request.get('types').split(',') if self.request.get('types').strip()!='' else []
        params['str_query'] = self.request.get('str_query').strip()
        # logging.info('cursor: %s' % json.dumps(taxonomy_arr))
        # logging.info('post_ids_list: %s' % post_id_list)
        params['timezone'] = user_timezone
        params['posts'] = joined_transformed_posts
        params['page']=page.to_dict()
        params['user'] =user

        params['page_id']=page_id
        params['page_token'] = page.page_token
        params['page_name'] = page.name
        params['page_general_taxonomies'] = page.general_taxonomies.split(',')
        params['page_photo_taxonomies'] = page.photo_taxonomies.split(',')
        params['page_link_taxonomies'] = page.link_taxonomies.split(',')
        params['page_video_taxonomies'] = page.video_taxonomies.split(',')
        all_taxonimies = list(set(page.general_taxonomies.split(',')+ page.photo_taxonomies.split(',') +page.link_taxonomies.split(',')+page.video_taxonomies.split(',')))
        all_taxonimies.sort()
        params['page_all_taxonomies'] = all_taxonimies
        params['page_previous'] =urllib.quote_plus(paging_posts.get('previous',''))
        params['page_next'] =urllib.quote_plus(paging_posts.get('next',''))

        self.render_template('available_posts.html',**params)


class ExtendGeneralFbUserTokenRequestHandler(BaseHandler):
    @user_required
    def get(self):
        params = {}
        user_id = int(self.user_id)
        fb_user_id  =  self.request.get('user_id')
        short_token = self.request.get('token')
        fb_api_key = self.app.config.get('fb_api_key')
        fb_secret = self.app.config.get('fb_secret')
        exchange_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&fb_exchange_token=%s&client_id=%s&client_secret=%s" % (short_token, fb_api_key, fb_secret)
        logging.info(exchange_url)
        logging.info('before')
        res = urlfetch.fetch(url=exchange_url)
        logging.info('exchange_token_response:%s' % res.content)
        logging.info('after')
        if res.status_code==200:
            j_res = json.loads(res.content)
            newtoken = j_res.get('access_token','')
            # newtoken = res.content.split('=')[1].replace('&expires','')
            db_access_token = localmodels.FBAccess_Token.get_or_insert('root_access_token')
            db_access_token.fb_access_token = newtoken
            db_access_token.put()
            self.response.out.write(newtoken)
        else:
            self.response.out.write('')

class ExtendFbUserTokenRequestHandler(BaseHandler):
    @user_required
    def get(self):
        params = {}
        user_id = int(self.user_id)
        fb_user_id  =  self.request.get('user_id')
        short_token = self.request.get('token')
        fb_api_key = self.app.config.get('fb_api_key')
        fb_secret = self.app.config.get('fb_secret')
        exchange_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&fb_exchange_token=%s&client_id=%s&client_secret=%s" % (short_token, fb_api_key, fb_secret)
        logging.info(exchange_url)
        logging.info('before')
        res = urlfetch.fetch(url=exchange_url)
        logging.info('exchange_token_response:%s' % res.content)
        logging.info('after')
        if res.status_code==200:
            j_res = json.loads(res.content)
            # newtoken = res.content.split('=')[1].replace('&expires','')
            newtoken = j_res.get('access_token','')
            db_user = ndb.Key('User', user_id).get()
            if db_user:
                logging.info('db_user exists: %s' % db_user)
                db_user.fb_access_token = newtoken
                db_user.put()
            else:
                logging.info('db_user_does not exist')
            self.response.out.write(newtoken)
        else:
            self.response.out.write('')
            logging.info(res.content)


        # self.response.out.write('')
class PagesHandler(BaseHandler):
    def extend_access_token(self,access_token):
        fb_api_key = self.app.config.get('fb_api_key')
        fb_secret = self.app.config.get('fb_secret')
        exchange_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&fb_exchange_token=%s&client_id=%s&client_secret=%s" % (access_token, fb_api_key, fb_secret)
        res = urlfetch.fetch(url=exchange_url)
        logging.info(res.content)
        logging.info('after')
        if res.status_code==200:
            # newtoken = res.content.split('=')[1].replace('&expires','')
            j_res = json.loads(res.content)
            newtoken = j_res.get('access_token','')
            # self.response.out.write(newtoken)
            return newtoken
        else:
            return ''

    @user_required
    def get(self):
        params={}
        user = ndb.Key('User',int(self.user_id)).get()
        params['user']=user
        if user.isadmin:
            pages = localmodels.Page.query().order(localmodels.Page.name).fetch()
        else:
            pages = localmodels.Page.query(localmodels.Page.user==ndb.Key('User',self.user_id), ancestor=ndb.Key('User',self.user_id)).order(localmodels.Page.name).fetch()
        action =self.request.get('action','')
        if action=='add':
            page_name = self.request.get('page_name')
            page_id = self.request.get('page_id')
            page = localmodels.Page.query(ndb.AND(localmodels.Page.user==ndb.Key('User',self.user_id), localmodels.Page.page_id==page_id), ancestor=ndb.Key('User',self.user_id)).get()
            page_token = self.request.get('page_token')
            user_access_token = self.request.get('user_access_token')
            pre_existent_pages = localmodels.Page.query(localmodels.Page.page_id==page_id).fetch()
            logging.info(page_token)
            logging.info(user_access_token)
            if user_access_token!='':
                user.fb_access_token= user_access_token
                user.put()
            if page:
                page_token = self.extend_access_token(page_token)
                page.page_token=page_token
                page.put()
            else:
                newpage = localmodels.Page(id=int(page_id),parent=ndb.Key('User',self.user_id),name=page_name, page_id=page_id, page_token=page_token, user=ndb.Key('User',self.user_id) )
                newpage.put()


            logging.info("Looking for pre_existing_page:%s\n%s\n%s " % (page_id, pre_existent_pages, len(pre_existent_pages)))
            if len(pre_existent_pages)==0:
                logging.info('##### will add page to queue')
                taskurl = self.uri_for('task-download-page-handler')
                taskqueue.add(url=taskurl, params={
                              'page_id': page_id,
                              'user_id' : self.user_id,
                              'days': 33
                              })
                # taskurl = self.uri_for('get_page_fans')
                # taskqueue.add(url=taskurl, params={
                #               'page_id': page_id,
                #               })
            else:
                logging.info('##### will not add page to queue')
            self.redirect_to('pages')
        elif action=='delete':
            page_id = self.request.get('page_ndb_key')
            page = ndb.Key('Page', int(page_id), parent=ndb.Key('User',self.user_id))
            logging.info(page.get())
            page.delete()
            self.redirect_to('pages')
        else:
            params['pages'] =pages
            logging.info(pages)
            self.render_template('pages.html',**params)

class ConfigPageHandler(BaseHandler):
    @user_required
    def get(self):
        params={}
        page_ndb_key=self.request.get('page_ndb_key','')
        page  = ndb.Key('Page',int(page_ndb_key),parent=ndb.Key('User',self.user_id)).get()
        page_id = page.page_id
        action = self.request.get('action','get')
        fb_api_key=self.app.config.get('fb_api_key')
        page_token = page.page_token
        page_subscriptions_url="https://graph.facebook.com/%s/subscribed_apps/?access_token=%s" % (page.page_id, page.page_token)
        page_dict = page.to_dict()
        params['delete_links'] = page_dict.get('delete_links', False)
        params['delete_pages'] = page_dict.get('delete_pages', False)
        params['delete_long_comment'] = page_dict.get('delete_long_comment', False)
        expireddate = datetime.datetime.today().strftime('%Y-%m-%d')
        # dk = hashlib.pbkdf2_hmac('sha256', b'%s%s' % (page.page_id, expireddate), b'%s' % HASH_SALT, 100000)
        dk = hash_custom( b'%s%s' % (page.page_id, expireddate), b'%s' % HASH_SALT)
        expireddate_token = binascii.hexlify(dk)
        params['page_id']=page.page_id
        params['expireddate'] = expireddate
        params['expireddate_token'] = expireddate_token
        params['share_except_fbuser_url'] ='http://%s%s' % (self.request.host, self.uri_for('confirm-exception', pageid=page.page_id, expiredate =expireddate, etoken=expireddate_token))
        logging.info(page_subscriptions_url)
        if action=='get':
            plan = localmodels.CustomerPlan.query(localmodels.CustomerPlan.user==ndb.Key('User',self.user_id)).get()
            params['fb_api_key'] = fb_api_key
            subscriptions = urlfetch.fetch(page_subscriptions_url)
            subscriptions = json.loads(subscriptions.content).get('data',[])
            subscribed = False
            for subscription in subscriptions:
                logging.info(subscription)
                if fb_api_key==subscription.get('id',''):
                    subscribed=True
                    break
            logging.info(subscribed)
            params['subscribed'] = subscribed

            if plan:
                params['plan']= plan.plan
            else:
                params['plan']= 'free'

            params['page']= page
            self.render_template('config-page.html',**params)
        elif action=='activateFilters':
            logging.info('activateFilters')
            page_subscriptions_url="https://graph.facebook.com/%s/subscribed_apps/?access_token=%s" % (page.page_id, page.page_token)
            # subscriptions = requests.post(page_subscriptions_url)
            subscriptions = urlfetch.fetch(page_subscriptions_url,method=urlfetch.POST)
            logging.info(subscriptions.content)
            result ={'status':'ok', 'result': json.loads(subscriptions.content)}
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(json.dumps(result))
        elif action=='deactivateFilters':
            logging.info('deactivateFilters')
            page_subscriptions_url="https://graph.facebook.com/%s/subscribed_apps/?access_token=%s" % (page.page_id, page.page_token)
            subscriptions = urlfetch.fetch(page_subscriptions_url, method=urlfetch.DELETE)
            logging.info(subscriptions.content)
            result ={'status':'ok' , 'result': json.loads(subscriptions.content)}
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(json.dumps(result))
        elif action=='update':
            field = self.request.get('field')
            field_type = self.request.get('field_type')
            field_value = self.request.get('field_value')
            if field!='':
                pages = localmodels.Page.query(localmodels.Page.page_id==str(page_id))
                for each_page in pages:
                    update_value = {}
                    if field_type=='boolean':
                        if field_value=='true':
                            update_value[field] = True
                        else:
                            update_value[field] = False
                    else:
                        update_value[field] = field_value
                    each_page.populate(**update_value)
                    each_page.put()
            result ={'status':'ok' }
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(json.dumps(result))

    @user_required
    def post(self):
        pass


class RealTimeCounterHandler(BaseHandler):
    def get(self,post_id):
        params = {}
        user = ndb.Key('User', int(self.user_id)).get()
        type = self.request.get('type','')
        access_token = user.fb_access_token
        params['post_id']=post_id
        params['access_token']=access_token
        if type=='fixed':
            picture = ''
            picture_url = 'https://graph.facebook.com/%s/?fields=message,full_picture,picture.type(large)&access_token=%s' % ( post_id ,access_token)
            print picture_url
            r = urlfetch.fetch(picture_url)

            jr  =json.loads(r.content)
            picture = jr.get('full_picture','')
            post_message = jr.get('message','')
            params['post_message'] = post_message
            params['picture'] =picture
            self.render_template('real_time_fixed.html', **params)
        elif type=="video":
            self.render_template('real_time_videos.html', **params)
        else:
            self.render_template('real_time.html', **params)

class ContactHandler(BaseHandler):
    """
    Handler for Contact Form
    """

    def get(self):
        """ Returns a simple HTML for contact form """

        if self.user:
            user_info = self.user_model.get_by_id(long(self.user_id))
            if user_info.name or user_info.last_name:
                self.form.name.data = user_info.name + " " + user_info.last_name
            if user_info.email:
                self.form.email.data = user_info.email
        params = {
            "exception": self.request.get('exception')
        }

        return self.render_template('contact.html', **params)

    def post(self):
        """ validate contact form """
        if not self.form.validate():
            return self.get()

        remote_ip = self.request.remote_addr
        city = i18n.get_city_code(self.request)
        region = i18n.get_region_code(self.request)
        country = i18n.get_country_code(self.request)
        coordinates = i18n.get_city_lat_long(self.request)
        user_agent = self.request.user_agent
        exception = self.request.POST.get('exception')
        name = self.form.name.data.strip()
        email = self.form.email.data.lower()
        message = self.form.message.data.strip()
        template_val = {}

        challenge = self.request.POST.get('recaptcha_challenge_field')
        response = self.request.POST.get('recaptcha_response_field')
        cResponse = captcha.submit(
            challenge,
            response,
            self.app.config.get('captcha_private_key'),
            remote_ip)

        if re.search(r"(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})", message) and not cResponse.is_valid:
            chtml = captcha.displayhtml(
            public_key=self.app.config.get('captcha_public_key'),
            use_ssl=(self.request.scheme == 'https'),
            error=None)
            if self.app.config.get('captcha_public_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE" or \
                            self.app.config.get('captcha_private_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE":
                chtml = '<div class="alert alert-danger"><strong>Error</strong>: You have to ' \
                        '<a href="http://www.google.com/recaptcha/whyrecaptcha" target="_blank">sign up ' \
                        'for API keys</a> in order to use reCAPTCHA.</div>' \
                        '<input type="hidden" name="recaptcha_challenge_field" value="manual_challenge" />' \
                        '<input type="hidden" name="recaptcha_response_field" value="manual_challenge" />'
            template_val = {
                "captchahtml": chtml,
                "exception": exception,
                "message": message,
                "name": name,

            }
            if not cResponse.is_valid and response is None:
                _message = _("Please insert the Captcha in order to finish the process of sending the message")
                self.add_message(_message, 'warning')
            elif not cResponse.is_valid:
                _message = _('Wrong image verification code. Please try again.')
                self.add_message(_message, 'danger')


            return self.render_template('contact.html', **template_val)
        else:
            try:
                # parsing user_agent and getting which os key to use
                # windows uses 'os' while other os use 'flavor'
                ua = httpagentparser.detect(user_agent)
                _os = ua.has_key('flavor') and 'flavor' or 'os'

                operating_system = str(ua[_os]['name']) if "name" in ua[_os] else "-"
                if 'version' in ua[_os]:
                    operating_system += ' ' + str(ua[_os]['version'])
                if 'dist' in ua:
                    operating_system += ' ' + str(ua['dist'])

                browser = str(ua['browser']['name']) if 'browser' in ua else "-"
                browser_version = str(ua['browser']['version']) if 'browser' in ua else "-"

                template_val = {
                    "name": name,
                    "email": email,
                    "ip": remote_ip,
                    "city": city,
                    "region": region,
                    "country": country,
                    "coordinates": coordinates,

                    "browser": browser,
                    "browser_version": browser_version,
                    "operating_system": operating_system,
                    "message": message
                }
            except Exception as e:
                logging.error("error getting user agent info: %s" % e)

            try:
                subject = _("Contact") + " " + self.app.config.get('app_name')
                # exceptions for error pages that redirect to contact
                if exception != "":
                    subject = "{} (Exception error: {})".format(subject, exception)

                body_path = "emails/contact.txt"
                body = self.jinja2.render_template(body_path, **template_val)

                email_url = self.uri_for('taskqueue-send-email')
                taskqueue.add(url=email_url, params={
                    'to': self.app.config.get('contact_recipient'),
                    'subject': subject,
                    'body': body,
                    'sender': self.app.config.get('contact_sender'),
                })

                message = _('Your message was sent successfully.')
                self.add_message(message, 'success')
                return self.redirect_to('contact')

            except (AttributeError, KeyError), e:
                logging.error('Error sending contact form: %s' % e)
                message = _('Error sending the message. Please try again later.')
                self.add_message(message, 'danger')
                return self.redirect_to('contact')

    @webapp2.cached_property
    def form(self):
        return forms.ContactForm(self)


class SecureRequestHandler(BaseHandler):
    """
    Only accessible to users that are logged in
    """

    @user_required
    def get(self, **kwargs):
        user_session = self.user
        user_session_object = self.auth.store.get_session(self.request)

        user_info = self.user_model.get_by_id(long(self.user_id))
        user_info_object = self.auth.store.user_model.get_by_auth_token(
            user_session['user_id'], user_session['token'])

        try:
            params = {
                "user_session": user_session,
                "user_session_object": user_session_object,
                "user_info": user_info,
                "user_info_object": user_info_object,
                "userinfo_logout-url": self.auth_config['logout_url'],
            }
            return self.render_template('secure_zone.html', **params)
        except (AttributeError, KeyError), e:
            return "Secure zone error:" + " %s." % e


class DeleteAccountHandler(BaseHandler):

    @user_required
    def get(self, **kwargs):
        chtml = captcha.displayhtml(
            public_key=self.app.config.get('captcha_public_key'),
            use_ssl=(self.request.scheme == 'https'),
            error=None)
        if self.app.config.get('captcha_public_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE" or \
                        self.app.config.get('captcha_private_key') == "PUT_YOUR_RECAPCHA_PUBLIC_KEY_HERE":
            chtml = '<div class="alert alert-danger"><strong>Error</strong>: You have to ' \
                    '<a href="http://www.google.com/recaptcha/whyrecaptcha" target="_blank">sign up ' \
                    'for API keys</a> in order to use reCAPTCHA.</div>' \
                    '<input type="hidden" name="recaptcha_challenge_field" value="manual_challenge" />' \
                    '<input type="hidden" name="recaptcha_response_field" value="manual_challenge" />'
        params = {
            'captchahtml': chtml,
        }
        return self.render_template('delete_account.html', **params)

    def post(self, **kwargs):
        challenge = self.request.POST.get('recaptcha_challenge_field')
        response = self.request.POST.get('recaptcha_response_field')
        remote_ip = self.request.remote_addr

        cResponse = captcha.submit(
            challenge,
            response,
            self.app.config.get('captcha_private_key'),
            remote_ip)

        if cResponse.is_valid:
            # captcha was valid... carry on..nothing to see here
            pass
        else:
            _message = _('Wrong image verification code. Please try again.')
            self.add_message(_message, 'danger')
            return self.redirect_to('delete-account')

        if not self.form.validate() and False:
            return self.get()
        password = self.form.password.data.strip()

        try:

            user_info = self.user_model.get_by_id(long(self.user_id))
            auth_id = "own:%s" % user_info.username
            password = utils.hashing(password, self.app.config.get('salt'))

            try:
                # authenticate user by its password
                user = self.user_model.get_by_auth_password(auth_id, password)
                if user:
                    # Delete Social Login
                    for social in models_boilerplate.SocialUser.get_by_user(user_info.key):
                        social.key.delete()

                    user_info.key.delete()

                    ndb.Key("Unique", "User.username:%s" % user.username).delete_async()
                    ndb.Key("Unique", "User.auth_id:own:%s" % user.username).delete_async()
                    ndb.Key("Unique", "User.email:%s" % user.email).delete_async()

                    #TODO: Delete UserToken objects

                    self.auth.unset_session()

                    # display successful message
                    msg = _("The account has been successfully deleted.")
                    self.add_message(msg, 'success')
                    return self.redirect_to('home')


            except (InvalidAuthIdError, InvalidPasswordError), e:
                # Returns error message to self.response.write in
                # the BaseHandler.dispatcher
                message = _("Incorrect password! Please enter your current password to change your account settings.")
                self.add_message(message, 'danger')
            return self.redirect_to('delete-account')

        except (AttributeError, TypeError), e:
            login_error_message = _('Your session has expired.')
            self.add_message(login_error_message, 'danger')
            self.redirect_to('login')

    @webapp2.cached_property
    def form(self):
        return forms.DeleteAccountForm(self)


class AudiencesHandler(BaseHandler):
    def get(self):
        pass

class PublicRenderPostIDtHandler(BaseHandler):
    def get(self,post_id):
        params={}
        select_type = self.request.get('type','video')
        # arr_post_id = post_id.split('_')
        # page_id = arr_post_id[0]
        # post = arr_post_id[1]
        render_html=""
        if select_type=='video':
            render_html="""
            <html>
                <head>
                  <title>Your Website Title</title>
                </head>
                <body>
                    Test
                  <!-- Load Facebook SDK for JavaScript -->
                  <iframe name="alex" id="alex" src="https://www.facebook.com/plugins/video.php?href=https://www.facebook.com/facebook/videos/%s/&width=500&show_text=false&appId=1283557448348524&height=280" width="500" height="280" style="border:none;overflow:hidden" scrolling="no" frameborder="0" allowTransparency="true"></iframe>
                </body>
            </html>
            """ % post_id
        elif select_type=='photo':
            parts = post_id.split('_')
            if len(parts)>1:
                page_id = parts[0]
                post=parts[1]
                render_html="""
                <html>
                    <head></head>
                    <body>
                    <iframe src="https://www.facebook.com/plugins/post.php?href=https://www.facebook.com/%s/posts/%s/&width=500&show_text=true&appId=1283557448348524&height=557" width="500" height="557" style="border:none;overflow:hidden" scrolling="no" frameborder="0" allowTransparency="true"></iframe>
                    </body>
                </html>
                """ % (page_id, post)
            else:
                render_html="""
                <html>
                    <head></head>
                    <body>
                    Post not found %s
                    </body>
                </html>
                """ % post_id
        elif select_type=='link':
            pass
        self.response.out.write(render_html)


class PostStatsHandler(BaseHandler):
    def get(self, post_id):
        params={}
        page_id = ""
        parts = post_id.split("_")
        if len(parts)>1:
            page_id = parts[0]
            post = parts[1]

            page = localmodels.Page.query(localmodels.Page.page_id==page_id).get()
            params['page_id'] = page_id
            params['page'] = page
            params['post_id']=post_id
            self.render_template("post_stats.html", **params)
        else:
            self.response.out.write("Error post not found")

    def post(self):
        pass

def get_msft_vision_api_metadata(picture_url):
    msft_key='ccaab9a15ebf44e7812ac18efa7bc708'
    ########### Python 2.7 #############
    import httplib, urllib, base64

    headers = {
        # Request headers
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Key': msft_key,
    }

    params = urllib.urlencode({
        # Request parameters
        'visualFeatures': 'Tags,Description',
        'language': 'en',
    })
    image_data = {"url" : picture_url}
    s_image_data = json.dumps(image_data)
    try:
        conn = httplib.HTTPSConnection('westus.api.cognitive.microsoft.com')

        conn.request("POST", "/vision/v1.0/analyze?%s" % params, s_image_data, headers)
        response = conn.getresponse()
        data = response.read()
        jdata =  json.loads(data)
        conn.close()
        return jdata
    except Exception as e:
        print("[Errno {0}] {1}".format(e.errno, e.strerror))

def get_as_base64(url):
    return base64.b64encode(urlfetch.fetch(url).content)

def get_cloud_vision_api_metadata(picture_url):
    api_key='AIzaSyCA6mWOqKOS934jXwNtmY-KAjt-Q5vJhfU'
    url = "https://vision.googleapis.com/v1/images:annotate?key=%s" % api_key
    headers = {'Content-Type': 'application/json'}
    img_base64=get_as_base64(picture_url)
    request_data={
      "requests": [
        {
          "image": {
            "content": img_base64,
          },
          "features": [
           {
              "type": "LABEL_DETECTION" ,
              "maxResults": 20,
            },
            {
              "type": "IMAGE_PROPERTIES" ,
              "maxResults": 20,
            },
            {
              "type": "WEB_DETECTION" ,
              "maxResults": 20,
            }

          ]
        }
      ],
    }
    logging.info(request_data)
    r = urlfetch.fetch(url,headers=headers, method=urlfetch.POST, payload=json.dumps(request_data))
    return json.loads(r.content)

class CloudVisionHandler(BaseHandler):
    def get(self):
        post_id = self.request.get("post_id")
        if post_id:
            access_token = getGeneralFBAccessToken()
            url = 'https://graph.facebook.com/%s/?fields=message,full_picture,picture.type(large)&access_token=%s' % ( post_id ,access_token)
            r =urlfetch.fetch(url)
            rj =json.loads(r.content)
            logging.info(rj)
            full_picture = rj.get('full_picture','')
            picture = rj.get('picture','')
            params = {}
            params['full_picture']=full_picture
            params['picture']=picture
            metadata1 = {"hola":"como estas"}
            metadata2 = {"hola":"como estas"}
            try:
                metadata1 = get_msft_vision_api_metadata(full_picture)
            except:
                metadata1 = {}
            json2html = Json2Html()
            params['metadata1']=json2html.convert(json.dumps(metadata1), table_attributes='class="table table-striped"')
            try:
                metadata2 =get_cloud_vision_api_metadata(full_picture)
            except:
                metadata2={}
            params['metadata2'] = json2html.convert(json.dumps(metadata2), table_attributes='class="table table-striped"')
            self.render_template('picture_metadata.html', **params)

        else:
            self.response.out.write('404: Post not found')
