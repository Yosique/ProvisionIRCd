#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides usermodes +g and /accept command (callerid)
"""

import ircd
import time
import os
import sys

from handle.functions import _print

@ircd.Modules.user_modes('g', 0, 'Only users in your accept-list can message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.support('CALLERID')
@ircd.Modules.events('privmsg')
def umode_g(self, localServer, target, msg, module):
    if type(target).__name__ != 'User' or 'o' in self.modes: ### Opers can bypass.
        return True
    if not hasattr(target, 'caller_id_accept'):
        target.caller_id_accept = []
    if not hasattr(target, 'caller_id_queue'):
        target.caller_id_queue = []
    if 'g' in target.modes:
        accept_lower = [x.lower() for x in target.caller_id_accept]
        if self.nickname.lower() not in accept_lower:
            self.sendraw(716, '{} :is in +g mode'.format(target.nickname))
            ### Send below raw only once per minute max.
            self.sendraw(717, '{} :has been informed of your request, awaiting reply'.format(target.nickname))
        if not hasattr(self, 'targnotify'):
            self.targnotify = {}
        if self.nickname.lower() not in accept_lower:
            ### Block message.
            if (target in self.targnotify and int(time.time()) - self.targnotify[target] > 60) or target not in self.targnotify:
                target.sendraw(718, '{} {}@{} :is messaging you, and you have umode +g.'.format(self.nickname, self.ident, self.cloakhost if 'x' in self.modes else self.hostname))
                self.targnotify[target] = int(time.time())
            if target.server == localServer:
                queue = (self.fullmask(), time.time()*10, msg)
                target.caller_id_queue.append(queue)
                return False
    return True

@ircd.Modules.params(1)
@ircd.Modules.commands('accept')
def callerid(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
            recv = recv[1:]
        sync = False
        if not hasattr(self, 'caller_id_accept'):
            self.caller_id_accept = []
        if not hasattr(self, 'caller_id_queue'):
            self.caller_id_queue = []
        if recv[1] == '*':
            ### Return list.
            for nick in self.caller_id_accept:
                self.sendraw(281, '{}'.format(nick))
            return self.sendraw(282, 'End of /ACCEPT list')

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\'
        for entry in recv[1].split(','):
            continueLoop = False
            action = ''
            if entry[0] == '-':
                action = '-'
                entry = entry[1:]
            for c in entry.lower():
                if c.lower() not in valid or entry[0].isdigit():
                    continueLoop = True
                    break
            if continueLoop:
                continue

            accept_lower = [x.lower() for x in self.caller_id_accept]
            if action != '-':
                if entry.lower() in accept_lower:
                    self.sendraw(457, '{} :does already exists on your ACCEPT list.'.format(entry))
                    continue
            if action == '-':
                if entry.lower() not in accept_lower:
                    self.sendraw(458, '{} :is not found on your ACCEPT list.'.format(entry))
                    continue
                match = list(filter(lambda a: a.lower() == entry.lower(), self.caller_id_accept))[0]
                self.caller_id_accept.remove(match)
                sync = True
                ### Remove targnotify
                for user in [user for user in localServer.users if user.nickname.lower() == entry.lower()]:
                    del user.targnotify[self]
                continue
            self.caller_id_accept.append(entry)
            sync = True
            ### Check queue.
            for q in [q for q in list(self.caller_id_queue) if q[0].split('!')[0].lower() == entry.lower()]:
                ### Do not make this count towards flood.
                ### In handleData, check if the data is prefixed by timestamps.
                p = {'safe': True}
                prefix = ''
                timestamp = int(q[1]/10)
                if 'server-time' in self.caplist:
                    ### @time=2011-10-19T16:40:51.620Z
                    prefix = '@time={}.{}Z '.format(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp)), round(q[1]%1000))
                raw_string = '{}:{} PRIVMSG {} :{}'.format(prefix, q[0], self.nickname, q[2])
                self._send(raw_string)
                self.caller_id_queue.remove(q)

        if sync:
            data = ':{} {}'.format(self.uid, ' '.join(recv))
            localServer.syncToServers(localServer, self.server, data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('eos')
def callerid_eos(self, localServer, recv):
    ### Sync all ACCEPT data to other servers.
    if not self.socket:
        return
    for user in [user for user in localServer.users if hasattr(user, 'caller_id_accept')]:
        data = []
        for accept in user.caller_id_accept:
            data.append(accept)
        if data:
            self._send(':{} ACCEPT {}'.format(user.uid, ','.join(data)))

def unload(localServer):
    for user in [user for user in localServer.users if hasattr(user, 'caller_id_queue')]:
        user.caller_id_queue = []
    for user in [user for user in localServer.users if hasattr(user, 'caller_id_accept')]:
        user.caller_id_accept = []
    for user in [user for user in localServer.users if hasattr(user, 'targnotify')]:
        user.targnotify = {}