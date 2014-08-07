#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import os, random, types
from proton import *
import socket
from select import select

class EventDispatcher(object):

    methods = {
        Event.CONNECTION_INIT: "connection_init",
        Event.CONNECTION_OPEN: "connection_open",
        Event.CONNECTION_REMOTE_OPEN: "connection_remote_open",
        Event.CONNECTION_CLOSE: "connection_close",
        Event.CONNECTION_REMOTE_CLOSE: "connection_remote_close",
        Event.CONNECTION_FINAL: "connection_final",

        Event.SESSION_INIT: "session_init",
        Event.SESSION_OPEN: "session_open",
        Event.SESSION_REMOTE_OPEN: "session_remote_open",
        Event.SESSION_CLOSE: "session_close",
        Event.SESSION_REMOTE_CLOSE: "session_remote_close",
        Event.SESSION_FINAL: "session_final",

        Event.LINK_INIT: "link_init",
        Event.LINK_OPEN: "link_open",
        Event.LINK_REMOTE_OPEN: "link_remote_open",
        Event.LINK_CLOSE: "link_close",
        Event.LINK_REMOTE_CLOSE: "link_remote_close",
        Event.LINK_FLOW: "link_flow",
        Event.LINK_FINAL: "link_final",

        Event.TRANSPORT: "transport",
        Event.DELIVERY: "delivery"
    }

    def dispatch(self, event):
        getattr(self, self.methods[event.type], self.unhandled)(event)

    def unhandled(self, event):
        pass

class Selectable(object):

    def __init__(self, conn, sock):
        self.conn = conn
        self.transport = Transport()
        self.transport.bind(self.conn)
        self.socket = sock
        self.socket.setblocking(0)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.write_done = False
        self.read_done = False

    def accept(self):
        #sasl = self.transport.sasl()
        #sasl.mechanisms("ANONYMOUS")
        #sasl.server()
        #sasl.done(SASL.OK)
        return self

    def connect(self, host, port=None, username=None, password=None):
        if username and password:
            sasl = self.transport.sasl()
            sasl.plain(username, password)
        self.socket.connect_ex((host, port or 5672))
        return self

    def _closed_cleanly(self):
        return self.conn.state & Endpoint.LOCAL_CLOSED and self.conn.state & Endpoint.REMOTE_CLOSED

    def closed(self):
        if self.write_done and self.read_done:
            self.socket.close()
            return True
        else:
            return False

    def fileno(self):
        return self.socket.fileno()

    def reading(self):
        if self.read_done: return False
        c = self.transport.capacity()
        if c > 0:
            return True
        elif c < 0:
            self.read_done = True

    def writing(self):
        if self.write_done: return False
        try:
            p = self.transport.pending()
            if p > 0:
                return True
            elif p < 0:
                self.write_done = True
                return False
            else: # p == 0
                return False
        except TransportException, e:
            self.write_done = True
            return False

    def readable(self):
        c = self.transport.capacity()
        if c > 0:
            try:
                data = self.socket.recv(c)
                if data:
                    self.transport.push(data)
                elif self._closed_cleanly():
                    self.transport.close_tail()
                else:
                    self.read_done = True
                    self.write_done = True
            except TransportException, e:
                print "Error on read: %s" % e
                self.read_done = True
            except socket.error, e:
                print "Error on recv: %s" % e
                self.read_done = True
        elif c < 0:
            self.read_done = True

    def writable(self):
        try:
            p = self.transport.pending()
            if p > 0:
                data = self.transport.peek(p)
                n = self.socket.send(data)
                self.transport.pop(n)
            elif p < 0:
                self.write_done = True
        except TransportException, e:
            print "Error on write: %s" % e
            self.write_done = True
        except socket.error, e:
            print "Error on send: %s" % e
            self.write_done = True

    def removed(self):
        if not self._closed_cleanly(): self.disconnected()

    def disconnected(self):
        if hasattr(self.conn, "context") and hasattr(self.conn.context, "disconnected"):
            self.conn.context.disconnected(self.conn)
        else:
            print "connection %s disconnected" % self.conn

class Acceptor:

    def __init__(self, events, selectables, host, port):
        self.events = events
        self.selectables = selectables
        self.socket = socket.socket()
        self.socket.setblocking(0)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.selectables.append(self)
        self._closed = False

    def closed(self):
        if self._closed:
            self.socket.close()
            return True
        else:
            return False

    def close(self):
        self._closed = True

    def fileno(self):
        return self.socket.fileno()

    def reading(self):
        return not self._closed

    def writing(self):
        return False

    def readable(self):
        sock, addr = self.socket.accept()
        print "Incoming Connection:", addr
        if sock:
            self.selectables.append(Selectable(self.events.connection(), sock).accept())

    def removed(self): pass

class Events(object):

    def __init__(self, *dispatchers):
        self.collector = Collector()
        self.dispatchers = dispatchers

    def connection(self):
        conn = Connection()
        conn.collect(self.collector)
        return conn

    def process(self):
        while True:
            ev = self.collector.peek()
            if ev:
                for d in self.dispatchers:
                    d.dispatch(ev)
                self.collector.pop()
            else:
                return

class SelectLoop(object):

    def __init__(self, events):
        self.events = events
        self.selectables = []
        self._abort = False

    def abort(self):
        self._abort = True

    def add(self, selectable):
        self.selectables.append(selectable)

    def remove(self, selectable):
        self.selectables.remove(selectable)

    def run(self):
        while True:
            self.events.process()
            if self._abort: return

            reading = []
            writing = []
            closed = []

            for s in self.selectables:
                if s.reading(): reading.append(s)
                if s.writing(): writing.append(s)
                if s.closed(): closed.append(s)

            for s in closed:
                self.selectables.remove(s)
                s.removed()

            if not self.selectables: return

            readable, writable, _ = select(reading, writing, [], 3)

            for s in readable:
                s.readable()
            for s in writable:
                s.writable()

class Handshaker(EventDispatcher):

    def connection_remote_open(self, event):
        conn = event.connection
        if conn.state & Endpoint.LOCAL_UNINIT:
            conn.open()

    def session_remote_open(self, event):
        ssn = event.session
        if ssn.state & Endpoint.LOCAL_UNINIT:
            ssn.open()

    def link_remote_open(self, event):
        link = event.link
        if link.state & Endpoint.LOCAL_UNINIT:
            link.source.copy(link.remote_source)
            link.target.copy(link.remote_target)
            link.open()

    def connection_remote_close(self, event):
        conn = event.connection
        if not (conn.state & Endpoint.LOCAL_CLOSED):
            conn.close()

    def session_remote_close(self, event):
        ssn = event.session
        if not (ssn.state & Endpoint.LOCAL_CLOSED):
            ssn.close()

    def link_remote_close(self, event):
        link = event.link
        if not (link.state & Endpoint.LOCAL_CLOSED):
            link.close()

class FlowController(EventDispatcher):

    def __init__(self, window):
        self.window = window

    def top_up(self, link):
        delta = self.window - link.credit
        link.flow(delta)

    def link_open(self, event):
        if event.link.is_receiver:
            self.top_up(event.link)

    def link_remote_open(self, event):
        if event.link.is_receiver:
            self.top_up(event.link)

    def link_flow(self, event):
        if event.link.is_receiver:
            self.top_up(event.link)

    def delivery(self, event):
        if event.delivery.link.is_receiver:
            self.top_up(event.delivery.link)

class ScopedDispatcher(EventDispatcher):

    targets = {
        Event.CATEGORY_CONNECTION: "connection_context",
        Event.CATEGORY_SESSION: "session_context",
        Event.CATEGORY_LINK: "link_context",
        Event.CATEGORY_DELIVERY: "delivery_context"
    }

    def connection_context(self, event):
        conn = event.connection
        if conn and hasattr(conn, "context"):
            return conn.context
        else:
            return None

    def session_context(self, event):
        ssn = event.session
        if ssn and hasattr(ssn, "context"):
            return ssn.context
        else:
            return self.connection_context(event)

    def link_context(self, event):
        link = event.link
        if link and hasattr(link, "context"):
            return link.context
        else:
            return self.session_context(event)

    def delivery_context(self, event):
        dlv = event.delivery
        if dlv and hasattr(dlv, "context"):
            return dlv.context
        return self.link_context(event)

    def target_context(self, event):
        f = getattr(self, self.targets.get(event.category, ""), None)
        if f:
            return f(event)
        else:
            return None

    def dispatch(self, event):
        target = self.target_context(event)
        if target:
            getattr(target, self.methods[event.type], self.unhandled)(event)

class ConnectionHandler(EventDispatcher):
    def __init__(self):
        super(ConnectionHandler, self).__init__()

    def connection_remote_open(self, event):
        self.opened(event.connection)

    def connection_remote_close(self, event):
        self.closed(event.connection, event.connection.remote_condition)

    def opened(self, conn): pass
    def closed(self, conn, condition): pass
    def disconnected(self, conn): pass

class SenderHandler(EventDispatcher):
    def link_remote_open(self, event):
        self.opened(event.link)

    def link_remote_close(self, event):
        self.closed(event.link, event.link.remote_condition)

    def delivery(self, event):
        dlv = event.delivery
        link = dlv.link
        if dlv.updated:
            if dlv.remote_state == Delivery.ACCEPTED:
                self.accepted(dlv.link, dlv)
            elif dlv.remote_state == Delivery.REJECTED:
                self.accepted(dlv.link, dlv)
            elif dlv.remote_state == Delivery.RELEASED:
                self.accepted(dlv.link, dlv)
            elif dlv.remote_state == Delivery.MODIFIED:
                self.accepted(dlv.link, dlv)
            if dlv.settled:
                self.settled(dlv.link, dlv)
            if self.auto_settle():
                dlv.settle()

    def opened(self, sender): pass
    def closed(self, sender, condition): pass
    def link_flow(self, event): pass
    def accepted(self, sender, delivery): pass
    def rejected(self, sender, delivery): pass
    def released(self, sender, delivery): pass
    def modified(self, sender, delivery): pass
    def settled(self, sender, delivery): pass
    def auto_settle(self): return True

def recv_msg(delivery):
    msg = Message()
    msg.decode(delivery.link.recv(delivery.pending))
    delivery.link.advance()
    return msg

class Reject(ProtonException):
  """
  An exception that indicate a message should be rejected
  """
  pass

class ReceiverHandler(EventDispatcher):
    def link_remote_open(self, event):
        self.opened(event.link)

    def link_remote_close(self, event):
        self.closed(event.link, event.link.remote_condition)

    def link_flow(self, event):
        if event.link.is_receiver and not event.link.draining():
            self.drained(event.link)

    def delivery(self, event):
        dlv = event.delivery
        link = dlv.link
        if dlv.readable and not dlv.partial:
            msg = recv_msg(dlv)
            try:
                self.received(dlv.link, dlv, msg)
                if self.auto_accept():
                    dlv.update(Delivery.ACCEPTED)
                    dlv.settle()
            except Reject:
                dlv.update(Delivery.REJECTED)
                dlv.settle()
        elif dlv.updated and dlv.settled:
            self.settled(dlv.link, dlv)

    def accept(self, delivery):
        self.settle(delivery, Delivery.ACCEPTED)

    def reject(self, delivery):
        self.settle(delivery, Delivery.REJECTED)

    def release(self, delivery, delivered=False):
        if delivered:
            self.settle(delivery, Delivery.MODIFIED)
        else:
            self.settle(delivery, Delivery.RELEASED)

    def settle(self, delivery, state=None):
        if state:
            delivery.update(state)
        delivery.settle()

    def opened(self, receiver): pass
    def closed(self, receiver, condition): pass
    def drained(self, receiver): pass
    def received(self, receiver, delivery, message): pass
    def settled(self, receiver, delivery): pass
    def auto_accept(self): return True

def delivery_tags():
    count = 1
    while True:
        yield str(count)
        count += 1

def send_msg(self, msg, tag=None, handler=None):
    dlv = self.delivery(tag or next(self.tags))
    if handler:
        dlv.context = handler
    self.send(msg.encode())
    self.advance()
    return dlv

class MessagingContext(object):
    def __init__(self, conn, handler=None, ssn=None):
        self.conn = conn
        if handler:
            self.conn.context = handler
        self.ssn = ssn

    def sender(self, target, source=None, name=None, handler=None, tags=None):
        snd = self._get_ssn().sender(name or self._get_id(target, source))
        if source:
            snd.source.address = source
        snd.target.address = target
        if handler:
            snd.context = handler
        snd.tags = tags or delivery_tags()
        snd.send_msg = types.MethodType(send_msg, snd)
        snd.open()
        return snd

    def receiver(self, source, target=None, name=None, dynamic=False, handler=None):
        rcv = self._get_ssn().receiver(name or self._get_id(source, target))
        rcv.source.address = source
        if dynamic:
            rcv.source.dynamic = True
        if target:
            rcv.target.address = target
        if handler:
            rcv.context = handler
        rcv.open()
        return rcv

    def session(self):
        return MessageContext(conn=None, ssn=self._new_ssn())

    def close(self):
        if self.ssn:
            self.ssn.close()
        if self.conn:
            self.conn.close()

    def _get_id(self, remote, local):
        if local: "%s-%s" % (remote, local)
        elif remote: return remote
        else: return "temp"

    def _get_ssn(self):
        if not self.ssn:
            self.ssn = self._new_ssn()
            self.ssn.context = self
        return self.ssn

    def _new_ssn(self):
        ssn = self.conn.session()
        ssn.open()
        return ssn

    def session_remote_close(self, event):
        if self.conn:
            self.conn.close()


class Runtime(object):
    def __init__(self, *handlers):
        self.loop = SelectLoop(Events(ScopedDispatcher(), *handlers))

    def connect(self, url, name=None, handler=None):
        identifier = name or url
        context = MessagingContext(self.loop.events.connection(), handler=handler)
        host, port = url.split(":")
        if port: port = int(port)
        context.conn.hostname = host
        self.loop.add(Selectable(context.conn, socket.socket()).connect(host, port))
        context.conn.open()
        return context

    def listen(self, url):
        host, port = url.split(":")
        if port: port = int(port)
        return Acceptor(self.loop.events, self.loop.selectables, host, port)

    def run(self):
        self.loop.run()

Runtime.DEFAULT = Runtime(FlowController(10))

