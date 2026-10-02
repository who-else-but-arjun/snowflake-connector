class ConnectorError(Exception):
    pass


class AuthenticationError(ConnectorError):
    pass