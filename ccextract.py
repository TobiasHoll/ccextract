#!/usr/bin/python3
# -*- coding: utf8 -*-

"""Convert Apple iPhone / iPod contact data from iTunes backups to vCard format"""

# About iTunes backups:
#  File 31bb7ba8914766d4ba40d6dfb6113c8b614be442 contains all contact information
#  as a sqlite3 database

import argparse
import datetime
import os
import plistlib
import re
import sqlite3 # Use the newest version possible -> this has to be a py3k tool
import sys

class Contact:
    def __init__(s):
        s.first_name = ""                                                       # ABPerson -> First
        s.last_name = ""                                                        # ABPerson -> Last
        s.middle_name = ""                                                      # ABPerson -> Middle
        s.prefix = "" # Mr., Ms.                                                # ABPerson -> Prefix
        s.suffix = "" # Dr., Dipl.-Ing.                                         # ABPerson -> Suffix
        s.nickname = ""                                                         # ABPerson -> Nickname
        s.birthday = ""                                                         # ABPerson -> Birthday
        s.address = ""                                                          # ABPersonFullTextSearch_content -> c17Address
        s.tel = ""                                                              # ABPersonFullTextSearch_content -> c15Phone
        s.mail = ""                                                             # ABPersonFullTextSearch_content -> c16Email
        s.im = ""                                                               # ABPersonFullTextSearch_content -> c21IM
        s.title = ""                                                            # ABPerson -> JobTitle
        s.org = ""                                                              # ABPerson -> Organization, ABPerson -> Department
        s.note = ""                                                             # ABPerson -> Note
        s.url = ""                                                              # ABPersonFullTextSearch_content -> c19URL
    def vcard(s):
        comma2semicolon = lambda x: ";".join(x.replace("\n", ",").split(","))
        semicolon = lambda x: ";".join(x.split())
        comma = lambda x: ",".join(x.split())
        space = lambda x: " ".join(x.split(","))
        lines = []
        lines.append("BEGIN:VCARD") # Start vCard
        lines.append("VERSION:4.0") # vCard version (4.0)
        if (s.first_name or s.last_name or s.middle_name or s.prefix or s.suffix):
            lines.append("N:%s;%s;%s;%s;%s" % (comma(s.last_name), comma(s.first_name), comma(s.middle_name), comma(s.prefix), comma(s.suffix))) # Name
        lines.append("FN:%s" % " ".join( x for x in (space(s.prefix), space(s.suffix), space(s.first_name), space(s.middle_name), space(s.last_name)) if x )) # Formatted name
        if (s.nickname):
            lines.append("NICKNAME:%s" % s.nickname)
        if (isinstance(s.birthday, (int, float))):
            realdate = datetime.datetime.fromtimestamp(int(s.birthday)).date() # int is OK (birthday references 12pm)
            lines.append("BDAY:%04d%02d%02d" % (realdate.year, realdate.month, realdate.day))
        if (s.address):
            lines.append("ADDR:LABEL=\"%s\";;;%s" % (s.address.replace("\n", ", ").replace("\"", "'"), comma2semicolon(s.address)))
        if (s.tel):
            for x in re.split("\D", s.tel):
                if (x):
                    lines.append("TEL:%s" % x)
        if (s.mail):
            for x in re.split("\s", s.mail):
                if (x):
                    lines.append("EMAIL:%s" % x)
        if (s.im):
            for x in re.split("\s", s.im):
                if (x):
                    lines.append("IMPP:%s" % x)
        if (s.title):
            lines.append("TITLE:%s" % s.title)
        if (s.org):
            lines.append("ORG:%s" % s.org)
        if (s.note):
            lines.append("NOTE:%s" % s.note)
        if (s.url):
            lines.append("URL:%s" % s.url)
        return "\r\n".join(lines)

# (loglevel, name, file descriptor, extra indent)
INFO = (0, "INFO", sys.stdout, 0)
WARNING = (1, "WARNING", sys.stdout, 0)
ERROR = (2, "ERROR", sys.stderr, 0)
FATAL = (3, "FATAL", sys.stderr, 0)

CONT = lambda level: (level[0], "...", level[2], 2) # for line continuations

LOGLEVEL = INFO
LEVELS = { x[1] : x for x in (INFO, WARNING, ERROR, FATAL) }
LEVELNAMES = [key for key in LEVELS]
PLAIN = False

_maxlevelwidth = max([len(key) for key in LEVELS])


def write(level, message):
    if (level[0] >= LOGLEVEL[0]):
        msg = str(message)
        if (PLAIN):
            level[2].write(" " * level[3] + msg + "\n")
        else:
            line_width = 80 - (_maxlevelwidth + level[3] + 6) # + 6 : '[', ']', 2 spaces extra indent, one space right margin and newline character
            level[2].write("[" + level[1] + "]" + " " * (2 + _maxlevelwidth - len(level[1]) + level[3]) + msg[:line_width] + "\n")
            if (len(msg) > line_width): # oversize message
                write(CONT(level), msg[line_width:]) # write rest

def find_newest(path):
    objs = [os.path.join(path, x) for x in os.listdir(path)]
    dirs = sorted([(x, os.path.getmtime(x)) for x in objs if os.path.isdir(x)], key=lambda pair: pair[1], reverse=True)
    try:
        return dirs[0][0]
    except:
        write(FATAL, "No backups found.")
        sys.exit(-1)

def find_by_name(path, name):
    objs = [os.path.abspath(os.path.join(path, x)) for x in os.listdir(path)]
    dirs = sorted([x for x in objs if os.path.isdir(x)], key=lambda x: os.path.getmtime(x), reverse=True) # sort to get newest backup of that device
    for d in dirs:
        head = plistlib.readPlist(os.path.join(d, "Info.plist"))
        if (head["Device Name"] == name or head["Display Name"] == name):
            return d
    write(FATAL, "No backup found for device '%s'" % name)
    sys.exit(-1)


if ("darwin" in sys.platform.lower()):
    DEFAULT_BACKUP_FOLDER = os.path.abspath(os.path.expanduser("~/Library/Application Support/MobileSync/Backup"))
elif ("win" in sys.platform.lower()):
    DEFAULT_BACKUP_FOLDER = os.path.abspath(os.path.expandvars("%appdata%\\Apple Computer\\MobileSync\\Backup"))
else:
    require_backup_dir = True
    write(ERROR, "Could not detect backup folder - please use the '-b'/'--backup' option")
    DEFAULT_BACKUP_FOLDER = "?"

p = argparse.ArgumentParser(description="Converts contact data from Apple iOS backups (via iTunes) to vCard format")
p.add_argument("-o", "--output", help="Output folder", action="store", metavar="FOLDER", required=True)
p.add_argument("-b", "--backup", help="iTunes backup folder (default: " + DEFAULT_BACKUP_FOLDER + ")", action="store", metavar="FOLDER", default=DEFAULT_BACKUP_FOLDER, required=require_backup_dir)
p.add_argument("-n", "--name", help="Device name (default: choose the most recent backup). Useful if you back up more than one device", action="store", metavar="NAME")
p.add_argument("--plain", help="Plain logging (generally discouraged except for automated output processing)", action="store_true")
p.add_argument("-l", "--loglevel", help="Log level. One of " + ", ".join(LEVELNAMES) + " (default: INFO)", action="store", metavar="LEVEL", choices=LEVELNAMES, type=lambda key: LEVELS[key], default="INFO")
# -- add options here
args = p.parse_args()

if (args.loglevel):
    LOGLEVEL = args.loglevel

if (args.plain):
    PLAIN = True

if (args.output):
    output_dir = os.path.abspath(args.output)
    if (not os.path.exists(output_dir)): # output directory does not exist
        write(INFO, "Creating output directory")
        os.makedirs(output_dir)
    elif (not os.path.isdir(output_dir)): # output "directory" path does not reference a directory
        write(FATAL, "Output directory exists, but is not a directory")
        sys.exit(-1)
else:
    write(FATAL, "No output directory given")
    sys.exit(-1)
    
if (args.backup):
    all_backup_dir = os.path.abspath(args.backup)
else:
    write(WARNING, "No backup directory given, using default")

if (args.name):
    backup_dir = find_by_name(all_backup_dir, args.name)
    if (not backup_dir):
        write(FATAL, "Device '%s' not found" % args.name)
        sys.exit(-1)
    write(INFO, "Backup for '%s' found." % args.name)
else:
    backup_dir = find_newest(all_backup_dir)

contact_db = os.path.join(backup_dir, "31bb7ba8914766d4ba40d6dfb6113c8b614be442")

write(INFO, "Contact data location:")
write(CONT(INFO), contact_db)
write(INFO, "Output folder:")
write(CONT(INFO), output_dir)

connection = sqlite3.connect(contact_db)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

try:
    cursor.execute("SELECT 1 FROM ABPerson")
except sqlite3.DatabaseError:
    write(FATAL, "Either the database is corrupted or your version of the sqlite3 module is too old.")
    sys.exit(-1)

write(INFO, "Fetching data...")

contacts = {}

# Select all contacts from ABPerson and ABPersonFullTextSearch_content

# s.first_name                # ABPerson -> First
# s.last_name                 # ABPerson -> Last
# s.middle_name               # ABPerson -> Middle
# s.prefix                    # ABPerson -> Prefix
# s.suffix                    # ABPerson -> Suffix
# s.nickname                  # ABPerson -> Nickname
# s.birthday                  # ABPerson -> Birthday
# s.address                   # ABPersonFullTextSearch_content -> c17Address
# s.tel                       # ABPersonFullTextSearch_content -> c15Phone
# s.mail                      # ABPersonFullTextSearch_content -> c16Email
# s.im                        # ABPersonFullTextSearch_content -> c21IM
# s.title                     # ABPerson -> JobTitle
# s.org                       # ABPerson -> Organization, ABPerson -> Department
# s.note                      # ABPerson -> Note
# s.url                       # ABPersonFullTextSearch_content -> c19URL
 
for row in cursor.execute("SELECT * FROM ABPerson JOIN ABPersonFullTextSearch_content ON ABPerson.ROWID == ABPersonFullTextSearch_content.docid"):
    c = Contact()
    
    res = { key : (row[key] if row[key] != None else "") for key in row.keys() }
    
    c.first_name = res["First"]
    c.last_name = res["Last"]
    c.middle_name = res["Middle"]
    c.prefix = res["Prefix"]
    c.suffix = res["Suffix"]
    c.nickname = res["Nickname"]
    c.birthday = res["Birthday"]
    c.address = res["c17Address"]
    c.tel = res["c15Phone"]
    c.mail = res["c16Email"]
    c.im = res["c21IM"]
    c.title = res["JobTitle"]
    c.org = res["Organization"] + (" - " + res["Department"] if res["Department"] else "")
    c.note = res["Note"]
    c.url = res["c19URL"]
    
    # get filename
    fn = ((c.first_name + " ") if c.first_name else "") + ((c.middle_name + " ") if c.middle_name else "") + (c.last_name if c.last_name else "")
    if (os.path.exists(os.path.join(output_dir, fn + ".vcf"))):
        cid = 2
        while (os.path.exists(os.path.join(output_dir, fn + " - %d" % cid + ".vcf"))):
            cid += 1
        fn += " - %d" % cid
        
    write(INFO, "Writing contact: %s" % fn)
    
    
    # write file
    with open(os.path.join(output_dir, fn), 'w') as f:
        f.write(c.vcard())
    
