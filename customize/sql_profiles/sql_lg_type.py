###############################################################
# Read in choices file and create appropriate representations
# in MatrixTDB.lt,lt_grp.

# python sql_lg_type.py <choices file> [r|p]
# r = random lt
# p = purpose-built lt

# ERB 2007-06-06 Updating this so that we put in singleton
# feature groups for all f:v pairs in the lt definition that aren't
# already in the DB.  These won't (initially anyway) have
# filters that care about them, but I don't see that that will hurt
# anything.

# When we take a lt and look for its filters, we get all the
# feature groups that correspond to the language type, and then
# get all of the filters that correspond to those feature groups.

# Then I can define a function 'update_lt_in_lfg' that
# looks at the lt definition in terms of fv pairs and finds all
# new groups that should be added for it.

# mysql> show columns in lt;
# +-----------+---------+------+-----+---------+----------------+
# | Field     | Type    | Null | Key | Default | Extra          |
# +-----------+---------+------+-----+---------+----------------+
# | lt_id     | int(11) | NO   | PRI | NULL    | auto_increment |
# | lt_origin | char(2) | YES  |     | NULL    |                |
# +-----------+---------+------+-----+---------+----------------+

# mysql> show columns in feat_grp;
# +-----------+----------+------+-----+---------+----------------+
# | Field     | Type     | Null | Key | Default | Extra          |
# +-----------+----------+------+-----+---------+----------------+
# | fg_id     | int(11)  | NO   | PRI | NULL    | auto_increment |
# | fg_grp_id | int(11)  | YES  | MUL | NULL    |                |
# | fg_feat   | char(20) | YES  | MUL | NULL    |                |
# | fg_value  | char(20) | YES  |     | NULL    |                |
# +-----------+----------+------+-----+---------+----------------+

# mysql> show columns in fltr_feat_grp;
# +-------------+---------+------+-----+---------+----------------+
# | Field       | Type    | Null | Key | Default | Extra          |
# +-------------+---------+------+-----+---------+----------------+
# | ffg_id      | int(11) | NO   | PRI | NULL    | auto_increment |
# | ffg_fltr_id | int(11) | YES  | MUL | NULL    |                |
# | ffg_grp_id  | int(11) | YES  | MUL | NULL    |                |
# +-------------+---------+------+-----+---------+----------------+

# mysql> show columns in lt_feat_grp;
# +------------+---------+------+-----+---------+----------------+
# | Field      | Type    | Null | Key | Default | Extra          |
# +------------+---------+------+-----+---------+----------------+
# | lfg_id     | int(11) | NO   | PRI | NULL    | auto_increment |
# | lfg_lt_id  | int(11) | YES  | MUL | NULL    |                |
# | lfg_grp_id | int(11) | YES  | MUL | NULL    |                |
# +------------+---------+------+-----+---------+----------------+


import sys
import MySQLdb
sys.path.append("..")
from choices import ChoicesFile

###############################################################
# check_lt_for_fvs(fvs,choices): Check whether all of the feature-value
# pairs in a group are represented in the language type.
# NB: choices is not a ChoicesFile, it is a dict of fv pairs.

def check_lt_for_fvs(fvs,choices):
    """
    Function: check_lt_for_fvs
    Input:
        fvs - a tuple of rows from the database reprsenting all the feature/value pairs in a feature
               group where a group is defined by feat_grp.fg_grp_id
        choices - a dict whose keys are features and whose values are those features' values
    Output: answer - True if the value of every feature in fvs matches that in choices.  False
                             otherwise
    Functionality: Compares the feat/val pairs of a feature group in fvs with the choices dict of
                         feat/val pairs to see if those in fvs are the same as those in choices.
    """
    for fv in fvs:                          # for every row of feature/value pairs...
        (f,v) = fv                           # ...set f and v
        try:
            # if the value of feature f in the choices dict does not equal that of the feat/val from the db           
            if choices[f] != v:
                answer = False  # then the answer is false...choices does not match fvs
                break                # and get out of here
        except KeyError:
            # this goofy little test below handles the syntax in filters that checks for absence of a
            # feature altogether.  That sytnax is, e.g., "fv = ['aux-verb:']", meaning that it applies
            # to anything without that feature in it.  We will get a KeyError if the feature isn't in
            # the choices dict representing the choices file, and here we verify that the syntax
            # given in the fvs was indeed that it was checking for absence.  If it was an empty string (looking for absence), we leave
            # it alone.  If it was looking for an actual value, though, then this isn't a match and we
            # move on.
            # TODO: make this doco more clear.  This will involve making sense of how this gets
            # called from both run_specific_filters.update_all_lts_in_lfg and
            # sql_lg_type.create_or_update_lt
            if not (v == ''):
                answer = False
                break
    else:                           # if every feature/value in fvs matched that in choices...
        answer = True          # ...then they match, set output to True

    return answer               # return output

###############################################################
# check_lt_for_grp_ids(grp_ids,choices): Check whether all of the feature-value
# pairs in a set of grp_ids (e.g., from an existing lt) are
# represented in a (new) set of choices.

def check_lt_for_grp_ids(grp_ids,choices,conn):
    """
    Function: check_lt_for_grp_ids
    Input:
        grp_ids - a tuple of tuples of greature group IDs, represnting all the feature group IDs that
                      correspond to a language type
        choices - a ChoicesFile representing a potentially different language type
        conn - a MatrixTDBConn, a connection to the MatrixTDB database
    Ouptput: answer - True if every f/v pair in the group IDs matches the f/v combo in choices,
                               False otherwise
    Functionality: Checks to see if the grp_ids that define a language type in Matrix TDB have
                         feature/value combos that match the language type defined by choices
    """

    # grp_ids is one of those obnoxious tuples from cursor.fetchal()

    for grp_id_tuple in grp_ids:        # for each row...
        grp_id = grp_ids[0]               #...get the feature group id

        # We can just check the first feature from each feature group
        # since the non-singleton groups should just have feature/value pairs that
        # also exist as singleton groups (and so will also be checked later in the loop.
        # for these purposes.  This is
        # cheaper than deciding whether each group is singleton
        # before we check it.

        # put the feature and value of the first row of feature/value pairs of this group
        # into variables f and v
        (f, v) = conn.selQuery("SELECT fg_feat, fg_value FROM feat_grp " + \
                              "WHERE fg_grp_id = %s",(grp_id))[0]

        # if the choices file's value of the feature doesn't match the value of the feature in the group
        # for the language type we're checking, then...
        if choices.get(f) != v:         # TODO: seems this should use get_full, not get
            answer = False      # ...this language type doesn't match choices file
            break                   # and get out of here
    else:                            # but if every feature's value matched...
        answer = True           # ...then the file does match th elt we're checking, so return True

    return answer               # return output

###############################################################
# check_existing_lt_for_completeness(lt_id,choices): Now go
# the other way: Check whether all of the fv pairs in choices
# are already in the lt.

def check_existing_lt_for_completeness(lt_id, choices, conn):
    """
    Function: check_existing_lt_for_completeness
    Input:
        lt_id - a language type ID from MatrixTDB
        choices - a ChoicesFile representing another language type
        conn - a MatrixTDBConn, a connection to the MatrixTDB database
    Output: answer- TODO: finish dosctring
    Functionality: checks that all the feature/value combos in a choices file match those of
                         language type lt_id
    """
    for f in choices.keys():        # for every feature in the choices file...
        # check that that feature/value combo is included in the language type in MatrixTDB.
        res = conn.selQuery("SELECT fg_grp_id FROM feat_grp " + \
                                       "INNER JOIN lt_feat_grp ON fg_grp_id = lfg_grp_id " + \
                                       "WHERE fg_feat = %s " + \
                                        "AND fg_value = %s " + \
                                        "AND lfg_lt_id = %s", (f, choices.get(f), lt_id))
        if len(res) == 0: # we found a fv pair which isn't already in lfg_feat_grp for the lt.
            answer = False  # so this lt doesn't match the chocies file
            break                # and get out of here
    else:                         # but if everything in the choices file matches what's in db
        answer = True        # then there is a match

    return answer             # return output

###############################################################
# lt_exists(choices): Check whether we've already created
# the language type represented by the f:v dictionary choices

def lt_exists(choices,conn):
    """
    Function: lt_exists
    Input:
        choices - a ChoicesFile representing a language type
        conn - a MatrixTDBConn, a connection to the MatrixTDB database.
    Output: answer - lt_id the id of a language type in MatrixTDB if there is one that matches the
                             f/v pairs in choices, False otherwise
    Functionality: Finds the id of a language type in MatrixTDB that matches the language type
                         defined by choices if one exists.
    """

    # Check existing language types until we find one that
    # is consistent (i.e., subsumed by choices)

    rows = conn.selQuery("SELECT lt_id FROM lt")  # get every language type id in database
    
    for row in rows:          # for each row returned...
        lt_id = row[0]         # get the language type id

        # then get the feature groups (groups of feature/value pairs) associated with that language
        # type
        grp_ids = conn.selQuery("SELECT lfg_grp_id FROM lt_feat_grp " + \
                                             "WHERE lfg_lt_id = %s", (lt_id))

        # TODO: could these next two if statements be executed more clearly and quiclky by
        # getting the f/v pairs from both places as sets and comparing?
        
        # if every f/v pair in this set of group IDs matches the lt defined by choices...
        if check_lt_for_grp_ids(grp_ids,choices,conn):

            # Now make sure that all of the information in choices is
            # also in that lt.

            # ...and if every f/v in choices exists in MatrixTDB for lt_id... 
            if check_existing_lt_for_completeness(lt_id,choices,conn):
                answer = lt_id        # ...then there is a match
                break                     # so get out of the for loop looking for a match
    else:                           # if i never find a match...
        answer = False        # set output to False

    return answer               # return output
        

###############################################################
# singleton_group_exists(f,v): Check whether the pair f:v is
# already in as a singleton group

def singleton_group_exists(f, v, conn):
    """
    Function: singleton_group_exists
    Input:
        f - a feature
        v - a value
        conn - a MatrixTDBConn, a connection to the MatrixTDB database.
    Output: answer - True if f and v exist as a singleton group (a group with only one feat/val pair
                              in it) in MatrixTDB. False otherwise.
    Functionality: Determines whether or not f/v exist as a singleton feat/val group in MatrixTDB.
    """
    # get rows with group IDs with this feat/val combo in it
    grpIDrows = conn.selQuery("SELECT fg_grp_id FROM feat_grp " +
                                        "WHERE fg_feat = %s and fg_value = %s", (f,v))

    for row in grpIDrows:               # for each row for grp with f/v combo in it...
        grpID = row[0]                    # ...get the group id
        # get all rows for feat/val pairs in that group
        fvRows = conn.selQuery("SELECT fg_id FROM feat_grp WHERE fg_grp_id = %s",
                                                                                                                       (grpID))
        if len(fvRows) == 1:            # if there's only one feat/val pair in that group...
            answer = True               # ...then f/v exist as a singleton group, set output to True
            break                            # and get out of here
    else:                                     # if we go thru for loop and never find a singleton group...
        answer = False                  # ...set output to False

    return answer                        # return output

###############################################################
# update_feat_group(choices): Make sure that all f:v pairs
# are in feat_group as singleton groups.

def update_feat_group(choices, conn):
    """
    Function: update_feat_group
    Input:
        choices - a ChoicesFile representing a language type
        conn - a MatrixTDBConn, a connection to the Matrix TDB database.
    Ouput: none
    Functionality: Inserts every feat/val combo in choices file into database as a singleton group if
                         such a group doesn't already exist
    """
    for f in choices.keys():            # for every feature in the ChoicesFile...
        v = choices.get(f)               # ...get that feature's value

        if not singleton_group_exists(f, v, conn):      # if f/v do not exist as singleton group in db...
            try:
                # ...get the highest group ID in the database...
                fg_grp_id = conn.selQuery("SELECT max(fg_grp_id) FROM feat_grp")[0][0]
            except IndexError:
                # ...or if there were no grp ids in the database yet, set initial group id to 1...
                fg_grp_id = 1

            # ...and enter f/v as singleton group into database
            conn.execute("INSERT INTO feat_grp " + \
                                 "SET fg_grp_id = %s, fg_feat = %s, fg_value = %s", (fg_grp_id ,f, v))

    return

###############################################################
# update_lt_in_lfg(choices,lt_id): Update the lt_feat_grp table to
# reflect all currently defined feature groups which correspond
# to this language type.
# NB: choices is sometimes a ChoicesFile (when called from sql_lg_type.create_or_update_lt)
#        and is sometimes a dict of fv pairs (when called from
#        run_specific_filters.update_all_lts_in_lg).

def update_lt_in_lfg(choices, lt_id, conn):
    """
    Function:update_lt_in_lfg
    Input:
        choices - either a ChoicesFile object or a dict of feature/value pairs, depending on where
                       this function was called from TODO: add to this to clarify
        lt_id - a language type ID
        conn - a MatrixTDBConn, a connection to MatrixTDB
    Output: none
    Functionality: For every feature group in the database, checks to see if all of the feat/val pairs
                         in that group are in choices.  If they are, it ensures there is a link from lt_id
                         to that group.  If they are not, it ensures there is not a link from lt_id to that
                         group.  So it ensures that lt_id is linked to the right feature groups.  TODO:
                         does choices represent the feat/vals in lt_id?  Verify by looking at all places this
                         is called and update this doco.  IThere is a link when called from
                         create_or_update_lt
    """

    # Get all feature groups from DB
    groupIDRows = conn.selQuery("SELECT DISTINCT fg_grp_id FROM feat_grp")

    for row in groupIDRows:     # for every row returned...
        g_id = row[0]                # ...get the group id

        # Get all of the feature-value pairs in a group
        fvrows = conn.selQuery("SELECT fg_feat, fg_value FROM feat_grp " + \
                                           "WHERE fg_grp_id = %s", (g_id))

        # Find out if we already have this group associated with this lt by querying for a row that
        # has the language type and this group in it
        ltGrpRow = conn.selQuery("SELECT * FROM lt_feat_grp " + \
                                                "WHERE lfg_lt_id = %s AND lfg_grp_id = %s",(lt_id, g_id))

        if ltGrpRow == ():                             # if a row was not returned...
            row_exists_p = False                   # ...the row does not exist
        else:                                               # otherwise...
            row_exists_p = True                     # ...it does

        if isinstance(choices, ChoicesFile):    # if this function was called with a ChoicesFile...
            chcDict = choices.choices            # ...set chcDict to the feat/val dict in that object
        elif isinstance(choices, dict):             # if it was called with a feat/val dict...
            chcDict = choices                        # ...then just set chcDit to that.
        else:                                               # and if it was called with some other type...
            # ...then raise an error            
            raise ValueError, "Invalid type of choices argument in " + \
                                     "sql_lg_type.update_lt_in_lfg. Expected dict or ChoicesFile."

        # if the value of every feature in this feature group match those in choices...
        if check_lt_for_fvs(fvrows, chcDict):
            # ...and if there is no link between the group and the language type id...
            if not(row_exists_p):
                # ...create such a link
                conn.execute("INSERT INTO lt_feat_grp " + \
                             "SET lfg_lt_id = %s, lfg_grp_id = %s",(lt_id,g_id))
        else:       # if there is some mismatch between the feat/vals in fvs and choices...
            if row_exists_p:        # ...and if there is a link between this group and this lt id
                # ...delete it.
                conn.execute("DELETE FROM lt_feat_grp " + \
                                    "WHERE lfg_lt_id = %s, lfg_grp_id = %s",(lt_id,g_id))
    return

###############################################################
# create_or_update_lt(choices): Given a new language type described
# in a dictionary of f:v pairs, create an entry in lt, put
# all of the singleton f:v pairs into feat_group (if they're
# not already there, and update lt_lfg to list all of the
# feature groups appropriate for this language type.

def create_or_update_lt(choices, conn):
    """
    Function: create_or_update_lt
    Input:
        choices - a ChoicesFile representing a language type
        conn - a MatrixTDBConn, a connection to MatrixTDB.
    Output: lt_id - the language type ID representing the choices file, whether we had to add it or
                if one already existed
    Functionality: If a language type that matches choices exists, it returns its ID.  If not, it
                         creates one (with input from user) and returns that ID.
    """

    # TODO: this function can probably be broken up into smaller ones

    # Check if the language type already exists, if so,
    # call update_lt_in_lfg instead and return lt_id.

    # get lang type ID of lang type in MatrixTDB if one matches choices (False otherwise)
    lt_id = lt_exists(choices,conn)

    # If no existing language type for this choices file was found...
    if not lt_id:                                                       # if a matching lt was found...
        # ...make sure all f:v pairs are in database as singleton groups
        update_feat_group(choices, conn)
            
        res = ''                                        # initialize input from user
        while (res != 'r' and res != 'p'):        # loop until we get answer we want
            # find out if lt represnted by choices was randomly generated or purpose-built 
            res = raw_input("Is this language type [r]andomly generated or [p]urpose-built? [r/p] ")

        # get a comment about the language type from the user
        comment = raw_input("Enter a short comment describing this language type: ")

        # insert a row for the language type into the lt table.
        conn.execute("INSERT INTO lt SET lt_origin = %s, lt_comment = %s", (res,comment))

        # and get that language type's ID
        lt_id = conn.selQuery("SELECT LAST_INSERT_ID()")[0][0]

    # ensure that this language type is linkted to the right feature groups
    update_lt_in_lfg(choices,lt_id,conn)
    
    return lt_id                                        # return output

###############################################################
# Main Program

def main():

  choices = ChoicesFile(sys.argv[1])

  # In order to have language-to-language comparisons work correctly,
  # remove the language name and test sentences
  choices.delete('language')
  choices.delete('sentence1')
  choices.delete('sentence2')

  # Set up the cursor

  db = MySQLdb.connect(host="localhost", user="ebender",
                       passwd="tr33house", db="MatrixTDB")

  cursor = db.cursor()

  lt_id = create_or_update_lt(choices,cursor)

  # Okay, we're done.  Print out the lt_id for future reference.

  print "Language type id (lt_id) is: " + str(lt_id)

if __name__ == "__main__":
  main()

