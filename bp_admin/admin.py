# -*- coding: utf-8 -*-
from bp_includes.lib.basehandler import BaseHandler
from google.appengine.api import users
from bp_content.themes.default.handlers import models
from bp_includes.lib.decorators import user_required

class AdminLogoutHandler(BaseHandler):
    def get(self):
        self.redirect(users.create_logout_url(dest_url=self.uri_for('home')))

class AdminFBAccessTokenHandler(BaseHandler):
    @user_required
    def get(self):
        params={}
        db_access_token = models.FBAccess_Token.get_or_insert('root_access_token')
        fb_access_token=db_access_token.fb_access_token
        params['fb_access_token']="**************%s" % fb_access_token[-4:-1]
        self.render_template('adminFBAccessToken.html',**params)


