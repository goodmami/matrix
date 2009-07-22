"""
File: import_from_tsdb.py
Author: KEN (captnpi@u.washington.edu, Scott Halgrim) - taking over from ???
Date: 7/12/09 - taken over on this date
Project: MatrixTDB RA, summer 2009
Project Owner: Emily M. Bender
Contents:
    - code that adds the parent directory to the path
    - validate_string_list - function that validates the combo of a file with harvester strings and the
                                   [incr_tsdb()] profile.
    - check_for_known_mrs_tags - function that checks that mrs tags in input file do not
                                                 have different sentences associated with them if they are
                                                 in the database.
    - update_orig_source_profile - function that creates a source profile in db and links it to a
                                                language type
    - update_harv_str - function that inserts new mrs tags into harv_str and links them to osp_id.
                                Links existing mrs tags to osp_id as well.
    - find_string - function that, given the mrs tag that is the value in a dict, returns the string that
                        is the key to that tag in the dict
    - update_mrs - function that reads in a [incr_tsdb()] profile for semantics and updates database
                          with those semantics
    - read_profile_file - function that breaks up a [incr_tsdb()] file into a two-dimensional list
    - import_to_sp - function that imports a [incr_tsdb()] profile into the sp_* tables in the database
    - validateProfile - function that validates a [incr_tsdb()] profile is good enough for our purposes
    - main - function that runs through all the steps of importing a set of harvester strings and the
                corresponding mrs tags and [incr_tsdb()] profile to MatrixTDB
    - main code that pulls arguments off the command line to call main()
    - module testing code that allows for local testing of unit functions and the entire module.  It
      can be ignored.
"""
############################################################
# Script for importing data from [incr tsdb()] profile into
# MatrixTDB.

# Usage:

# python import_from_itsdb.py <dir> <h-m> <choices>

# Input:
#
# 1) <dir>: Directory containing [incr tsdb()] profile with harvester
# strings parsed by harvester grammar.
#
# 2) <h-m>: File linking harvester strings to mrs_tags.
#
# 3) <choices>: Choices file from which the harvester grammar was
# created.

# TODO: Verify and update as necessary the steps below in this section.

# First, we look through the harvester-strings to make sure
# that they each correspond to an i_input field in item.
# If not, return an error.

# Then we look through the harvester-mrs_tag pairs and
# see if any of the mrs_tags are already known.  If so,
# we query the user, to determine which case we're in:

# 1) Inadvertent reuse of mrs_tag; mrs_tag corresponds to
# a different harvester string than before

# 1a) User means for it to be a different mrs, and needs
# to be a new name.

# 1b) User means for it to be the same mrs, and should
# be modifying modstring.py rather than adding a new
# harvester string

# 2) mrs_tag and harvester string are already known and
# already in correspondence. User means to update the
# mrs_value.

# Case 1) should result in the user getting an error
# message with directions about what to do.

# Case 2) should result in a new entry in MatrixTDB.mrs
# pairing the mrs_tag with the new mrs_value.  The
# old entry in MatrixTDB.mrs should be updated so that
# the mrs_current is now - and mrs_date is the current
# date.

# If there are any new MRSs to store (i.e., we are in case
# 2 above and/or there are new mrs_tags listed), then:

# 1) Look up or create LT entry in lt and lt_feat_grp
# 2) Ask user for comment to store about this source profile
# 3) Create a new row in orig_source_profile with information
# about this source profile.  
# 4) Update harvester string table with strings and mrs_tags
# 5) Update mrs table with mrs_tags and mrs_values
# 6) Add rows from tsdb_profile/item,parse,result to sp_item,
# sp_parse, sp_result, replacing mrs in sp_result with mrs_tag
# 7) Print out osp_orig_src_prof_id for user to use as input
# to add_permutes.py
# 8) Print out message about updating g.py to map include ne
# mrs_tags in the mrs_tag sets they belong in, and updating
# u_filters.py and s_filters.py to handle new strings, and updating
# stringmod.py as well.

##########################################################################
# Preliminaries

import sys
import os
import datetime
from validate import validate_choices
from sql_lg_type import create_or_update_lt
from choices import ChoicesFile
from matrix_tdb_conn import MatrixTDBConn

sys.path.append("..")           # add parent directory to path

###########################################################################
# Validating file relating harvester strings to mrs.
# Check format (@ delimited)
# Check that each i_input in item corresponds to a row in harv_mrs file
# and vice versa
# Check that each harvester string is unique (within file) and that
# each mrs_tag is unique (within file).

def validate_string_list(harv_mrs, itsdbDir):
    """
    Function: validate_string_list
    Input:
        harv_mrs - a string containing the harvester strings and their mrs tags.
        itsdbDir - a directory of a [incr_tsdb()] profile
    Output: mrs_dict - a dict whose keys are the harvester strings and whose values are the mrs
                                tags
    Functionality:  validates the combo of file with harvester strings and the [incr_tsdb()] profile.
                         Ensures each item in the profile is a harvester string and vice-versa.  Ensures
                         each harvester string is unique and that each given mrs tag is unique.
    """
    mrs_dict = {}               # initialize output dict
    f = open(harv_mrs)      # open the harvester string file

    # convert lines in f to arrays of harvester string and then mars tag
    hlines = [line.strip().split('@') for line in f.readlines()]
    f.close()                       # close the harvester string file
    
    for line in hlines:         # for every harvester string line in harvester string file...
        try:
            # ...insert the mrs tag as the value of the string as the key
            mrs_dict[line[1]] = line[0]
        except IndexError:                  # if the array doesn't have enough items...
            # ...raise an error indicating problem.
            raise ValueError, "File " + harv_mrs + " is not a well-formed input file. " + \
                                      "Line format should be mrs_tag@string"

    itemFile = open(itsdbDir + "item", 'r')        # open item file from source profile

    # extract sentence strings from item file and put into list
    ilines = [line.strip().split('@')[6] for line in itemFile.readlines()]

    itemFile.close()                                    # close the item file

    for item in ilines:                             # for each item in the profile...
        if not mrs_dict.has_key(item):      # ..verify it is was given in the harv string file
            # ...and if not, raise an error.
            raise ValueError, "Item " + item + " in " + itsdbDir + "item is not represented in " + \
                                      harv_mrs + "."

    mrs_keys = mrs_dict.keys()          # get the set of given harvester strings

    for string in mrs_keys:                  # for each harvester string...
        if ilines.count(string) == 0:        # ...verify it is in the profile as an item...
            # ...if not, raise an error.
            raise ValueError, "Item " + string + " in " + harv_mrs + " is not represented in " + \
                                      itsdbDir + "item."
        if mrs_keys.count(string) > 1:   # ...also verify it doesn't appear multiple times as an item
            # ...if so, raise an error.
            raise ValueError, "Item " + string + " appears more than once in " + harv_mrs + "."

    mrs_tags = mrs_dict.values()        # get the set of given mrs tags.

    for tag in mrs_tags:                        # for each given mrs tag...
        if mrs_tags.count(tag) > 1:         # ...verify it only appears once in the harv file.
            # if it appears more than once ,raise an error.
            raise ValueError, "Mrs tag " + string + " appears more than once in " + harv_mrs + "."
  
    return mrs_dict                             # return output

###########################################################################
# Checking for known mrs_tags and deciding what to do

def check_for_known_mrs_tags(mrs_dict, conn):
    """
    Function: check_for_known_mrs_tags
    Input: 
        mrs_dict - a dict whose keys are the harvester strings and whose tags are the mrs tags for
                        those strings
        conn - a MatrixTDBConn
    Output:
        new_mrs_tags - a set of mrs tags that are values of mrs_dict that are not already in the db.
        known_mrs_tags - a set of mrs tags that are values of mrs_dict taht are already in the db.
    Functionality: If all mrs tags in mrs_dict, verifies with user this is intended.  For mrs tags in
                         db, determines if those tags keys in mrs_dict match the strings in the db.
                         If not, warns user and exits.  For those mrs tags with strings identical to those
                         already in db, verifies user wants to update MRSs and exits if not.
    """
    # TODO: I think this function could be broken up
    new_mrs_tags = set()          # initialize output set of new mrs tags
    known_mrs_tags = set()       # initialize output set of known mrs tags

    # get every mrs tag out of the db
    rows = conn.selQuery("SELECT mrs_tag FROM mrs")

    db_tags = set([row[0] for row in rows])  # put mrs tags in database into a set

    # get a set of the mrs tags given in harvester_mrs input file
    input_tags = set(mrs_dict.values())
    input_strings = set(mrs_dict.keys())    # get a set of the harv strings given in same file

    # TODO: could i make this faster with sets?  like, using differences and intersections instead
    # of for loops?
    for tag in input_tags:                           # for each mrs tag given...
        if tag in db_tags:                             # ...if that tag is already in the db
            known_mrs_tags.add(tag)           # ...add it to the set of known tags
        else:                                              # ...otherwise...
            new_mrs_tags.add(tag)               # ...add it to the set of new tags

    if len(known_mrs_tags) == 0:                # if every given tag is new...
        # ...ask user if that was the intent.
        res  =  raw_input("All of the mrs_tags you are reporting are new.\n" + \
                                  "If this is right, press 'y' to continue.  Press any other key to abort. ")
        if res != 'y':      # if they say anything but yes...
            sys.exit()    # ...exit
            
    else:           # we have some mrs tags given that we already knew about.  We want to verify
                      # they correspond to the same strings as before.
        same_string_tags = []           # initalize list of strings that are the same
        diff_string_tags = []               # initialize list of strings that are different.

        for tag in known_mrs_tags:          # for every mrs tag that we already knew about...
            s1 = find_string(tag,mrs_dict)     # get the given harvester string as s1
            try:
                # get the string that is in the database for this tag as s2
                # TODO: would we have a case where the tag has two strings in db?
                s2 = conn.selQuery("SELECT hs_string FROM harv_str " + \
                                           "WHERE hs_mrs_tag = %s",(tag))[0][0]
            except IndexError:
                s2 = ''         # make s2 the empty string if tag wasn't associated with a string

            # TODO: test this function with the new indenting.
            if s1 == s2:
                same_string_tags.append(tag)
            else:
                diff_string_tags.append(tag)

        if len(diff_string_tags) > 0:
            # we shouldn't ge using old mrs tags for new strings here, so if we are inform user of
            # what they did wrong and exit
            print "The following mrs_tags are already in MatrixTDB with\n different harvester " + \
                     "strings associated with them.\n"
            print diff_string_tags
            print "\n"
            print "Either you have inadvertently reused an mrs_tag or you\n should be " + \
                     "modifying stringmod.py rather than\n adding harvester strings.\n"
            print "MatrixTDB has not been modified.\n"
            sys.exit()
        elif len(same_string_tags) > 0:
            # if the user is using old mrs tags with old strings...
            print "The following mrs_tags already exist in MatrixTDB with\n the harvester " + \
                    "string indicated.\n"
            print same_string_tags

            # ...ask them if they want to update the MRSs associated with those.
            res = raw_input("If you mean to update the MRSs associated with them,\n press " + \
                                    "'y' to continue (any other key will abort): ")
            if res != 'y':          # if that's not what they want,...
                sys.exit()        # ...exit

        # if they gave some mrs tags in their file that aren't in the database...
        if len(new_mrs_tags) > 0:
            # ...tell them which tags they're adding.
            print "In addition, you are adding the following new mrs tags:\n"
            print new_mrs_tags
            print "\n"

            # verify they want to add those
            res = raw_input("If this is correct, press 'y' to continue (any other key to abort): ")
            if res != 'y':      # if they don't...
                sys.exit()    # ...exit

    # return sets of mrs tags they gave us either as new tags or tags already in db.
    return [new_mrs_tags,known_mrs_tags]


###########################################################################
# Create new row in orig_source_profile

def update_orig_source_profile(lt_id, conn):
    """
    Function: update_org_source_profile
    Input:
        lt_id - a language type ID
        conn - a MatrixTDBConn, a connection to the MatrixTDB database        
    Output:
        osp_id - the id of a source profile entered that links to lt_id
        timestamp - a formatted time representing when source profile was added to db
    Functionality: Prompts user for input to db and creates a source profile in db and links it to
                         lt_id
    """
    try:
        user = os.environ['USER']           # get the user's username from Unix system
    except KeyError:                           # if 'USER' isn't a key, they might be on Windows...
        user = os.environ['USERNAME'] # ...so get their username from Windows.

    comment = ''                                 # initialize comment from user
    while comment == '':                      # while they haven't entered a comment...
        # ...prompt user for a comment.
        comment = raw_input("Enter a non-empty description of this source profile " + \
                                        "(1000 char max): ")

    t = datetime.datetime.now()                             # get current date and time
    timestamp = t.strftime("%Y-%m-%d %H:%M")  # format the current date/time

    # insert the source profile into the database and link it to the language type lt_id
    conn.execute("INSERT INTO orig_source_profile " + \
                        "SET osp_developer_name = %s, osp_prod_date = %s, " + \
                         "osp_orig_lt_id = %s, osp_comment = %s", (user, timestamp, lt_id, comment))

    # get the ID of inserted source profile
    osp_id = conn.selQuery("SELECT LAST_INSERT_ID()")[0][0]

    return [osp_id, timestamp]       # return output

###########################################################################
# Update harvester string table with strings and mrs_tags

def update_harv_str(new_mrs_tags, known_mrs_tags, mrs_dict, osp_id, conn):
    """
    Function: update_harv_str
    Input:
        new_mrs_tags - a set of mrs tags that are values of mrs_dict that are not already in the db
        known_mrs_tags - a set of mrs tags that are values of mrs_dict taht are already in the db
        mrs_dict - a dict whose keys are the harvester strings and whose tags are the mrs tags for
                        those strings
        osp_id - the ID of an original source profile
        conn - a MatrixTDBConn, a connection to the MatrixTDB database        
    Output: none
    Functionality: Inserts new mrs tags into harv_str and links them to osp_id.  Links existing
                         mrs tags to osp_id as well.
    """
    # TODO: would this make more sense to go through the mrs_dict, comparing for inclusion in
    # new_mrs_tags and known_mrs_tags?
    for tag in new_mrs_tags:                    # for every mrs tag not already in db...
        harv = find_string(tag, mrs_dict)       # ...get the harvester string corresponding to it

        # insert the string/tag combo into the database and link it to osp_id for both its original
        # osp and its current osp
        conn.execute("INSERT INTO harv_str " + \
                           "SET hs_string = %s,  hs_mrs_tag = %s, hs_init_osp_id = %s, " + \
                            "hs_cur_osp_id = %s", (harv, tag, osp_id, osp_id))

    for tag in known_mrs_tags:      # for every mrs tag that we already had in db...
        # ...set its current osp to osp_id
        conn.execute("UPDATE harv_str SET hs_cur_osp_id = %s " + \
                           "WHERE hs_mrs_tag = %s", (osp_id, tag))

    return

###########################################################################
# Find string corresponding to a given mrs_tag.  Need a little subroutine
# here because the strings are the keys in mrs_dict, not vice versa.  Also
# Note that we can assume that the tags are unique in mrs_dict.values(), i.e.,
# no two strings have the same tag as their value.

def find_string(tag, mrs_dict):
    """
    Function: find_string
    Input:
        tag - an mrs tag
        mrs_dict -a dict whose keys are harvester strings and whose keys are mrs tags for those
                      strings
    Output: answer - the harvester string corresponding to the mrs tag tag in mrs_dict
    Functionality: returns the harvester string corresponding to an mrs tag in mrs_dict.  raises a
                         ValueError if tag isn't in mrs_dict
    """
    for (key, value) in mrs_dict.items():       # for each key/value pair in mrs_dict
        if value == tag:                                # look for the tag matching input tag
            answer = key                              # if found, set answer to corresponding harv string
            break                                         # and exit loop
    else:                                                  # else is for for loop, not if stmt.
        # if tag was never found in mrs_dict.values(), raise error
        raise ValueError, "Error: import_from_itsdb.find_string() was passed an mrs tag with " + \
                                  "no corresponding harvester string."

    return answer                                       # return output

###########################################################################
# Update mrs table with mrs_tags and mrs_values
# _FIX_ME_ Still assuming one mrs per harvester string, but this doesn't
# allow for abiguous harvester strings, which we will surely arrive at one day.

def update_mrs(mrs_dict, osp_id, new_mrs_tags, known_mrs_tags, profDir, timestamp, conn):
    """
    Function: update_mrs
    Input:
        mrs_dict - a dict whose keys are the harvester strings and whose tags are the mrs tags for
                        those strings
        osp_id - the ID of an original source profile
        new_mrs_tags - a set of mrs tags that are values of mrs_dict that were not already in the
                                db
        known_mrs_tags - a set of mrs tags that are values of mrs_dict that were already in the db
        profDir- a path to an [incr_tsdb()] profile
        timestamp - formatted string representing time original source profile was inserted into db.
        conn - a MatrixTDBConn, a connection to MatrixTDB
    Output: none
    Functionality: reads in the [incr_tsdb()] profile in profDir to get semantics.  For each mrs tag,
                         inserts its semantics into mrs table.  Additionally, for each mrs tag we already
                         knew about, deprecates existing record in mrs table and inserts a new one with
                         the new semantics.
    """
    # TODO: now that new_mrs_tags have been inserted into harv_str, is there a reason I have
    # them as two separte sets here?  Should I refactor?

    # Read in info from itsdb files
    harv_id = {}                # initalize dict mapping harvester strings to item IDs
    parse_id = {}             # initialize dict mapping item IDs to parse IDs
    mrs_values = {}         # initalize dict mapping parse IDs to mrs semantics values    

    # get the harvester strings out of mrs_dict and assign to input_strings    
    input_strings = mrs_dict.keys() 

    itemFile = open(profDir + "item", 'r')      # open the profile's item file

    for line in itemFile.readlines():             # for each item in the file
        line = line.strip()                            # strip off line's leading and trailing whitespace
        line = line.split('@')                        # split line into columns delimited by '@'

        # populate harv_id dict.  key is i_input (the string), value is i_id (a unique id)
        harv_id[line[6]] = line[0]

    itemFile.close()                                   # close item file
    parseFile = open(profDir + "parse", 'r')    # open the profile's parse file

    for line in parseFile.readlines():           # for each parse in the file
        line = line.strip()                            # strip off line's leading and trailing whitespace
        line = line.split('@')                        # split line into columns delimited by '@'

        # populate parse_id dict.k ey is p_i_id (unique id of item), value is parse_id (unique id of
        # parse)
        parse_id[line[2]] = line[0]

    parseFile.close()                              # close parse file
    resFile = open(profDir + "result", 'r')     # open the profile's result file

    for line in resFile.readlines():             # for each result in the file   
        line = line.strip()                           # strip off line's leading and trailing whitespace
        line = line.split('@')                       # split line into columns delimited by '@'

        # populate mrs_values dict. key is parse_id (unique id of parse), value is mrs_value
        # (semantics of sentence)
        mrs_values[line[0]] = line[13]
        
    resFile.close()                                  # close the result file
       
    # For new mrs tags, create a new entry in mrs table:
    for tag in new_mrs_tags:                            # for every new mrs tag
        i_input = find_string(tag, mrs_dict)          # get the harvester string
        i_id = harv_id[i_input]                             # get the item ID for that string
        p_id = parse_id[i_id]                              # get the parse id for that string/item
        mrs_value = mrs_values[p_id]                # get the semantics of that string/item/parse

        # insert the mrs into the mrs table, setting its semantics, current flag, and  osp
        # appropriately.
        conn.execute("INSERT INTO mrs SET mrs_tag = %s, mrs_value = %s, " + \
                            "mrs_current =1, mrs_osp_id = %s",(tag, mrs_value, osp_id))

    for tag in known_mrs_tags:                      # for every mrs tag we already knew about
        # set its current line in the mrs table to be mrs_current = 0 (deprecate it)
        conn.execute("UPDATE mrs " + \
                             "SET mrs_current = 0, mrs_date = %s " + \
                             "WHERE mrs_tag = %s " + \
                             "AND mrs_current = 1", (timestamp, tag))
        i_input = find_string(tag,mrs_dict)             # get the tag's harvester string
        i_id = harv_id[i_input]                               # get the item ID for that string
        p_id = parse_id[i_id]                                # get the parse id for that string/item
        mrs_value = mrs_values[p_id]                  # get the semantics of that string/item/parse

        # insert the mrs into the mrs table, setting its semantics, current flag, and  osp
        # appropriately.
        conn.execute("INSERT INTO mrs " + \
                            "SET mrs_tag = %s, mrs_value = %s, mrs_current = 1, " + \
                             "mrs_osp_id = %s",(tag, mrs_value, osp_id))
    return

##########################################################################
# Reading in tsdb files

def read_profile_file(filename):
    """
    Function: read_profile_file
    Input: filename - the name of a file in a [incr_tsdb()] profile
    Output: contents - a list of lists.  The outer list is a list of each row in the file and the inner
                               lists are the columns/fields in each row
    Functionality: Breaks up a [incr_tsdb()] file into a list (representing each row) of lists
                        (representing each field in the row)
    """
    # TODO: couldn't this function be used in update_mrs?
    contents = []                                # initalize output list
    f = open(filename, 'r')                     # open the profile file
    
    for line in f.readlines():                    # for every line in the file
        line = line.strip()                         # strip off its leading and trailing whitespace

        # break it into a list of columns delimited by @ and add that list to the output list
        contents.append(line.split('@'))    
        
    f.close()                                         # close the file

    return contents                               # return the output

##########################################################################
# Finally, we're ready to import the data from the itsdb profile into
# MatrixTDB.

# 6) Add rows from tsdb_profile/item,parse,result to sp_item,
# sp_parse, sp_result, replacing mrs in sp_result with mrs_tag

def import_to_sp(itsdb_dir,osp_id, mrs_dict, conn):
    """
    Function: import_to_sp
    Input:
        itsdb_dir - a path to an [incr_tsdb()] profile
        osp_id - the ID of an original source profile
        mrs_dict - a dict whose keys are the harvester strings and whose tags are the mrs tags for
                        those strings
        conn - a MatrixTDBConn, a connection to the MatrixTDB database
    Output: none
    Functionality: imports a [incr_tsdb()] profile into the sp_* tables in the database.  Links all
                         rows with globally unique IDs, eventually casting aside the profile-wide-unqiue
                         IDs from the profile.
    """
    # initialize dict of item IDs.  The keys are the item IDs from the item file in the profile and the
    # values are the correspdonding value of the spi_id column in the sp_item table.  I think this
    # allows us to work between the intra-profile uniqueness of item IDs in the file and our
    # global, inter-profile uniqueness required for the database.
    spi_ids = {}

    # initialize dict of parse IDs.  The keys are the parse IDs from the parse file in the profile and
    # the values are the correspdonding value of the spp_parse_id column in the sp_parse table.  I
    # think this allows us to work between the intra-profile uniqueness of parse IDs in the file and
    # our global, inter-profile uniqueness required for the database.    
    spp_ids = {}
    items = read_profile_file(itsdb_dir + "item")        # convert item file into two-dimensional list

    for item in items:                                              # for each item in item file...
        # ...insert the columns we care about into the sp_item table plus our add'l column of osp_id
        conn.execute("INSERT INTO sp_item " + \
                            "SET spi_input = %s, spi_wf = %s, spi_length = %s, spi_author = %s, " + \
                            "spi_osp_id = %s", (item[6], item[7], item[8], item[10], osp_id))
        # We're not using the tsdb i_id because in the general case we'll be adding to a table.
        # So, we need to get the spi_id and link it to the i_id for use in the next load.

        # Get the spi_id value from row just entered and store it in dict linking item IDs from profile
        # to the IDs in the table.
        spi_ids[item[0]] = conn.selQuery("SELECT LAST_INSERT_ID()")[0][0]

    parses = read_profile_file(itsdb_dir + "parse")     # convert parse file into two-dimensional list

    for parse in parses:                                          # for each parse in parse file...
        # ...insert the columns we care about into the sp_parse table plus our add'l column of
        # osp_id.  Use the item id from the parse file (parse[2]) to access the unique table id
        # of the item in sp_item via the spi_ids dict
        conn.execute("INSERT INTO sp_parse " + \
                           "SET spp_run_id = %s, spp_i_id = %s, spp_readings = %s, " + \
                                   "spp_osp_id = %s", (parse[1], spi_ids[parse[2]], parse[3], osp_id))

        # get the spp_parse_id value of the row we just entered and enter it in the spp_ids dict
        # to link the parse id from the profile (parse[0]) to this id we used in the table
        spp_ids[parse[0]] = conn.selQuery("SELECT LAST_INSERT_ID()")[0][0]

    results = read_profile_file(itsdb_dir + "result")   # convert result file into two-dimensional list

    for result in results:                                        # for each result in result file...
        # ...get the harvester string out of the sp_item table by using the parse id from the result
        # file (result[0]) to get the parse id in the table, and then querying through to sp_item
        harv_string = conn.selQuery("SELECT spi_input " + \
                                                  "FROM sp_item " + \
                                                  "INNER JOIN sp_parse " + \
                                                        "ON spi_id = spp_i_id " + \
                                                  "WHERE  spp_parse_id = %s", (spp_ids[result[0]]))[0][0]
        mrs_tag = mrs_dict[harv_string]             # use the harvester string to get the mrs tag

        # insert into sp_result table, setting columns we care about appropriately, including our
        # add'l column of osp_id
        conn.execute("INSERT INTO sp_result " + \
                            "SET spr_parse_id = %s, spr_mrs = %s, spr_osp_id = %s",
                                                                                (spp_ids[result[0]], mrs_tag, osp_id))

    return

def validateProfile(itsdbDir):
    """
    Function: validateProfile
    Input: itsdbDir - a path to an [incr_tsdb()] profile
    Ouptut: answer - True if itsdbDir points to a valid profile, False otherwise
    Functionality: validates that itsdbDir exists and contains the three main files: item, result, and
                         parse
    """
    # check that the path exists as well as the three files we're importing
    if (os.path.exists(itsdbDir) and os.path.exists(itsdbDir + "item") and
            os.path.exists(itsdbDir + "parse") and os.path.exists(itsdbDir + "result")):
        answer = True           # if so, set output to True
    else:                             # if not, ...
        answer = False          # ...set output to False

    return answer               # return output

##########################################################################
# Main program

# Check that inputs are all well formed
def main(itsdb_dir, harv_mrs, choices_filename, conn = None):
    """
    Function: main
    Input:
        itsdb_dir - a path to an [incr_tsdb()] profile
        harv_mrs - a path to and the name of a file linking the test items to mrs tags
        choices_filename - a path to and name of a choices file from the customization system
                                    TODO: yeah, but why is this being given here?
        conn - a MatrixTDBConn, a connection to the MatrixTDB database
    Output: none
    Functionality: runs through all the steps of importing a set of harvester strings and the
                         corresponding mrs tags and [incr_tsdb()] profile to MatrixTDB
    """
    if conn is None:                            # if the user doesn't supply a connection to a db...
        conn = MatrixTDBConn()           # ...use this one by default
        
    if not validateProfile(itsdb_dir):          # if the [incr_tsdb()] profile isn't valid...
        # ...raise an error
        raise ValueError, "The first argument must be the path to a directory containing a valid " + \
                                  "[incr tsdb()] profile, ending in /."

    # validate that harv/mrs file is formatted right and corresponds to [incr_tsdb()] profile
    # this will raise an error if not.
    # also assign harvstring/mrsTag as key/value pairs to mrs_dict
    mrs_dict = validate_string_list(harv_mrs, itsdb_dir)

    # validate the choices file.  put those choices that are into the dict wrong
    wrong = validate_choices(choices_filename)

    # if any choices in the file were wrong...
    if len(wrong) > 0:
        # ...inform user and exit.
        raise ValueError, "Invalid choices file.  Wrong choices: " + str(wrong)

    # convert the choices file into a ChoicesFile object.
    choices = ChoicesFile(choices_filename)

    # Check for presence of known mrs tags, and query user
    [new_mrs_tags, known_mrs_tags] = check_for_known_mrs_tags(mrs_dict, conn)
    
    # 1) Look up or create LT entry in lt and lt_feat_grp
    # This will also make sure that lt_feat_grp is up to date
    # for an existing language type.  Defined in sql_lg_type.py
    lt_id = create_or_update_lt(choices, conn)

    # 2) Ask user for comment to store about this source profile
    # 3) Create a new row in orig_source_profile with information
    # about this source profile.
    [osp_id, timestamp] = update_orig_source_profile(lt_id, conn)

    # Insert new mrs tags into harv_str and links them to osp_id.  Link existing mrs tags to osp_id
    # as well.
    update_harv_str(new_mrs_tags, known_mrs_tags, mrs_dict, osp_id, conn)

    # 5) Update mrs table with mrs_tags and mrs_values
    update_mrs(mrs_dict, osp_id, new_mrs_tags, known_mrs_tags, itsdb_dir, timestamp, conn)

    # 6) Add rows from tsdb_profile/item,parse,result to sp_item,
    # sp_parse, sp_result, replacing mrs in sp_result with mrs_tag
    import_to_sp(itsdb_dir, osp_id, mrs_dict, conn)

    # 7) Print out osp_orig_src_prof_id for user to use as input
    # to add_permutes.py
    print "The original source profile id for your profile is: " + str(osp_id)

    # 8) Print out message about updating g.py to map include ne
    # mrs_tags in the mrs_tag sets they belong in, and updating
    # u_filters.py and s_filters.py to handle new strings, and updating
    # stringmod.py as well.

    if len(known_mrs_tags) > 0:
        print "The following mrs_tags now have updated mrs_values in MatrixTDB:\n"
        print known_mrs_tags

    if len(new_mrs_tags) > 0:
        print "The following mrs_tags and their corresponding strings and values have been " + \
                "added to MatrixTDB:\n" + str(new_mrs_tags) + "\nBe sure to map them to the " + \
                "right sets of mrs_tags\n in g.py (for proper functioning of existing filters).\nBe " + \
                "sure to update s_filters.py, u_filters.py and\n potentially stringmod.py to reflect " + \
                "your new strings.  Then run add_permutes.py with the osp_id " + str(osp_id) + \
                ".  Then run run_u_filters.py and run_specific_filters.py."

    return

# set to true for running on my machine.  set to False before commiting to repository.
moduleTest = True

if __name__ == '__main__':      # only run if run as main module...not if imported
    if len(sys.argv < 4):                # if the user gave too few arguments....
        # ...give an error message indicating usage.
        print >> sys.stderr, "Usage: python import_from_itsdb.py itsdb_directory " + \
                                     "harv_mrs_filename choices_filename"
    else:                                             # if the user gave at least three arguments...
        # ...get the directory of the [incr_tsdb()] directory from the command line...
        itsdbDir = sys.argv[1]

        # ...and the name of the file linking test sentences to mrs tags...
        harvMrsFilename = sys.argv[2]

        # ...and the name of the choices file for the customization system
        choicesFilename = sys.argv[3]
        
        #Connect to MySQL server
        conn = MatrixTDBConn()

        # call the main program to import a source profile into MatrixTDB
        main(itsdbDir, harvMrsFilename, choicesFilename, conn)
        
elif moduleTest:                        # if we are testing this module locally...
    conn = MatrixTDBConn('2')      # ...create a connection to the smaller, newer database...

    # ... and notify the user moduleTest is set to True.
    print >> sys.stderr, "Note: module testing turned on in import_from_itsdb.py.  " + \
                                 "Unless testing locally, set moduleTest to False."
    mypath = "C:\RA\matrix\customize\sql_profiles\harv2\\" # set root path
    itsdbDir = mypath + "sourceprof\\attempt1\\"        # set path to source [incr_tsdb()] profile

    # set path and filename of file linking test sentences to mrs tags
    harvMrsFilename = mypath + "harv_mrs_2"
    choicesFilename = mypath + "choices1"     # set path to and name of choices file

    # call the main program to import a source profile into MatrixTDB2
    main(itsdbDir, harvMrsFilename, choicesFilename, conn)
