**Spikexplore** is a Python library that allows graph exploration using the 
methods described in our paper 
[Spikyball Sampling: Exploring Large Networks via an Inhomogeneous Filtered Diffusion](https://www.mdpi.com/1999-4893/13/11/275).

Please cite if you find this package useful :
```
@Article{spikyball_sampling,
AUTHOR = {Ricaud, Benjamin and Aspert, Nicolas and Miz, Volodymyr},
TITLE = {Spikyball Sampling: Exploring Large Networks via an Inhomogeneous Filtered Diffusion},
JOURNAL = {Algorithms},
VOLUME = {13},
YEAR = {2020},
NUMBER = {11},
ARTICLE-NUMBER = {275},
URL = {https://www.mdpi.com/1999-4893/13/11/275},
ISSN = {1999-4893},
ABSTRACT = {Studying real-world networks such as social networks or web networks is a challenge. These networks often combine a complex, highly connected structure together with a large size. We propose a new approach for large scale networks that is able to automatically sample user-defined relevant parts of a network. Starting from a few selected places in the network and a reduced set of expansion rules, the method adopts a filtered breadth-first search approach, that expands through edges and nodes matching these properties. Moreover, the expansion is performed over a random subset of neighbors at each step to mitigate further the overwhelming number of connections that may exist in large graphs. This carries the image of a &ldquo;spiky&rdquo; expansion. We show that this approach generalize previous exploration sampling methods, such as Snowball or Forest Fire and extend them. We demonstrate its ability to capture groups of nodes with high interactions while discarding weakly connected nodes that are often numerous in social networks and may hide important structures.},
DOI = {10.3390/a13110275}
}
```

So far this implementation supports:
- synthetic graphs using [NetworkX](https://networkx.org/)
- ~~Twitter using [v1 API](https://developer.twitter.com/en/docs/twitter-api/api-reference-index) through [Twython](https://twython.readthedocs.io/en/latest/)~~ 
Twitter API is no longer available unless you pay. Latest version supporting it is v0.0.12. 
- Wikipedia using [Mediawiki API](https://www.mediawiki.org/wiki/API:Main_page) through [Wikipedia-API](https://pypi.org/project/Wikipedia-API/)
- Bluesky using [ATProto](https://atproto.blue/en/latest/)
