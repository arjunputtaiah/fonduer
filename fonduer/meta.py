"""Manages the metadata required for the sqlalchemy connection to the database.

This module exports the Meta object, which is used by the user to get access
to a session to their PostgreSQL database, as shown below.

.. code-block:: python
    from fonduer import Meta

    DB = "db_name"
    session = Meta.init("postgres://localhost:5432/" + DB).Session()

The new_sessionmaker function is used internally for parallelization.
"""

import logging
from builtins import object
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


# Defines procedure for setting up a sessionmaker
def new_sessionmaker():
    """Return a session bound to the sqlalchemy engine."""
    # Turning on autocommit for Postgres, see
    # http://oddbird.net/2014/06/14/sqlalchemy-postgres-autocommit/
    # Otherwise any e.g. query starts a transaction, locking tables... very
    # bad for e.g. multiple notebooks open, multiple processes, etc.
    if Meta.postgres and Meta.ready:
        engine = create_engine(Meta.conn_string, isolation_level="AUTOCOMMIT")
    else:
        raise ValueError(
            "Meta variables have not been initialized with a postgres connection string."
        )

    # New sessionmaker
    session = sessionmaker(bind=engine)
    return session


class Meta(object):
    """Singleton-like metadata class for all global variables.

    Adapted from the Unique Design Pattern:
    https://stackoverflow.com/questions/1318406/why-is-the-borg-pattern-better-than-the-singleton-pattern-in-python
    """

    # Static class variables
    conn_string = None
    DBNAME = None
    DBUSER = None
    DBPORT = None
    DBPWD = None
    Session = None
    engine = None
    Base = declarative_base(name="Base", cls=object)
    postgres = False
    ready = False

    @classmethod
    def init(cls, conn_string=None):
        """Return the unique Meta class."""
        if conn_string and not Meta.ready:
            url = urlparse(conn_string)
            Meta.conn_string = conn_string
            Meta.DBNAME = url.path[1:]
            Meta.DBUSER = url.username
            Meta.DBPWD = url.password
            Meta.DBPORT = url.port
            Meta.postgres = url.scheme.startswith("postgres")
            # We initialize the engine within the models module because models'
            # schema can depend on which data types are supported by the engine
            Meta.ready = Meta.postgres
            Meta.Session = new_sessionmaker()
            Meta.engine = Meta.Session.kw["bind"]
            logger.info(
                "Connecting {} to {}:{}".format(Meta.DBUSER, Meta.DBNAME, Meta.DBPORT)
            )
            if Meta.ready:
                Meta._init_db()
            else:
                raise ValueError(
                    "{} is not a valid postgres connection string.".format(conn_string)
                )

        return cls

    @classmethod
    def _init_db(cls):
        """Initialize the storage schema.

        This call must be performed after all classes that extend
        Base are declared to ensure the storage schema is initialized.
        """
        if Meta.ready:
            logger.info("Initializing the storage schema")
            Meta.Base.metadata.create_all(Meta.engine)
        else:
            raise ValueError("The Meta variables haven't been initialized.")
