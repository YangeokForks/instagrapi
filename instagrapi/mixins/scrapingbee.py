import os
import time
from json import JSONDecodeError

import requests
from requests import Session
from scrapingbee import ScrapingBeeClient

from instagrapi import config
from instagrapi.exceptions import ChallengeRequired, ClientRequestTimeout
from instagrapi.utils import random_delay


class ScrapingBeeRequestMixin:
    domain = config.API_DOMAIN

    def __init__(self, *args, **kwargs):
        self.spb = ScrapingBeeClient(
            api_key=os.getenv("SCRAPING_BEE_API_KEY"), session=Session()
        )
        self.retries = 3

        super().__init__(*args, **kwargs)

    def spb_request(
        self,
        endpoint: str,
        data=None,
        params=None,
        login=False,
        with_signature=True,
        headers=None,
        extra_sig=None,
        return_json=False,
        retries_count=3,
        retries_timeout=10,
    ):
        if self.authorization:
            if not headers:
                headers = {}
            if "authorization" not in headers:
                headers.update({"Authorization": self.authorization})
        kwargs = dict(
            data=data,
            params=params,
            login=login,
            with_signature=with_signature,
            headers=headers,
            extra_sig=extra_sig,
            return_json=return_json,
        )
        try:
            if self.delay_range:
                random_delay(delay_range=self.delay_range)
            self.private_requests_count += 1
            self._send_private_request(endpoint, **kwargs)
        except ClientRequestTimeout:
            self.logger.info(
                "Wait 60 seconds and try one more time (ClientRequestTimeout)"
            )
            time.sleep(60)
            return self._send_private_request(endpoint, **kwargs)
        # except BadPassword as e:
        #     raise e
        except Exception as e:
            if self.handle_exception:
                self.handle_exception(self, e)
            elif isinstance(e, ChallengeRequired):
                self.challenge_resolve(self.last_json)
            else:
                raise e
            if login and self.user_id:
                # After challenge resolve return last_json
                return self.last_json
            return self._send_private_request(endpoint, **kwargs)
        return self.last_json

    def _send_spb_request(
        self, endpoint: str, data=None, headers=None, return_json=False
    ):
        # FIXME: update to inject parameters
        params = {
            "render_js": "false",
            "timeout": "30000",
            "premium_proxy": "true",
            "country_code": "kr",
            "device": "mobile",
        }

        if headers:
            self.headers.update(headers)

        api_url = f"https://{self.domain or config.API_DOMAIN}/{endpoint}"

        try:
            if data is not None:  # POST
                response = self.spb.post(
                    url=api_url,
                    data=data,
                    headers=self.headers,
                    params=params,
                )
            else:  # GET
                response = self.spb.get(
                    url=api_url,
                    headers=self.headers,
                    params=params,
                )

            response.raise_for_status()

            if return_json:
                return response.json()
            return response

        except JSONDecodeError as e:
            if "/login/" in response.url:
                raise Exception("ClientLoginRequired: " + str(e.response.status_code))

            raise Exception("ClientJSONDecodeError: " + str(e.response.status_code))

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                raise Exception("ClientForbiddenError: " + str(e.response.status_code))

            if e.response.status_code == 400:
                raise Exception("ClientBadRequestError: " + str(e.response.status_code))

            if e.response.status_code == 429:
                raise Exception("ClientThrottledError: " + str(e.response.status_code))

            if e.response.status_code == 404:
                raise Exception("ClientNotFoundError: " + str(e.response.status_code))

            raise Exception("ClientError: " + str(e.response.status_code))

        except requests.ConnectionError as e:
            raise Exception("ClientConnectionError: " + str(e.response.status_code))
