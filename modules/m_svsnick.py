#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/svsnick command (server)
"""

import ircd

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('svsnick')
def svsnick(self, localServer, recv):
    S = recv[0][1:]
    source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
    if not source:
        return
    source = source[0]
    target = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], localServer.users))
    if not target:
        return
    p = {'sanick': source}
    target[0].handle('nick', recv[3], params=p)
