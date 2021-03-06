"""
/whois and /whowas command
"""

import ircd
import time
import datetime
from handle.functions import logging

@ircd.Modules.user_modes('c', 0, 'Hide channels in /WHOIS') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.user_modes('W', 1, 'See when people are doing a /WHOIS on you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.commands('whois')
def whois(self, localServer, recv):
    try:
        if len(recv) < 2:
            self.sendraw(431, ':No nickname given')
            return
        user = list(filter(lambda u: u.nickname.lower() == recv[1].lower(), self.server.users))

        if not user or not user[0].registered:
            self.sendraw(401, '{} :No such nick'.format(recv[1]))
            self.sendraw(318, '{} :End of /WHOIS list.'.format(recv[1]))
            return

        user = user[0]

        if 'W' in user.modes and user != self:
            msg = '*** Notice -- {} ({}@{}) did a /WHOIS on you.'.format(self.nickname, self.ident, self.hostname)
            us = list(filter(lambda u: u.nickname == user.nickname and user.server == localServer, localServer.users))
            if us:
                self.server.broadcast(us, 'NOTICE {} {}'.format(user.nickname, msg))
            else:
                data = ':{} NOTICE {} :{}'.format(localServer.hostname, user.nickname, msg)
                sock = user.server if user.server.socket else user.server.introducedBy
                sock._send(data)

        self.sendraw(311, '{} {} {} * :{}'.format(user.nickname, user.ident, user.cloakhost if 'x' in user.modes else user.hostname, user.realname))

        if 'o' in self.modes or user == self:
            self.sendraw(379, '{} :is using modes: +{} {}'.format(user.nickname, user.modes, '+'+user.snomasks if user.snomasks else ''))

        if ('o' in self.modes or user == self) and user.server.hostname not in localServer.conf['settings']['ulines'] and 'S' not in user.modes:
            self.sendraw(378, '{} :is connecting from *@{} {}'.format(user.nickname, user.hostname, user.ip))

        if 'r' in user.modes:
            self.sendraw(307, '{} :is identified for this nick'.format(user.nickname))

        if 'c' not in user.modes or 'o' in self.modes or user == self:
            if user.channels and user.server.hostname not in localServer.conf['settings']['ulines'] and 'S' not in user.modes:
                channels = []
                for channel in user.channels:
                    visible = 1
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](self, localServer, user, channel)
                        except Exception as ex:
                            logging.exception(ex)
                        if not visible:
                            break
                    if not visible:
                        continue

                    prefix = ''
                    if visible == 2:
                        prefix += '?'
                    if '^' in user.modes and not self.ocheck('o', 'stealth'):
                        continue
                    if '^' in user.modes:
                        prefix = '^'
                    if 's' in channel.modes or 'p' in channel.modes:
                        if user != self and self not in channel.users and 'o' not in self.modes:
                            continue
                        if '!' not in prefix and '?' not in prefix:
                            prefix += '?'
                    if 'c' in user.modes and ('o' in self.modes or user == self) and '?' not in prefix:
                        prefix += '!'
                    if 'q' in channel.usermodes[user]:
                        prefix += '~'
                    if 'a' in channel.usermodes[user]:
                        prefix += '&'
                    if 'o' in channel.usermodes[user]:
                        prefix += '@'
                    if 'h' in channel.usermodes[user]:
                        prefix += '%'
                    if 'v' in channel.usermodes[user]:
                        prefix += '+'
                    channels.append('{}{}'.format(prefix, channel.name))
                if channels:
                    self.sendraw(319, '{} :{}'.format(user.nickname, ' '.join(channels)))

        self.sendraw(312, '{} {} :{}'.format(user.nickname, user.server.hostname, user.server.name))

        if user.away:
            self.sendraw(301, '{} :{}'.format(user.nickname, user.away))

        if 'H' not in user.modes or 'o' in self.modes:
            if 'o' in user.modes and 'S' not in user.modes:
                show_acc = True if user.operaccount and (user == self or (self.operaccount and self.operaccount == user.operaccount)) else False
                self.sendraw(313, '{} :is an IRC Operator{}'.format(user.nickname, ' [{}]'.format(user.operaccount) if 'o' in self.modes and show_acc else ''))

        #if 'h' in user.modes and 'S' not in user.modes and user.server.hostname not in localServer.conf['settings']['ulines'] and 'H' not in user.modes:
        #    self.sendraw(310, '{} :is available for help'.format(user.nickname))

        #if 'q' in user.modes and 'S' not in user.modes and user.server.hostname not in localServer.conf['settings']['ulines'] and 'H' not in user.modes:
        #    self.sendraw(310, '{} :is protected on all channels'.format(user.nickname))
        if 'B' in user.modes:
            self.sendraw(335, '{} :is a bot on {}'.format(user.nickname, user.server.name))

        if 'z' in user.modes and 'S' not in user.modes and user.server.hostname not in localServer.conf['settings']['ulines']:
            self.sendraw(671, '{} :is using a secure connection'.format(user.nickname))

            if user.fingerprint:
                self.sendraw(276, '{} :has client certificate fingerprint {}'.format(user.nickname, user.fingerprint))

        ### Read below.
        if 'H' not in user.modes or 'o' in self.modes: ### TODO: only exclude oper-whois on +H. Other swhois should be visible.
            for line in user.swhois:
                self.sendraw(320, '{} :{}'.format(user.nickname,line))

        if hasattr(user, 'svid') and user.svid != '*':
            self.sendraw(330, '{} {} :is using acount'.format(user.nickname, user.svid))

        if localServer.hostname == user.server.hostname or 'o' in self.modes and 'S' not in user.modes and user.server.hostname not in localServer.conf['settings']['ulines']:
            self.sendraw(317, '{} {} {} :seconds idle, signon time'.format(user.nickname, int(time.time()) - user.idle, user.signon))

        if 'S' in user.modes:
            self.sendraw(313, '{} :is a Network Service'.format(user.nickname))

        self.sendraw(318, '{} :End of /WHOIS list.'.format(user.nickname))
    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.commands('whowas')
def whowas(self, localServer, recv):
    try:
        if len(recv) < 2:
            self.sendraw(431, ':No nickname given')
            return
        isWhowas = False
        if not hasattr(localServer, 'whowas'):
            localServer.whowas = {}
        for nick in localServer.whowas:
            if nick.lower() == recv[1].lower():
                isWhowas = True
                for info in localServer.whowas[nick]:
                    ident = info['ident']
                    cloakhost = info['cloakhost']
                    realname = info['realname']
                    hostname = info['hostname']
                    ip = info['ip']
                    signoff = int(info['signoff'])
                    d = datetime.datetime.fromtimestamp(signoff).strftime('%a %b %d')
                    t = datetime.datetime.fromtimestamp(signoff).strftime('%H:%M:%S %Z').strip()
                    y = datetime.datetime.fromtimestamp(signoff).strftime('%Y')
                    server = info['server']
                    self.sendraw(314, '{} {} {} * :{}'.format(nick, ident, cloakhost, realname))
                    if 'o' in self.modes:
                        self.sendraw(378, '{} :connected from *@{} {}'.format(nick, hostname, ip))
                    self.sendraw(312, '{} {} :{} {} {}'.format(nick, server, d, t, y))

        if not isWhowas:
            self.sendraw(406, '{} :There was no such nickname'.format(recv[1]))
            self.sendraw(369, '{} :End of /WHOWAS list.'.format(recv[1]))
            return

        self.sendraw(369, '{} :End of /WHOWAS list.'.format(recv[1]))

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.local_quit()
@ircd.Modules.hooks.remote_quit()
@ircd.Modules.hooks.local_nickchange()
@ircd.Modules.hooks.remote_nickchange()
def savewhowas(self, localServer):
    try:
        if type(self).__name__ == 'Server' or not self.registered:
            return
        if not hasattr(localServer, 'whowas'):
            localServer.whowas = {}
        if self.nickname not in localServer.whowas:
            localServer.whowas[self.nickname] = []
        whowasInfo = {}
        whowasInfo[self.nickname] = {}
        whowasInfo[self.nickname]['ident'] = self.ident
        whowasInfo[self.nickname]['cloakhost'] = self.cloakhost
        whowasInfo[self.nickname]['realname'] = self.realname
        whowasInfo[self.nickname]['hostname'] = self.hostname
        whowasInfo[self.nickname]['ip'] = self.ip
        whowasInfo[self.nickname]['server'] = self.server.hostname
        whowasInfo[self.nickname]['signoff'] = int(time.time())

        localServer.whowas[self.nickname].append(whowasInfo[self.nickname])
        if len(localServer.whowas[self.nickname]) > 12:
            del localServer.whowas[self.nickname][0]

        for nick in dict(localServer.whowas):
            info = list(localServer.whowas[nick])
            for data in info:
                signoff = data['signoff']
                if int(time.time()) - signoff > 3600*24*30: ### 1 month expire?
                    localServer.whowas[nick].remove(data)

    except Exception as ex:
        logging.exception(ex)
