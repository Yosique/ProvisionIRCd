#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/error command (server)
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('error')
def error(self, localServer, recv):
    ### 00B ERROR :msg
    msg = ' '.join(recv[1:])[1:]
    localServer.snotice('s', '*** {}'.format(msg))
    self.quit(msg, silent=True)
