#pylint: disable=c0111,c0325,c0301,e0401

import subprocess
import happybase

from charms.reactive import when, when_not, set_state, remove_state
from charmhelpers.fetch.archiveurl import ArchiveUrlFetchHandler
from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import status_set, open_port, close_port, config
from charmhelpers.core.templating import render
from charmhelpers.core.host import service_restart

# Key value store that can be used across hooks.
DB = unitdata.kv()

@when_not('layer-opentsdb.installed')
def install_layer_opentsdb():
    status_set('maintenance', 'Installing OpenTSDB...')
    fetcher = ArchiveUrlFetchHandler()
    fetcher.download('https://github.com/OpenTSDB/opentsdb/releases/download/v2.3.0/opentsdb-2.3.0_all.deb',
                     '/opt/opentsdb-2.3.0_all.deb')
    subprocess.check_call(['dpkg', '-i', '/opt/opentsdb-2.3.0_all.deb'])
    set_state('layer-opentsdb.installed')


@when('layer-opentsdb.installed')
@when('layer-opentsdb.zookeeper-configured')
@when('layer-opentsdb.hbase-configured')
@when_not('layer-opentsdb.started')
def start_layer_opentsdb():
    status_set('maintenance', 'Starting up...')
    service_restart('opentsdb')
    open_port(config()["port"])
    set_state('layer-opentsdb.started')
    status_set('active', 'OpenTSDB is running.')


@when('layer-opentsdb.installed')
@when('config.changed')
def change_config():
    if config().changed('port'):
        # It is necessary to close the previous port for security reasons.
        prev_port = config().previous('port')
        # Config.changed runs immediately after "install". At that moment
        # there is no previous port. We can only close a previous port
        # when there actually is one.
        if prev_port is not None:
            close_port(prev_port)
        # Open new port.
        open_port(config()["port"])

    render_config()
    service_restart('opentsdb')


@when_not('zookeeper.joined')
@when_not('layer-opentsdb.zookeeper-configured')
def wait_zookeeper_join():
    status_set('blocked', 'Please create a relation with Zookeeper.')


@when_not('hbase.joined')
@when_not('layer-opentsdb.hbase-configured')
def wait_hbase_join():
    status_set('blocked', 'Please create a relation with HBase.')


@when('zookeeper.joined')
@when_not('zookeeper.ready')
def wait_zookeeper_ready(zookeeper):
    status_set('waiting', 'Waiting for Zookeeper to become available.')


@when('hbase.joined')
@when_not('hbase.ready')
def wait_hbase_ready(hbase):
    status_set('waiting', 'Waiting for HBase to become available.')


@when('zookeeper.ready')
@when_not('layer-opentsdb.zookeeper-configured')
def configure_zookeeper(zookeeper):
    zookeepers = zookeeper.zookeepers()
    # Add zookeepers to the key-value store.
    DB.set('zookeepers', zookeepers)
    # Update OpenTSDB its config file.
    render_config()
    # After the Zookeeper relation is added we want to make sure that
    # OpenTSDB will be restarted.
    remove_state('layer-opentsdb.started')
    set_state('layer-opentsdb.zookeeper-configured')


@when('hbase.ready')
@when_not('layer-opentsdb.hbase-configured')
def configure_hbase(hbase):
    hbase_servers = hbase.hbase_servers()
    # Add hbase_servers to key-value store in case we need this info later on.
    DB.set('hbase_servers', hbase_servers)
    # Create necessary tables in HBase instance.
    # Just pick the first server from the dict.
    hbase_server = hbase_servers[0]
    create_tables(hbase_server['host'])
    # After the HBase relation is added we want to make sure that
    # OpenTSDB will be restarted.
    remove_state('layer-opentsdb.started')
    set_state('layer-opentsdb.hbase-configured')


@when('layer-opentsdb.zookeeper-configured')
@when_not('zookeeper.joined')
@when_not('zookeeper.ready')
def remove_zookeepers_config():
    """When the user removes the relation with zookeeper then the
    zookeepers must be removed from config file."""
    DB.set('zookeepers', [])
    render_config()
    remove_state('layer-opentsdb.zookeeper-configured')


@when('layer-opentsdb.hbase-configured')
@when_not('hbase.joined')
@when_not('hbase.ready')
def remove_hbase_tables():
    """When the user removes the relation with HBase then the
    tables of OpenTSDB must be removed from HBase."""
    hbase_servers = DB.get('hbase_servers')
    hbase_server = hbase_servers[0]
    delete_tables(hbase_server['host'])
    remove_state('layer-opentsdb.hbase-configured')


def render_config():
    context = get_context()
    render('opentsdb.conf', '/etc/opentsdb/opentsdb.conf', context)


def get_context():
    conf = config()
    addresses = get_zookeepers_config_line()
    context = {'port': conf["port"],
               'bind': conf["bind"],
               'tcp_no_delay': conf["tcp_no_delay"],
               'keep_alive': conf["keep_alive"],
               'reuse_address': conf["reuse_address"],
               'worker_threads': conf["worker_threads"],
               'async_io': conf["async_io"],
               'mode': conf["mode"],
               'enable_chunked': conf["enable_chunked"],
               'auto_create_metrics': conf["auto_create_metrics"],
               'enable_compaction': conf["enable_compaction"],
               'flush_interval': conf["flush_interval"],
               'zookeepers': addresses}
    return context


def get_zookeepers_config_line():
    zookeepers = DB.get('zookeepers')
    config_line = ''

    if zookeepers is not None:
        for zookeeper in zookeepers:
            host = zookeeper['host']
            port = zookeeper['port']
            zookeeper_address = host + ':' + port
            config_line += zookeeper_address + ', '
        # Remove last comma and space from line
        return config_line[:-2]

    return config_line


def create_tables(ip_hbase, thrift_port=9090):
    # Connect with HBase instance.
    connection = happybase.Connection(host=ip_hbase, port=thrift_port, autoconnect=False)
    connection.open()

    # Get existing tables.
    tables = connection.tables()
    tables_decoded = []
    for table in tables:
        tables_decoded.append(table.decode('UTF-8'))

    # Create necessary tables for OpenTSDB.
    if 'tsdb-uid' not in tables_decoded:
        connection.create_table(
            'tsdb-uid',
            {'id': dict(bloom_filter_type='ROW', compression='SNAPPY'),
             'name': dict(bloom_filter_type='ROW', compression='SNAPPY')})
    if 'tsdb' not in tables_decoded:
        connection.create_table(
            'tsdb',
            {'t': dict(max_versions=1, bloom_filter_type='ROW', compression='SNAPPY')})
    if 'tsdb-tree' not in tables_decoded:
        connection.create_table(
            'tsdb-tree',
            {'t': dict(max_versions=1, bloom_filter_type='ROW', compression='SNAPPY')})
    if 'tsdb-meta' not in tables_decoded:
        connection.create_table(
            'tsdb-meta',
            {'name': dict(bloom_filter_type='ROW', compression='SNAPPY')})

    # Close the connection.
    connection.close()


def delete_tables(ip_hbase, thrift_port=9090):
    # Connect with HBase instance.
    connection = happybase.Connection(host=ip_hbase, port=thrift_port, autoconnect=False)
    connection.open()

    # Get existing tables.
    tables = connection.tables()
    tables_decoded = []
    for table in tables:
        tables_decoded.append(table.decode('UTF-8'))

    # If these tables exist then delete them.
    table_names = ['tsdb-uid', 'tsdb', 'tsdb-tree', 'tsdb-meta']
    for table in table_names:
        if table in tables_decoded:
            connection.delete_table(table, disable=True)

    connection.close()