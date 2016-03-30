from gevent import monkey; monkey.patch_all()

import os
import re
from six.moves.urllib.parse import quote

from bottle import Bottle, request, redirect

from urlrewrite.rewriterapp import RewriterApp


# ============================================================================
class WebRecApp(RewriterApp):
    DEF_REC_NAME = 'my_recording'

    PATHS = {'live': '{replay_host}/live/resource/postreq?url={url}&closest={closest}',
             'record': '{record_host}/record/live/resource/postreq?url={url}&closest={closest}&param.recorder.user={user}&param.recorder.coll={coll}&param.recorder.rec={rec}',
             'replay': '{replay_host}/replay/resource/postreq?url={url}&closest={closest}&param.replay.user={user}&param.replay.coll={coll}&param.replay.rec={rec}',
             'replay-coll': '{replay_host}/replay-coll/resource/postreq?url={url}&closest={closest}&param.user={user}&param.coll={coll}'
            }

    WB_URL_RX = re.compile('((\d*)([a-z]+_)?/)?(https?:)?//.*')

    def __init__(self, app=None):
        super(WebRecApp, self).__init__(True)

        if not app:
            app = Bottle()
        self.app = app

        self.record_host = os.environ.get('RECORD_HOST', 'http://localhost:8010')
        self.replay_host = os.environ.get('REPLAY_HOST', 'http://localhost:8080')

        self.init_routes()

    def init_routes(self):
        # REDIRECTS
        @self.app.route(['/record/<wb_url:path>', '/anonymous/record/<wb_url:path>'])
        def redir_anon_rec(wb_url):
            new_url = '/anonymous/{rec}/record/{url}'.format(rec=self.DEF_REC_NAME,
                                                             url=wb_url)
            return self.redirect_with_query(new_url)

        @self.app.route(['/replay/<wb_url:path>'])
        def redir_anon_replay(wb_url):
            new_url = '/anonymous/{url}'.format(url=wb_url)
            return self.redirect_with_query(new_url)

        # LIVE DEBUG
        @self.app.route('/live/<wb_url:path>')
        def live(wb_url):
            request.path_shift(1)

            return self.render_anon_content(wb_url, rec='', type='live')

        # ANON ROUTES
        @self.app.route('/anonymous/<rec_name>/record/<wb_url:path>')
        def anon_record(rec_name, wb_url):
            request.path_shift(3)

            return self.render_anon_content(wb_url, rec=rec_name, type='record')

        @self.app.route('/anonymous/<wb_url:path>')
        def anon_replay(wb_url):
            rec_name = '*'

            # recording replay
            if not self.WB_URL_RX.match(wb_url) and '/' in wb_url:
                rec_name, wb_url = wb_url.split('/', 1)

                if not wb_url:
                    wb_url = rec_name
                    rec_name = '*'

            if rec_name == '*':
                request.path_shift(1)
                type_ = 'replay-coll'

            else:
                request.path_shift(2)
                type_ = 'replay'

            return self.render_anon_content(wb_url, rec=rec_name, type=type_)

        # ERRORS
        @self.app.error(404)
        def not_found(error):
            if isinstance(error.exception, dict):
                msg = 'The url <b>{url}</b> was not found in the archive'
                msg = msg.format(url=error.exception['url'])
            else:
                msg = 'Url Not Found'

            return msg

    def redirect_with_query(self, url):
        if request.query_string:
            url += '?' + request.query_string

        redirect(url)

    def render_anon_content(self, wb_url, rec, type):
        sesh = request.environ['webrec.session']

        user = sesh.anon_user.replace('@anon-', 'anon/')
        coll = 'anonymous'

        if not sesh.is_anon():
            sesh.set_anon()

        if request.query_string:
            wb_url += '?' + request.query_string

        return self.render_content(wb_url, user=user,
                                           coll=coll,
                                           rec=rec,
                                           type=type)

    def get_upstream_url(self, url, closest, kwargs):
        type = kwargs['type']
        upstream_url = self.PATHS[type].format(url=quote(url),
                                               closest=closest,
                                               record_host=self.record_host,
                                               replay_host=self.replay_host,
                                               **kwargs)

        return upstream_url

    def _add_custom_params(self, cdx, kwargs):
        type = kwargs['type']
        if type in ('live', 'record'):
            cdx['is_live'] = 'true'


# ============================================================================
if __name__ == "__main__":
    application = WebRecApp().app


