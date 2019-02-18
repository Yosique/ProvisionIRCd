#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +f (flood control)
"""

import ircd
from threading import Timer
import time
import os
import sys
from handle.functions import _print

rt = None

def checkExpiredFloods(localServer):
    ### Checking for timed-out flood protection.
    channels = (channel for channel in localServer.channels if 'f' in channel.modes and 'm' in channel.chmodef)
    for chan in channels:
        for user in (user for user in chan.users if user in dict(chan.messageQueue)):
            if time.time() - chan.messageQueue[user]['ctime'] > chan.chmodef['m']['time']:
                #print('Resetting flood for {} on {}'.format(user,chan))
                del chan.messageQueue[user]

    channels = (channel for channel in localServer.channels if 'f' in channel.modes and 'j' in channel.chmodef)
    for chan in channels:
        for entry in (entry for entry in dict(chan.joinQueue)):
            if int(time.time()) - chan.joinQueue[entry]['ctime'] > chan.chmodef['j']['time']:
                #print('Resetting flood for {} on {}'.format(user, chan))
                del chan.joinQueue[entry]
        if chan.chmodef['j']['action'] == 'i' and 'i' in chan.modes:
            if chan.chmodef['j']['actionSet'] and int(time.time()) - chan.chmodef['j']['actionSet'] > chan.chmodef['j']['duration']*60:
                localServer.handle('MODE', '{} -i'.format(chan.name))
                chan.chmodef['j']['actionSet'] = None
        elif chan.chmodef['j']['action'] == 'R' and 'R' in chan.modes:
            if chan.chmodef['j']['actionSet'] and int(time.time()) - chan.chmodef['j']['actionSet'] > chan.chmodef['j']['duration']*60:
                localServer.handle('MODE', '{} -R'.format(chan.name))
                chan.chmodef['j']['actionSet'] = None

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.daemon = True
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

@ircd.Modules.events('after_privmsg') ### self, localServer, channel, msg, module
def msg(*args):
    if len(args) < 3:
        return
    self = args[0]
    localServer = args[1]
    channel = args[2]
    ### Move this to module
    if 'f' in channel.modes and 'm' in channel.chmodef and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
        if self not in channel.messageQueue:
            channel.messageQueue[self] = {}
            channel.messageQueue[self]['ctime'] = time.time()
        channel.messageQueue[self][int(round(time.time() * 1000))] = None
        if len(channel.messageQueue[self]) > channel.chmodef['m']['amount']:
            if channel.chmodef['m']['action'] == 'kick':
                localServer.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']))
            elif channel.chmodef['m']['action'] == 'b':
                duration = channel.chmodef['m']['duration']
                localServer.handle('MODE', '{} +b ~t:{}:*@{}'.format(channel.name, duration, self.cloakhost))
                localServer.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']))
            continue

@ircd.Modules.events('after_join')
def after_join(self, localServer, channel):
    if 'f' in channel.modes and 'j' in channel.chmodef and self.server == localServer: # and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override
        r = int(round(time.time() * 1000))
        channel.joinQueue[r] = {}
        channel.joinQueue[r]['ctime'] = int(time.time())
        if len(channel.joinQueue) > channel.chmodef['j']['amount']:
            ### What should we do?
            channel.joinQueue = {}
            if channel.chmodef['j']['action'] == 'i':
                localServer.handle('MODE', '{} +i'.format(channel.name))
            elif channel.chmodef['j']['action'] == 'R':
                localServer.handle('MODE', '{} +R'.format(channel.name))
            channel.chmodef['j']['actionSet'] = int(time.time())

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes('f', 2, 3, 'Set flood protection for your channel', None, None, '[params]') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.events('mode')
def chmodeF(*args): ### Params: self, localServer, recv, tmodes, param, commandQueue
    if len(args) < 4:
        return
    try:
        self = args[0]
        localServer = args[1]
        recv = args[2]
        tmodes = args[3]
        param = args[4]
        channel = channel = list(filter(lambda c: c.name.lower() == recv[0].lower(), localServer.channels))
        if not channel:
            return
        channel = channel[0]
        ### Format: +f [amount:type:secs][action:duration] --- duration is in minutes.

        ### Example: +f 3:j:10 (3 join in 10 sec, default is +i for 1 minute)
        ### Example: +f 3:j:10:i:2 (3 joins in 10 sec, sets channel to +i for 2 minutes)
        ### Example: +f 3:j:10:R:5 (3 joins in 10 sec, sets channel to +R for 5 minutes)

        ### Example: +f 3:m:10 (3 messages in 10 sec, default action is kick)
        ### Example: +f 5:m:3:b:1 (5 messages in 3 sec, will ban/kick for 1 minute)

        floodTypes = 'jm'

        paramcount = 0
        action = ''
        for m in recv[1]:
            if m in '+-':
                action = m
                continue
            try:
                p = recv[2:][paramcount]
            except:
                paramcount += 1
                continue
            if action == '+' and m == 'f':
                if len(p) < 2:
                    paramcount += 1
                    continue
                if p[0] == '-':
                    type = p[1]
                    #print('Removing flood type')
                    if type not in floodTypes or type not in channel.chmodef:
                        #print('Type {} not found in {}'.format(type, channel.chmodef))
                        paramcount += 1
                        continue
                    del channel.chmodef[type]
                    #print('Success! Returning {}'.format(type))
                    if len(channel.chmodef) == 0:
                        #print('No more protections set. Removing \'f\' completely')
                        self.handle('MODE', '{} -f'.format(channel.name))
                        break
                    tmodes.append(m)
                    param.append('-{}'.format(type))
                    paramcount += 1
                    continue

                if len(p.split(':')) < 3:
                    #print('Invalid param format')
                    paramcount += 1
                    continue
                if not p.split(':')[0].isdigit():
                    #print('Amount must be a number')
                    paramcount += 1
                    continue
                if p.split(':')[1] not in floodTypes:
                    #print('Invalid flood type')
                    paramcount += 1
                    continue
                if not p.split(':')[2].isdigit():
                    #print('Seconds must be a number (really!)')
                    paramcount += 1
                    continue
                ### All is good, set the mode.
                amount = int(p.split(':')[0])
                type = p.split(':')[1]
                secs = int(p.split(':')[2])
                if type in channel.chmodef:
                    #print('Updating current protection from {}'.format(channel.chmodef))
                    if amount == channel.chmodef[type]['amount'] and secs == channel.chmodef[type]['time']:
                        #print('Protection is the same. Doing nothing.')
                        paramcount += 1
                        continue
                    del channel.chmodef[type]

                ### Check for alternative action:
                fAction = None
                try:
                    fAction = p.split(':')[3]
                except:
                    pass
                if fAction:
                    ### We have an action, check if it is valid.
                    #print('Checking alternative action')
                    if type == 'm' and fAction not in ['m', 'b']:
                        ### Invalid action, reverting to default.
                        fAction = None
                    elif type == 'j' and fAction not in ['i', 'R']:
                        ### Invalid action, reverting to default.
                        fAction = None
                    if fAction:
                        ### Ok, valid action.
                        try:
                            duration = p.split(':')[4]
                            if not duration.isdigit():
                                #print('Invalid duration, unsetting action')
                                fAction = None
                            else:
                                duration = int(duration)
                                #print('Duration for {} set to: {}'.format(fAction, duration))
                        except:
                            #print('Alternative action was given, but no duration. Unsetting action')
                            fAction = None

                channel.chmodef[type] = {}
                channel.chmodef[type]['amount'] = amount
                channel.chmodef[type]['time']   = secs
                if not fAction:
                    p = ':'.join(p.split(':')[:3])
                    ### Default action
                    if type == 'm':
                        channel.chmodef[type]['action'] = 'kick'
                    elif type == 'j':
                        channel.chmodef[type]['action'] = 'i'
                        channel.chmodef[type]['actionSet'] = None
                        channel.chmodef[type]['duration'] = 1

                else:
                    channel.chmodef[type]['action'] = str(fAction)
                    channel.chmodef[type]['duration'] = duration
                    channel.chmodef[type]['actionSet'] = None

                #print('Success! Returning {}'.format(p))
                if m not in channel.modes:
                    channel.modes += m
                tmodes.append(m)
                param.append(p)
                paramcount += 1

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

def init(self):
    global rt
    rt = RepeatedTimer(1, checkExpiredFloods, self) # it auto-starts, no need of rt.start()
    for chan in [chan for chan in self.channels]:
        if not hasattr(chan, 'chmodef'):
            chan.chmodef = {}
        if not hasattr(chan, 'messageQueue'):
            chan.messageQueue = {}
        if not hasattr(chan, 'joinQueue'):
            chan.joinQueue = {}

def unload(self):
    global rt
    rt.stop()