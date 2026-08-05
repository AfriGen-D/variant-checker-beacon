"""
Guards for user-supplied values that end up inside a MongoDB query.

Standalone by design: this module imports nothing from Django, DRF or
MongoEngine, so the rules below can be unit-tested without a settings module
or a database (see ``beacon_api/test_query_injection.py``).

Why this exists
---------------
Query values that arrive as JSON (a POST body) are *arbitrary* JSON — a value
is not necessarily a string. MongoEngine hands a non-string value straight
through to PyMongo for an equality lookup::

    Individual.objects(sex={'$ne': None})      # -> {"sex": {"$ne": None}}
    Individual.objects(__raw__={'diseases.diseaseCode': {'$regex': '^A'}})

Both are live Mongo operators. On a boolean beacon that is worse than it looks:
the YES/NO answer becomes an oracle, and an attacker can binary-search a
disease code (or any other stored value) one character at a time with a
sequence of ``$regex`` probes. Every value reaching a query must therefore be
proven to be a single scalar, and every key must be proven not to be an
operator or a dotted path the caller chose.

MongoEngine's ``StringField.prepare_query_value`` does ``re.escape`` the value
for ``__contains``/``__icontains``/``__startswith``, so regex metacharacters
are not directly injectable there — but that is an implementation detail of
one ODM version, it does not apply to non-string values, and it applies no
length limit at all. An unbounded substring term against the 42M-document
variants collection is a CPU-exhaustion vector on its own, hence
:func:`safe_regex_term`.
"""

# Longest accepted value for an equality lookup. Real identifiers (ontology
# codes, dataset ids, sample ids) are far shorter; anything longer is either a
# mistake or an attempt to make the server do expensive work.
MAX_TERM_LENGTH = 128

# Substring/regex lookups cannot use an index and are evaluated per document,
# so they get a tighter bound than equality lookups.
MAX_REGEX_TERM_LENGTH = 64


class UnsafeQueryValue(ValueError):
    """A user-supplied query value or key cannot be safely used in a query."""


def is_operator_key(key):
    """True if `key` could be read by MongoDB as an operator or a field path.

    ``$``-prefixed keys are operators (``$where``, ``$regex``, ``$expr``);
    keys containing ``.`` address a nested field the caller was not offered.
    """
    if not isinstance(key, str):
        return True
    return key.startswith('$') or '.' in key


def reject_operator_keys(params, label='query'):
    """Reject a request body whose top-level keys are operator-like.

    Defence in depth: the views only read named keys, so an injected ``$or``
    would normally be ignored rather than executed. Failing loudly instead
    keeps that safe-by-accident property from silently becoming
    safe-by-nothing the next time a view starts iterating the body.
    """
    if not isinstance(params, dict):
        raise UnsafeQueryValue(f'{label} must be an object')
    for key in params:
        if is_operator_key(key):
            raise UnsafeQueryValue(f'Invalid parameter name in {label}')


def scalar_query_value(value, field_name='value', max_length=MAX_TERM_LENGTH):
    """Coerce `value` to a plain string safe for an equality lookup.

    Returns ``None`` for ``None`` (the caller decides whether the field was
    supplied). Numbers and booleans are accepted and stringified — MongoEngine
    re-casts them for ``IntField``/``FloatField`` — so a caller passing
    ``{"start": 12345}`` still works and, critically, a caller passing
    ``{"sex": 1}`` gets a clean answer instead of an ``AttributeError`` 500
    from ``.upper()``.

    Anything with structure (dict, list, tuple, set) is refused: structure is
    exactly what turns a value into a Mongo operator document.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        raise UnsafeQueryValue(f'{field_name} must be a single value, not a list or object')
    if isinstance(value, bool):
        # bool is an int subclass; stringify explicitly rather than as 0/1.
        value = 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        value = str(value)
    elif not isinstance(value, str):
        raise UnsafeQueryValue(f'{field_name} must be a text value')

    if len(value) > max_length:
        raise UnsafeQueryValue(f'{field_name} is too long (max {max_length} characters)')
    if '\x00' in value:
        raise UnsafeQueryValue(f'{field_name} contains an invalid character')
    return value


def safe_regex_term(value, field_name='value'):
    """Scalar-ise and length-cap a value used in a substring/regex lookup.

    The tighter cap is the point: a substring match is a collection scan, so
    the term length directly buys the attacker server CPU.
    """
    return scalar_query_value(value, field_name, max_length=MAX_REGEX_TERM_LENGTH)


def scalar_query_mapping(params, label='query', max_length=MAX_TERM_LENGTH):
    """Return a copy of `params` with every key and value proven safe.

    Applied once at the top of a view, this makes every downstream
    ``.filter(field=query['x'])`` in that view a plain equality lookup on a
    string, with no per-call-site guard to forget.
    """
    reject_operator_keys(params, label=label)
    return {
        key: scalar_query_value(value, field_name=key, max_length=max_length)
        for key, value in params.items()
    }
