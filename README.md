# Overview

OpenTSDB is a scalable time series database built on top of Hadoop and HBase. It simplifies the process of storing and analyzing large amounts of time-series data generated by endpoints like sensors or servers.

http://opentsdb.net

# Usage

## Deployment

Deploy the OpenTSDB charm:
```sh
juju deploy cs:~tengu-team/opentsdb-0
```
For OpenTSDB to work relations are needed with Zookeeper and HBase. Add the relations
when you got HBase and Zookeeper running:
```sh
juju add-relation opentsdb hbase
juju add-relation opentsdb zookeeper
```
To make OpenTSDB's GUI public you have to expose OpenTSDB:
```sh
juju expose opentsdb
```
Browse to the public IP with port to see OpenTSDB's GUI. Here you can select
metrics and graph them.

## How OpenTSDB can be used

### HTTP API
You can communicate with OpenTSDB by using the HTTP API. For storing data the endpoint '/api/put' is used, for example:
```
35.194.184.37:4242/api/put
```
With as JSON body:
```
{
    "metric": "sys.cpu.nice",
    "timestamp": 1346846400,
    "value": 18,
    "tags": {
       "host": "web01",
       "dc": "lga"
    }
}
```
[HTTP API documentation]

### TCollector

TCollector is a client-side process that gathers data from local collectors and pushes the data to OpenTSDB.

[TCollector documentation]

### Graph

In order to inspect metrics you must go to OpenTSDB's GUI by browsing to the public
IP and port (after you exposed the charm). There you can select metrics for a certain
timeframe and plot them.

### Telegraf

The Telegraf charm can be used with OpenTSDB. How to make it work:
1. Deploy Telegraf:
    ```sh
    juju deploy cs:telegraf-6
    ```
2. Add relation between the service you want to collect data from and Telegraf.
   For example if you want to collect metrics from your HAproxy instance and send
   them to OpenTSDB then you first have to add a relation to Telegraf:

   ```sh
   juju add-relation telegraf:juju-info haproxy:juju-info
   ```
3. Update the outputs_config of the Telegraf charm:
    ```
    # Configuration for OpenTSDB server to send metrics to
    [[outputs.opentsdb]]
      ## prefix for metrics keys
      prefix = "my.specific.prefix."

      ## DNS name of the OpenTSDB server
      ## Using "opentsdb.example.com" or "tcp://opentsdb.example.com" will use the
      ## telnet API. "http://opentsdb.example.com" will use the Http API.
      host = "opentsdb.example.com"

      ## Port of the OpenTSDB server
      port = 4242

      ## Number of data points to send to OpenTSDB in Http requests.
      ## Not used with telnet API.
      httpBatchSize = 50

      ## Debug true - Prints OpenTSDB communication
      debug = false
    ```
[Telegraf Charm]

# Important to know
## Removing relation with HBase
When you remove the relation between OpenTSDB and HBase your data will **not** be removed from HBase. This prevents data loss from users that accidentally remove the relation between OpenTSDB and HBase.

# To Do

- Implement clustering

# Contact Information

- [OpenTSDB Homepage]

## Authors

- Michiel Ghyselinck <michiel.ghyselinck@tengu.io>

[telegraf charm]: https://jujucharms.com/telegraf/6
[opentsdb homepage]: http://opentsdb.net/
[http api documentation]: http://opentsdb.net/docs/build/html/api_http/put.html
[tcollector documentation]: http://opentsdb.net/docs/build/html/user_guide/utilities/tcollector.html
