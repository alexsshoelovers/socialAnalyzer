
# Put here your models or extend User model from bp_includes/models.py

from google.appengine.ext import ndb
from bp_includes import models
# Put here your models or extend User model from bp_includes/models.py
class cronJobConfig(ndb.Model):
    user = ndb.KeyProperty(kind=models.User)
    webhook_address = ndb.StringProperty(default = '')
    frequency = ndb.IntegerProperty(default = 60*60)

class CustomerPlan(ndb.Model):
    user = ndb.KeyProperty(kind=models.User)
    plan = ndb.StringProperty(default='free')
    #: Creation date.
    created = ndb.DateTimeProperty(auto_now_add=True)
    #: Modification date.
    updated = ndb.DateTimeProperty(auto_now=True)
    status = ndb.StringProperty(default = 'active')

class HiddenMessage(ndb.Model):
    page_id = ndb.StringProperty(default='')
    message_id = ndb.StringProperty(default='')
    message = ndb.TextProperty(default='')
    message_obj = ndb.TextProperty(default='')
    training_data = ndb.TextProperty(default ='')

class Page(ndb.Model):
    user = ndb.KeyProperty(kind=models.User)
    name = ndb.StringProperty(default='')
    page_token = ndb.StringProperty(default='')
    page_id = ndb.StringProperty(default='')
    #: Creation date.
    created = ndb.DateTimeProperty(auto_now_add=True)
    #: Modification date.
    updated = ndb.DateTimeProperty(auto_now=True)
    delete_links= ndb.BooleanProperty(default=False)
    delete_pages= ndb.BooleanProperty(default=False)
    delete_long_comment = ndb.BooleanProperty(default=False)
    rt_counters = ndb.BooleanProperty(default=False)
    comment_long_int  =ndb.IntegerProperty(default=150)
    user_exception_list = ndb.JsonProperty()
    general_taxonomies = ndb.TextProperty(default="")
    link_taxonomies = ndb.TextProperty(default="")
    video_taxonomies = ndb.TextProperty(default="")
    photo_taxonomies = ndb.TextProperty(default="")
    frequent_post_insight_update =ndb.BooleanProperty(default=False)


class Like(ndb.Model):
    user = ndb.KeyProperty(kind=models.User)
    name = ndb.StringProperty(default='')
    page_token = ndb.StringProperty(default='')
    page_id = ndb.StringProperty(default='')
    #: Creation date.
    created = ndb.DateTimeProperty(auto_now_add=True)
    #: Modification date.
    updated = ndb.DateTimeProperty(auto_now=True)

class PagePost(ndb.Model):
    page = ndb.KeyProperty(kind=Page)
    comment_text = ndb.TextProperty()
    url = ndb.StringProperty()
    bitlyurl = ndb.StringProperty()
    #: Creation date.
    created = ndb.DateTimeProperty(auto_now_add=True)
    #: Modification date.
    updated = ndb.DateTimeProperty(auto_now=True)

class FBAccess_Token(ndb.Model):
    fb_access_token= ndb.StringProperty(default='')
    created = ndb.DateTimeProperty(auto_now_add=True)
    #: Modification date.
    updated = ndb.DateTimeProperty(auto_now=True)
