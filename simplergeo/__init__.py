import urllib
import httplib
from urlparse import urljoin
import oauth2 as oauth
import logging
import time

try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5

try:
    import simplejson as json
except ImportError:
    import json

class simplergeo:

    def __init__(self, **kwargs):

        token = kwargs.get('token', None)
        secret = kwargs.get('secret', None)
        api_version = kwargs.get('api_version', '0.1')
        host = kwargs.get('host', 'api.simplegeo.com')
        port = kwargs.get('port', 80)

        self.host = host
        self.port = port

        self.realm = 'http://%s' % host
        self.consumer = oauth.Consumer(token, secret)
        self.token = token
        self.secret = secret
        self.api_version = api_version
        self.signature = oauth.SignatureMethod_HMAC_SHA1()
        self.uri = "http://%s:%s" % (host, port)
        self.http = httplib.HTTPConnection(self.host, self.port)

        if kwargs.get('debug', False):
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def is_success(self, head):

        status = head.get('status', None)

        if status and status.startswith('2'):
            return True

        return False

    def execute_request(self, endpoint, **kwargs):

        method = kwargs.get('method', 'GET')
        args = kwargs.get('args', None)

        body = None
        params = {}

        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        endpoint = '/' + self.api_version + endpoint

        if method == "GET" and isinstance(args, dict):
            endpoint = endpoint + '?' + urllib.urlencode(args)
        else:
            if isinstance(args, dict):
                body = urllib.urlencode(args)
            else:
                body = args

        oauth_endpoint = self.uri + endpoint

        request = oauth.Request.from_consumer_and_token(self.consumer, http_method=method, http_url=oauth_endpoint, parameters=params)
        request.sign_request(self.signature, self.consumer, None)

        headers = request.to_header(self.realm)
        headers['User-Agent'] = 'SimplerGeo v%s' % self.api_version

        logging.debug('%s %s' % (method, endpoint))
        logging.debug(headers)
        logging.debug(body)

        try:
            self.http.request(method, endpoint, body, headers)
        except Exception, e:
            logging.error('HTTP request (%s) failed: %s' % (endpoint, e))
            return { 'status' : '999' }, str(e)

        rsp = self.http.getresponse()

        body = rsp.read()
        head = { 'status' : str(rsp.status) }

        for k,v in rsp.getheaders():
            head[k] = v

        logging.debug(head)
        logging.debug(body)

        return (head, body)

    def execute_request_simple(self, endpoint, **kwargs):

        head, body = self.execute_request(endpoint, **kwargs)

        if not self.is_success(head):
            return { 'stat' : 'fail', 'error' : head['status'], 'message' : body }

        if not body:
            return { 'stat' : 'ok' }
            return True

        body = json.loads(body)
        body['stat'] = 'ok'

        return body

# helper class for working with layers specifically

class layer (simplergeo):

    def __init__ (self, **kwargs):
        self.layer = kwargs['layer']
        simplergeo.__init__(self, **kwargs)

    def add_point(self, **kwargs):

        created = int(time.time())

        if kwargs.get('created', False):
            created = kwargs['created']
        else:
            created = int(time.time())

        args = {
            'geometry' : {
                'type' : 'Point',
                'coordinates' : [ kwargs['lon'], kwargs['lat'] ],
                },
            'created' : created,
            'properties' : {},
            'type' : 'Feature',
            }

        if kwargs.get('properties', False):
            args['properties'] = kwargs['properties']

            if not args['properties'].get('type', False):
                args['properties']['type'] = 'object'

        req = '/records/%s/%s.json' % (self.layer, kwargs['id'])

        return self.execute_request_simple(req, method='PUT', args=json.dumps(args))

    def list_points(self, lat=0, lon=0):

        req = 'records/%s/nearby/%s,%s.json' % (self.layer, lat, lon)
        return self.execute_request_simple(req)

# helper class for loading simplegeo configs from a config
# file / command line interface

class cli (simplergeo):

    def __init__(self, **kwargs):

        import optparse
        import ConfigParser

        parser = optparse.OptionParser()

        parser.add_option('-c', '--config', dest='config',
                          help='Path to your config file',
                          action='store')

        options, args = parser.parse_args()

        cfg = ConfigParser.ConfigParser()
        cfg.read(options.config)

        kwargs['token'] = cfg.get('simplegeo', 'oauth_token')
        kwargs['secret'] = cfg.get('simplegeo', 'oauth_secret')

        simplergeo.__init__(self, **kwargs)
        self.cfg = cfg

if __name__ == '__main__' :

    import Geohash
    import time
    import json

    token='YER_SIMPLEGEO_TOKEN'
    secret='YER_SIMPLEGEO_SECRET'
    layer_name='YER_SIMPLEGEO_LAYER'

    lat = 37.764845
    lon = -122.419857
    uid = Geohash.encode(lat, lon)

    args = {
        'geometry' : {
            'type' : 'Point',
            'coordinates' : [ lon, lat ],
            },
        'created' : int(time.time()),
        'properties' : {},
        'type' : 'Feature',
        }

    geo = simplegeo(token=token, secret=secret, debug=True)

    req = '/records/%s/%s.json' % (layer_name, uid)
    rsp = geo.execute_request_simple(req, method='PUT', args=json.dumps(args))
    print rsp

    # or you can just use the handy (but still incomplete)
    # 'layer' class for working with...well, layers

    lyr = layer(token=token, secret=secret, layer=layer_name, debug=True)
    rsp = lyr.add_point(id=uid, lat=lat, lon=lon)
    print rsp
