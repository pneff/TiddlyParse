TiddlyParse allows Python to interact with [TiddlyWiki](https://tiddlywiki.com/) files.

At the moment it handles standalone HTML files, with the [two tiddler formats](https://tiddlywiki.com/prerelease/dev/#Data%20Storage%20in%20Single%20File%20TiddlyWiki). The first one was used in version up to and including 5.1.23, the second one uses JSON snippets and is in use since 5.2.0.

Points that are currently open but can be added upon interest:

-   Seamlessly interact with a server-side TiddlyWiki and use the REST API in that context
-   Handle encrypted files

# Usage

Use the parse method to get a wiki instance returned:

```python
from tiddlyparse import parse
from pathlib import Path

wiki_file = Path('wiki.html')
wiki = parse(file=wiki_file)
```

This will automatically detect the format and transparently handle this also for saving back.

The number of tiddlers are returned with the `len` function:

```pycon
>>> len(wiki)
7
```

Note that only the root tiddlers are returned. The individual tiddlers contained therein are not currently handled, though that may change.

You can access individual tiddlers using dictionary notation or `get`:

```pycon
>>> wiki['$:/isEncrypted']
<tiddlyparse.parser.JsonTiddler object at 0x105a85130>
>>> wiki.get('no such tiddler')
```

It is also possible to execute simple searches. Any keyword argument to the `search` function is converted into a query component. If the argument value is `True`, then all tiddlers that have this attribute defined are returned:

```pycon
>>> tiddlers = wiki.search(author=True)
>>> tiddlers
[<tiddlyparse.parser.JsonTiddler object at 0x101827e80>, <tiddlyparse.parser.JsonTiddler object at 0x101832130>, <tiddlyparse.parser.JsonTiddler object at 0x101832190>]
>>> [t.title for t in tiddlers]
['$:/core', '$:/themes/tiddlywiki/snowwhite', '$:/themes/tiddlywiki/vanilla']
```

If it's any string value, then all tiddlers that have this attribute set to exactly this value are returned:

```pycon
>>> tiddlers = wiki.search(name='Snow White')
>>> [t.title for t in tiddlers]
['$:/themes/tiddlywiki/snowwhite']
```

The tiddlers are all represented using the `Tiddler` class (`JsonTiddler` or `DivTiddler` more specifically). The tiddler attributes are available as properties are available on those objects:

```pycon
>>> tiddler = wiki['$:/isEncrypted']
>>> tiddler.text
'no'
>>> tiddler = wiki.get('$:/core')
>>> tiddler.author
'JeremyRuston'
```

To create or modify a tiddler, use the `get_or_create` method to first get the tiddler. Then add it to the wiki with `add`:

```pycon
>>> tiddler = wiki.get_or_create('Testing TiddlyParse')
>>> tiddler.text = "This is the first ''test'' with TiddlyParse."
>>> tiddler.tags = 'Test TiddlyParse'
>>> wiki.add(tiddler)
```

To persist the changes, use `save`:

```pycon
>>> wiki.save()
```
