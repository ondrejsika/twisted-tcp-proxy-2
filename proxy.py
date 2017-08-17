from __future__ import print_function
import argparse
import sys
from twisted.internet import reactor, protocol, defer


def _print(*parts):
    sys.stdout.write(' '.join(map(str, parts)))
    sys.stdout.write('\n')
    sys.stdout.flush()


class ProxyClientProtocol(protocol.Protocol):
    def connectionMade(self):
        self.cli_queue = self.factory.cli_queue
        self.cli_queue.get().addCallback(self.serverDataReceived)

    def serverDataReceived(self, chunk):
        if chunk is False:
            self.cli_queue = None
            self.factory.continueTrying = False
            self.transport.loseConnection()
        elif self.cli_queue:
            self.transport.write(chunk)
            self.cli_queue.get().addCallback(self.serverDataReceived)
        else:
            self.factory.cli_queue.put(chunk)

    def dataReceived(self, chunk):
        _print('server', chunk)
        self.factory.srv_queue.put(chunk)

    def connectionLost(self, why):
        if self.cli_queue:
            self.cli_queue = None


class ProxyClientFactory(protocol.ReconnectingClientFactory):
    maxDelay = 10
    continueTrying = True
    protocol = ProxyClientProtocol

    def __init__(self, srv_queue, cli_queue):
        self.srv_queue = srv_queue
        self.cli_queue = cli_queue


class ProxyServer(protocol.Protocol):
    def connectionMade(self):
        self.srv_queue = defer.DeferredQueue()
        self.cli_queue = defer.DeferredQueue()
        self.srv_queue.get().addCallback(self.clientDataReceived)

        factory = ProxyClientFactory(self.srv_queue, self.cli_queue)
        reactor.connectTCP(args.connect_host, args.connect_port, factory)

    def clientDataReceived(self, chunk):
        self.transport.write(chunk)
        self.srv_queue.get().addCallback(self.clientDataReceived)

    def dataReceived(self, chunk):
        _print('client', chunk)
        self.cli_queue.put(chunk)

    def connectionLost(self, why):
        self.cli_queue.put(False)


parser = argparse.ArgumentParser()
parser.add_argument('listen_port', type=int)
parser.add_argument('connect_host')
parser.add_argument('connect_port', type=int)

args = parser.parse_args()

factory = protocol.Factory()
factory.protocol = ProxyServer
reactor.listenTCP(args.listen_port, factory, interface="0.0.0.0")
reactor.run()

