import logging

from hdbcli import dbapi


def create_hana_connection(url, port, user, password) -> dbapi.Connection | None:
    try:
        connection = dbapi.connect(
            address=url,
            port=port,
            user=user,
            password=password,
        )
        return connection
    except dbapi.Error:
        logging.exception("Connection to Hana Cloud failed.")
    except Exception:
        logging.exception("Unknown error occurred.")
    return None
