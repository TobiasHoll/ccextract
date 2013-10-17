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
import uuid

# Version number
VERSION = "1.2"

# Constants

EPOCH = datetime.datetime(2001, 1, 1, 0, 0, 0, 0) # Not UNIX, but some sort of Apple constant (??)

# Logging
# (loglevel, name, file descriptor, extra indent)
DEBUG = (-1, "DEBUG", sys.stdout, 0)
INFO = (0, "INFO", sys.stdout, 0)
WARNING = (1, "WARNING", sys.stdout, 0)
ERROR = (2, "ERROR", sys.stderr, 0)
FATAL = (3, "FATAL", sys.stderr, 0)

CONT = lambda level: (level[0], "...", level[2], 2) # for line continuations

LOGLEVEL = INFO
LEVELS = { x[1] : x for x in (DEBUG, INFO, WARNING, ERROR, FATAL) }
LEVELNAMES = sorted([key for key in LEVELS], key=lambda k: LEVELS[k][0])
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
                write(CONT(level), msg[line_width:].strip()) # write rest

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

require_backup_dir = False
if ("darwin" in sys.platform.lower()):
    DEFAULT_BACKUP_FOLDER = os.path.abspath(os.path.expanduser("~/Library/Application Support/MobileSync/Backup"))
elif ("win" in sys.platform.lower()):
    DEFAULT_BACKUP_FOLDER = os.path.abspath(os.path.expandvars("%appdata%\\Apple Computer\\MobileSync\\Backup"))
else:
    require_backup_dir = True
    write(ERROR, "Could not detect backup folder - please use the '-b'/'--backup' option")
    DEFAULT_BACKUP_FOLDER = "?"

p = argparse.ArgumentParser(prog="ccextract", description="Converts contact data from Apple iOS backups (via iTunes) to vCard format")
p.add_argument("-o", "--output", help="Output folder (default: " + os.path.join(".", "extracted") + ")", action="store", metavar="FOLDER", default=os.path.join(os.getcwd(), "extracted"))
p.add_argument("-b", "--backup", help="iTunes backup folder (default: " + DEFAULT_BACKUP_FOLDER + ")", action="store", metavar="FOLDER", default=DEFAULT_BACKUP_FOLDER, required=require_backup_dir)
p.add_argument("-n", "--name", help="Device name (default: choose the most recent backup). Useful if you back up more than one device", action="store", metavar="NAME")
p.add_argument("-l", "--loglevel", help="Log level. One of " + ", ".join(LEVELNAMES) + " (default: INFO)", action="store", metavar="LEVEL", choices=LEVELNAMES, default="INFO")
p.add_argument("--plain", help="Plain text logging (generally discouraged except for automated output processing)", action="store_true")
p.add_argument("--version", action="version", version="%(prog)s " + VERSION + " - for more information, see the CHANGELOG file")
# -- add options here

args = p.parse_args()

if (args.loglevel):
    LOGLEVEL = LEVELS[args.loglevel]

if (args.plain):
    PLAIN = True

if (args.output):
    output_dir = os.path.abspath(args.output)
    group_dir = os.path.join(output_dir, "groups")
    if (not os.path.exists(output_dir)): # output directory does not exist
        write(INFO, "Creating output directory")
        os.makedirs(output_dir)
    elif (not os.path.isdir(output_dir)): # output "directory" path does not reference a directory
        write(FATAL, "Output directory exists, but is not a directory")
        sys.exit(-1)
    else:
        write(WARNING, "Output directory exists - If files with the same names as chosen by ccextract exist, the new filenames will have a counter number attached")
    if (not os.path.exists(group_dir)): # create group directory
        write(INFO, "Creating groups directory")
        os.makedirs(group_dir)
    elif (not os.path.isdir(group_dir)): # group "directory" is not a directory
        write(FATAL, "Groups directory exists, but is not a directory")
        sys.exit(-1)
    else:
        write(WARNING, "Group directory exists - If files with the same names as chosen by ccextract exist, the new filenames will have a counter number attached")
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
# s.address                   # via ABMultiValue
# s.tel                       # dto.
# s.mail                      # dto.
# s.im                        # dto.
# s.title                     # ABPerson -> JobTitle
# s.org                       # ABPerson -> Organization, ABPerson -> Department
# s.note                      # ABPerson -> Note
# s.url                       # via ABMultiValue


uid_map = {}

for row in cursor.execute("SELECT ROWID, First, Last, Middle, Prefix, Suffix, Nickname, Birthday, JobTitle, Organization, Department, Note FROM ABPerson").fetchall():
    row_id = row["ROWID"]
    
    lines = []
    
    # Metadata
    lines.append("BEGIN:VCARD") # Start vCard
    lines.append("VERSION:4.0") # vCard version (4.0)
    
    # UUID
    uid = str(uuid.uuid1())
    uid_map[row_id] = uid
    lines.append("UID:urn:uuid:%s" % uid)
    
    # Name
    first_name = row["First"]
    last_name = row["Last"]
    middle_name = row["Middle"]
    prefix = row["Prefix"]
    suffix = row["Suffix"]
    if (first_name or last_name or middle_name or prefix or suffix):
        lines.append("N:%s;%s;%s;%s;%s" % (last_name, first_name, middle_name, prefix, suffix)) # Name
    full_name = " ".join( x for x in (prefix, first_name, middle_name, last_name, suffix) if x )
    lines.append("FN:%s" % full_name) # Formatted name (required)
    
    # Nickname
    nickname = row["Nickname"]
    if (nickname):
        lines.append("NICKNAME:%s" % nickname.replace(",", "\\,"))
    
    # Birthday
    try:
        birthday = float(row["Birthday"])
    except:
        birthday = None    
    if (birthday != None):
        birthday = int(birthday) # int is OK (birthday references 12pm from the epoch on that day)
        realdate = EPOCH + datetime.timedelta(seconds=birthday) # direct datetime.datetime.fromtimestamp does not work on dates prior to 19700101
        lines.append("BDAY:%04d%02d%02d" % (realdate.year, realdate.month, realdate.day))
    
    # Title
    title = row["JobTitle"]
    if (title):
        lines.append("TITLE:%s" % title.replace(",", "\\,"))
    
    # Organization
    dept_raw = row["Department"]
    org_raw = row["Organization"]
    if (dept_raw and org_raw):
        org = str(org_raw) + ";" + str(dept_raw)
    elif (org_raw):
        org = str(org_raw)
    elif (dept_raw):
        org = str(dept_raw)
    else:
        org = None
    if (org):
        lines.append("ORG:%s" % org.replace(",", "\\,"))
        
    # Note
    note = row["Note"]
    if (note):
        lines.append("NOTE:%s" % note.replace(",", "\\,"))
    
   
    # Get phone number / mail address / ...
    address = []
    im = []
    skipped_social_media = False
    for subrow in cursor.execute("SELECT * FROM ABMultiValue m WHERE m.record_id == ?", [str(row_id)]).fetchall():
        # Get label ("home", "work", ...)
        if (subrow["label"]):
            label = cursor.execute("SELECT value FROM ABMultiValueLabel l WHERE l.rowid == ?", [str(subrow["label"])]).fetchall()
            if (len(label) <= 0):
                value_type = subrow["label"]
            else:
                value_type = label[0]["value"]
        else:
            value_type = ""
        if (value_type.startswith("_$!<")):
            value_type = value_type[4:-4].lower() # _$!<Home>!$_
        
        # Get value (phone numbers, ...)
        top_value = (str(subrow["value"]) if subrow["value"] else "")
        
        # Check for multi-part entry (from ABMultiValueEntry)
        entries = cursor.execute("SELECT * FROM ABMultiValueEntry e WHERE e.parent_id == ?", [str(subrow["UID"])]).fetchall() # get from Entry table (for multiple parts, eg. address)
        
        if (len(entries) <= 0):
            entries = [None]
        
        for multivalueentry in entries:
            value = top_value
            if (multivalueentry):
                value = multivalueentry["value"]
                # Check for parts of the entry
                sub_value_type_key = multivalueentry["key"]
                sub_value_type_entries = cursor.execute("SELECT value FROM ABMultiValueEntryKey k WHERE k.rowid == ?", [str(sub_value_type_key)]).fetchall()
                if (len(sub_value_type_entries) <= 0): # There are multiple parts for this key
                    sub_value_type_entries = [{"value": ""}] # empty
            else:
                sub_value_type_entries = [{"value": ""}] # empty
            
            # For all subkeys
            for entry in sub_value_type_entries:
                sub_value_type = entry["value"] # Part of the field (indicator for ZIP code / State / ...)
                
                # Phone number
                if (subrow["property"] == 3 and value):
                    lines.append("TEL;TYPE=%s:%s" % (value_type, value))
                
                # Mail address
                if (subrow["property"] == 4 and value):
                    lines.append("EMAIL;TYPE=%s:%s" % (value_type, value))
                
                # Address
                if (subrow["property"] == 5 and value):
                    addr_id = int(subrow["identifier"]) # n-th address
                    while len(address) <= addr_id:
                        address.append([len(address) - 1, None, {}])
                    if address[addr_id][1] == None:
                        address[addr_id][1] = value_type
                    address[addr_id][2][sub_value_type] = value
                
                # Anniversary / other date
                try:
                    anniv = float(value)
                except:
                    anniv = None
                if (subrow["property"] == 12 and anniv != None):
                    realdate = EPOCH + datetime.timedelta(seconds=int(anniv)) # int is OK (date references 12pm from the epoch on that day)
                    if (value_type.lower() != "anniversary"):
                        extra = ";TYPE=\"%s\"" % value_type
                    else:
                        extra = ""
                    lines.append("ANNIVERSARY%s:%04d%02d%02d" % (extra, realdate.year, realdate.month, realdate.day))
                
                # IM
                if (subrow["property"] == 13 and value):
                    im_id = int(subrow["identifier"]) # n-th IM entry
                    while len(im) <= im_id:
                        im.append([len(im), None, {}])
                    if im[im_id][1] == None:
                        im[im_id][1] = value_type
                    im[im_id][2][sub_value_type] = value
                    
                # URL
                if (subrow["property"] == 22 and value):
                    lines.append("URL;TYPE=%s:%s" % (value_type, value))
                    
                
                # Related people
                if (subrow["property"] == 23 and value):
                    # Cannot use UUIDs because the entry is not linked to the related person
                    lines.append("RELATED;TYPE=%s;VALUE=text:%s" % (value_type, value.replace(",", "\,")))
                
                # Social networks et al.
                if (subrow["property"] == 46):
                    skipped_social_media = True # display warning later
    
    # Warn if social media data was skiped
    if (skipped_social_media):
        write(WARNING, "Could not transfer social media user information - Feature not yet supported by the vCard standard")
    
    # Add address
    for addr in address:
        try:
            addr_id, lbl, entry = addr
            if (lbl == None and len(entry) == 0):
                raise ValueError("Empty address")
        except Exception as e:
            write(WARNING, "Left out invalid address (reason: '" + e.message + "'). Enable debug output (-l DEBUG) to get more information")
            write(DEBUG, "Skipped: " + str(addr) + " due to error of type " + str(type(e)))
            continue
        vals = [ entry.get(k, "") for k in ("Apartment", "Floor", "Street", "ZIP", "City", "State", "Country") ] # Apartment and Floor will never be set, but are required for vCard
        content = ";".join(vals)
        lines.append("ADDR;TYPE=%s:%s" % (lbl, content))
    
    # Add IM
    for im_entry in im:
        try:
            im_id, lbl, entry = im_entry
            if (lbl == None and len(entry) == 0):
                raise ValueError("Empty IM entry")
        except Exception as e:
            write(WARNING, "Left out invalid IM entry (reason: '" + e.message + "'). Enable debug output (-l DEBUG) to get more information")
            write(DEBUG, "Skipped: " + str(im_entry) + " due to error of type " + str(type(e)))
            continue
        vals = [ entry.get(k, "") for k in ("service", "username") ] # Apartment and Floor will never be set, but are required for vCard
        content = ":".join(vals)
        lines.append("IMPP;TYPE=%s:%s" % (lbl, content))
    
    # End vCard
    lines.append("END:VCARD")
    
    # Remove newlines and similar stuff from the lines
    lines = [x.replace("\n", "\\n").replace("\r", "") for x in lines]
    
    # get filename
    base_fn = ((first_name + " ") if first_name else "") + ((middle_name + " ") if middle_name else "") + (last_name if last_name else "")
    if (not base_fn):
        base_fn = "UNNAMED"
    fn = os.path.join(output_dir, base_fn + ".vcf")
    if (os.path.exists(fn)):
        cid = 2
        fn = os.path.join(output_dir, base_fn + " - %d" % cid + ".vcf")
        while (os.path.exists(fn)):
            cid += 1
            fn = os.path.join(output_dir, base_fn + " - %d" % cid + ".vcf")
        
    write(INFO, "Writing contact: %s" % full_name)
    
    
    # write file
    with open(os.path.join(output_dir, fn), 'w') as f:
        f.write("\r\n".join(lines) + "\r\n")
    
# Groups
for row in cursor.execute("SELECT ROWID, Name FROM ABGroup").fetchall():
    lines = []
    
    group_id = str(row["ROWID"])
    
    # Begin vCard
    lines.append("BEGIN:VCARD")
    lines.append("VERSION:4.0")
    
    # Group
    lines.append("KIND:group")
    
    # Group name
    name = row["Name"]
    if (not name):
        write(ERROR, "Cannot write an unnamed group")
        continue
    lines.append("FN:%s" % str(name))
    
    # Group members
    for member in cursor.execute("SELECT member_id FROM ABGroupMembers WHERE group_id == ?", group_id).fetchall():
        lines.append("MEMBER:urn:uuid:%s" % uid_map[member["member_id"]])
    
    # End vCard
    lines.append("END:VCARD")
    
    # Remove newlines and similar stuff from the lines
    lines = [x.replace("\n", "\\n").replace("\r", "") for x in lines]
    
    # Get filename
    base_fn = str(name)
    if (not base_fn):
        base_fn = "UNNAMED"
    fn = base_fn + ".vcf"
    if (os.path.exists(os.path.join(group_dir, fn))):
        cid = 2
        fn = os.path.join(group_dir, base_fn + " - %d" % cid + ".vcf")
        while (os.path.exists(fn)):
            cid += 1
            fn = os.path.join(group_dir, base_fn + " - %d" % cid + ".vcf")
        
    write(INFO, "Writing group: %s" % str(name))
    
    
    # write file
    with open(os.path.join(group_dir, fn), 'w') as f:
        f.write("\r\n".join(lines) + "\r\n")
