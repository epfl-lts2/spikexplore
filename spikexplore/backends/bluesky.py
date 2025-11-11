import pandas
from atproto import Client, client_utils
import networkx as nx
import time
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone

from atproto_client.exceptions import BadRequestError

from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import add_node_attributes, add_edges_attributes

logger = logging.getLogger(__name__)


class BlueskyCredentials:
    def __init__(self, handle, password):
        self.handle = handle
        self.password = password


class SkeetsGetter:
    def __init__(self, credentials, config):
        # Instantiate an object
        self.config = config
        self.bsky_client = Client()
        self.bsky_client.login(credentials.handle, credentials.password)
        self.profiles_cache = {}
        self.features_attrs = {"mention": "did", "tag": "tag", "link": "uri"}

    def _filter_old_skeets(self, skeets):
        max_day_old = self.config.max_day_old
        if not max_day_old:
            return skeets

        days_limit = datetime.now() - timedelta(days=max_day_old)
        skeets_filt = filter(
            lambda t: datetime.fromisoformat(t.post.record["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) >= days_limit, skeets
        )
        return list(skeets_filt)

    def get_profile(self, did):
        profile = self.profiles_cache.get(did)
        if profile is not None:
            return profile
        try:
            p = self.bsky_client.get_profile(did)
            if p is not None:
                self.profiles_cache[did] = p
                return p
        except Exception as e:
            logger.error("Error in getting profile: ", e)
        
        return None

    def facet_data(self, skeet, data):
        if not hasattr(skeet, "record"):
            return []
        if skeet.record.facets is None:
            return []
        return [
            getattr(f.features[0], self.features_attrs[data])
            for f in skeet.record.facets
            if f.features[0].py_type == f"app.bsky.richtext.facet#{data}"
        ]

    def get_user_skeets(self, username):
        # Collect skeets from a username/did

        count = self.config.max_skeets_per_user

        # Test if ok
        try:
            user_skeets_raw = self.bsky_client.get_author_feed(actor=username, limit=count).feed
            # remove old tweets
            user_skeets_filt = self._filter_old_skeets(user_skeets_raw)
            # make a dictionary
            user_skeets = {x.post.cid: x.post for x in user_skeets_filt}

            # update profile cache
            for v in user_skeets.items():
                if v[1].author.did not in self.profiles_cache:
                    self.profiles_cache[v[1].author.did] = self.bsky_client.get_profile(v[1].author.handle)

            skeets_metadata = dict(
                map(
                    lambda x: (
                        x[0],
                        {
                            "user_did": x[1].author.did,
                            "user": x[1].author.handle,
                            "name": x[1].author.display_name,
                            "mentions": self.facet_data(x[1], "mention"),
                            "hashtags": self.facet_data(x[1], "tag"),
                            "links": self.facet_data(x[1], "link"),
                            "repost_count": x[1].repost_count,
                            "favorite_count": x[1].like_count,
                            "reply_to": x[1].reply.parent.author.handle if hasattr(x[1], "reply") else [],
                            "created_at": x[1].record.created_at,
                            "account_creation": x[1].author.created_at,
                            "account_followers": self.profiles_cache[x[1].author.did].followers_count,
                            "account_following": self.profiles_cache[x[1].author.did].follows_count,
                            "account_statuses": self.profiles_cache[x[1].author.did].posts_count,
                            "account_description": self.profiles_cache[x[1].author.did].description,
                            "account_verified": x[1].author.verification is not None and x[1].author.verification.verified_status == "valid",
                        },
                    ),
                    user_skeets.items(),
                )
            )
            return user_skeets, skeets_metadata
        except BadRequestError as e:
            logger.error(f"Error in getting user skeets: code {e.response.status_code} - {e.response.content.message}")
            return {}, {}
        except Exception as e:
            logger.error(f"Error in getting user skeets: {e}")
            return {}, {}

    def reshape_node_data(self, node_df):
        node_df = node_df[
            [
                "user_did",
                "user",
                "name",
                "spikyball_hop",
                "created_at",
            ]
        ]
        node_df = node_df.reset_index().groupby("user").max().rename(columns={"index": "last_skeet_id"})
        return node_df


class BlueskyNetwork:
    class BlueskyNodeInfo(NodeInfo):
        def __init__(self, user_hashtags=None, user_skeets=None, user_links=None, skeets_meta=pd.DataFrame()):
            self.user_hashtags = user_hashtags if user_hashtags else {}
            self.user_links = user_links if user_links else {}
            self.user_skeets = user_skeets if user_skeets else {}
            self.skeets_meta = skeets_meta

        def update(self, new_info):
            self.user_hashtags.update(new_info.user_hashtags)
            self.user_skeets.update(new_info.user_skeets)
            self.user_links.update(new_info.user_skeets)
            self.skeets_meta = pandas.concat([self.skeets_meta, new_info.skeets_meta])
            self.skeets_meta = self.skeets_meta[~self.skeets_meta.index.duplicated(keep="first")]

        def get_nodes(self):
            return self.skeets_meta

    def __init__(self, credentials, config):
        self.skeets_getter = SkeetsGetter(credentials, config)
        self.config = config

    def create_node_info(self):
        return self.BlueskyNodeInfo()

    def get_neighbors(self, user):
        if not isinstance(user, str):
            return self.BlueskyNodeInfo(), pd.DataFrame()
        skeets_dic, skeets_meta = self.skeets_getter.get_user_skeets(user)
        edges_df, node_info = self.edges_nodes_from_user(user, skeets_meta, skeets_dic)

        # replace user and mentions by source and target
        if not edges_df.empty:
            edges_df.index.names = ["source", "target"]
            edges_df.reset_index(level=["source", "target"], inplace=True)

        return node_info, edges_df

    def filter(self, node_info, edges_df):
        # filter edges according to node properties
        # filter according to edges properties
        edges_df = self.filter_edges(edges_df)
        return node_info, edges_df

    def filter_edges(self, edges_df):
        # filter edges according to their properties
        if edges_df.empty:
            return edges_df
        return edges_df[edges_df["weight"] >= self.config.min_mentions]

    def neighbors_list(self, edges_df):
        users_connected = edges_df["target"].tolist()
        return users_connected

    def neighbors_with_weights(self, edges_df):
        if edges_df.empty:
            return {}
        user_list = self.neighbors_list(edges_df)
        return dict.fromkeys(user_list, 1)

    ###############################################################
    # Functions for extracting skeet info from the bluesky API
    ###############################################################

    def edges_nodes_from_user(self, user, skeets_meta, skeets_dic):
        # Make an edge and node property dataframes
        edges_df = self.get_edges(user, skeets_meta)
        user_info = self.get_nodes_properties(skeets_meta, skeets_dic)
        return edges_df, user_info

    def did_to_handle(self, did):
        return self.skeets_getter.get_profile(did)

    def match_usernames(self, meta_df):
        mask = meta_df["mentions"].str.startswith("did:")
        meta_df.loc[mask, "mentions"] = meta_df.loc[mask, "mentions"].apply(self.did_to_handle)

        return meta_df.dropna(subset=["mentions"])

    def get_edges(self, user, skeets_meta):
        if not skeets_meta:
            return pd.DataFrame()
        # Create the user -> mention table with their properties fom the list of tweets of a user
        mentions_df = pd.DataFrame.from_dict(skeets_meta, orient="index")
        mentions_df["full_mentions"] = mentions_df["mentions"] + mentions_df["reply_to"]  # a reply is a kind of mention
        mentions_df = (
            mentions_df.drop(columns=["reply_to", "mentions"]).explode("full_mentions").dropna().rename(columns={"full_mentions": "mentions"})
        )
        # Some bots to be removed from the collection
        users_to_remove = self.config.users_to_remove

        # mentions can be dids so need to translate that first into user handles
        mentions_df = self.match_usernames(mentions_df)
        filtered_mentions_df = mentions_df[~mentions_df["mentions"].isin(users_to_remove) & ~mentions_df["mentions"].isin(mentions_df["user"])]

        # group by mentions and keep list of tweets for each mention
        tmp = filtered_mentions_df.groupby(["user", "mentions"]).apply(lambda x: (x.index.tolist(), len(x.index)), include_groups=False)
        if tmp.empty:
            edge_mentions_df = pd.DataFrame([], columns=["source", "target", "cid", "weight"])
        else:
            edge_mentions_df = pd.DataFrame(tmp.tolist(), index=tmp.index).rename(columns={0: "cid", 1: "weight"})
            edge_mentions_df.index.names = ["source", "target"]
        # Now get reposts
        repost_df = pd.DataFrame.from_dict(skeets_meta, orient="index")
        repost_df["source_user"] = user
        # remove self edges
        repost_df = repost_df[repost_df["user"] != repost_df["source_user"]]
        tmp = repost_df.groupby(["source_user", "user"]).apply(lambda x: (x.index.tolist(), len(x.index)), include_groups=False)
        if tmp.empty:
            edge_repost_df = pd.DataFrame([], columns=["source", "target", "cid", "weight"])
        else:
            edge_repost_df = pd.DataFrame(tmp.tolist(), index=tmp.index).rename(columns={0: "cid", 1: "weight"})
            edge_repost_df.index.names = ["source", "target"]
        edges_df = pd.concat([edge_mentions_df, edge_repost_df]).groupby(["source", "target"]).sum()
        return edges_df

    def get_nodes_properties(self, skeets_meta, skeets_dic):
        if not skeets_meta:
            return self.BlueskyNodeInfo({}, {}, {}, pd.DataFrame())
        nb_popular_skeets = self.config.nb_popular_skeets
        # global properties
        meta_df = pd.DataFrame.from_dict(skeets_meta, orient="index").sort_values("repost_count", ascending=False)
        # hashtags statistics
        ht_df = meta_df.explode("hashtags").dropna()
        htgb = ht_df.groupby(["hashtags"]).size()
        user_hashtags = pd.DataFrame(htgb).rename(columns={0: "count"}).sort_values("count", ascending=False).to_dict()
        links_df = meta_df.explode("links").dropna()
        links = links_df.groupby(["links"]).size()
        user_links = pd.DataFrame(links).rename(columns={0: "count"}).sort_values("count", ascending=False).to_dict()
        user_name = meta_df["user"].iloc[0]
        skeets_meta_kept = meta_df.head(nb_popular_skeets)
        skeets_kept = {k: skeets_dic[k] for k in skeets_meta_kept.index.to_list()}
        # Get most popular tweets of user
        return self.BlueskyNodeInfo(
            user_hashtags={user_name: user_hashtags["count"]},
            user_skeets=skeets_kept,
            user_links={user_name: user_links["count"]},
            skeets_meta=skeets_meta_kept,
        )

    #####################################################
    ## Utils functions for the graph
    #####################################################

    def add_graph_attributes(self, g, nodes_df, edges_df, nodes_info):
        g = add_edges_attributes(g, edges_df, drop_cols=["cid"])
        g = add_node_attributes(g, self.skeets_getter.reshape_node_data(nodes_df), attr_dic=nodes_info.user_hashtags, attr_name="all_hashtags")
        return g
