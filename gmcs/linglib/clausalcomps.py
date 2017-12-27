from gmcs.utils import merge_constraints, get_name

from gmcs import constants, utils

######################################################################
# Clausal Complements
#   Create the type definitions associated with the user's choices
#   about clasual complements.

######################################################################

# Constants (specific to this module)
COMPS = 'comps' # choice name for clausal complement strategies
COMP = 'comp' # reserved head name for complementizers; should be a constant on some other page?
              # Also, the name for the choice for complementizer of a clausal complement strategy.
CLAUSE_POS_EXTRA = 'clause-pos-extra' # Choice name for extraposed complement
CLAUSE_POS_SAME = 'clause-pos-same' # Choice name for default noun position complement

COMP_POS_BEFORE = 'comp-pos-before' # Choice name for complementizer attaching before embedded clause
COMP_POS_AFTER = 'comp-pos-after' # Choice name for complementizer attaching after embedded clause

COMPLEX = 'complex' # TDL file section name for complementizer lexical items

COMP_LEX_ITEM = 'comp-lex-item'

COMP_LEX_ITEM_DEF = COMP_LEX_ITEM + ' := raise-sem-lex-item & basic-one-arg &\
      [ SYNSEM.LOCAL.CAT [ HEAD comp &\
                                [ MOD < > ],\
                           VAL [ SPR < >,\
                                 SUBJ < >,\
                                 COMPS < #comps > ] ],\
        ARG-ST < #comps & \
                 [ LOCAL.CAT [ HEAD verb, MC -,\
                               VAL [ SUBJ < >,\
                                     COMPS < > ] ] ] > ].'

FORM = 'FORM' # FORM feature name
FORM_PATH = 'SYNSEM.LOCAL.CAT.VAL.COMPS.FIRST.LOCAL.CAT.HEAD' # FORM feature path

# Note: the below lists do not include V2 or free.
OV_ORDERS = ['sov', 'ovs', 'osv', 'v-final']
#EXTRA_ORDERS = ['sov', 'v-final', 'osv'] # orders allowed with extraposed clausal complements
VFINAL = ['sov','osv','v-final']
VO_ORDERS = ['svo', 'vos', 'vso', 'v-initial']

CLAUSALCOMP = 'clausalcomp'
COMPLEMENTIZER = 'complementizer' # Choices key for choices pertaining
                                  # to the complementizer defined for
                                  # a particular complementation strategy.
EXTRA = 'EXTRA' # Feature for extraposed complements


# Error messages:
EXTRA_VO = 'The only supporded word orders for extraposed complements are: SOV, VOS, OVS, OSV, v-final. ' \
           'V-initial is not supported with optional complementizer.'
SAME_OR_EXTRA = 'Please choose whether the clausal complement takes the same position as noun ' \
                        'complements or is extraposed to the end of the clause ' \
                        '(the latter valid only for strict OV orders).'

#### Methods ###

'''
Main function which will be called by customize.py.
Should fully cover all the customization needed for
what was specified on the Clausal Complements subpage
of the Questionnaire.
'''
def customize_clausalcomps(mylang,ch,lexicon,rules,irules):
    if not COMPS in ch:
        return
    # Note: clausal verb type will be added by lexical_items.py,
    # just like a regular verb. It would be better to do it here instead?
    have_comp = add_complementizers_to_lexicon(lexicon,ch)
    add_types_to_grammar(mylang,ch,rules,have_comp)

def add_complementizers_to_lexicon(lexicon,ch):
    lexicon.add_literal(';;; Complementizers')
    have_comp = False
    for comp_strategy in ch[COMPS]:
        id = comp_strategy.full_key
        typename = id + '-' + COMP_LEX_ITEM
        for complementizer in comp_strategy[COMPLEMENTIZER]:
            orth = complementizer[constants.ORTH]
            typedef = complementizer.full_key + ' := ' + typename + '& \
                          [ STEM < "' + orth + '" > ].'

            lexicon.add(typedef)
            have_comp = True
    return have_comp


def add_types_to_grammar(mylang,ch,rules,have_complementizer):
    if have_complementizer:
        mylang.set_section(COMPLEX)
        add_complementizer_supertype(mylang)
    init = False # Has the INIT feature been used?
    # Note: iterating over ch.get(COMPS) (the complementation strategies)
    # twice on purpose here, to avoid convoluted logic
    # involving whether we are using the INIT feature. If we use it for any clausal complement
    # strategy, we must constrain all of them properly with respect to INIT. But if we don't need
    # it at all, best not to put an unnecessary feature into the grammar.
    wo = ch.get(constants.WORD_ORDER)
    if wo in OV_ORDERS or wo in VO_ORDERS:
        for cs in ch.get(COMPS):
            init = init_needed(ch.get(constants.WORD_ORDER),cs,mylang)
            if init:
                break
        # Which is the default head-complement rule for nouns etc.,
        # and which needs to be added for this complementation strategy?
        general, additional = determine_head_comp_rule_type(ch.get(constants.WORD_ORDER))
        if wo=='v-initial' or wo == 'vos' and has_extraposition(ch):
            additional = 'head-comp-ccomp'
    mylang.add('head :+ [ EXTRA bool ].', section='addenda')
    for cs in ch.get(COMPS):
        ccomp_type = determine_ccomp_mark_type(ch)
        # There can only be one complementizer type per strategy
        clausalverb = find_clausalverb_typename(ch,cs)
        customize_clausal_verb(clausalverb,mylang,ch,cs)
        typename = add_complementizer_subtype(cs, mylang) if cs[COMP] else None
        if wo in OV_ORDERS or wo in VO_ORDERS:
        # Some strategies require changes to the word order
            customize_order(ch, cs, mylang, rules, typename, init,general,additional)

def add_complementizer_supertype(mylang):
    mylang.add(COMP_LEX_ITEM_DEF, section=COMPLEX)

def add_complementizer_subtype(cs, mylang):
    id = cs.full_key
    typename = id + '-' + COMP_LEX_ITEM
    mylang.add(typename + ' := ' + COMP_LEX_ITEM + '.', section=COMPLEX)
    # merge feature information in
    path = FORM_PATH + '.' + FORM
    merge_constraints(choicedict=cs, mylang=mylang, typename=typename,
                      path=path, key1='feat', key2='name', val='form')
    return typename

'''
Add and modify head-complement rules depending
on what kind of word order variations clausal complements
exhibit.
General and additional are default and new head-comp rule
(determined simply by the word order).
For example, if the order is OV, the general rule will
be comp-head, and the additional will be head-comp,
to accommodate non-default orders.
Typename is the name of the complementizer involved in this
complementation strategy.
cs is the complementation strategy.
init tells if the INIT feature is needed or not. The value must
be true if INIT feature will be used in at least one of
the complementation strategies in this grammar.
'''
def customize_order(ch, cs, mylang, rules, typename, init, general, additional):
    wo = ch.get(constants.WORD_ORDER)
    init_value = '+' if additional == constants.HEAD_COMP else '-'
    default_init_value = '-' if init_value == '+' else '+'
    # What is the head of the added rule's head daughter?
    head = determine_head(wo,cs)
    if init and head:
        # If INIT feature was used before or is needed now:
        # Which lexical types need to be constrained wrt INIT?
        constrain_lex_items(head,ch,cs,typename,init_value,default_init_value,mylang)
    # Constrain added and general rule wrt head and INIT
    if need_customize_hc(wo,cs):
        #TODO: this should probably be split somehow; the number of args is unhealthy.
        constrain_head_comp_rules(mylang,rules,init,init_value,default_init_value,head,general,additional,cs,wo,ch)
    if need_customize_hs(wo,cs):
        constrain_head_subj_rules(wo,cs,mylang,rules)

def need_customize_hc(wo,cs):
    if cs[COMP]:
        if wo in OV_ORDERS and cs[COMP_POS_AFTER] == 'on' and cs[CLAUSE_POS_SAME] == 'on' \
                and not cs[COMP_POS_BEFORE] == 'on' and not cs[CLAUSE_POS_EXTRA] == 'on':
            return False
        if wo in VO_ORDERS and cs[COMP_POS_BEFORE] == 'on'and not cs[COMP_POS_AFTER] == 'on':
            if wo in ['svo','vso']:
                return False
            if wo in ['v-initial','vos'] and cs[CLAUSE_POS_SAME] and not cs[CLAUSE_POS_EXTRA]:
                return False
        return True
    else:
        return not (wo in ['vso','svo'] or not cs[CLAUSE_POS_EXTRA])

def need_customize_hs(wo,cs):
    return wo in ['vos'] and cs[CLAUSE_POS_EXTRA]

def customize_complementizer_order():
    pass

def customize_cverb_ccomp_order():
    pass

def constrain_head_subj_rules(wo,cs,mylang,rules):
    #if wo == 'vos' and cs[CLAUSE_POS_EXTRA]:
    if cs[COMP]:
        head = 'comp' if cs[COMP] == 'oblig' else '+vc'
    elif is_nominalized_complement(cs):
        head = '[ NMZ + ]'
    else:
        head = 'verb'
    mylang.add('head-subj-ccomp-phrase := decl-head-subj-phrase & head-initial & '
               '[ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.COMPS < [ LOCAL.CAT.HEAD ' + head + ' ] > ].',section='phrases')
    for f in cs['feat']:
        if f['name'] == 'form':
            mylang.add('head-subj-ccomp-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.COMPS '
                       '< [ LOCAL.CAT.HEAD.FORM ' + f['value'] + ' ] > ].')
    rules.add('head-subj-ccomp := head-subj-ccomp-phrase.')
    mylang.add('head-subj-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.COMPS < > ].',merge=True)

'''
An additional HCR will *not* be needed if:
The matrix order is VO and clausal complements can take the nouny complement position,
and there is not a complementizer or
there is a complementizer but it can use the normal HCR.
'''
def additional_needed(cs,wo):
    #TODO: Currently, there is a special case that has
    # to do with cs[COMP_POS_AFTER] and v-intial orders. I can probably get rid of it.
    return not (wo in ['v-initial', 'vos'] and cs[CLAUSE_POS_SAME]
                and (not cs[COMP] or (cs[COMP_POS_AFTER] and cs[COMP_POS_BEFORE])))

'''
If an additional head-comp rule is needed, it may also need constraints
with respect to its head or the INIT feature. The default rule will
also need to be constrained with respect to INIT, if INIT is used in
the additional rule.
'''
def constrain_head_comp_rules(mylang,rules,init,init_value, default_init_value,head,general,additional,cs,wo,ch):
    handle_special_cases(additional, cs, general, mylang, rules, wo)
    if additional_needed(cs,wo):
        supertype = 'head-initial' if additional.startswith(constants.HEAD_COMP) else 'head-final'
        mylang.add(additional + '-phrase := basic-head-1st-comp-phrase & ' + supertype + '.'
               ,section = 'phrases',merge=True)
        if not head:
            rules.add(additional + ' := ' + additional + '-phrase.')
        else:
            # For some combinations of choices, we may need separate rules for complementizers
            # and clausal verbs, to avoid spurious parses.
            if head == '+vc':
                #TODO: Different rules for complementizer and noun head-comp rule are also
                # needed for v-initial extraposed with optional complementizer
                if cs[CLAUSE_POS_EXTRA] and not cs[CLAUSE_POS_SAME] \
                        and cs[COMP_POS_AFTER] and cs[COMP_POS_BEFORE]:
                    rules.add(additional + '-verb := ' + additional + '-verb-phrase.')
                    rules.add(additional + '-comp := ' + additional + '-comp-phrase.')
                    mylang.add(additional + '-verb-phrase := '
                               + additional + '-phrase & [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD verb ].',section='phrases')
                    if wo in VFINAL:
                        mylang.add(additional + '-verb-phrase := '
                               + additional + '-phrase & [ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.SUBJ < [ ] > ].',merge=True)
                    mylang.add(additional + '-comp-phrase := '
                               + additional + '-phrase & [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD comp ].',section='phrases')
                else:
                    rules.add(additional + ' := ' + additional + '-phrase.', merge=True)
            # Here, head must be either comp or verb, but not both
            else:
                rules.add(additional + ' := ' + additional + '-phrase.', merge=True)
                mylang.add(additional + '-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD ' + head +' ].'
                       ,merge=True)
                if is_nominalized_complement(cs):
                    mylang.add(additional + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD [ NMZ + ] ].'
                       ,merge=True)
        if init:
            mylang.add(additional +
                       '-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD.INIT ' + init_value + ' ].',
                       merge=True)
            mylang.add(general + '-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD.INIT ' + default_init_value + ' ].',
                       merge=True)
        for f in cs['feat']:
            if f['name'] != 'nominalization':
                mylang.add(additional + '-phrase := '
                                       '[ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD.' + f['name'].upper() +' '
                          + f['value'] + ' ].',merge=True)

#TODO: I haven't still grasped the general logic here, hopefully one day it'll generalize.
def handle_special_cases(additional, cs, general, mylang, rules, wo):
    if (wo in ['ovs', 'v-initial','vos']) and cs[CLAUSE_POS_EXTRA]:
        if not cs[CLAUSE_POS_SAME]:
            mylang.add(additional + '-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.SUBJ <  > ].', merge=True)
    if wo in ['v-initial','vos'] and cs[CLAUSE_POS_EXTRA]:
        if cs[COMP] == 'oblig':
            gen_head = '+nv'
            add_head = 'comp'
        elif cs[COMP] == 'opt':
            gen_head = 'noun'
            add_head = '+vc' if cs[COMP] == 'opt' else 'verb'
            #if not cs[CLAUSE_POS_SAME]:
            #    mylang.add('head-comp-complementizer-phrase := basic-head-1st-comp-phrase & head-initial & '
            #           '[ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD comp ].', section='phrases', merge=True)
            #    rules.add('head-comp-cmpl := head-comp-complementizer-phrase.')
        elif not cs[COMP]:
            if is_nominalized_complement(cs):
                gen_head = '[ NMZ - ]'
                add_head = '[ NMZ + ]'
                mylang.add(general + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD ' + gen_head + ' ].')
            else:
                gen_head = 'noun'
                add_head = 'verb'
        if not cs[CLAUSE_POS_SAME]:
            mylang.add(additional + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD.EXTRA + ].', merge=True)
            mylang.add(general + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD.EXTRA - ].', merge=True)
        #mylang.add(general + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD ' + gen_head + ' ].')
        if not wo in ['v-initial', 'vos']:
            mylang.add(additional + '-phrase := [ NON-HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD ' + add_head + ' ].')
        if cs[CLAUSE_POS_SAME] and cs[COMP]:
            mylang.add('comp-head-phrase := basic-head-1st-comp-phrase & head-final '
                       '& [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD comp ].',section='phrases')
            rules.add('comp-head := comp-head-phrase.')
    elif wo == 'v-final' and cs[CLAUSE_POS_EXTRA]:
        if cs[COMP] == 'opt' or not cs[COMP]:
            mylang.add(additional + '-phrase := [ HEAD-DTR.SYNSEM.LOCAL.CAT.VAL.SUBJ < [ ] > ].', merge=True)
            if cs[COMP] == 'opt':
                mylang.add('head-comp-complementizer-phrase := basic-head-1st-comp-phrase '
                           '& head-initial & [ HEAD-DTR.SYNSEM.LOCAL.CAT.HEAD comp & [ INIT + ] ].',
                           section='phrases')
                rules.add('head-comp-cmpl := head-comp-complementizer-phrase.')

def find_clausalverb_typename(ch,cs):
    for v in ch.get(constants.VERB):
        if v.get(constants.VALENCE) == cs.full_key:
            return get_name(v) + '-' + cs.full_key + '-verb-lex'

'''
This function assumes that the INIT feature is needed.
It will constrain verbs and/or complementizers with respect to the INIT feature.
'''
def constrain_lex_items(head,ch,cs,comptype, init_value, default_init_value,mylang):
    clausalverb = find_clausalverb_typename(ch,cs)
    init_path = 'SYNSEM.LOCAL.CAT.HEAD'
    if head == '+vc':
        if cs[CLAUSE_POS_EXTRA]:
            if not cs[CLAUSE_POS_SAME]:
                constrain_lexitem_for_feature(clausalverb,init_path, 'INIT',init_value,mylang)
                mylang.add('transitive-verb-lex := [ '  + init_path + '.INIT ' + default_init_value + ' ].'
                   , merge=True)
            elif cs[COMP] == 'opt':
                mylang.add('transitive-verb-lex := [ ' + init_path + '.INIT ' + default_init_value + ' ].'
                   , merge=True)
        if cs[COMP_POS_BEFORE] and not cs[COMP_POS_AFTER] and ch.get(constants.WORD_ORDER) in OV_ORDERS:
            constrain_lexitem_for_feature(comptype,init_path,'INIT',init_value,mylang)
    elif head == constants.VERB:
        if cs[CLAUSE_POS_EXTRA] and not cs[CLAUSE_POS_SAME]:
            constrain_lexitem_for_feature(clausalverb,init_path, 'INIT', init_value,mylang)
        mylang.add('transitive-verb-lex := [ ' + init_path + '.INIT ' + default_init_value + ' ].'
                   , merge=True)
    elif head == 'comp':
        if (cs[COMP_POS_BEFORE] and not cs[COMP_POS_AFTER] and ch.get(constants.WORD_ORDER) in OV_ORDERS) \
                or (cs[COMP_POS_AFTER] and ch.get(constants.WORD_ORDER) in VO_ORDERS):
            mylang.add(comptype + ':= [ ' + init_path + '.INIT ' + init_value + ' ].',merge=True)


def constrain_lexitem_for_feature(typename, feature_path, feature_name, feature_value,mylang):
    mylang.add( typename + ' := [ ' + feature_path + '.' + feature_name.upper() + ' ' + feature_value + ' ]. ',
                            merge=True)

'''
Determine whether the head of the additional head-comp rule
should be constrained to just verbs, just complementizers, or both.
'''
def determine_head(wo,cs):
    head = None
    if not cs[COMP]:
        head = 'verb'
    elif wo in OV_ORDERS:
        if cs[COMP_POS_BEFORE]:
            if cs[CLAUSE_POS_EXTRA]:
                head = '+vc'
            elif cs[CLAUSE_POS_SAME]:
                head = 'comp'
        elif cs[COMP_POS_AFTER]:
            if cs[CLAUSE_POS_EXTRA]:
                head = 'verb'
    elif wo in VO_ORDERS:
        if cs[COMP_POS_AFTER]:
            if cs[CLAUSE_POS_EXTRA]:
                head = '+vc'
            elif cs[CLAUSE_POS_SAME]:
                head = 'comp'
        elif cs[COMP_POS_BEFORE]:
            if cs[CLAUSE_POS_EXTRA]:
                head = 'verb'
    return head

'''
Determine which head-complement rule is the generally applicable one
and which one would be the secondary one, applicable only to complementizers
and/or clausal complement verbs.
'''
def determine_head_comp_rule_type(wo):
    if wo == 'v2' or wo == 'free':
        # Note: it is possible that not much is needed here, as v2 and free are very flexible
        raise Exception('Currently only supporting strict VO/OV orders, but not V2 or free.')
    return (constants.HEAD_COMP, constants.COMP_HEAD) if wo in VO_ORDERS \
        else (constants.COMP_HEAD,constants.HEAD_COMP)

'''
Given word order and clausal complement choices,
determine whether the INIT feature will be used,
for this particular clausal complement strategy.
Note that once the INIT feaure has been used for
one strategy, you will need to keep it in mind
for all of them, so you will need to stop
calling this function once it returns True.
'''

def init_needed(wo, cs,mylang):
    res = False
    if cs[COMP]:
        if wo in OV_ORDERS:
            if cs[COMP] == 'opt' and cs[CLAUSE_POS_EXTRA]:
                res = True
            # Note that cs is a dict which will return an empty string
            # if the object is not there. In this case, the IF statement should
            # return False, but perhaps it would be clearer to write this out.
            elif cs[COMP_POS_BEFORE]:
                if not cs[COMP_POS_AFTER]: # complementizer before clause only
                    res = True
                else: # complementizer both before and after clause
                    res = (cs[CLAUSE_POS_SAME] and not cs[CLAUSE_POS_EXTRA]) \
                          or (cs[CLAUSE_POS_EXTRA]and not cs[CLAUSE_POS_SAME])
            elif cs[COMP_POS_AFTER]:
                res = cs[CLAUSE_POS_EXTRA] == constants.ON
        elif wo in VO_ORDERS:
            res = (cs[COMP_POS_AFTER] == constants.ON and not cs[COMP_POS_BEFORE] == constants.ON)
    else:
         res = (wo in OV_ORDERS or wo == 'vos') and cs[CLAUSE_POS_EXTRA] == 'on'
    if res:
        mylang.add('head :+ [ INIT bool ].', section='addenda')
    return res

def extra_needed(ch,mylang):
    res = ch.get(constants.WORD_ORDER) in ['v-initial','vos'] \
           and len([cs for cs in ch[COMPS] if cs[CLAUSE_POS_EXTRA]]) > 0
    if res:
        mylang.add('head :+ [ EXTRA bool ].', section='addenda')
        if len([cs for cs in ch[COMPS] if cs[CLAUSE_POS_SAME]]) == 0:
            mylang.add('transitive-verb-lex := [ SYNSEM.LOCAL.CAT.VAL.COMPS < [ LOCAL.CAT.HEAD.EXTRA - ] > ].'
                       ,merge=True)
    return res

'''
Add clausal verb supertype to the grammar.
'''
# Note: this function is currently called from within lexical_items.py.
# It is possible that that call should be moved to this module.

def add_clausalcomp_verb_supertype(ch, mainorverbtype,mylang):
    typedef = CLAUSALCOMP + '-verb-lex := ' + mainorverbtype + '&\
      [ SYNSEM.LOCAL.CAT.VAL.COMPS < #comps >,\
        ARG-ST < [ LOCAL.CAT.HEAD noun ],\
                 #comps &\
                 [ LOCAL.CAT.VAL [ SPR < >, COMPS < >, SUBJ < > ] ] > ].'
    mylang.add(typedef,section='verblex')

def determine_clausal_verb_head(cs):
    head = ''
    if cs[COMP]:
        if cs[COMP] == 'oblig':
            head = 'comp'
        elif cs[COMP] == 'opt':
            head = '+vc'
    else:
        head = 'noun' if is_nominalized_complement(cs) else 'verb'
    return head

def is_nominalized_complement(cs):
    return 'nominalization' in [ f['name'] for f in cs['feat'] ]

def customize_clausal_verb(clausalverb,mylang,ch,cs):
    supertype = None
    for f in cs['feat']:
        if f['name'] == 'nominalization':
            path = 'SYNSEM.LOCAL.CAT.VAL.COMPS.FIRST.LOCAL.CAT'
            constrain_lexitem_for_feature(clausalverb, path, 'HEAD', '[ NMZ + ] ',mylang)
            for ns in ch['ns']:
                if ns['name'] == f['value']:
                    if ns['nmzRel'] == 'yes':
                        supertype = 'transitive-lex-item'
        else:
            path = 'SYNSEM.LOCAL.CAT.VAL.COMPS.FIRST.LOCAL.CAT.HEAD'
            constrain_lexitem_for_feature(clausalverb, path, f['name'],f['value'],mylang)
    if not supertype:
        supertype = 'clausal-second-arg-trans-lex-item'
    mylang.add(clausalverb +' := ' + supertype + '.',merge=True)
    if extra_needed(ch,mylang):
        if cs[CLAUSE_POS_EXTRA] and not cs[CLAUSE_POS_SAME]:
            mylang.add(clausalverb + ' := [ SYNSEM.LOCAL.CAT.VAL.COMPS < [ LOCAL.CAT.HEAD.EXTRA + ] > ].'
                       , merge=True)


# This is currently called by lexical_items.py
def update_verb_lextype(ch,verb, vtype):
    suffix = ''
    head = ''
    val = verb.get(constants.VALENCE)
    for ccs in ch.get(COMPS):
        if val == ccs.full_key:
            suffix = val
            head = determine_clausal_verb_head(ccs)
    if suffix:
        name = vtype.split('-',1)[0]
        rest = vtype.split('-',1)[1]
        vtype = name + '-' + val + '-' + rest
    return vtype,head

def has_extraposition(ch):
    return len([cs for cs in ch.get(COMPS) if cs[CLAUSE_POS_EXTRA]]) > 0

def nonempty_nmz(cs,ch):
    for f in cs['feat']:
        if f['name'] == 'nominalization':
            for ns in ch['ns']:
                if ns['name'] == f['value']:
                    if ns['nmzRel'] == 'yes':
                        return True
    return False

def determine_ccomp_mark_type(cs):
    if cs[COMP]:
        return 'COMP'
    else:
        for f in cs['feat']:
            if f['name'] == 'nominalization':
                return 'NMZ'
        return 'FEAT'

def validate(ch,vr):
    if not ch.get(COMPS):
        pass
    for ccs in ch.get(COMPS):
        if not (ccs[CLAUSE_POS_EXTRA] or ccs[CLAUSE_POS_SAME]):
            vr.err(ccs.full_key + '_' + CLAUSE_POS_SAME, SAME_OR_EXTRA)
        if ccs[CLAUSE_POS_EXTRA]:
            if ch.get(constants.WORD_ORDER) in ['free','v2','svo','vso']:
                vr.err(ccs.full_key + '_' + CLAUSE_POS_EXTRA,EXTRA_VO)
