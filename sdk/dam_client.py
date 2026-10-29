"""Thin standard-library client; retain the returned original text and annotations."""
import json
from urllib.request import Request, urlopen


class DAMClient:
    def __init__(self, base_url, api_key, app_id, timeout=35):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.app_id = app_id
        self.timeout = timeout

    def verify(self, text, context='', confidence_threshold=None):
        body = {'text': text, 'source_app_id': self.app_id, 'context': context}
        if confidence_threshold is not None:
            body['confidence_threshold'] = confidence_threshold
        request = Request(self.base_url + '/verify', data=json.dumps(body).encode(), headers={
            'Authorization': 'Bearer ' + self.api_key, 'Content-Type': 'application/json'})
        # The caller supplies the service URL; this SDK is not a server-side URL fetch API.
        with urlopen(request, timeout=self.timeout) as response:  # nosec B310
            return json.load(response)
