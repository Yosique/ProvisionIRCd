#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/chgcname command
"""

import ircd

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('chgcname')
def cmd_CHGCNAME(self, localServer, recv):
    if type(self).__name__ == 'Server':
        sourceServer = self
        self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
        recv = recv[1:]
    else:
        sourceServer = self.server
    name = recv[2]
    requested_prefix = name[0]

    channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
    if not channel:
        return localServer.notice(self, 'That channel does not exist.')

    channel = channel[0]

    original_prefix = channel.name[0]

    if requested_prefix != original_prefix:
        return localServer.notice(self, 'Converting of channel type is not allowed.')

    if name == channel.name:
        return localServer.notice(self, 'Channel names are equal; nothing changed.')

    if name.lower() != channel.name.lower():
        return localServer.notice(self, 'Only case changing is allowed.')

    if sourceServer == localServer:
        localServer.notice(self, 'Channel {} successfully changed to {}'.format(channel.name, name))

    localServer.new_sync(localServer, sourceServer, ':{} CHGCNAME {} {}'.format(self.uid, channel.name, name))
    old_name = channel.name
    channel.name = name
    if sourceServer == localServer:
        msg = '*** {} ({}@{}) used CHGCNAME to change channel name {} to {}'.format(self.nickname, self.ident, self.hostname, old_name, name)
        localServer.snotice('s', msg)
