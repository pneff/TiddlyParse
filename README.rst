TiddlyParse allows Python to interact with `TiddlyWiki`_.

At the moment it handles standalone HTML files, with the `two tiddler formats`_.
The first one was used in version up to and including 5.1.23, the second one uses JSON snippets and is in use since 5.2.0.

Points that are currently open but can be added upon interest:

* Seamlessly interact with a server-side TiddlyWiki and use the REST API in that context
* Handle encrypted files


Usage
=====

Use the parse method to get a wiki instance returned::

    from tiddlyparse import parse
    from pathlib import Path

    wiki_file = Path('wiki.html')
    wiki = parse(file=wiki_file)


This will automatically detect the format and transparently handle this also for saving back.

The number of tiddlers are returned with the `len` function::

    >>> len(wiki)
    7

Note that only the root tiddlers are returned. The individual tiddlers contained therein are not currently handled, though that may change.

You can access individual tiddlers using dictionary notation or `get`::

    >>> wiki['$:/isEncrypted']
    <tiddlyparse.parser.JsonTiddler object at 0x105a85130>
    >>> wiki.get('no such tiddler')

The properties are available on those tiddlers::

    >>> tiddler = wiki['$:/isEncrypted']
    >>> tiddler.text
    'no'
    >>> tiddler = wiki.get('$:/core')
    >>> tiddler.author
    'JeremyRuston'


To create or modify a tiddler, use the `get_or_create` method to first get the tiddler. Then add it to the wiki with `add`::

    >>> tiddler = wiki.get_or_create('Testing TiddlyParse')
    >>> tiddler.text = "This is the first ''test'' with TiddlyParse."
    >>> tiddler.tags = 'Test TiddlyParse'
    >>> wiki.add(tiddler)

To persist the changes, use `save`:

    >>> wiki.save()

.. _TiddlyWiki: https://tiddlywiki.com/
.. _two tiddler formats: https://tiddlywiki.com/prerelease/dev/#Data%20Storage%20in%20Single%20File%20TiddlyWiki
