from gmcs.utils import TDLencode
from gmcs.lib import TDLHierarchy
from gmcs.utils import get_name

######################################################################
# customize_case()
#   Create the type definitions associated with the user's choices
#   about case.

# case_names()
#   Create and return a list containing information about the cases
#   in the language described by the current choices.  This list consists
#   of tuples with three values:
#     [canonical name, friendly name, abbreviation]
def case_names(ch):
  # first, make two lists: the canonical and user-provided case names
  cm = ch.get('case-marking')
  canon = []
  user = []
  if cm == 'nom-acc':
    canon.append('nom')
    user.append(ch[cm + '-nom-case-name'])
    canon.append('acc')
    user.append(ch[cm + '-acc-case-name'])
  elif cm == 'erg-abs':
    canon.append('erg')
    user.append(ch[cm + '-erg-case-name'])
    canon.append('abs')
    user.append(ch[cm + '-abs-case-name'])
  elif cm == 'tripartite':
    canon.append('s')
    user.append(ch[cm + '-s-case-name'])
    canon.append('a')
    user.append(ch[cm + '-a-case-name'])
    canon.append('o')
    user.append(ch[cm + '-o-case-name'])
  elif cm in ['split-s']:
    canon.append('a')
    user.append(ch[cm + '-a-case-name'])
    canon.append('o')
    user.append(ch[cm + '-o-case-name'])
  elif cm in ['fluid-s']:
    a_name = ch[cm + '-a-case-name']
    o_name = ch[cm + '-o-case-name']
    canon.append('a+o')
    user.append('fluid')
    canon.append('a')
    user.append(a_name)
    canon.append('o')
    user.append(o_name)
  elif cm in ['split-n', 'split-v']:
    canon.append('nom')
    user.append(ch[cm + '-nom-case-name'])
    canon.append('acc')
    user.append(ch[cm + '-acc-case-name'])
    canon.append('erg')
    user.append(ch[cm + '-erg-case-name'])
    canon.append('abs')
    user.append(ch[cm + '-abs-case-name'])
  elif cm in ['focus']:
    canon.append('focus')
    user.append(ch[cm + '-focus-case-name'])
    canon.append('a')
    user.append(ch[cm + '-a-case-name'])
    canon.append('o')
    user.append(ch[cm + '-o-case-name'])

  # fill in any additional cases the user has specified
  for case in ch.get('case'):
    canon.append(case['name'])
    user.append(case['name'])

  # if possible without causing collisions, shorten the case names to
  # three-letter abbreviations; otherwise, just use the names as the
  # abbreviations
  abbrev = [ l[0:3] for l in user ]
  if len(set(abbrev)) != len(abbrev):
    abbrev = user

  return zip(canon, user, abbrev)

# Given the canonical (i.e. choices variable) name of a case, return
# its abbreviation from the list of cases, which should be created by
# calling case_names().  If there is no abbreviation, return the name.
def canon_to_abbr(name, cases):
  for c in cases:
    if c[0] == name:
      return c[2]
  return name

# Given the name of a case, return its abbreviation from the list of
# cases, which should be created by calling case_names().  If there
# is no abbreviation, return the name.
def name_to_abbr(name, cases):
  for c in cases:
    if c[1] == name:
      return c[2]
  return name

def init_case_hierarchy(ch, hierarchies):
  cm = ch.get('case-marking')
  cases = case_names(ch)

  hier = TDLHierarchy('case')

  # For most case patterns, just make a flat hierarchy.  For fluid-s,
  # split-n and split-v, however, a more articulated hierarchy is required.
  if cm in ['nom-acc', 'erg-abs', 'tripartite', 'split-s', 'focus']:
    for c in cases:
      hier.add(c[2], 'case', c[1])
  elif cm in ['fluid-s']:
    abbr = canon_to_abbr('a+o', cases)
    for c in cases:
      if c[0] in ['a', 'o']:
        hier.add(c[2], abbr, c[1])
      else:
        hier.add(c[2], 'case', c[1])
  elif cm in ['split-n', 'split-v']:
    nom_a = canon_to_abbr('nom', cases)
    acc_a = canon_to_abbr('acc', cases)
    erg_a = canon_to_abbr('erg', cases)
    abs_a = canon_to_abbr('abs', cases)
    if cm == 'split-v':
      for c in cases:
        hier.add(c[2], 'case', c[1])
    else:  # 'split-n':
      hier.add('a', 'case', 'transitive agent')
      hier.add('s', 'case', 'intransitive subject')
      hier.add('o', 'case', 'transitive patient')
      for c in cases:
        if c[2] == erg_a:
          hier.add(c[2], 'a', c[1])
        elif c[2] == nom_a:
          hier.add(c[2], 'a', c[1])
          hier.add(c[2], 's', c[1])
        elif c[2] == abs_a:
          hier.add(c[2], 's', c[1])
          hier.add(c[2], 'o', c[1])
        elif c[2] == acc_a:
          hier.add(c[2], 'o', c[1])
        else:
          hier.add(c[2], 'case', c[1])

  if not hier.is_empty():
    hierarchies[hier.name] = hier


# customize_case_type()
#   Create a type for case

def customize_case_type(mylang, hierarchies):
  if 'case' in hierarchies:
    hierarchies['case'].save(mylang)

# customize_case_adpositions()
#   Create the appropriate types for case-marking adpositions

def customize_case_adpositions(mylang, lexicon, ch):
  cases = case_names(ch)
  features = ch.features()
  to_cfv = []

  if ch.has_adp_case():
    comment = \
      ';;; Case-marking adpositions\n' + \
      ';;; Case marking adpositions are constrained not to\n' + \
      ';;; be modifiers.'
    mylang.add_literal(comment)

    mylang.add('+np :+ [ CASE case ].', section='addenda')

    typedef = \
      'case-marking-adp-lex := basic-one-arg & raise-sem-lex-item & \
          [ SYNSEM.LOCAL.CAT [ HEAD adp & [ CASE #case, MOD < > ], \
                               VAL [ SPR < >, \
                                     SUBJ < >, \
                                     COMPS < #comps >, \
                                     SPEC < > ]], \
            ARG-ST < #comps & [ LOCAL.CAT [ HEAD noun & [ CASE #case ], \
                                            VAL.SPR < > ]] > ].'
    mylang.add(typedef)

    if ch.has_mixed_case():
      mylang.add('+np :+ [ CASE-MARKED bool ].', section='addenda')
      mylang.add(
        'case-marking-adp-lex := \
         [ ARG-ST < [ LOCAL.CAT.HEAD.CASE-MARKED - ] > ].')

    # Lexical entries
    lexicon.add_literal(';;; Case-marking adpositions')

    for adp in ch.get('adp',[]):
      orth = adp.get('orth','')

      # figure out the abbreviation for the case this adp marks
      cn = ''
      abbr = ''
      for feat in adp.get('feat', []):
        if feat['name'] == 'case':
          cn = feat['value']
          break

      abbr = name_to_abbr(cn, cases)

      adp_type = TDLencode(abbr + '-marker')
      typedef = \
        adp_type + ' := case-marking-adp-lex & \
                        [ STEM < "' + orth + '" > ].'
      lexicon.add(typedef)

      to_cfv += [(adp.full_key, adp_type, 'adp')]

  return to_cfv

def customize_case(mylang, ch, hierarchies):
  # first we need to peek in things like lex-rules for when something
  # has mixed case, and replace with the appropriate type covering
  from gmcs.linglib.lexbase import ALL_LEX_TYPES
  cases = case_names(ch)
  for x in ALL_LEX_TYPES:
    for lex_type in ch[x]:
      convert_mixed_case(lex_type, hierarchies, cases)
    for pc in ch[x + '-pc']:
      convert_mixed_case(pc, hierarchies, cases)
      for lrt in pc['lrt']:
        convert_mixed_case(lrt, hierarchies, cases)
  # now output the case hierarchies
  customize_case_type(mylang, hierarchies)

def convert_mixed_case(item, hierarchies, cases):
  for feat in item.get('feat',[]):
    if feat['name'] == 'case' and ',' in feat['value']:
      v = [canon_to_abbr(c, cases) for c in feat['value'].split(', ')]
      feat['value'] = hierarchies['case'].get_type_covering(v)

def add_lexrules(ch):
  # only need to add rules for mixed_case
  if not ch.has_mixed_case():
    return
  for pc in ch['noun-pc']:
    if 'case' in [feat['name'] for lrt in pc['lrt'] for feat in lrt['feat']]:
      for c in case_names(ch):
        if ch.has_adp_case(c[0]):
          idx = ch[pc.full_key + '_lrt'].next_iter_num()
          lrt_key = pc.full_key + '_lrt' + str(idx)
          ch[lrt_key + '_name'] = get_name(pc) + '-synth-' + c[0]
          ch[lrt_key + '_feat1_name'] = 'case'
          ch[lrt_key + '_feat1_value'] = c[0]
          ch[lrt_key + '_lri1_inflecting'] = 'no'
          ch[lrt_key + '_lri1_orth'] = ''

def interpret_verb_valence(valence):
  '''
  Return the canonical valence name (e.g. iverb, tverb) given the
  valence for a verb as defined in a choices file.
  '''
  if valence == 'trans' or '-' in valence:
    return 'tverb'
  else:
    return 'iverb'

##################
### VALIDATION ###
##################

def validate(choices, vr):
  cm = choices.get('case-marking')

  if not cm:
    vr.err('case-marking', 'You must specify if/how case is marked.')

  if cm in ('nom-acc', 'split-n', 'split-v'):
    validate_one_case(choices, vr, cm + '-nom')
    validate_one_case(choices, vr, cm + '-acc')
  if cm in ('erg-abs', 'split-n', 'split-v'):
    validate_one_case(choices, vr, cm + '-erg')
    validate_one_case(choices, vr, cm + '-abs')
  if cm in ('tripartite', 'split-s', 'fluid-s', 'focus'):
    validate_one_case(choices, vr, cm + '-a')
    validate_one_case(choices, vr, cm + '-o')
  if cm in ('tripartite'):
    validate_one_case(choices, vr, cm + '-s')
  if cm in ('focus'):
    validate_one_case(choices, vr, cm + '-focus')

  if cm == 'none' and 'case' in choices:
    for case in choices['case']:
      vr.err(case.full_key + '_name',
             'You may not specify additional cases ' +
             'if your language has no case marking.')

  if 'scale' in choices and not choices.get('scale-equal'):
    vr.err('scale-equal',
           'If you define a direct-inverse scale, ' +
           'you must say what direction the verb is ' +
           'when the agent and patient have equal rank.')

######################################################################
# validate_one_case(pre)
#   A helper function to validate the user's choices about one case.
#   pre is the first few characters of the associated choices names
#  (e.g. 'nom-acc-nom')

def validate_one_case(ch, vr, pre):
  if not ch.get(pre + '-case-name'):
    vr.err(pre + '-case-name', 'You must specify a name for every case.')
