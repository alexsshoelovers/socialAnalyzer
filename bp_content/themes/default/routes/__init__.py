"""
Using redirect route instead of simple routes since it supports strict_slash
Simple route: http://webapp-improved.appspot.com/guide/routing.html#simple-routes
RedirectRoute: http://webapp-improved.appspot.com/api/webapp2_extras/routes.html#webapp2_extras.routes.RedirectRoute
"""
from webapp2_extras.routes import RedirectRoute
from bp_content.themes.default.handlers import handlers

secure_scheme = 'https'

# Here go your routes, you can overwrite boilerplate routes (bp_includes/routes)

_routes = [
    RedirectRoute('/secure/', handlers.SecureRequestHandler, name='secure', strict_slash=True),
    RedirectRoute('/settings/delete_account', handlers.DeleteAccountHandler, name='delete-account', strict_slash=True),
    RedirectRoute('/contact/', handlers.ContactHandler, name='contact', strict_slash=True),
    RedirectRoute('/createLiveCounter/', handlers.CreateLiveCounter, name='create-counter', strict_slash=True),
    RedirectRoute('/extendFbUserToken/', handlers.ExtendFbUserTokenRequestHandler, name='extend_fb_user_token', strict_slash=True),
    RedirectRoute('/pages/', handlers.PagesHandler, name='pages', strict_slash=True),
    RedirectRoute('/pages/<page_id>/config_page/', handlers.PagesConfigHandler, name='page_config', strict_slash=True),
    RedirectRoute('/taxonomy/<page_id>/', handlers.TaxonomyHandler, name='taxonomy', strict_slash=True),
    RedirectRoute('/config_page/', handlers.ConfigPageHandler, name='config_page', strict_slash=True),
    RedirectRoute('/available_posts/<page_id>/', handlers.AvailablePostsHandler, name='available-posts', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/overview', handlers.PageStatsOverviewHandler, name='page-stats', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/overview', handlers.PageStatsOverviewHandler, name='page-stats-overview', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/fans', handlers.PageStatsFansHandler, name='page-stats-fans', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/content', handlers.PageStatsContentHandler, name='page-stats-content', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/engagement', handlers.PageStatsEngagementHandler, name='page-stats-engagement', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/publishing', handlers.PageStatsPublishingHandler, name='page-stats-publishing', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/lives', handlers.PageStatsLivesHandler, name='page-stats-lives', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/shares', handlers.PageStatsSharesHandler, name='page-stats-shares', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/with', handlers.PageStatsWithHandler, name='page-stats-with', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/clicks', handlers.PageStatsClicksHandler, name='page-stats-clicks', strict_slash=True),
    RedirectRoute('/page_stats/<page_id>/reach_geo', handlers.PageStatsReachGeoHandler, name='page-stats-reach-distribution', strict_slash=True),
    RedirectRoute('/schedule_live_video/<page_id>/', handlers.ScheduleLiveHandler, name='schedule-live', strict_slash=True),
    RedirectRoute('/realtime_counter/<post_id>/', handlers.RealTimeCounterHandler, name='realtime_counter', strict_slash=True),
    RedirectRoute('/general_config/', handlers.GeneralConfigHandler, name='general-config', strict_slash=True),
    RedirectRoute('/testMysql/', handlers.TestMySQL, name='testMySQL', strict_slash=True),
    RedirectRoute('/update_post_taxonomy/', handlers.UpdatePostTaxonomyHandler, name='update-post-taxonomy', strict_slash=True),
    RedirectRoute('/taskqueue_updata_mysql/', handlers.UpdateMySQLHandler, name='update-mysql-handler', strict_slash=True),
    RedirectRoute('/taskqueue_download_page/', handlers.task_downloadPageHandler, name='task-download-page-handler', strict_slash=True),
    RedirectRoute('/download_page/<page_id>', handlers.trigger_downloadPageHandler, name='download-page-handler', strict_slash=True),
    RedirectRoute('/query/<page_id>/', handlers.jsonQuery, name='jsonQuery', strict_slash=True),
    RedirectRoute('/crontasks/fetch_new_posts/', handlers.fetchNewPostsHandler, name='fetch-new-posts', strict_slash=True),
    RedirectRoute('/crontasks/fetch_new_posts_for_days/<number_of_days>/', handlers.fetchNewPostsDaysHandler, name='fetch-new-posts-days', strict_slash=True),
    RedirectRoute('/taskqueue_download_page_fetch_page_fans/', handlers.taskGetPageFansInDate, name='get_page_fans', strict_slash=True),
    RedirectRoute('/taskqueue_download_page_last_page_fans/', handlers.taskGetLastPageFans, name='get_last_page_fans', strict_slash=True),
    RedirectRoute('/taskqueue_daily_download_page_fans/', handlers.taskGetDailyLastPageFans, name='get_daily_page_fans', strict_slash=True),
    RedirectRoute('/taskqueue_get_public_page_fans/', handlers.taskGetPublicPageFans, name='get_public_page_fans', strict_slash=True),
    RedirectRoute('/extendGeneralFbUserToken/', handlers.ExtendGeneralFbUserTokenRequestHandler, name='extend_general_fb_user_token', strict_slash=True),

]

def get_routes():
    return _routes

def add_routes(app):
    if app.debug:
        secure_scheme = 'http'
    for r in _routes:
        app.router.add(r)
