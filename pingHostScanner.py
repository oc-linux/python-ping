#!/usr/bin/env python
# -*- coding:utf-8 -*-
 
"""
    A pure python ping implementation using raw socket.
 
 
    Note that ICMP messages can only be sent from processes running as root.
 
 
    Derived from ping.c distributed in Linux's netkit. That code is
    copyright (c) 1989 by The Regents of the University of California.
    That code is in turn derived from code written by Mike Muuss of the
    US Army Ballistic Research Laboratory in December, 1983 and
    placed in the public domain. They have my thanks.
 
    Bugs are naturally mine. I'd be glad to hear about them. There are
    certainly word - size dependenceies here.
 
    Copyright (c) Matthew Dixon Cowles, <http://www.visi.com/~mdc/>.
    Distributable under the terms of the GNU General Public License
    version 2. Provided with no warranties of any sort.
 
    Original Version from Matthew Dixon Cowles:
      -> ftp://ftp.visi.com/users/mdc/ping.py
 
    Rewrite by Jens Diemer:
      -> http://www.python-forum.de/post-69122.html#69122
 
    Rewrite by George Notaras:
      -> http://www.g-loaded.eu/2009/10/30/python-ping/

    Fork by Pierre Bourdon:
      -> http://bitbucket.org/delroth/python-ping/
      
    Fork by Joan-Luc Labòrda : porting to Python3
      -> https://github.com/oc-linux/python-ping
 
    Revision history
    ~~~~~~~~~~~~~~~~
 
    November 22, 1997
    -----------------
    Initial hack. Doesn't do much, but rather than try to guess
    what features I (or others) will want in the future, I've only
    put in what I need now.
 
    December 16, 1997
    -----------------
    For some reason, the checksum bytes are in the wrong order when
    this is run under Solaris 2.X for SPARC but it works right under
    Linux x86. Since I don't know just what's wrong, I'll swap the
    bytes always and then do an htons().
 
    December 4, 2000
    ----------------
    Changed the struct.pack() calls to pack the checksum and ID as
    unsigned. My thanks to Jerome Poincheval for the fix.
 
    May 30, 2007
    ------------
    little rewrite by Jens Diemer:
     -  change socket asterisk import to a normal import
     -  replace time.time() with time.clock()
     -  delete "return None" (or change to "return" only)
     -  in checksum() rename "str" to "source_string"
 
    November 8, 2009
    ----------------
    Improved compatibility with GNU/Linux systems.
 
    Fixes by:
     * George Notaras -- http://www.g-loaded.eu
    Reported by:
     * Chris Hallman -- http://cdhallman.blogspot.com
 
    Changes in this release:
     - Re-use time.time() instead of time.clock(). The 2007 implementation
       worked only under Microsoft Windows. Failed on GNU/Linux.
       time.clock() behaves differently under the two OSes[1].
 
    [1] http://docs.python.org/library/time.html#time.clock
"""

__version__ = "0.1"
 
 
import os, sys, socket, struct, select, time
# import os, socket, struct, select, time
 
# From /usr/include/linux/icmp.h; your milage may vary.
ICMP_ECHO_REQUEST = 8 # Seems to be the same on Solaris.
 
class pingHostScanner():
    """
    """
    def __init__ (self,Host,output=sys.stdout,log=sys.stderr):
        self.dest_addr=Host
        if (output != sys.stdout):
            # The standard output is redirected to a file
            self.outf = open(output,'a')
        else :
            self.outf=output
        if (log != sys.stderr) :
            # The standard error is redirected to a log file
            self.logf = open(log,'a')
        else :
            self.logf = log
            
    def __del__(self):
        self.outf.close()
        self.logf.close()
    
    def checksum(self,source_string):
        """
        I'm not too confident that this is right but testing seems
        to suggest that it gives the same answers as in_cksum in ping.c
        """
        sum = 0
        countTo = (len(source_string)/2)*2
        count = 0
        while count<countTo:
            thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
            sum = sum + thisVal
            sum = sum & 0xffffffff # Necessary?
            count = count + 2
 
        if countTo<len(source_string):
            sum = sum + ord(source_string[len(source_string) - 1])
            sum = sum & 0xffffffff # Necessary?
 
        sum = (sum >> 16)  +  (sum & 0xffff)
        sum = sum + (sum >> 16)
        answer = ~sum
        answer = answer & 0xffff
        
        # Swap bytes. Bugger me if I know why.
        answer = answer >> 8 | (answer << 8 & 0xff00)
        
        return answer
 
 
    def receive_one_ping(self,my_socket, ID, timeout):
        """
        receive the ping from the socket.
        """
        timeLeft = timeout
        while True:
            startedSelect = time.time()
            whatReady = select.select([my_socket], [], [], timeLeft)
            howLongInSelect = (time.time() - startedSelect)
            if whatReady[0] == []: # Timeout
                return
 
            timeReceived = time.time()
            recPacket, addr = my_socket.recvfrom(1024)
            icmpHeader = recPacket[20:28]
            type, code, checksum, packetID, sequence = struct.unpack(
                "bbHHh", icmpHeader
            )
            if packetID == ID:
                bytesInDouble = struct.calcsize("d")
                timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
                return timeReceived - timeSent
 
            timeLeft = timeLeft - howLongInSelect
            if timeLeft <= 0:
                return
 
 
    def send_one_ping(self,my_socket, ID):
        """
        Send one ping to the given >self.dest_addr<.
        """
        dest_addr  =  socket.gethostbyname(self.dest_addr)
 
        # Header is type (8), code (8), checksum (16), id (16), sequence (16)
        my_checksum = 0
 
        # Make a dummy heder with a 0 checksum.
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
        bytesInDouble = struct.calcsize("d")
        data = (192 - bytesInDouble) * "Q"
        data = struct.pack("d", time.time()) + data
 
        # Calculate the checksum on the data and the dummy header.
        my_checksum = self.checksum(header + data)
 
        # Now that we have the right checksum, we put that in. It's just easier
        # to make up a new header than to stuff it into the dummy.
        header = struct.pack(
        "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
        )
        packet = header + data
        my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1
 
 
    def do_one(self, timeout):
        """
        Returns either the delay (in seconds) or none on timeout.
             # socket.socket([family[, type[, proto]]])
             # my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        """
        icmp = socket.getprotobyname("icmp")
        try: 
            my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        except socket.herror as err :
            if err[0] == 1:
                # Operation not permitted
                msg = err[1] + (
                    " - Note that ICMP messages can only be sent from processes"
                    " running as root."
                )
                raise socket.error(msg)
            raise # raise the original error
 
        my_ID = os.getpid() & 0xFFFF
 
        self.send_one_ping(my_socket, my_ID)
        delay = self.receive_one_ping(my_socket, my_ID, timeout)
 
        my_socket.close()
        return delay
 
 
    def verbose_ping(self, timeout = 2, count = 4):
        """
        Send >count< ping to >self.dest_addr< with the given >timeout< and display
        the result.
        """
    #    for i in xrange(count):
        for i in range(count):
            # print ("ping %s..." % self.dest_addr)
            self.outf.write ("ping %s...\n" % self.dest_addr)
            try:
                delay  =  self.do_one(timeout)
            except socket.gaierror as e :
                # print ("failed. (socket error: '%s')" % e[1])
                self.logf.write ("failed. (socket error: '%s'\n)" % e[1])
                break
 
            if delay  ==  None:
                # print ("failed. (timeout within %ssec.)" % timeout)
                self.outf.write  ("failed. (timeout within %ssec.\n)" % timeout)
            else:
                delay  =  delay * 1000
                # print ("get ping in %0.4fms" % delay)
                self.outf.write ("get ping in %0.4fms\n" % delay)
            # self.outf.write ("\")
 
def test_pingHostScanner(Host):
    ping=pingHostScanner(Host, "/tmp/test_pingHostScanner",
                         "/tmp/log_pingHostScanner")
    ping.verbose_ping()
 
if __name__ == '__main__':
    test_pingHostScanner("127.0.0.1")   #     verbose_ping("127.0.0.1")
    test_pingHostScanner("192.168.1.1")   #    verbose_ping("192.168.1.1")
    test_pingHostScanner("heise.de")  #     verbose_ping("heise.de")  # 
    test_pingHostScanner("google.com")  #     verbose_ping("google.com")
    test_pingHostScanner("513.5130.1920.1127.168")   #     verbose_ping("127.0.0.1")
    test_pingHostScanner("a-test-url-that-is-not-available.com")
     # verbose_ping("a-test-url-that-is-not-available.com")
