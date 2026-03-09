# ruff: noqa
"""HTTP clients and helpers for the public `nova_sdk_py_file` SDK."""

import ssl
from typing import Any

import httpx
from attrs import define, evolve, field


@define
class Client:
    """A class for keeping track of data related to the API

    The following are accepted as keyword arguments and will be used to construct httpx Clients internally:

        ``base_url``: The base URL for the API, all requests are made to a relative path to this URL

        ``cookies``: A dictionary of cookies to be sent with every request

        ``headers``: A dictionary of headers to be sent with every request

        ``timeout``: The maximum amount of a time a request can take. API functions will raise
        httpx.TimeoutException if this is exceeded.

        ``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
        but can be set to False for testing purposes.

        ``follow_redirects``: Whether or not to follow redirects. Default value is False.

        ``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.


    Attributes:
        raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(
        factory=dict, kw_only=True, alias="cookies"
    )
    _headers: dict[str, str] = field(
        factory=dict, kw_only=True, alias="headers"
    )
    _timeout: httpx.Timeout | None = field(
        default=None, kw_only=True, alias="timeout"
    )
    _verify_ssl: str | bool | ssl.SSLContext = field(
        default=True, kw_only=True, alias="verify_ssl"
    )
    _follow_redirects: bool = field(
        default=False, kw_only=True, alias="follow_redirects"
    )
    _httpx_args: dict[str, Any] = field(
        factory=dict, kw_only=True, alias="httpx_args"
    )
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    def with_headers(self, headers: dict[str, str]) -> "Client":
        """Build a copy of this client with merged default headers.

        Args:
            headers (dict[str, str]): Headers to merge into client defaults.

        Returns:
            Client: A new client instance with merged headers.
        """
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "Client":
        """Build a copy of this client with merged default cookies.

        Args:
            cookies (dict[str, str]): Cookies to merge into client defaults.

        Returns:
            Client: A new client instance with merged cookies.
        """
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "Client":
        """Build a copy of this client with a replacement timeout.

        Args:
            timeout (httpx.Timeout): Timeout configuration for future requests.

        Returns:
            Client: A new client instance with the provided timeout.
        """
        return evolve(self, timeout=timeout)

    def set_httpx_client(self, client: httpx.Client) -> "Client":
        """Set a caller-managed sync HTTPX client instance.

        Args:
            client (httpx.Client): Preconfigured sync HTTPX client instance.

        Returns:
            Client: This client wrapper.
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Return the backing sync HTTPX client, creating it if needed.

        Returns:
            httpx.Client: The configured sync HTTPX client instance.

        Raises:
            httpx.HTTPError: Propagated when HTTPX client setup fails.
        """
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "Client":
        """Enter the sync HTTPX client context for this wrapper.

        Returns:
            Client: This client wrapper for use inside a context manager.

        Raises:
            httpx.HTTPError: Propagated by HTTPX context entry.
        """
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the sync HTTPX client context for this wrapper.

        Args:
            *args (Any): Positional exception-context arguments from `with`.
            **kwargs (Any): Keyword exception-context arguments from `with`.

        Returns:
            None

        Raises:
            httpx.HTTPError: Propagated by HTTPX context exit.
        """
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(
        self, async_client: httpx.AsyncClient
    ) -> "Client":
        """Set a caller-managed async HTTPX client instance.

        Args:
            async_client (httpx.AsyncClient): Preconfigured async HTTPX client.

        Returns:
            Client: This client wrapper.
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Return the backing async HTTPX client, creating it if needed.

        Returns:
            httpx.AsyncClient: The configured async HTTPX client instance.

        Raises:
            httpx.HTTPError: Propagated when HTTPX client setup fails.
        """
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "Client":
        """Enter the async HTTPX client context for this wrapper.

        Returns:
            Client: This client wrapper for use inside an async context manager.

        Raises:
            httpx.HTTPError: Propagated by HTTPX async context entry.
        """
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the async HTTPX client context for this wrapper.

        Args:
            *args (Any): Positional exception-context arguments from `async with`.
            **kwargs (Any): Keyword exception-context arguments from `async with`.

        Returns:
            None

        Raises:
            httpx.HTTPError: Propagated by HTTPX async context exit.
        """
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)


@define
class AuthenticatedClient:
    """A Client which has been authenticated for use on secured endpoints

    The following are accepted as keyword arguments and will be used to construct httpx Clients internally:

        ``base_url``: The base URL for the API, all requests are made to a relative path to this URL

        ``cookies``: A dictionary of cookies to be sent with every request

        ``headers``: A dictionary of headers to be sent with every request

        ``timeout``: The maximum amount of a time a request can take. API functions will raise
        httpx.TimeoutException if this is exceeded.

        ``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
        but can be set to False for testing purposes.

        ``follow_redirects``: Whether or not to follow redirects. Default value is False.

        ``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.


    Attributes:
        raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
        token: The token to use for authentication
        prefix: The prefix to use for the Authorization header
        auth_header_name: The name of the Authorization header
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(
        factory=dict, kw_only=True, alias="cookies"
    )
    _headers: dict[str, str] = field(
        factory=dict, kw_only=True, alias="headers"
    )
    _timeout: httpx.Timeout | None = field(
        default=None, kw_only=True, alias="timeout"
    )
    _verify_ssl: str | bool | ssl.SSLContext = field(
        default=True, kw_only=True, alias="verify_ssl"
    )
    _follow_redirects: bool = field(
        default=False, kw_only=True, alias="follow_redirects"
    )
    _httpx_args: dict[str, Any] = field(
        factory=dict, kw_only=True, alias="httpx_args"
    )
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    token: str
    prefix: str = "Bearer"
    auth_header_name: str = "Authorization"

    def with_headers(self, headers: dict[str, str]) -> "AuthenticatedClient":
        """Build a copy of this client with merged default headers.

        Args:
            headers (dict[str, str]): Headers to merge into client defaults.

        Returns:
            AuthenticatedClient: A new client instance with merged headers.
        """
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "AuthenticatedClient":
        """Build a copy of this client with merged default cookies.

        Args:
            cookies (dict[str, str]): Cookies to merge into client defaults.

        Returns:
            AuthenticatedClient: A new client instance with merged cookies.
        """
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "AuthenticatedClient":
        """Build a copy of this client with a replacement timeout.

        Args:
            timeout (httpx.Timeout): Timeout configuration for future requests.

        Returns:
            AuthenticatedClient: A new client instance with the provided timeout.
        """
        return evolve(self, timeout=timeout)

    def set_httpx_client(self, client: httpx.Client) -> "AuthenticatedClient":
        """Set a caller-managed sync HTTPX client instance.

        Args:
            client (httpx.Client): Preconfigured sync HTTPX client instance.

        Returns:
            AuthenticatedClient: This client wrapper.
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Return the backing sync HTTPX client, creating it if needed.

        Returns:
            httpx.Client: The configured sync HTTPX client instance.

        Raises:
            httpx.HTTPError: Propagated when HTTPX client setup fails.
        """
        if self._client is None:
            headers = {**self._headers}
            headers[self.auth_header_name] = (
                f"{self.prefix} {self.token}" if self.prefix else self.token
            )
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "AuthenticatedClient":
        """Enter the sync HTTPX client context for this wrapper.

        Returns:
            AuthenticatedClient: This client wrapper for use in a context manager.

        Raises:
            httpx.HTTPError: Propagated by HTTPX context entry.
        """
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the sync HTTPX client context for this wrapper.

        Args:
            *args (Any): Positional exception-context arguments from `with`.
            **kwargs (Any): Keyword exception-context arguments from `with`.

        Returns:
            None

        Raises:
            httpx.HTTPError: Propagated by HTTPX context exit.
        """
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(
        self, async_client: httpx.AsyncClient
    ) -> "AuthenticatedClient":
        """Set a caller-managed async HTTPX client instance.

        Args:
            async_client (httpx.AsyncClient): Preconfigured async HTTPX client.

        Returns:
            AuthenticatedClient: This client wrapper.
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Return the backing async HTTPX client, creating it if needed.

        Returns:
            httpx.AsyncClient: The configured async HTTPX client instance.

        Raises:
            httpx.HTTPError: Propagated when HTTPX client setup fails.
        """
        if self._async_client is None:
            headers = {**self._headers}
            headers[self.auth_header_name] = (
                f"{self.prefix} {self.token}" if self.prefix else self.token
            )
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "AuthenticatedClient":
        """Enter the async HTTPX client context for this wrapper.

        Returns:
            AuthenticatedClient: This client wrapper for async context usage.

        Raises:
            httpx.HTTPError: Propagated by HTTPX async context entry.
        """
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the async HTTPX client context for this wrapper.

        Args:
            *args (Any): Positional exception-context arguments from `async with`.
            **kwargs (Any): Keyword exception-context arguments from `async with`.

        Returns:
            None

        Raises:
            httpx.HTTPError: Propagated by HTTPX async context exit.
        """
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)
